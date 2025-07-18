"""
Snowflake Data Extractor Lambda Function

This Lambda function extracts data from Snowflake using configurable SQL queries,
implements connection pooling, credential management, and stores data in S3.
"""

import json
import os
import logging
import boto3
import snowflake.connector
from snowflake.connector import DictCursor
from datetime import datetime, timezone
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
import time
import random
import jsonschema

# Import custom modules
from watermark_manager import WatermarkManager, BatchProcessor, DataValidator
from error_handler import (
    ComprehensiveErrorHandler, RetryStrategy, DeadLetterQueueHandler,
    CircuitBreaker, MonitoringIntegration, ErrorType
)
from utils.config_loader import ConfigLoader

# Import and configure X-Ray SDK
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

# Configure structured logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "aws_request_id": getattr(record, 'aws_request_id', 'not_available'),
            "function_name": getattr(record, 'function_name', 'not_available'),
        }
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_record)

logger = logging.getLogger()
for handler in logger.handlers:
    handler.setFormatter(JsonFormatter())
logger.setLevel(logging.INFO)

class SnowflakeExtractor:
    """Handles Snowflake data extraction with connection pooling and error handling"""
    
    def __init__(self):
        self.secrets_client = boto3.client('secretsmanager')
        self.s3_client = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        
        # Get project and environment from environment variables
        project_name = os.environ.get('PROJECT_NAME', 'snowflake-aws-pipeline')
        environment = os.environ.get('ENVIRONMENT', 'dev')
        
        # Initialize configuration loader
        self.config_loader = ConfigLoader(project_name, environment)
        
        # Load configuration with schema validation
        with open('config_schema_v2.json', 'r') as schema_file:
            config_schema = json.load(schema_file)
        
        # Default configuration values
        default_config = {
            "batch_size": 10000,
            "max_batches": 100,
            "max_retries": 3,
            "output_format": "parquet",
            "validation_rules": {
                "min_rows": 1,
                "required_columns": ["created_at", "updated_at"],
                "non_null_columns": ["created_at"]
            },
            "queries": []
        }
        
        # Load configuration from SSM Parameter Store with defaults
        try:
            self.config = self.config_loader.load_config_with_defaults(
                "snowflake_extraction",
                default_config,
                config_schema
            )
            logger.info("Successfully loaded configuration from SSM Parameter Store")
        except Exception as e:
            logger.warning(f"Failed to load configuration from SSM Parameter Store: {str(e)}. Using environment variables.")
            # Fall back to environment variables
            self.config = default_config
        
        # Configuration from environment variables (fallback) or config
        self.secret_name = os.environ.get('SNOWFLAKE_SECRET_NAME')
        self.s3_bucket = os.environ.get('S3_BUCKET_NAME')
        self.watermark_table = os.environ.get('WATERMARK_TABLE_NAME')
        self.max_retries = int(os.environ.get('MAX_RETRIES', str(self.config.get('max_retries', 3))))
        self.batch_size = int(os.environ.get('BATCH_SIZE', str(self.config.get('batch_size', 10000))))
        self.max_batches = int(os.environ.get('MAX_BATCHES', str(self.config.get('max_batches', 100))))
        
        self._connection = None
        self._credentials = None
        
        # Initialize helper classes
        self.watermark_manager = WatermarkManager(self.watermark_table)
        self.batch_processor = BatchProcessor(self.batch_size, self.max_batches)
        self.data_validator = DataValidator()
        
        # Initialize error handling components
        dlq_url = os.environ.get('DLQ_URL')
        alert_topic_arn = os.environ.get('ALERT_TOPIC_ARN')
        
        retry_strategy = RetryStrategy(
            max_retries=self.max_retries,
            base_delay=1.0,
            max_delay=60.0,
            backoff_multiplier=2.0,
            jitter=True
        )
        
        dlq_handler = DeadLetterQueueHandler(dlq_url) if dlq_url else None
        circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        
        self.error_handler = ComprehensiveErrorHandler(
            retry_strategy=retry_strategy,
            dlq_handler=dlq_handler,
            circuit_breaker=circuit_breaker
        )
        
        self.monitoring = MonitoringIntegration(alert_topic_arn=alert_topic_arn)
    
    def _get_snowflake_credentials(self) -> Dict[str, str]:
        """Retrieve Snowflake credentials from AWS Secrets Manager"""
        if self._credentials:
            return self._credentials
            
        try:
            response = self.secrets_client.get_secret_value(SecretId=self.secret_name)
            self._credentials = json.loads(response['SecretString'])
            logger.info("Successfully retrieved Snowflake credentials")
            return self._credentials
        except ClientError as e:
            logger.error(f"Failed to retrieve credentials: {str(e)}")
            raise
    
    def _get_connection(self) -> snowflake.connector.SnowflakeConnection:
        """Get or create Snowflake connection with connection pooling"""
        if self._connection and not self._connection.is_closed():
            return self._connection
        
        credentials = self._get_snowflake_credentials()
        
        try:
            self._connection = snowflake.connector.connect(
                user=credentials['username'],
                password=credentials['password'],
                account=credentials['account'],
                warehouse=credentials['warehouse'],
                database=credentials['database'],
                schema=credentials['schema'],
                session_parameters={
                    'QUERY_TAG': 'lambda-data-extraction',
                    'TIMEZONE': 'UTC'
                }
            )
            logger.info("Successfully connected to Snowflake")
            return self._connection
        except Exception as e:
            logger.error(f"Failed to connect to Snowflake: {str(e)}")
            raise
    
    def _execute_query_with_retry(self, query: str, params: Optional[List] = None) -> List[Dict]:
        """Execute SQL query with exponential backoff retry logic"""
        for attempt in range(self.max_retries):
            try:
                conn = self._get_connection()
                cursor = conn.cursor(DictCursor)
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                results = cursor.fetchall()
                cursor.close()
                
                logger.info(f"Query executed successfully, returned {len(results)} rows")
                return results
                
            except Exception as e:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Query attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                    # Reset connection on retry
                    self._connection = None
                else:
                    logger.error(f"Query failed after {self.max_retries} attempts")
                    raise
    
    def _get_watermark(self, table_name: str, watermark_column: str) -> Optional[str]:
        """Get the last watermark value for incremental extraction"""
        watermark_info = self.watermark_manager.get_watermark(table_name, watermark_column)
        return watermark_info['watermark_value'] if watermark_info else None
    
    def _update_watermark(self, table_name: str, watermark_column: str, watermark_value: str, row_count: int = 0):
        """Update the watermark value after successful extraction"""
        self.watermark_manager.update_watermark(table_name, watermark_column, watermark_value, row_count)
    
    def _validate_data(self, data: List[Dict], validation_rules: Dict) -> bool:
        """Validate extracted data against defined rules using DataValidator"""
        if not data:
            logger.warning("No data to validate")
            return False
        
        logger.info(f"Validating {len(data)} rows")
        
        # Use DataValidator for comprehensive validation
        is_valid, validation_report = self.data_validator.validate_data_quality(data, validation_rules)
        
        # Log validation results
        if validation_report['errors']:
            for error in validation_report['errors']:
                logger.error(f"Validation error: {error}")
        
        if validation_report['warnings']:
            for warning in validation_report['warnings']:
                logger.warning(f"Validation warning: {warning}")
        
        # Log validation metrics
        for check_name, check_value in validation_report['checks'].items():
            logger.info(f"Validation check {check_name}: {check_value}")
        
        if is_valid:
            logger.info("Data validation passed")
        else:
            logger.error("Data validation failed")
        
        return is_valid
    
    def _upload_to_s3(self, data: List[Dict], s3_key: str, output_format: str = 'parquet'):
        """Upload data to S3 in specified format"""
        try:
            if output_format.lower() == 'parquet':
                # Convert to pandas DataFrame then to Parquet
                df = pd.DataFrame(data)
                
                # Add extraction metadata
                df['extraction_timestamp'] = datetime.now(timezone.utc)
                df['source_system'] = 'snowflake'
                
                # Convert to PyArrow table and write to Parquet
                table = pa.Table.from_pandas(df)
                
                # Write to buffer first
                import io
                buffer = io.BytesIO()
                pq.write_table(table, buffer, compression='snappy')
                buffer.seek(0)
                
                # Upload to S3
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=buffer.getvalue(),
                    ContentType='application/octet-stream'
                )
                
            else:  # JSON format
                json_data = json.dumps(data, default=str, indent=2)
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=json_data,
                    ContentType='application/json'
                )
            
            logger.info(f"Successfully uploaded data to s3://{self.s3_bucket}/{s3_key}")
            
        except Exception as e:
            logger.error(f"Failed to upload to S3: {str(e)}")
            raise
    
    @xray_recorder.capture('extract_data')
    def extract_data(self, extraction_config: Dict) -> Dict[str, Any]:
        """Main method to extract data based on configuration"""
        results = {
            'status': 'success',
            'extractions': [],
            'errors': []
        }
        
        try:
            queries = extraction_config.get('queries', [])
            output_format = extraction_config.get('output_format', 'parquet')
            validation_rules = extraction_config.get('validation_rules', {})
            
            for query_config in queries:
                with xray_recorder.in_subsegment(f"process_query_{query_config.get('name', 'unknown')}") as subsegment:
                    try:
                        query_name = query_config['name']
                        sql_query = query_config['sql']
                        watermark_column = query_config.get('watermark_column')
                        partition_by = query_config.get('partition_by', 'date')
                        
                        logger.info(f"Processing query: {query_name}")
                        subsegment.put_annotation("query_name", query_name)
                        
                        # Handle incremental extraction with watermark and batch processing
                        watermark_value = None
                        if watermark_column:
                            watermark_value = self._get_watermark(query_name, watermark_column)
                        
                        # Check if batch processing is enabled
                        enable_batching = query_config.get('enable_batching', True)
                        
                        if enable_batching and watermark_column:
                            # Use batch processor for large datasets
                            logger.info(f"Using batch processing for query: {query_name}")
                            data = self.batch_processor.process_in_batches(
                                self._execute_query_with_retry,
                                sql_query,
                                watermark_column,
                                watermark_value
                            )
                        else:
                            # Execute query directly with parameters
                            params = [watermark_value] if watermark_value else None
                            data = self._execute_query_with_retry(sql_query, params)
                        
                        if not data:
                            logger.warning(f"No data returned for query: {query_name}")
                            continue
                        
                        # Validate data
                        if not self._validate_data(data, validation_rules):
                            raise ValueError(f"Data validation failed for query: {query_name}")
                        
                        # Generate S3 key with partitioning
                        current_time = datetime.now(timezone.utc)
                        if partition_by == 'date':
                            partition_path = f"year={current_time.year}/month={current_time.month:02d}/day={current_time.day:02d}"
                        elif partition_by == 'hour':
                            partition_path = f"year={current_time.year}/month={current_time.month:02d}/day={current_time.day:02d}/hour={current_time.hour:02d}"
                        else:
                            partition_path = partition_by
                        
                        file_extension = 'parquet' if output_format == 'parquet' else 'json'
                        s3_key = f"bronze/{query_name}/{partition_path}/{query_name}_{current_time.strftime('%Y%m%d_%H%M%S')}.{file_extension}"
                        
                        # Upload to S3
                        self._upload_to_s3(data, s3_key, output_format)
                        
                        # Update watermark if applicable
                        if watermark_column and data:
                            # Find the maximum watermark value in the extracted data
                            max_watermark = max(row.get(watermark_column) for row in data if row.get(watermark_column))
                            if max_watermark:
                                self._update_watermark(query_name, watermark_column, str(max_watermark), len(data))
                        
                        results['extractions'].append({
                            'query_name': query_name,
                            'row_count': len(data),
                            's3_location': f"s3://{self.s3_bucket}/{s3_key}",
                            'extraction_time': current_time.isoformat()
                        })
                        
                        logger.info(f"Successfully processed query: {query_name}")
                        
                    except Exception as e:
                        error_msg = f"Failed to process query {query_config.get('name', 'unknown')}: {str(e)}"
                        logger.error(error_msg)
                        results['errors'].append(error_msg)
                        results['status'] = 'partial_success' if results['extractions'] else 'failed'
        
        except Exception as e:
            error_msg = f"Extraction failed: {str(e)}"
            logger.error(error_msg)
            results['status'] = 'failed'
            results['errors'].append(error_msg)
        
        finally:
            # Close connection
            if self._connection and not self._connection.is_closed():
                self._connection.close()
                logger.info("Snowflake connection closed")
        
        return results


@xray_recorder.capture('lambda_handler')
def lambda_handler(event, context):
    """AWS Lambda handler function with comprehensive error handling"""
    # Add context to logger
    extra_info = {
        'aws_request_id': getattr(context, 'aws_request_id', 'unknown'),
        'function_name': getattr(context, 'function_name', 'snowflake-extractor')
    }
    logger.info(f"Lambda function started with event: {json.dumps(event, default=str)}", extra=extra_info)
    
    # Initialize extractor
    extractor = SnowflakeExtractor()
    
    # Prepare execution context for error handler
    execution_context = {
        'event': event,
        'aws_request_id': getattr(context, 'aws_request_id', 'unknown'),
        'function_name': getattr(context, 'function_name', 'snowflake-extractor'),
        'remaining_time_ms': getattr(context, 'get_remaining_time_in_millis', lambda: 0)()
    }
    
    def execute_extraction():
        """Inner function to execute extraction with error handling"""
        # Parse extraction configuration from event
        extraction_config = event.get('extraction_config', {})
        
        if not extraction_config:
            raise ValueError("extraction_config is required in event payload")
        
        # Process data extraction
        results = extractor.extract_data(extraction_config)
        
        # Log custom metrics
        extractor.monitoring.log_custom_metric(
            'ExtractionRowCount',
            sum(ext.get('row_count', 0) for ext in results.get('extractions', [])),
            'Count'
        )
        
        extractor.monitoring.log_custom_metric(
            'ExtractionTableCount',
            len(results.get('extractions', [])),
            'Count'
        )
        
        # Send alerts for partial failures
        if results['status'] == 'partial_success':
            extractor.monitoring.send_alert(
                'WARNING',
                f"Partial extraction success: {len(results['errors'])} errors occurred",
                {'errors': results['errors'], 'extractions': results['extractions']}
            )
        elif results['status'] == 'failed':
            extractor.monitoring.send_alert(
                'ERROR',
                "Extraction completely failed",
                {'errors': results['errors']}
            )
        
        return results
    
    try:
        # Execute with comprehensive error handling
        results, execution_metadata = extractor.error_handler.execute_with_retry(
            execute_extraction,
            context=execution_context
        )
        
        # Prepare successful response
        response = {
            'statusCode': 200 if results['status'] == 'success' else 207,  # 207 for partial success
            'body': json.dumps({
                **results,
                'execution_metadata': {
                    'attempts': execution_metadata['attempts'],
                    'duration': execution_metadata['total_duration'],
                    'success': execution_metadata['success']
                }
            }, default=str)
        }
        
        logger.info(f"Lambda function completed with status: {results['status']}", extra=extra_info)
        return response
        
    except Exception as e:
        error_msg = f"Lambda execution failed after all retries: {str(e)}"
        logger.error(error_msg, extra=extra_info)
        
        # Send critical alert
        extractor.monitoring.send_alert(
            'ERROR',
            f"Critical Lambda failure: {error_msg}",
            {
                'error_type': type(e).__name__,
                'aws_request_id': execution_context['aws_request_id'],
                'function_name': execution_context['function_name']
            }
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'failed',
                'error': error_msg,
                'error_type': type(e).__name__,
                'aws_request_id': execution_context['aws_request_id']
            })
        }
"""
Data Quality Monitoring Lambda Function

This Lambda function performs automated data quality validation including schema validation,
null checks, range validation, and implements data quarantine and alerting mechanisms.
"""

import json
import os
import logging
import boto3
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from botocore.exceptions import ClientError
import re
from decimal import Decimal
import statistics

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

class DataQualityMonitor:
    """Comprehensive data quality monitoring and validation"""
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        self.sns_client = boto3.client('sns')
        self.glue_client = boto3.client('glue')
        
        # Configuration from environment variables
        self.quality_results_table = os.environ.get('QUALITY_RESULTS_TABLE')
        self.quarantine_bucket = os.environ.get('QUARANTINE_BUCKET')
        self.alert_topic_arn = os.environ.get('ALERT_TOPIC_ARN')
        self.glue_database = os.environ.get('GLUE_DATABASE')
        
        # Initialize DynamoDB table
        self.results_table = self.dynamodb.Table(self.quality_results_table) if self.quality_results_table else None
        
        # Quality check thresholds
        self.default_thresholds = {
            'null_percentage_threshold': 10.0,  # Max 10% nulls allowed
            'duplicate_percentage_threshold': 5.0,  # Max 5% duplicates allowed
            'outlier_percentage_threshold': 2.0,  # Max 2% outliers allowed
            'schema_compliance_threshold': 95.0,  # Min 95% schema compliance
            'data_freshness_hours': 24  # Data should be less than 24 hours old
        }
    
    def read_data_from_s3(self, bucket: str, key: str) -> pd.DataFrame:
        """Read data from S3 into pandas DataFrame"""
        try:
            if key.endswith('.parquet'):
                df = pd.read_parquet(f's3://{bucket}/{key}')
            elif key.endswith('.csv'):
                df = pd.read_csv(f's3://{bucket}/{key}')
            elif key.endswith('.json'):
                df = pd.read_json(f's3://{bucket}/{key}')
            else:
                raise ValueError(f"Unsupported file format: {key}")
            
            logger.info(f"Successfully read {len(df)} rows from s3://{bucket}/{key}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to read data from s3://{bucket}/{key}: {str(e)}")
            raise
    
    def get_glue_table_schema(self, table_name: str) -> Optional[Dict]:
        """Get table schema from AWS Glue Data Catalog"""
        if not self.glue_database:
            return None
            
        try:
            response = self.glue_client.get_table(
                DatabaseName=self.glue_database,
                Name=table_name
            )
            
            table = response['Table']
            columns = table['StorageDescriptor']['Columns']
            
            schema = {}
            for column in columns:
                schema[column['Name']] = {
                    'type': column['Type'],
                    'comment': column.get('Comment', '')
                }
            
            logger.info(f"Retrieved schema for table {table_name} with {len(schema)} columns")
            return schema
            
        except Exception as e:
            logger.error(f"Failed to get schema for table {table_name}: {str(e)}")
            return None
    
    def validate_schema_compliance(self, df: pd.DataFrame, expected_schema: Dict) -> Dict:
        """Validate data against expected schema"""
        results = {
            'check_name': 'schema_compliance',
            'passed': True,
            'score': 100.0,
            'details': {
                'missing_columns': [],
                'extra_columns': [],
                'type_mismatches': [],
                'total_columns': len(expected_schema),
                'compliant_columns': 0
            }
        }
        
        if not expected_schema:
            results['passed'] = False
            results['score'] = 0.0
            results['details']['error'] = 'No expected schema provided'
            return results
        
        # Check for missing columns
        expected_columns = set(expected_schema.keys())
        actual_columns = set(df.columns)
        
        missing_columns = expected_columns - actual_columns
        extra_columns = actual_columns - expected_columns
        
        results['details']['missing_columns'] = list(missing_columns)
        results['details']['extra_columns'] = list(extra_columns)
        
        # Check data types for existing columns
        type_mismatches = []
        compliant_columns = 0
        
        for col in expected_columns.intersection(actual_columns):
            expected_type = expected_schema[col]['type']
            actual_dtype = str(df[col].dtype)
            
            # Map pandas dtypes to Glue types
            if self._types_compatible(actual_dtype, expected_type):
                compliant_columns += 1
            else:
                type_mismatches.append({
                    'column': col,
                    'expected': expected_type,
                    'actual': actual_dtype
                })
        
        results['details']['type_mismatches'] = type_mismatches
        results['details']['compliant_columns'] = compliant_columns
        
        # Calculate compliance score
        total_checks = len(expected_columns)
        compliance_score = (compliant_columns / total_checks * 100) if total_checks > 0 else 0
        results['score'] = compliance_score
        
        # Determine if check passed
        threshold = self.default_thresholds['schema_compliance_threshold']
        results['passed'] = compliance_score >= threshold and len(missing_columns) == 0
        
        return results
    
    def _types_compatible(self, pandas_type: str, glue_type: str) -> bool:
        """Check if pandas dtype is compatible with Glue type"""
        type_mappings = {
            'int64': ['bigint', 'int', 'integer'],
            'int32': ['int', 'integer'],
            'float64': ['double', 'float'],
            'float32': ['float'],
            'object': ['string', 'varchar'],
            'bool': ['boolean'],
            'datetime64': ['timestamp', 'date']
        }
        
        compatible_types = type_mappings.get(pandas_type, [])
        return glue_type.lower() in compatible_types
    
    def check_null_values(self, df: pd.DataFrame, column_rules: Dict = None) -> Dict:
        """Check for null values in the dataset"""
        results = {
            'check_name': 'null_values',
            'passed': True,
            'score': 100.0,
            'details': {
                'total_rows': len(df),
                'columns_with_nulls': {},
                'overall_null_percentage': 0.0
            }
        }
        
        total_cells = df.size
        total_nulls = df.isnull().sum().sum()
        overall_null_percentage = (total_nulls / total_cells * 100) if total_cells > 0 else 0
        
        results['details']['overall_null_percentage'] = round(overall_null_percentage, 2)
        
        # Check each column
        failed_columns = []
        for column in df.columns:
            null_count = df[column].isnull().sum()
            null_percentage = (null_count / len(df) * 100) if len(df) > 0 else 0
            
            # Get column-specific threshold or use default
            threshold = self.default_thresholds['null_percentage_threshold']
            if column_rules and column in column_rules:
                threshold = column_rules[column].get('null_threshold', threshold)
            
            column_info = {
                'null_count': int(null_count),
                'null_percentage': round(null_percentage, 2),
                'threshold': threshold,
                'passed': null_percentage <= threshold
            }
            
            results['details']['columns_with_nulls'][column] = column_info
            
            if not column_info['passed']:
                failed_columns.append(column)
        
        # Overall pass/fail
        results['passed'] = len(failed_columns) == 0
        results['score'] = max(0, 100 - overall_null_percentage)
        
        return results
    
    def check_duplicate_records(self, df: pd.DataFrame, key_columns: List[str] = None) -> Dict:
        """Check for duplicate records"""
        results = {
            'check_name': 'duplicate_records',
            'passed': True,
            'score': 100.0,
            'details': {
                'total_rows': len(df),
                'duplicate_rows': 0,
                'duplicate_percentage': 0.0,
                'key_columns': key_columns or []
            }
        }
        
        if key_columns:
            # Check duplicates based on key columns
            duplicates = df.duplicated(subset=key_columns, keep=False)
        else:
            # Check for completely duplicate rows
            duplicates = df.duplicated(keep=False)
        
        duplicate_count = duplicates.sum()
        duplicate_percentage = (duplicate_count / len(df) * 100) if len(df) > 0 else 0
        
        results['details']['duplicate_rows'] = int(duplicate_count)
        results['details']['duplicate_percentage'] = round(duplicate_percentage, 2)
        
        threshold = self.default_thresholds['duplicate_percentage_threshold']
        results['passed'] = duplicate_percentage <= threshold
        results['score'] = max(0, 100 - duplicate_percentage)
        
        return results
    
    def check_data_ranges(self, df: pd.DataFrame, range_rules: Dict) -> Dict:
        """Check if numeric data falls within expected ranges"""
        results = {
            'check_name': 'data_ranges',
            'passed': True,
            'score': 100.0,
            'details': {
                'column_checks': {},
                'total_violations': 0
            }
        }
        
        total_violations = 0
        total_checks = 0
        
        for column, rules in range_rules.items():
            if column not in df.columns:
                continue
            
            column_data = df[column].dropna()
            if len(column_data) == 0:
                continue
            
            violations = 0
            column_checks = {
                'total_values': len(column_data),
                'violations': 0,
                'violation_percentage': 0.0,
                'rules_applied': []
            }
            
            # Check minimum value
            if 'min' in rules:
                min_violations = (column_data < rules['min']).sum()
                violations += min_violations
                column_checks['rules_applied'].append(f"min >= {rules['min']}")
            
            # Check maximum value
            if 'max' in rules:
                max_violations = (column_data > rules['max']).sum()
                violations += max_violations
                column_checks['rules_applied'].append(f"max <= {rules['max']}")
            
            # Check allowed values
            if 'allowed_values' in rules:
                allowed_violations = (~column_data.isin(rules['allowed_values'])).sum()
                violations += allowed_violations
                column_checks['rules_applied'].append(f"values in {rules['allowed_values']}")
            
            column_checks['violations'] = int(violations)
            column_checks['violation_percentage'] = round((violations / len(column_data) * 100), 2)
            
            results['details']['column_checks'][column] = column_checks
            total_violations += violations
            total_checks += len(column_data)
        
        results['details']['total_violations'] = int(total_violations)
        
        if total_checks > 0:
            violation_percentage = (total_violations / total_checks * 100)
            results['score'] = max(0, 100 - violation_percentage)
            results['passed'] = violation_percentage <= self.default_thresholds['outlier_percentage_threshold']
        
        return results
    
    def check_data_freshness(self, df: pd.DataFrame, timestamp_column: str) -> Dict:
        """Check if data is fresh (within acceptable time window)"""
        results = {
            'check_name': 'data_freshness',
            'passed': True,
            'score': 100.0,
            'details': {
                'timestamp_column': timestamp_column,
                'latest_timestamp': None,
                'hours_since_latest': None,
                'threshold_hours': self.default_thresholds['data_freshness_hours']
            }
        }
        
        if timestamp_column not in df.columns:
            results['passed'] = False
            results['score'] = 0.0
            results['details']['error'] = f"Timestamp column '{timestamp_column}' not found"
            return results
        
        try:
            # Convert to datetime if not already
            timestamp_series = pd.to_datetime(df[timestamp_column])
            latest_timestamp = timestamp_series.max()
            
            # Calculate hours since latest data
            current_time = datetime.now(timezone.utc)
            if latest_timestamp.tz is None:
                latest_timestamp = latest_timestamp.tz_localize(timezone.utc)
            
            time_diff = current_time - latest_timestamp
            hours_since_latest = time_diff.total_seconds() / 3600
            
            results['details']['latest_timestamp'] = latest_timestamp.isoformat()
            results['details']['hours_since_latest'] = round(hours_since_latest, 2)
            
            threshold = self.default_thresholds['data_freshness_hours']
            results['passed'] = hours_since_latest <= threshold
            results['score'] = max(0, 100 - (hours_since_latest / threshold * 100))
            
        except Exception as e:
            results['passed'] = False
            results['score'] = 0.0
            results['details']['error'] = f"Failed to check data freshness: {str(e)}"
        
        return results
    
    def detect_statistical_outliers(self, df: pd.DataFrame, numeric_columns: List[str] = None) -> Dict:
        """Detect statistical outliers using IQR method"""
        results = {
            'check_name': 'statistical_outliers',
            'passed': True,
            'score': 100.0,
            'details': {
                'column_outliers': {},
                'total_outliers': 0,
                'total_numeric_values': 0
            }
        }
        
        if numeric_columns is None:
            numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        total_outliers = 0
        total_values = 0
        
        for column in numeric_columns:
            if column not in df.columns:
                continue
            
            column_data = df[column].dropna()
            if len(column_data) < 4:  # Need at least 4 values for IQR
                continue
            
            # Calculate IQR
            Q1 = column_data.quantile(0.25)
            Q3 = column_data.quantile(0.75)
            IQR = Q3 - Q1
            
            # Define outlier bounds
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            # Find outliers
            outliers = (column_data < lower_bound) | (column_data > upper_bound)
            outlier_count = outliers.sum()
            
            column_info = {
                'total_values': len(column_data),
                'outlier_count': int(outlier_count),
                'outlier_percentage': round((outlier_count / len(column_data) * 100), 2),
                'lower_bound': float(lower_bound),
                'upper_bound': float(upper_bound),
                'Q1': float(Q1),
                'Q3': float(Q3)
            }
            
            results['details']['column_outliers'][column] = column_info
            total_outliers += outlier_count
            total_values += len(column_data)
        
        results['details']['total_outliers'] = int(total_outliers)
        results['details']['total_numeric_values'] = int(total_values)
        
        if total_values > 0:
            outlier_percentage = (total_outliers / total_values * 100)
            results['score'] = max(0, 100 - outlier_percentage)
            results['passed'] = outlier_percentage <= self.default_thresholds['outlier_percentage_threshold']
        
        return results
    
    def quarantine_data(self, df: pd.DataFrame, quality_results: List[Dict], source_info: Dict) -> str:
        """Move failed data to quarantine bucket"""
        if not self.quarantine_bucket:
            logger.warning("Quarantine bucket not configured")
            return None
        
        try:
            # Add quality check results as metadata
            df_quarantine = df.copy()
            df_quarantine['quarantine_timestamp'] = datetime.now(timezone.utc).isoformat()
            df_quarantine['source_bucket'] = source_info.get('bucket')
            df_quarantine['source_key'] = source_info.get('key')
            
            # Generate quarantine key
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            quarantine_key = f"quarantine/{source_info.get('table_name', 'unknown')}/{timestamp}/data.parquet"
            
            # Save to quarantine bucket
            df_quarantine.to_parquet(f's3://{self.quarantine_bucket}/{quarantine_key}')
            
            # Save quality report
            quality_report = {
                'quarantine_timestamp': datetime.now(timezone.utc).isoformat(),
                'source_info': source_info,
                'quality_results': quality_results,
                'quarantine_location': f's3://{self.quarantine_bucket}/{quarantine_key}'
            }
            
            report_key = quarantine_key.replace('.parquet', '_quality_report.json')
            self.s3_client.put_object(
                Bucket=self.quarantine_bucket,
                Key=report_key,
                Body=json.dumps(quality_report, default=str, indent=2),
                ContentType='application/json'
            )
            
            logger.info(f"Data quarantined to s3://{self.quarantine_bucket}/{quarantine_key}")
            return f's3://{self.quarantine_bucket}/{quarantine_key}'
            
        except Exception as e:
            logger.error(f"Failed to quarantine data: {str(e)}")
            return None
    
    def save_quality_results(self, results: Dict):
        """Save quality check results to DynamoDB"""
        if not self.results_table:
            return
        
        try:
            # Convert numpy types to Python types for DynamoDB
            def convert_types(obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: convert_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_types(item) for item in obj]
                return obj
            
            converted_results = convert_types(results)
            
            self.results_table.put_item(Item=converted_results)
            logger.info(f"Quality results saved for check ID: {results.get('check_id')}")
            
        except Exception as e:
            logger.error(f"Failed to save quality results: {str(e)}")
    
    def send_quality_alert(self, results: Dict, severity: str = 'WARNING'):
        """Send quality alert via SNS"""
        if not self.alert_topic_arn:
            logger.warning("Alert topic ARN not configured")
            return
        
        try:
            failed_checks = [check for check in results['quality_checks'] if not check['passed']]
            
            if not failed_checks:
                return  # No failed checks to alert about
            
            message = {
                'severity': severity,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': results['source_info'],
                'overall_score': results['overall_quality_score'],
                'failed_checks': len(failed_checks),
                'total_checks': len(results['quality_checks']),
                'failed_check_details': [
                    {
                        'check_name': check['check_name'],
                        'score': check['score'],
                        'details': check['details']
                    }
                    for check in failed_checks
                ]
            }
            
            subject = f"Data Quality Alert - {severity} - {results['source_info'].get('table_name', 'Unknown')}"
            
            self.sns_client.publish(
                TopicArn=self.alert_topic_arn,
                Message=json.dumps(message, default=str, indent=2),
                Subject=subject
            )
            
            logger.info(f"Quality alert sent: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send quality alert: {str(e)}")
    
    @xray_recorder.capture('run_quality_checks')
    def run_quality_checks(self, data_config: Dict) -> Dict:
        """Run comprehensive data quality checks"""
        check_id = f"quality_check_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{data_config.get('table_name', 'unknown')}"
        
        results = {
            'check_id': check_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source_info': {
                'bucket': data_config.get('bucket'),
                'key': data_config.get('key'),
                'table_name': data_config.get('table_name'),
                'data_source': data_config.get('data_source', 'unknown')
            },
            'quality_checks': [],
            'overall_quality_score': 0.0,
            'passed': True,
            'quarantine_location': None
        }
        
        with xray_recorder.in_subsegment('quality_check_execution') as subsegment:
            subsegment.put_annotation("check_id", check_id)
            subsegment.put_annotation("table_name", data_config.get('table_name'))
            
            try:
                # Read data
                df = self.read_data_from_s3(data_config['bucket'], data_config['key'])
                
                if df.empty:
                    results['passed'] = False
                    results['quality_checks'].append({
                        'check_name': 'data_availability',
                        'passed': False,
                        'score': 0.0,
                        'details': {'error': 'No data found'}
                    })
                    return results
                
                # Get quality rules from config
                quality_rules = data_config.get('quality_rules', {})
                
                # 1. Schema compliance check
                if quality_rules.get('check_schema', True):
                    with xray_recorder.in_subsegment('schema_validation') as schema_subsegment:
                        expected_schema = self.get_glue_table_schema(data_config.get('table_name'))
                        if expected_schema:
                            schema_result = self.validate_schema_compliance(df, expected_schema)
                            results['quality_checks'].append(schema_result)
                            schema_subsegment.put_metadata('result', schema_result)
                
                # 2. Null value check
                if quality_rules.get('check_nulls', True):
                    with xray_recorder.in_subsegment('null_check') as null_subsegment:
                        column_rules = quality_rules.get('column_rules', {})
                        null_result = self.check_null_values(df, column_rules)
                        results['quality_checks'].append(null_result)
                        null_subsegment.put_metadata('result', null_result)
                
                # 3. Duplicate check
                if quality_rules.get('check_duplicates', True):
                    with xray_recorder.in_subsegment('duplicate_check') as duplicate_subsegment:
                        key_columns = quality_rules.get('key_columns')
                        duplicate_result = self.check_duplicate_records(df, key_columns)
                        results['quality_checks'].append(duplicate_result)
                        duplicate_subsegment.put_metadata('result', duplicate_result)
                
                # 4. Data range check
                if quality_rules.get('range_rules'):
                    with xray_recorder.in_subsegment('range_check') as range_subsegment:
                        range_result = self.check_data_ranges(df, quality_rules['range_rules'])
                        results['quality_checks'].append(range_result)
                        range_subsegment.put_metadata('result', range_result)
                
                # 5. Data freshness check
                if quality_rules.get('timestamp_column'):
                    with xray_recorder.in_subsegment('freshness_check') as freshness_subsegment:
                        freshness_result = self.check_data_freshness(df, quality_rules['timestamp_column'])
                        results['quality_checks'].append(freshness_result)
                        freshness_subsegment.put_metadata('result', freshness_result)
                
                # 6. Statistical outlier detection
                if quality_rules.get('check_outliers', True):
                    with xray_recorder.in_subsegment('outlier_detection') as outlier_subsegment:
                        numeric_columns = quality_rules.get('numeric_columns')
                        outlier_result = self.detect_statistical_outliers(df, numeric_columns)
                        results['quality_checks'].append(outlier_result)
                        outlier_subsegment.put_metadata('result', outlier_result)
                
                # Calculate overall quality score
                if results['quality_checks']:
                    total_score = sum(check['score'] for check in results['quality_checks'])
                    results['overall_quality_score'] = round(total_score / len(results['quality_checks']), 2)
                
                # Determine overall pass/fail
                failed_checks = [check for check in results['quality_checks'] if not check['passed']]
                results['passed'] = len(failed_checks) == 0
                
                # Quarantine data if quality checks failed
                if not results['passed'] and quality_rules.get('quarantine_on_failure', True):
                    quarantine_location = self.quarantine_data(df, results['quality_checks'], results['source_info'])
                    results['quarantine_location'] = quarantine_location
                
                # Send alerts for failed checks
                if failed_checks:
                    severity = 'ERROR' if results['overall_quality_score'] < 50 else 'WARNING'
                    self.send_quality_alert(results, severity)
                
                # Save results
                self.save_quality_results(results)
                
                logger.info(f"Quality check completed: {check_id}, Score: {results['overall_quality_score']}, Passed: {results['passed']}")
                
            except Exception as e:
                logger.error(f"Quality check failed: {str(e)}")
                results['passed'] = False
                results['quality_checks'].append({
                    'check_name': 'execution_error',
                    'passed': False,
                    'score': 0.0,
                    'details': {'error': str(e)}
                })
            
            subsegment.put_metadata('final_results', results)
            return results


@xray_recorder.capture('lambda_handler')
def lambda_handler(event, context):
    """AWS Lambda handler function"""
    extra_info = {
        'aws_request_id': getattr(context, 'aws_request_id', 'unknown'),
        'function_name': getattr(context, 'function_name', 'data-quality-monitor')
    }
    logger.info(f"Data quality monitor started with event: {json.dumps(event, default=str)}", extra=extra_info)
    
    try:
        monitor = DataQualityMonitor()
        
        # Parse data configuration from event
        data_config = event.get('data_config')
        if not data_config:
            raise ValueError("data_config is required in event payload")
        
        # Run quality checks
        results = monitor.run_quality_checks(data_config)
        
        return {
            'statusCode': 200,
            'body': json.dumps(results, default=str)
        }
        
    except Exception as e:
        error_msg = f"Data quality monitoring failed: {str(e)}"
        logger.error(error_msg, extra=extra_info)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'failed',
                'error': error_msg,
                'error_type': type(e).__name__
            })
        }
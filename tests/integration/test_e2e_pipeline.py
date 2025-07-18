"""
End-to-End Pipeline Integration Tests

This module contains integration tests for the complete data pipeline flow from
Snowflake extraction to data quality validation and transformation.
"""

import os
import json
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import io
import pyarrow as pa
import pyarrow.parquet as pq

# Import Lambda functions
# We need to mock AWS services before importing the Lambda functions
import boto3
import snowflake.connector

# Path manipulation to import Lambda functions
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../lambda/snowflake_extractor')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../lambda/pipeline_orchestrator')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../lambda/data_quality_monitor')))

class TestEndToEndPipeline:
    """Test the end-to-end data pipeline flow."""
    
    @pytest.mark.integration
    def test_snowflake_to_s3_extraction(self, mock_aws_services, mock_snowflake_connection, 
                                        test_environment, synthetic_customer_data, 
                                        snowflake_extraction_event, mock_context):
        """Test the Snowflake to S3 extraction process."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {
            'boto3': boto3,
            'snowflake.connector': snowflake.connector
        }):
            from lambda_function import lambda_handler as snowflake_extractor_handler
        
        # Setup mocks
        mock_conn, mock_cursor = mock_snowflake_connection
        mock_secrets = mock_aws_services['secrets']
        mock_s3 = mock_aws_services['s3']
        mock_table = mock_aws_services['table']
        
        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'username': 'test_user',
                'password': 'test_password',
                'account': 'test_account',
                'warehouse': 'test_warehouse',
                'database': 'test_db',
                'schema': 'test_schema'
            })
        }
        
        # Mock DynamoDB watermark response
        mock_table.get_item.return_value = {
            'Item': {
                'watermark_value': '2023-01-01T00:00:00Z'
            }
        }
        
        # Convert synthetic data to Snowflake cursor result format
        records = synthetic_customer_data.to_dict('records')
        mock_cursor.fetchall.return_value = records
        
        # Mock S3 put_object
        mock_s3.put_object.return_value = {}
        
        # Execute the Lambda function
        response = snowflake_extractor_handler(snowflake_extraction_event, mock_context)
        
        # Assertions
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        assert len(body['extractions']) > 0
        
        # Verify S3 upload was called
        mock_s3.put_object.assert_called()
        
        # Verify watermark was updated
        mock_table.put_item.assert_called()
        
        return body  # Return for use in subsequent tests
    
    @pytest.mark.integration
    def test_data_quality_monitoring(self, mock_aws_services, test_environment, 
                                     synthetic_customer_data, data_quality_event, 
                                     mock_context):
        """Test the data quality monitoring process."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import lambda_handler as data_quality_handler
        
        # Setup mocks
        mock_s3 = mock_aws_services['s3']
        mock_glue = mock_aws_services['glue']
        mock_table = mock_aws_services['table']
        mock_sns = mock_aws_services['sns']
        
        # Mock S3 get_object for parquet file
        def mock_read_parquet(*args, **kwargs):
            # Convert DataFrame to parquet bytes
            table = pa.Table.from_pandas(synthetic_customer_data)
            buf = io.BytesIO()
            pq.write_table(table, buf)
            buf.seek(0)
            
            # Create mock response
            mock_response = {
                'Body': io.BytesIO(buf.read())
            }
            return mock_response
        
        # Mock pandas read_parquet to return our synthetic data
        with patch('pandas.read_parquet', return_value=synthetic_customer_data):
            # Mock Glue table schema
            mock_glue.get_table.return_value = {
                'Table': {
                    'StorageDescriptor': {
                        'Columns': [
                            {'Name': 'customer_id', 'Type': 'string'},
                            {'Name': 'first_name', 'Type': 'string'},
                            {'Name': 'last_name', 'Type': 'string'},
                            {'Name': 'email', 'Type': 'string'},
                            {'Name': 'phone', 'Type': 'string'},
                            {'Name': 'address', 'Type': 'string'},
                            {'Name': 'city', 'Type': 'string'},
                            {'Name': 'state', 'Type': 'string'},
                            {'Name': 'zip_code', 'Type': 'string'},
                            {'Name': 'created_at', 'Type': 'timestamp'},
                            {'Name': 'updated_at', 'Type': 'timestamp'}
                        ]
                    }
                }
            }
            
            # Execute the Lambda function
            response = data_quality_handler(data_quality_event, mock_context)
            
            # Assertions
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert 'check_id' in body
            assert 'quality_checks' in body
            assert len(body['quality_checks']) > 0
            
            # Check if quality results were saved
            mock_table.put_item.assert_called()
            
            # If quality checks failed, verify alert was sent
            if not body['passed']:
                mock_sns.publish.assert_called()
            
            return body
    
    @pytest.mark.integration
    def test_pipeline_orchestration(self, mock_aws_services, test_environment, 
                                   pipeline_orchestration_event, mock_context):
        """Test the pipeline orchestration process."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import lambda_handler as pipeline_orchestrator_handler
        
        # Setup mocks
        mock_lambda = mock_aws_services['lambda']
        mock_glue = mock_aws_services['glue']
        mock_table = mock_aws_services['table']
        mock_sns = mock_aws_services['sns']
        
        # Mock Lambda invoke response
        mock_lambda.invoke.return_value = {
            'StatusCode': 200,
            'Payload': MagicMock(read=lambda: json.dumps({
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'extractions': [{'row_count': 1000}]
                })
            }).encode())
        }
        
        # Mock Glue start_job_run response
        mock_glue.start_job_run.return_value = {
            'JobRunId': 'test-job-run-id'
        }
        
        # Mock Glue get_job_run response
        mock_glue.get_job_run.return_value = {
            'JobRun': {
                'JobRunState': 'SUCCEEDED'
            }
        }
        
        # Execute the Lambda function
        response = pipeline_orchestrator_handler(pipeline_orchestration_event, mock_context)
        
        # Assertions
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'execution_id' in body
        assert body['status'] in ['RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED']
        
        # Verify Lambda was invoked
        mock_lambda.invoke.assert_called()
        
        # Verify Glue job was started
        mock_glue.start_job_run.assert_called()
        
        # Verify pipeline state was saved
        mock_table.put_item.assert_called()
        
        return body
    
    @pytest.mark.integration
    def test_complete_e2e_pipeline(self, mock_aws_services, mock_snowflake_connection, 
                                  test_environment, synthetic_customer_data, 
                                  synthetic_order_data, mock_context):
        """Test the complete end-to-end pipeline flow."""
        # This test simulates the entire pipeline flow:
        # 1. Extract data from Snowflake
        # 2. Run data quality checks
        # 3. Orchestrate the pipeline
        
        # First, test Snowflake extraction
        extraction_event = {
            'extraction_config': {
                'queries': [
                    {
                        'name': 'customers',
                        'sql': 'SELECT * FROM customers WHERE updated_at > ?',
                        'watermark_column': 'updated_at',
                        'partition_by': 'date'
                    }
                ],
                'output_format': 'parquet'
            }
        }
        
        extraction_result = self.test_snowflake_to_s3_extraction(
            mock_aws_services, mock_snowflake_connection, test_environment,
            synthetic_customer_data, extraction_event, mock_context
        )
        
        # Get the S3 location from extraction result
        s3_location = extraction_result['extractions'][0]['s3_location']
        bucket, key = s3_location.replace('s3://', '').split('/', 1)
        
        # Next, test data quality monitoring
        quality_event = {
            'data_config': {
                'bucket': bucket,
                'key': key,
                'table_name': 'customers',
                'quality_rules': {
                    'check_schema': True,
                    'check_nulls': True,
                    'timestamp_column': 'updated_at'
                }
            }
        }
        
        quality_result = self.test_data_quality_monitoring(
            mock_aws_services, test_environment, synthetic_customer_data,
            quality_event, mock_context
        )
        
        # Finally, test pipeline orchestration
        orchestration_event = {
            'action': 'orchestrate',
            'pipeline_config': {
                'pipeline_name': 'snowflake-to-s3-etl',
                'jobs': [
                    {
                        'job_id': 'extract-snowflake-data',
                        'job_type': 'lambda',
                        'function_name': 'snowflake-extractor',
                        'payload': extraction_event
                    },
                    {
                        'job_id': 'run-data-quality',
                        'job_type': 'lambda',
                        'function_name': 'data-quality-monitor',
                        'payload': quality_event
                    }
                ]
            }
        }
        
        orchestration_result = self.test_pipeline_orchestration(
            mock_aws_services, test_environment, orchestration_event, mock_context
        )
        
        # Assertions for the complete flow
        assert extraction_result['status'] == 'success'
        assert 'quality_checks' in quality_result
        assert 'execution_id' in orchestration_result
        
        # Return the combined results
        return {
            'extraction': extraction_result,
            'quality': quality_result,
            'orchestration': orchestration_result
        }
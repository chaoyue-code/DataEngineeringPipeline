"""
Configuration for integration tests.

This module provides fixtures and utilities for integration testing of the Snowflake-AWS pipeline.
"""

import os
import json
import boto3
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import uuid

# Mock AWS services for testing
@pytest.fixture
def mock_aws_services():
    """Mock AWS services for integration testing."""
    with patch('boto3.client') as mock_client, \
         patch('boto3.resource') as mock_resource:
        
        # Mock S3 client
        mock_s3 = MagicMock()
        
        # Mock DynamoDB resource and table
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock Glue client
        mock_glue = MagicMock()
        
        # Mock SNS client
        mock_sns = MagicMock()
        
        # Mock Lambda client
        mock_lambda = MagicMock()
        
        # Mock Step Functions client
        mock_stepfunctions = MagicMock()
        
        # Mock Secrets Manager client
        mock_secrets = MagicMock()
        
        # Configure mock_client to return appropriate service mocks
        mock_client.side_effect = lambda service_name, **kwargs: {
            's3': mock_s3,
            'glue': mock_glue,
            'sns': mock_sns,
            'lambda': mock_lambda,
            'stepfunctions': mock_stepfunctions,
            'secretsmanager': mock_secrets
        }.get(service_name, MagicMock())
        
        # Configure mock_resource to return DynamoDB mock
        mock_resource.return_value = mock_dynamodb
        
        yield {
            's3': mock_s3,
            'dynamodb': mock_dynamodb,
            'table': mock_table,
            'glue': mock_glue,
            'sns': mock_sns,
            'lambda': mock_lambda,
            'stepfunctions': mock_stepfunctions,
            'secrets': mock_secrets
        }

@pytest.fixture
def mock_snowflake_connection():
    """Mock Snowflake connection for integration testing."""
    with patch('snowflake.connector.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        yield mock_conn, mock_cursor

@pytest.fixture
def test_environment():
    """Set up test environment variables."""
    original_env = os.environ.copy()
    
    # Set environment variables for testing
    os.environ['SNOWFLAKE_SECRET_NAME'] = 'test-snowflake-secret'
    os.environ['S3_BUCKET_NAME'] = 'test-data-lake-bucket'
    os.environ['WATERMARK_TABLE_NAME'] = 'test-watermark-table'
    os.environ['PIPELINE_STATE_TABLE'] = 'test-pipeline-state-table'
    os.environ['JOB_DEPENDENCY_TABLE'] = 'test-job-dependency-table'
    os.environ['QUALITY_RESULTS_TABLE'] = 'test-quality-results-table'
    os.environ['QUARANTINE_BUCKET'] = 'test-quarantine-bucket'
    os.environ['ALERT_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-alert-topic'
    os.environ['GLUE_DATABASE'] = 'test-glue-database'
    os.environ['MAX_RETRIES'] = '3'
    os.environ['BATCH_SIZE'] = '1000'
    os.environ['MAX_BATCHES'] = '10'
    os.environ['DLQ_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-dlq'
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture
def synthetic_customer_data():
    """Generate synthetic customer data for testing."""
    num_records = 1000
    
    # Create customer IDs
    customer_ids = [f"CUST{i:06d}" for i in range(1, num_records + 1)]
    
    # Create names
    first_names = ["John", "Jane", "Michael", "Emily", "David", "Sarah", "Robert", "Lisa"]
    last_names = ["Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller", "Wilson"]
    
    # Generate random data
    np.random.seed(42)  # For reproducibility
    
    data = {
        'customer_id': customer_ids,
        'first_name': np.random.choice(first_names, num_records),
        'last_name': np.random.choice(last_names, num_records),
        'email': [f"{fn.lower()}.{ln.lower()}@example.com" for fn, ln in 
                 zip(np.random.choice(first_names, num_records), 
                     np.random.choice(last_names, num_records))],
        'phone': [f"+1-555-{np.random.randint(100, 999)}-{np.random.randint(1000, 9999)}" 
                 for _ in range(num_records)],
        'address': [f"{np.random.randint(100, 9999)} Main St" for _ in range(num_records)],
        'city': np.random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"], num_records),
        'state': np.random.choice(["NY", "CA", "IL", "TX", "AZ"], num_records),
        'zip_code': [f"{np.random.randint(10000, 99999)}" for _ in range(num_records)],
        'created_at': [
            (datetime.now(timezone.utc) - timedelta(days=np.random.randint(1, 365))).isoformat()
            for _ in range(num_records)
        ],
        'updated_at': [
            (datetime.now(timezone.utc) - timedelta(days=np.random.randint(0, 30))).isoformat()
            for _ in range(num_records)
        ]
    }
    
    # Introduce some nulls (about 5% of data)
    for col in ['phone', 'address', 'city']:
        null_indices = np.random.choice(num_records, size=int(num_records * 0.05), replace=False)
        for idx in null_indices:
            data[col][idx] = None
    
    # Introduce some duplicates (about 2% of data)
    duplicate_indices = np.random.choice(num_records, size=int(num_records * 0.02), replace=False)
    for idx in duplicate_indices:
        # Pick a random index to duplicate
        dup_idx = np.random.randint(0, num_records)
        for col in data:
            if col != 'customer_id':  # Keep customer_id unique
                data[col][idx] = data[col][dup_idx]
    
    return pd.DataFrame(data)

@pytest.fixture
def synthetic_order_data(synthetic_customer_data):
    """Generate synthetic order data related to customer data."""
    num_customers = len(synthetic_customer_data)
    num_orders = int(num_customers * 2.5)  # Average 2.5 orders per customer
    
    # Create order IDs
    order_ids = [f"ORD{i:08d}" for i in range(1, num_orders + 1)]
    
    # Generate random data
    np.random.seed(43)  # Different seed from customer data
    
    # Select customer IDs (some customers will have multiple orders)
    customer_indices = np.random.choice(num_customers, num_orders)
    customer_ids = [synthetic_customer_data.iloc[idx]['customer_id'] for idx in customer_indices]
    
    # Generate order dates (between 1 and 180 days ago)
    order_dates = [
        (datetime.now(timezone.utc) - timedelta(days=np.random.randint(1, 180))).isoformat()
        for _ in range(num_orders)
    ]
    
    # Generate order amounts
    order_amounts = np.round(np.random.uniform(10.0, 500.0, num_orders), 2)
    
    # Generate order statuses
    statuses = ["completed", "shipped", "processing", "cancelled"]
    status_weights = [0.7, 0.15, 0.1, 0.05]  # 70% completed, 15% shipped, etc.
    order_statuses = np.random.choice(statuses, num_orders, p=status_weights)
    
    data = {
        'order_id': order_ids,
        'customer_id': customer_ids,
        'order_date': order_dates,
        'order_amount': order_amounts,
        'order_status': order_statuses,
        'payment_method': np.random.choice(["credit_card", "paypal", "bank_transfer"], num_orders),
        'created_at': order_dates,
        'updated_at': [
            (datetime.fromisoformat(date.replace('Z', '+00:00')) + 
             timedelta(hours=np.random.randint(0, 48))).isoformat()
            for date in order_dates
        ]
    }
    
    # Introduce some nulls (about 3% of data)
    for col in ['payment_method']:
        null_indices = np.random.choice(num_orders, size=int(num_orders * 0.03), replace=False)
        for idx in null_indices:
            data[col][idx] = None
    
    return pd.DataFrame(data)

@pytest.fixture
def snowflake_extraction_event():
    """Generate a sample Snowflake extraction event."""
    return {
        'extraction_config': {
            'queries': [
                {
                    'name': 'customers',
                    'sql': 'SELECT * FROM customers WHERE updated_at > ?',
                    'watermark_column': 'updated_at',
                    'partition_by': 'date',
                    'enable_batching': True
                },
                {
                    'name': 'orders',
                    'sql': 'SELECT * FROM orders WHERE updated_at > ?',
                    'watermark_column': 'updated_at',
                    'partition_by': 'date',
                    'enable_batching': True
                }
            ],
            'output_format': 'parquet',
            'validation_rules': {
                'min_rows': 1,
                'required_columns': ['created_at', 'updated_at'],
                'non_null_columns': ['created_at']
            }
        }
    }

@pytest.fixture
def pipeline_orchestration_event():
    """Generate a sample pipeline orchestration event."""
    return {
        'action': 'orchestrate',
        'pipeline_config': {
            'pipeline_name': 'snowflake-to-s3-etl',
            'jobs': [
                {
                    'job_id': 'extract-snowflake-data',
                    'job_type': 'lambda',
                    'function_name': 'snowflake-extractor',
                    'payload': {
                        'extraction_config': {
                            'queries': [
                                {
                                    'name': 'customers',
                                    'sql': 'SELECT * FROM customers WHERE updated_at > ?',
                                    'watermark_column': 'updated_at'
                                }
                            ]
                        }
                    }
                },
                {
                    'job_id': 'run-data-quality',
                    'job_type': 'lambda',
                    'function_name': 'data-quality-monitor',
                    'payload': {
                        'data_config': {
                            'bucket': 'test-data-lake-bucket',
                            'key': 'bronze/customers/year=2024/month=07/day=18/customers_20240718_120000.parquet',
                            'table_name': 'customers',
                            'quality_rules': {
                                'check_schema': True,
                                'check_nulls': True,
                                'check_duplicates': True,
                                'timestamp_column': 'updated_at'
                            }
                        }
                    }
                },
                {
                    'job_id': 'transform-bronze-to-silver',
                    'job_type': 'glue',
                    'job_name': 'bronze-to-silver-customers',
                    'arguments': {
                        '--source_path': 's3://test-data-lake-bucket/bronze/customers/',
                        '--target_path': 's3://test-data-lake-bucket/silver/dim_customers/'
                    }
                }
            ]
        }
    }

@pytest.fixture
def data_quality_event():
    """Generate a sample data quality monitoring event."""
    return {
        'data_config': {
            'bucket': 'test-data-lake-bucket',
            'key': 'bronze/customers/year=2024/month=07/day=18/customers_20240718_120000.parquet',
            'table_name': 'customers',
            'data_source': 'snowflake',
            'quality_rules': {
                'check_schema': True,
                'check_nulls': True,
                'check_duplicates': True,
                'check_outliers': True,
                'timestamp_column': 'updated_at',
                'key_columns': ['customer_id'],
                'numeric_columns': ['order_count', 'total_spend'],
                'range_rules': {
                    'total_spend': {
                        'min': 0,
                        'max': 10000
                    }
                },
                'column_rules': {
                    'email': {
                        'null_threshold': 0  # No nulls allowed in email
                    },
                    'phone': {
                        'null_threshold': 20  # Allow up to 20% nulls in phone
                    }
                },
                'quarantine_on_failure': True
            }
        }
    }

@pytest.fixture
def mock_context():
    """Mock Lambda context for testing."""
    context = MagicMock()
    context.aws_request_id = str(uuid.uuid4())
    context.function_name = 'test-function'
    context.get_remaining_time_in_millis.return_value = 300000  # 5 minutes
    return context
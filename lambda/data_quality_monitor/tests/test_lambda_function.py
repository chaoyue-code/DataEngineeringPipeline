
import pytest
from unittest.mock import patch, MagicMock
import os
import json
import pandas as pd
from datetime import datetime, timezone

# Mock AWS SDK and other dependencies before importing the Lambda function
mock_boto3 = MagicMock()

with patch.dict('sys.modules', {'boto3': mock_boto3}):
    from lambda_function import lambda_handler, DataQualityMonitor

@pytest.fixture(autouse=True)
def set_environment_variables():
    """Set environment variables required by the Lambda function."""
    os.environ['QUALITY_RESULTS_TABLE'] = 'test_quality_table'
    os.environ['QUARANTINE_BUCKET'] = 'test_quarantine_bucket'
    os.environ['ALERT_TOPIC_ARN'] = 'test_alert_topic'
    os.environ['GLUE_DATABASE'] = 'test_glue_db'
    yield
    # Clean up environment variables
    del os.environ['QUALITY_RESULTS_TABLE']
    del os.environ['QUARANTINE_BUCKET']
    del os.environ['ALERT_TOPIC_ARN']
    del os.environ['GLUE_DATABASE']

@pytest.fixture
def mock_aws_clients():
    """Mock AWS clients for S3, DynamoDB, SNS, and Glue."""
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_sns = MagicMock()
    mock_glue = MagicMock()
    
    mock_boto3.client.side_effect = lambda service_name: {
        's3': mock_s3,
        'sns': mock_sns,
        'glue': mock_glue
    }.get(service_name)
    
    mock_boto3.resource.return_value = mock_dynamodb
    
    return mock_s3, mock_dynamodb, mock_sns, mock_glue

@pytest.fixture
def sample_event():
    """Provide a sample event for the Lambda handler."""
    return {
        'data_config': {
            'bucket': 'test_bucket',
            'key': 'test_data.parquet',
            'table_name': 'test_table',
            'data_source': 'test_source',
            'quality_rules': {
                'check_schema': True,
                'check_nulls': True,
                'check_duplicates': True,
                'key_columns': ['id'],
                'range_rules': {
                    'value': {'min': 0, 'max': 100}
                },
                'timestamp_column': 'timestamp'
            }
        }
    }

@pytest.fixture
def mock_context():
    """Provide a mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = 'test_request_id'
    context.function_name = 'test_function'
    return context

@pytest.fixture
def sample_dataframe():
    """Provide a sample pandas DataFrame for testing."""
    data = {
        'id': [1, 2, 3, 4, 5],
        'name': ['A', 'B', 'C', 'D', 'E'],
        'value': [10, 20, 30, 40, 50],
        'timestamp': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05'])
    }
    return pd.DataFrame(data)

class TestDataQualityMonitor:
    """Unit tests for the DataQualityMonitor class."""

    @patch('pandas.read_parquet')
    def test_read_data_from_s3_success(self, mock_read_parquet, sample_dataframe):
        """Test successful data reading from S3."""
        mock_read_parquet.return_value = sample_dataframe
        monitor = DataQualityMonitor()
        df = monitor.read_data_from_s3('test_bucket', 'test.parquet')
        
        assert not df.empty
        assert len(df) == 5
        mock_read_parquet.assert_called_once_with('s3://test_bucket/test.parquet')

    def test_get_glue_table_schema_success(self, mock_aws_clients):
        """Test successful schema retrieval from Glue."""
        _, _, _, mock_glue = mock_aws_clients
        mock_glue.get_table.return_value = {
            'Table': {
                'StorageDescriptor': {
                    'Columns': [
                        {'Name': 'id', 'Type': 'bigint'},
                        {'Name': 'name', 'Type': 'string'}
                    ]
                }
            }
        }
        
        monitor = DataQualityMonitor()
        schema = monitor.get_glue_table_schema('test_table')
        
        assert schema is not None
        assert 'id' in schema
        assert schema['id']['type'] == 'bigint'

    def test_validate_schema_compliance_success(self, sample_dataframe):
        """Test successful schema validation."""
        monitor = DataQualityMonitor()
        expected_schema = {
            'id': {'type': 'int64'},
            'name': {'type': 'object'}
        }
        
        # Mock the type compatibility check to simplify the test
        with patch.object(monitor, '_types_compatible', return_value=True):
            result = monitor.validate_schema_compliance(sample_dataframe, expected_schema)
        
        assert result['passed']
        assert result['score'] == 100.0

    def test_check_null_values_no_nulls(self, sample_dataframe):
        """Test null value check with no nulls."""
        monitor = DataQualityMonitor()
        result = monitor.check_null_values(sample_dataframe)
        
        assert result['passed']
        assert result['details']['overall_null_percentage'] == 0.0

    def test_check_duplicate_records_no_duplicates(self, sample_dataframe):
        """Test duplicate record check with no duplicates."""
        monitor = DataQualityMonitor()
        result = monitor.check_duplicate_records(sample_dataframe, key_columns=['id'])
        
        assert result['passed']
        assert result['details']['duplicate_rows'] == 0

    @patch('pandas.DataFrame.to_parquet')
    def test_run_quality_checks_success(self, mock_to_parquet, mock_aws_clients, sample_dataframe):
        """Test the main run_quality_checks method for a successful run."""
        mock_s3, mock_dynamodb, mock_sns, mock_glue = mock_aws_clients
        
        # Mock S3 read
        with patch.object(DataQualityMonitor, 'read_data_from_s3', return_value=sample_dataframe):
            # Mock Glue schema
            mock_glue.get_table.return_value = {
                'Table': {
                    'StorageDescriptor': {
                        'Columns': [
                            {'Name': 'id', 'Type': 'bigint'},
                            {'Name': 'name', 'Type': 'string'},
                            {'Name': 'value', 'Type': 'double'},
                            {'Name': 'timestamp', 'Type': 'timestamp'}
                        ]
                    }
                }
            }
            
            monitor = DataQualityMonitor()
            # Mock type compatibility
            with patch.object(monitor, '_types_compatible', return_value=True):
                results = monitor.run_quality_checks({
                    'bucket': 'test_bucket',
                    'key': 'test.parquet',
                    'table_name': 'test_table',
                    'quality_rules': {
                        'check_schema': True,
                        'check_nulls': True,
                        'check_duplicates': True,
                        'key_columns': ['id'],
                        'range_rules': {'value': {'min': 0, 'max': 100}},
                        'timestamp_column': 'timestamp'
                    }
                })
        
        assert results['passed']
        assert results['overall_quality_score'] > 90
        mock_dynamodb.Table.return_value.put_item.assert_called_once()
        mock_sns.publish.assert_not_called()

class TestLambdaHandler:
    """Unit tests for the lambda_handler function."""

    @patch('lambda_function.DataQualityMonitor')
    def test_lambda_handler_success(self, mock_monitor_class, sample_event, mock_context):
        """Test the lambda_handler for a successful invocation."""
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.run_quality_checks.return_value = {
            'passed': True,
            'overall_quality_score': 100.0
        }
        mock_monitor_class.return_value = mock_monitor_instance
        
        response = lambda_handler(sample_event, mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['passed']
        
        mock_monitor_instance.run_quality_checks.assert_called_once_with(sample_event['data_config'])

    @patch('lambda_function.DataQualityMonitor')
    def test_lambda_handler_failure(self, mock_monitor_class, sample_event, mock_context):
        """Test the lambda_handler for a failed invocation."""
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.run_quality_checks.side_effect = Exception("Quality check failed")
        mock_monitor_class.return_value = mock_monitor_instance
        
        response = lambda_handler(sample_event, mock_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['status'] == 'failed'
        assert 'Quality check failed' in body['error']

    def test_lambda_handler_no_config(self, mock_context):
        """Test the lambda_handler with a missing data_config."""
        response = lambda_handler({}, mock_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'data_config is required' in body['error']

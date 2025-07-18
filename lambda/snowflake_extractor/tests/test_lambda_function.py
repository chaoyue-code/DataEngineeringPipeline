
import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
from datetime import datetime, timezone

# Mock AWS SDK and other dependencies before importing the Lambda function
mock_boto3 = MagicMock()
mock_snowflake = MagicMock()

with patch.dict('sys.modules', {'boto3': mock_boto3, 'snowflake.connector': mock_snowflake}):
    from lambda_function import lambda_handler, SnowflakeExtractor

@pytest.fixture(autouse=True)
def set_environment_variables():
    """Set environment variables required by the Lambda function."""
    os.environ['SNOWFLAKE_SECRET_NAME'] = 'test_secret'
    os.environ['S3_BUCKET_NAME'] = 'test_bucket'
    os.environ['WATERMARK_TABLE_NAME'] = 'test_watermark_table'
    os.environ['MAX_RETRIES'] = '3'
    os.environ['BATCH_SIZE'] = '10000'
    os.environ['MAX_BATCHES'] = '100'
    os.environ['DLQ_URL'] = 'test_dlq_url'
    os.environ['ALERT_TOPIC_ARN'] = 'test_alert_topic_arn'
    yield
    # Clean up environment variables
    del os.environ['SNOWFLAKE_SECRET_NAME']
    del os.environ['S3_BUCKET_NAME']
    del os.environ['WATERMARK_TABLE_NAME']
    del os.environ['MAX_RETRIES']
    del os.environ['BATCH_SIZE']
    del os.environ['MAX_BATCHES']
    del os.environ['DLQ_URL']
    del os.environ['ALERT_TOPIC_ARN']

@pytest.fixture
def mock_aws_clients():
    """Mock AWS clients for Secrets Manager, S3, and DynamoDB."""
    mock_secrets_manager = MagicMock()
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    
    mock_boto3.client.side_effect = lambda service_name: {
        'secretsmanager': mock_secrets_manager,
        's3': mock_s3
    }.get(service_name)
    
    mock_boto3.resource.return_value = mock_dynamodb
    
    return mock_secrets_manager, mock_s3, mock_dynamodb

@pytest.fixture
def mock_snowflake_connection():
    """Mock the Snowflake connection and cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_snowflake.connect.return_value = mock_conn
    return mock_conn, mock_cursor

@pytest.fixture
def sample_event():
    """Provide a sample event for the Lambda handler."""
    return {
        'extraction_config': {
            'queries': [
                {
                    'name': 'test_query',
                    'sql': 'SELECT id, name, updated_at FROM test_table WHERE updated_at > ?',
                    'watermark_column': 'updated_at',
                    'partition_by': 'date',
                    'enable_batching': True
                }
            ],
            'output_format': 'parquet',
            'validation_rules': {
                'id': {'type': 'integer', 'required': True},
                'name': {'type': 'string', 'required': True}
            }
        }
    }

@pytest.fixture
def mock_context():
    """Provide a mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = 'test_request_id'
    context.function_name = 'test_function'
    context.get_remaining_time_in_millis.return_value = 300000
    return context

class TestSnowflakeExtractor:
    """Unit tests for the SnowflakeExtractor class."""

    def test_get_snowflake_credentials_success(self, mock_aws_clients):
        """Test successful retrieval of Snowflake credentials."""
        mock_secrets_manager, _, _ = mock_aws_clients
        mock_secrets_manager.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'username': 'test_user',
                'password': 'test_password',
                'account': 'test_account',
                'warehouse': 'test_warehouse',
                'database': 'test_db',
                'schema': 'test_schema'
            })
        }
        
        extractor = SnowflakeExtractor()
        creds = extractor._get_snowflake_credentials()
        
        assert creds['username'] == 'test_user'
        mock_secrets_manager.get_secret_value.assert_called_once_with(SecretId='test_secret')

    def test_get_connection_success(self, mock_aws_clients, mock_snowflake_connection):
        """Test successful connection to Snowflake."""
        mock_secrets_manager, _, _ = mock_aws_clients
        mock_secrets_manager.get_secret_value.return_value = {
            'SecretString': '{"username": "user", "password": "pw", "account": "acc", "warehouse": "wh", "database": "db", "schema": "sc"}'
        }
        
        extractor = SnowflakeExtractor()
        conn = extractor._get_connection()
        
        assert conn is not None
        mock_snowflake.connect.assert_called_once()

    def test_execute_query_with_retry_success(self, mock_aws_clients, mock_snowflake_connection):
        """Test successful query execution."""
        _, mock_cursor = mock_snowflake_connection
        mock_cursor.fetchall.return_value = [{'id': 1, 'name': 'test'}]
        
        extractor = SnowflakeExtractor()
        # Mock the connection to avoid re-establishing it
        extractor._connection = mock_snowflake_connection[0]
        
        results = extractor._execute_query_with_retry("SELECT * FROM test")
        
        assert len(results) == 1
        assert results[0]['id'] == 1

    def test_upload_to_s3_parquet(self, mock_aws_clients):
        """Test uploading data to S3 in Parquet format."""
        _, mock_s3, _ = mock_aws_clients
        
        extractor = SnowflakeExtractor()
        test_data = [{'id': 1, 'name': 'test'}]
        s3_key = 'bronze/test/test.parquet'
        
        with patch('pyarrow.parquet.write_table') as mock_write_table:
            extractor._upload_to_s3(test_data, s3_key, 'parquet')
            
            mock_write_table.assert_called_once()
            mock_s3.put_object.assert_called_once()
            assert mock_s3.put_object.call_args[1]['Bucket'] == 'test_bucket'
            assert mock_s3.put_object.call_args[1]['Key'] == s3_key

    def test_extract_data_success(self, mock_aws_clients, mock_snowflake_connection, sample_event):
        """Test the main extract_data method for a successful run."""
        mock_secrets_manager, mock_s3, mock_dynamodb = mock_aws_clients
        mock_conn, mock_cursor = mock_snowflake_connection
        
        # Mock credentials
        mock_secrets_manager.get_secret_value.return_value = {
            'SecretString': '{"username": "user", "password": "pw", "account": "acc", "warehouse": "wh", "database": "db", "schema": "sc"}'
        }
        
        # Mock watermark
        mock_dynamodb.Table.return_value.get_item.return_value = {
            'Item': {'watermark_value': '2023-01-01T00:00:00Z'}
        }
        
        # Mock query result
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'name': 'test1', 'updated_at': datetime(2023, 1, 2, tzinfo=timezone.utc)},
            {'id': 2, 'name': 'test2', 'updated_at': datetime(2023, 1, 3, tzinfo=timezone.utc)}
        ]
        
        extractor = SnowflakeExtractor()
        
        with patch('pyarrow.parquet.write_table'):
            results = extractor.extract_data(sample_event['extraction_config'])
        
        assert results['status'] == 'success'
        assert len(results['extractions']) == 1
        assert results['extractions'][0]['row_count'] == 2
        
        mock_s3.put_object.assert_called_once()
        mock_dynamodb.Table.return_value.put_item.assert_called_once()

class TestLambdaHandler:
    """Unit tests for the lambda_handler function."""

    @patch('lambda_function.SnowflakeExtractor')
    def test_lambda_handler_success(self, mock_extractor_class, sample_event, mock_context):
        """Test the lambda_handler for a successful invocation."""
        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract_data.return_value = {
            'status': 'success',
            'extractions': [{'row_count': 10}],
            'errors': []
        }
        mock_extractor_class.return_value = mock_extractor_instance
        
        response = lambda_handler(sample_event, mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        
        mock_extractor_instance.extract_data.assert_called_once_with(sample_event['extraction_config'])

    @patch('lambda_function.SnowflakeExtractor')
    def test_lambda_handler_partial_success(self, mock_extractor_class, sample_event, mock_context):
        """Test the lambda_handler for a partially successful invocation."""
        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract_data.return_value = {
            'status': 'partial_success',
            'extractions': [],
            'errors': ['Something went wrong']
        }
        mock_extractor_class.return_value = mock_extractor_instance
        
        response = lambda_handler(sample_event, mock_context)
        
        assert response['statusCode'] == 207
        body = json.loads(response['body'])
        assert body['status'] == 'partial_success'

    @patch('lambda_function.SnowflakeExtractor')
    def test_lambda_handler_failure(self, mock_extractor_class, sample_event, mock_context):
        """Test the lambda_handler for a failed invocation."""
        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract_data.side_effect = Exception("Major failure")
        mock_extractor_class.return_value = mock_extractor_instance
        
        # Mock the error handler to re-raise the exception
        mock_error_handler = mock_extractor_instance.error_handler
        mock_error_handler.execute_with_retry.side_effect = Exception("Major failure")

        response = lambda_handler(sample_event, mock_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['status'] == 'failed'
        assert 'Major failure' in body['error']

    def test_lambda_handler_no_config(self, mock_context):
        """Test the lambda_handler with a missing extraction_config."""
        response = lambda_handler({}, mock_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'extraction_config is required' in body['error']


import pytest
from unittest.mock import patch, MagicMock
import os
import json

# Mock AWS SDK before importing the Lambda function
mock_boto3 = MagicMock()

with patch.dict('sys.modules', {'boto3': mock_boto3}):
    from lambda_function import lambda_handler, FeatureStoreIntegration

@pytest.fixture(autouse=True)
def set_environment_variables():
    """Set environment variables required by the Lambda function."""
    os.environ['PROJECT_NAME'] = 'test_project'
    os.environ['ENVIRONMENT'] = 'test_env'
    os.environ['DATA_LAKE_BUCKET'] = 'test_bucket'
    os.environ['FEATURE_STORE_ROLE_ARN'] = 'arn:aws:iam::123456789012:role/test_role'
    os.environ['LINEAGE_TABLE_NAME'] = 'test_lineage_table'
    yield
    # Clean up environment variables
    del os.environ['PROJECT_NAME']
    del os.environ['ENVIRONMENT']
    del os.environ['DATA_LAKE_BUCKET']
    del os.environ['FEATURE_STORE_ROLE_ARN']
    del os.environ['LINEAGE_TABLE_NAME']

@pytest.fixture
def mock_aws_clients():
    """Mock AWS clients for SageMaker, S3, and DynamoDB."""
    mock_sagemaker = MagicMock()
    mock_sagemaker_runtime = MagicMock()
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    
    def client_side_effect(service_name):
        if service_name == 'sagemaker':
            return mock_sagemaker
        if service_name == 'sagemaker-featurestore-runtime':
            return mock_sagemaker_runtime
        if service_name == 's3':
            return mock_s3
        return MagicMock() # Default mock for other services

    mock_boto3.client.side_effect = client_side_effect
    mock_boto3.resource.return_value = mock_dynamodb
    
    return mock_sagemaker, mock_sagemaker_runtime, mock_s3, mock_dynamodb

@pytest.fixture
def sample_event():
    """Provide a sample event for the Lambda handler."""
    return {
        'action': 'ingest_features',
        'ingestion_config': {
            'feature_group_name': 'test_feature_group',
            'gold_data_s3_uri': 's3://test_bucket/gold/data.json'
        }
    }

@pytest.fixture
def mock_context():
    """Provide a mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = 'test_request_id'
    context.function_name = 'test_function'
    return context

class TestFeatureStoreIntegration:
    """Unit tests for the FeatureStoreIntegration class."""

    def test_create_feature_group_success(self, mock_aws_clients):
        """Test successful creation of a feature group."""
        mock_sagemaker, _, _, _ = mock_aws_clients
        mock_sagemaker.create_feature_group.return_value = {
            'FeatureGroupArn': 'arn:aws:sagemaker:us-east-1:123456789012:feature-group/test_fg'
        }
        
        integration = FeatureStoreIntegration()
        config = {
            'feature_group_name': 'test_fg',
            'record_identifier_feature_name': 'id',
            'event_time_feature_name': 'timestamp',
            'feature_definitions': []
        }
        result = integration.create_feature_group(config)
        
        assert result['status'] == 'Creating'
        assert 'feature_group_arn' in result
        mock_sagemaker.create_feature_group.assert_called_once()

    def test_ingest_features_from_gold_layer_success(self, mock_aws_clients):
        """Test successful feature ingestion."""
        _, mock_sagemaker_runtime, mock_s3, mock_dynamodb = mock_aws_clients
        
        # Mock S3 get_object
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=json.dumps([{'id': 1, 'feature': 0.5}]).encode()))
        }
        
        # Mock DynamoDB query for versioning
        mock_dynamodb.Table.return_value.query.return_value = {'Items': []}
        
        integration = FeatureStoreIntegration()
        config = {
            'feature_group_name': 'test_fg',
            'gold_data_s3_uri': 's3://test_bucket/gold/data.json'
        }
        
        result = integration.ingest_features_from_gold_layer(config)
        
        assert result['records_processed'] == 1
        assert result['lineage_recorded']
        mock_sagemaker_runtime.put_record.assert_called()
        mock_dynamodb.Table.return_value.put_item.assert_called_once()

    def test_get_online_features_success(self, mock_aws_clients):
        """Test successful retrieval of online features."""
        _, mock_sagemaker_runtime, _, _ = mock_aws_clients
        mock_sagemaker_runtime.get_record.return_value = {
            'Record': [
                {'FeatureName': 'id', 'ValueAsString': '123'},
                {'FeatureName': 'feature1', 'ValueAsString': '0.5'}
            ]
        }
        
        integration = FeatureStoreIntegration()
        result = integration.get_online_features('test_fg', '123')
        
        assert 'features' in result
        assert result['features']['id'] == '123'
        mock_sagemaker_runtime.get_record.assert_called_once_with(
            FeatureGroupName='test_fg', RecordIdentifierValueAsString='123'
        )

class TestLambdaHandler:
    """Unit tests for the lambda_handler function."""

    @patch('lambda_function.FeatureStoreIntegration')
    def test_lambda_handler_ingest_success(self, mock_integration_class, sample_event, mock_context):
        """Test the lambda_handler for a successful ingestion action."""
        mock_instance = MagicMock()
        mock_instance.ingest_features_from_gold_layer.return_value = {'status': 'success'}
        mock_integration_class.return_value = mock_instance
        
        response = lambda_handler(sample_event, mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'success'
        mock_instance.ingest_features_from_gold_layer.assert_called_once_with(sample_event['ingestion_config'])

    @patch('lambda_function.FeatureStoreIntegration')
    def test_lambda_handler_create_fg_success(self, mock_integration_class, mock_context):
        """Test the lambda_handler for a successful create_feature_group action."""
        mock_instance = MagicMock()
        mock_instance.create_feature_group.return_value = {'status': 'Creating'}
        mock_integration_class.return_value = mock_instance
        
        event = {
            'action': 'create_feature_group',
            'feature_group_config': {'name': 'test'}
        }
        response = lambda_handler(event, mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'Creating'
        mock_instance.create_feature_group.assert_called_once_with({'name': 'test'})

    def test_lambda_handler_unknown_action(self, mock_context):
        """Test the lambda_handler with an unknown action."""
        event = {'action': 'unknown_action'}
        response = lambda_handler(event, mock_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'Unknown action' in body['error']

    @patch('lambda_function.FeatureStoreIntegration')
    def test_lambda_handler_exception(self, mock_integration_class, sample_event, mock_context):
        """Test the lambda_handler when an exception occurs."""
        mock_instance = MagicMock()
        mock_instance.ingest_features_from_gold_layer.side_effect = Exception("Test error")
        mock_integration_class.return_value = mock_instance
        
        response = lambda_handler(sample_event, mock_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'Test error' in body['error']

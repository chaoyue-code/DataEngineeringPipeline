#!/usr/bin/env python3
"""
SageMaker Feature Store Integration Lambda Function
Handles automated feature ingestion from Gold layer with versioning and lineage tracking
"""

import json
import logging
import os
import boto3
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import uuid

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
sagemaker_client = boto3.client('sagemaker')
sagemaker_featurestore_runtime = boto3.client('sagemaker-featurestore-runtime')
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

class FeatureStoreIntegration:
    """Manages SageMaker Feature Store integration with automated feature ingestion"""
    
    def __init__(self):
        self.project_name = os.environ.get('PROJECT_NAME', 'snowflake-aws-pipeline')
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        self.data_lake_bucket = os.environ.get('DATA_LAKE_BUCKET')
        self.feature_store_role_arn = os.environ.get('FEATURE_STORE_ROLE_ARN')
        self.lineage_table_name = os.environ.get('LINEAGE_TABLE_NAME', f'{self.project_name}-feature-lineage')
        
        # Initialize DynamoDB table for lineage tracking
        self.lineage_table = dynamodb.Table(self.lineage_table_name)
        
    def create_feature_group(self, feature_group_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new feature group in SageMaker Feature Store"""
        logger.info(f"Creating feature group: {feature_group_config['feature_group_name']}")
        
        try:
            response = sagemaker_client.create_feature_group(
                FeatureGroupName=feature_group_config['feature_group_name'],
                RecordIdentifierFeatureName=feature_group_config['record_identifier_feature_name'],
                EventTimeFeatureName=feature_group_config['event_time_feature_name'],
                FeatureDefinitions=feature_group_config['feature_definitions'],
                OnlineStoreConfig={
                    'EnableOnlineStore': feature_group_config.get('enable_online_store', True)
                },
                OfflineStoreConfig={
                    'S3StorageConfig': {
                        'S3Uri': f"s3://{self.data_lake_bucket}/feature-store/offline/{feature_group_config['feature_group_name']}/",
                        'KmsKeyId': feature_group_config.get('kms_key_id')
                    },
                    'DisableGlueTableCreation': False,
                    'DataCatalogConfig': {
                        'TableName': f"{feature_group_config['feature_group_name']}_table",
                        'Catalog': 'AwsDataCatalog',
                        'Database': feature_group_config.get('glue_database', 'feature_store_db')
                    }
                },
                RoleArn=self.feature_store_role_arn,
                Description=feature_group_config.get('description', ''),
                Tags=[
                    {'Key': 'Project', 'Value': self.project_name},
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'CreatedBy', 'Value': 'feature-store-integration'}
                ]
            )
            
            logger.info(f"Feature group created successfully: {feature_group_config['feature_group_name']}")
            return {
                'feature_group_name': feature_group_config['feature_group_name'],
                'feature_group_arn': response['FeatureGroupArn'],
                'status': 'Creating'
            }
            
        except Exception as e:
            logger.error(f"Failed to create feature group: {str(e)}")
            raise
    
    def describe_feature_group(self, feature_group_name: str) -> Dict[str, Any]:
        """Get feature group details and status"""
        try:
            response = sagemaker_client.describe_feature_group(
                FeatureGroupName=feature_group_name
            )
            
            return {
                'feature_group_name': feature_group_name,
                'feature_group_status': response['FeatureGroupStatus'],
                'creation_time': response.get('CreationTime'),
                'online_store_config': response.get('OnlineStoreConfig', {}),
                'offline_store_config': response.get('OfflineStoreConfig', {}),
                'feature_definitions': response.get('FeatureDefinitions', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to describe feature group: {str(e)}")
            return {'feature_group_name': feature_group_name, 'status': 'Unknown', 'error': str(e)}
    
    def ingest_features_from_gold_layer(self, ingestion_config: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest features from Gold layer data into Feature Store"""
        logger.info(f"Starting feature ingestion from Gold layer")
        
        feature_group_name = ingestion_config['feature_group_name']
        gold_data_s3_uri = ingestion_config['gold_data_s3_uri']
        
        try:
            # Parse S3 URI
            bucket_name = gold_data_s3_uri.replace('s3://', '').split('/')[0]
            object_key = '/'.join(gold_data_s3_uri.replace('s3://', '').split('/')[1:])
            
            # Read data from S3 (assuming Parquet format)
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            
            # For this implementation, we'll assume the data is in JSON format
            # In a real scenario, you'd handle Parquet files using pandas or pyarrow
            data = json.loads(response['Body'].read().decode('utf-8'))
            
            if not isinstance(data, list):
                data = [data]
            
            # Prepare records for ingestion
            records = []
            ingestion_id = str(uuid.uuid4())
            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            
            for record in data:
                # Add event time if not present
                if 'event_time' not in record:
                    record['event_time'] = current_time
                
                # Add ingestion metadata
                record['ingestion_id'] = ingestion_id
                record['source_s3_uri'] = gold_data_s3_uri
                
                records.append({
                    'Record': [
                        {
                            'FeatureName': key,
                            'ValueAsString': str(value)
                        }
                        for key, value in record.items()
                    ]
                })
            
            # Ingest records in batches
            batch_size = ingestion_config.get('batch_size', 100)
            ingestion_results = []
            
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                
                try:
                    response = sagemaker_featurestore_runtime.batch_get_record(
                        Identifier={
                            'FeatureGroupName': feature_group_name,
                            'RecordIdentifiersValueAsString': [
                                record['Record'][0]['ValueAsString']  # Assuming first feature is the identifier
                                for record in batch
                            ]
                        }
                    )
                    
                    # Put records
                    for record in batch:
                        sagemaker_featurestore_runtime.put_record(
                            FeatureGroupName=feature_group_name,
                            Record=record['Record']
                        )
                    
                    ingestion_results.append({
                        'batch_start': i,
                        'batch_size': len(batch),
                        'status': 'Success'
                    })
                    
                except Exception as batch_error:
                    logger.error(f"Batch ingestion failed for batch {i}: {str(batch_error)}")
                    ingestion_results.append({
                        'batch_start': i,
                        'batch_size': len(batch),
                        'status': 'Failed',
                        'error': str(batch_error)
                    })
            
            # Record lineage information
            lineage_record = {
                'ingestion_id': ingestion_id,
                'feature_group_name': feature_group_name,
                'source_s3_uri': gold_data_s3_uri,
                'ingestion_timestamp': current_time,
                'records_processed': len(records),
                'batch_results': ingestion_results,
                'version': self._get_next_version(feature_group_name),
                'metadata': {
                    'project': self.project_name,
                    'environment': self.environment,
                    'ingestion_config': ingestion_config
                }
            }
            
            self._record_lineage(lineage_record)
            
            logger.info(f"Feature ingestion completed: {ingestion_id}")
            return {
                'ingestion_id': ingestion_id,
                'feature_group_name': feature_group_name,
                'records_processed': len(records),
                'batch_results': ingestion_results,
                'lineage_recorded': True,
                'version': lineage_record['version']
            }
            
        except Exception as e:
            logger.error(f"Feature ingestion failed: {str(e)}")
            raise
    
    def _get_next_version(self, feature_group_name: str) -> int:
        """Get the next version number for feature group"""
        try:
            response = self.lineage_table.query(
                IndexName='FeatureGroupIndex',  # Assuming GSI exists
                KeyConditionExpression='feature_group_name = :fg_name',
                ExpressionAttributeValues={':fg_name': feature_group_name},
                ScanIndexForward=False,  # Get latest first
                Limit=1
            )
            
            if response['Items']:
                return response['Items'][0]['version'] + 1
            else:
                return 1
                
        except Exception as e:
            logger.warning(f"Could not get version, defaulting to 1: {str(e)}")
            return 1
    
    def _record_lineage(self, lineage_record: Dict[str, Any]):
        """Record feature lineage information in DynamoDB"""
        try:
            self.lineage_table.put_item(Item=lineage_record)
            logger.info(f"Lineage recorded for ingestion: {lineage_record['ingestion_id']}")
        except Exception as e:
            logger.error(f"Failed to record lineage: {str(e)}")
            # Don't raise exception as this is not critical for the main flow
    
    def get_feature_lineage(self, feature_group_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get feature lineage history for a feature group"""
        try:
            response = self.lineage_table.query(
                IndexName='FeatureGroupIndex',
                KeyConditionExpression='feature_group_name = :fg_name',
                ExpressionAttributeValues={':fg_name': feature_group_name},
                ScanIndexForward=False,  # Get latest first
                Limit=limit
            )
            
            return response['Items']
            
        except Exception as e:
            logger.error(f"Failed to get feature lineage: {str(e)}")
            return []
    
    def setup_online_offline_serving(self, feature_group_name: str) -> Dict[str, Any]:
        """Configure online and offline feature serving"""
        logger.info(f"Setting up feature serving for: {feature_group_name}")
        
        try:
            # Get feature group details
            fg_details = self.describe_feature_group(feature_group_name)
            
            if fg_details['feature_group_status'] != 'Created':
                return {
                    'feature_group_name': feature_group_name,
                    'status': 'NotReady',
                    'message': f"Feature group status: {fg_details['feature_group_status']}"
                }
            
            # Online serving configuration
            online_config = {
                'enabled': fg_details['online_store_config'].get('EnableOnlineStore', False),
                'endpoint_url': f"https://featurestore-runtime.{boto3.Session().region_name}.amazonaws.com",
                'feature_group_name': feature_group_name
            }
            
            # Offline serving configuration
            offline_config = {
                'enabled': True,
                's3_uri': fg_details['offline_store_config']['S3StorageConfig']['S3Uri'],
                'glue_table': fg_details['offline_store_config']['DataCatalogConfig']['TableName'],
                'glue_database': fg_details['offline_store_config']['DataCatalogConfig']['Database']
            }
            
            # Create serving configuration document
            serving_config = {
                'feature_group_name': feature_group_name,
                'online_serving': online_config,
                'offline_serving': offline_config,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'feature_definitions': fg_details['feature_definitions']
            }
            
            # Save configuration to S3
            config_key = f"feature-store/serving-configs/{feature_group_name}/config.json"
            s3.put_object(
                Bucket=self.data_lake_bucket,
                Key=config_key,
                Body=json.dumps(serving_config, indent=2, default=str),
                ContentType='application/json'
            )
            
            logger.info(f"Feature serving configuration created for: {feature_group_name}")
            return {
                'feature_group_name': feature_group_name,
                'status': 'Configured',
                'online_serving': online_config,
                'offline_serving': offline_config,
                'config_s3_uri': f"s3://{self.data_lake_bucket}/{config_key}"
            }
            
        except Exception as e:
            logger.error(f"Failed to setup feature serving: {str(e)}")
            raise
    
    def get_online_features(self, feature_group_name: str, record_identifier: str) -> Dict[str, Any]:
        """Retrieve features from online store"""
        try:
            response = sagemaker_featurestore_runtime.get_record(
                FeatureGroupName=feature_group_name,
                RecordIdentifierValueAsString=record_identifier
            )
            
            # Convert response to dictionary
            features = {}
            for feature in response.get('Record', []):
                features[feature['FeatureName']] = feature['ValueAsString']
            
            return {
                'feature_group_name': feature_group_name,
                'record_identifier': record_identifier,
                'features': features,
                'retrieved_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get online features: {str(e)}")
            return {
                'feature_group_name': feature_group_name,
                'record_identifier': record_identifier,
                'error': str(e)
            }

def lambda_handler(event, context):
    """Lambda handler function"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        feature_store = FeatureStoreIntegration()
        
        # Determine the action based on event
        action = event.get('action', 'ingest_features')
        
        if action == 'create_feature_group':
            # Create new feature group
            feature_group_config = event.get('feature_group_config', {})
            result = feature_store.create_feature_group(feature_group_config)
            
        elif action == 'ingest_features':
            # Ingest features from Gold layer
            ingestion_config = event.get('ingestion_config', {})
            result = feature_store.ingest_features_from_gold_layer(ingestion_config)
            
        elif action == 'describe_feature_group':
            # Get feature group details
            feature_group_name = event.get('feature_group_name')
            result = feature_store.describe_feature_group(feature_group_name)
            
        elif action == 'setup_serving':
            # Setup online/offline serving
            feature_group_name = event.get('feature_group_name')
            result = feature_store.setup_online_offline_serving(feature_group_name)
            
        elif action == 'get_lineage':
            # Get feature lineage
            feature_group_name = event.get('feature_group_name')
            limit = event.get('limit', 10)
            result = feature_store.get_feature_lineage(feature_group_name, limit)
            
        elif action == 'get_online_features':
            # Get features from online store
            feature_group_name = event.get('feature_group_name')
            record_identifier = event.get('record_identifier')
            result = feature_store.get_online_features(feature_group_name, record_identifier)
            
        else:
            raise ValueError(f"Unknown action: {action}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str)
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }
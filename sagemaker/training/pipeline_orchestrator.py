#!/usr/bin/env python3
"""
Enhanced SageMaker Training Pipeline Orchestrator
Integrates with Feature Store and provides comprehensive model training automation
"""

import json
import logging
import os
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import uuid

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
sagemaker = boto3.client('sagemaker')
sagemaker_featurestore_runtime = boto3.client('sagemaker-featurestore-runtime')
s3 = boto3.client('s3')
stepfunctions = boto3.client('stepfunctions')
sns = boto3.client('sns')

class TrainingPipelineOrchestrator:
    """Enhanced training pipeline orchestrator with Feature Store integration"""
    
    def __init__(self):
        self.project_name = os.environ.get('PROJECT_NAME', 'snowflake-aws-pipeline')
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        self.artifacts_bucket = os.environ.get('SAGEMAKER_ARTIFACTS_BUCKET')
        self.data_lake_bucket = os.environ.get('DATA_LAKE_BUCKET')
        self.execution_role_arn = os.environ.get('SAGEMAKER_EXECUTION_ROLE_ARN')
        self.sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        
    def prepare_training_data_from_feature_store(self, data_config: Dict[str, Any]) -> str:
        """Prepare training data from Feature Store"""
        logger.info("Preparing training data from Feature Store")
        
        feature_group_name = data_config['feature_group_name']
        query = data_config.get('query', f"SELECT * FROM {feature_group_name}")
        output_format = data_config.get('output_format', 'parquet')
        
        # Create Athena query for Feature Store offline store
        query_execution_id = str(uuid.uuid4())
        output_location = f"s3://{self.data_lake_bucket}/feature-store/query-results/{query_execution_id}/"
        
        # In a real implementation, this would execute an Athena query
        # For now, we'll simulate the process
        logger.info(f"Executing query: {query}")
        logger.info(f"Output location: {output_location}")
        
        # Simulate query execution and return S3 path
        training_data_s3_uri = f"{output_location}training_data.{output_format}"
        
        return training_data_s3_uri
    
    def create_training_job_with_feature_store(self, pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create training job with Feature Store integration"""
        logger.info("Creating training job with Feature Store integration")
        
        training_config = pipeline_config.get('training_config', {})
        job_name = f"{self.project_name}-{self.environment}-training-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Prepare input data configuration
        input_data_config = []
        
        # Training data from Feature Store or S3
        train_channel_config = training_config.get('input_data_config', {}).get('train_channel', {})
        if train_channel_config.get('data_source') == 'feature_store':
            train_data_uri = self.prepare_training_data_from_feature_store(train_channel_config)
        else:
            train_data_uri = train_channel_config.get('s3_uri', f"s3://{self.data_lake_bucket}/gold/ml_features/train/")
        
        input_data_config.append({
            'ChannelName': 'train',
            'DataSource': {
                'S3DataSource': {
                    'S3DataType': 'S3Prefix',
                    'S3Uri': train_data_uri,
                    'S3DataDistributionType': 'FullyReplicated'
                }
            },
            'ContentType': train_channel_config.get('content_type', 'application/x-parquet'),
            'CompressionType': 'None',
            'InputMode': 'File'
        })
        
        # Validation data if specified
        validation_channel_config = training_config.get('input_data_config', {}).get('validation_channel', {})
        if validation_channel_config:
            input_data_config.append({
                'ChannelName': 'validation',
                'DataSource': {
                    'S3DataSource': {
                        'S3DataType': 'S3Prefix',
                        'S3Uri': validation_channel_config.get('s3_uri'),
                        'S3DataDistributionType': 'FullyReplicated'
                    }
                },
                'ContentType': validation_channel_config.get('content_type', 'application/x-parquet'),
                'InputMode': 'File'
            })
        
        # Output configuration
        output_config = training_config.get('output_config', {})
        output_path = output_config.get('s3_output_path', f"s3://{self.artifacts_bucket}/training-output/{job_name}/")
        
        # Resource configuration with spot instances support
        resource_config = {
            'InstanceType': training_config.get('instance_type', 'ml.m5.large'),
            'InstanceCount': training_config.get('instance_count', 1),
            'VolumeSizeInGB': training_config.get('volume_size', 20)
        }
        
        # Add spot instance configuration if enabled
        if training_config.get('enable_spot_instances', False):
            resource_config['InstanceType'] = training_config.get('instance_type', 'ml.m5.large')
            # Note: Spot instances configuration would be handled in the training job definition
        
        # Training job configuration
        training_job_config = {
            'TrainingJobName': job_name,
            'RoleArn': self.execution_role_arn,
            'AlgorithmSpecification': {
                'TrainingImage': training_config.get('training_image'),
                'TrainingInputMode': 'File'
            },
            'InputDataConfig': input_data_config,
            'OutputDataConfig': {
                'S3OutputPath': output_path
            },
            'ResourceConfig': resource_config,
            'StoppingCondition': {
                'MaxRuntimeInSeconds': training_config.get('max_runtime', 3600)
            },
            'HyperParameters': training_config.get('hyperparameters', {}),
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'Pipeline', 'Value': 'automated-training'},
                {'Key': 'FeatureStoreIntegrated', 'Value': 'true'}
            ]
        }
        
        # Add encryption configuration if specified
        if output_config.get('kms_key_id'):
            training_job_config['OutputDataConfig']['KmsKeyId'] = output_config['kms_key_id']
        
        # Add spot instance configuration
        if training_config.get('enable_spot_instances', False):
            training_job_config['EnableManagedSpotTraining'] = True
            training_job_config['CheckpointConfig'] = {
                'S3Uri': f"{output_path}checkpoints/"
            }
            if training_config.get('spot_instance_max_wait_time'):
                training_job_config['StoppingCondition']['MaxWaitTimeInSeconds'] = training_config['spot_instance_max_wait_time']
        
        try:
            response = sagemaker.create_training_job(**training_job_config)
            logger.info(f"Training job created: {job_name}")
            
            # Send notification
            self._send_notification(
                f"Training job started: {job_name}",
                "ML Pipeline - Training Started"
            )
            
            return {
                'job_name': job_name,
                'job_arn': response['TrainingJobArn'],
                'status': 'InProgress',
                'output_path': output_path,
                'feature_store_integrated': True
            }
            
        except Exception as e:
            logger.error(f"Failed to create training job: {str(e)}")
            raise
    
    def create_hyperparameter_tuning_job_with_feature_store(self, pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create hyperparameter tuning job with Feature Store integration"""
        logger.info("Creating hyperparameter tuning job with Feature Store integration")
        
        tuning_config = pipeline_config.get('tuning_config', {})
        training_config = pipeline_config.get('training_config', {})
        
        job_name = f"{self.project_name}-{self.environment}-tuning-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Prepare training data (similar to training job)
        train_channel_config = training_config.get('input_data_config', {}).get('train_channel', {})
        if train_channel_config.get('data_source') == 'feature_store':
            train_data_uri = self.prepare_training_data_from_feature_store(train_channel_config)
        else:
            train_data_uri = train_channel_config.get('s3_uri', f"s3://{self.data_lake_bucket}/gold/ml_features/train/")
        
        # Build parameter ranges
        parameter_ranges = {}
        
        if 'integer_parameters' in tuning_config.get('parameter_ranges', {}):
            parameter_ranges['IntegerParameterRanges'] = [
                {
                    'Name': param['name'],
                    'MinValue': param['min_value'],
                    'MaxValue': param['max_value'],
                    'ScalingType': param.get('scaling_type', 'Auto')
                }
                for param in tuning_config['parameter_ranges']['integer_parameters']
            ]
        
        if 'continuous_parameters' in tuning_config.get('parameter_ranges', {}):
            parameter_ranges['ContinuousParameterRanges'] = [
                {
                    'Name': param['name'],
                    'MinValue': param['min_value'],
                    'MaxValue': param['max_value'],
                    'ScalingType': param.get('scaling_type', 'Auto')
                }
                for param in tuning_config['parameter_ranges']['continuous_parameters']
            ]
        
        if 'categorical_parameters' in tuning_config.get('parameter_ranges', {}):
            parameter_ranges['CategoricalParameterRanges'] = [
                {
                    'Name': param['name'],
                    'Values': param['values']
                }
                for param in tuning_config['parameter_ranges']['categorical_parameters']
            ]
        
        # Hyperparameter tuning job configuration
        tuning_job_config = {
            'HyperParameterTuningJobName': job_name,
            'HyperParameterTuningJobConfig': {
                'Strategy': 'Bayesian',
                'HyperParameterTuningJobObjective': {
                    'Type': 'Maximize',
                    'MetricName': tuning_config.get('objective_metric', 'validation:accuracy')
                },
                'ResourceLimits': {
                    'MaxNumberOfTrainingJobs': tuning_config.get('max_jobs', 10),
                    'MaxParallelTrainingJobs': tuning_config.get('max_parallel_jobs', 2)
                },
                'ParameterRanges': parameter_ranges
            },
            'TrainingJobDefinition': {
                'AlgorithmSpecification': {
                    'TrainingImage': tuning_config.get('training_image'),
                    'TrainingInputMode': 'File'
                },
                'InputDataConfig': [
                    {
                        'ChannelName': 'train',
                        'DataSource': {
                            'S3DataSource': {
                                'S3DataType': 'S3Prefix',
                                'S3Uri': train_data_uri,
                                'S3DataDistributionType': 'FullyReplicated'
                            }
                        },
                        'ContentType': 'application/x-parquet',
                        'InputMode': 'File'
                    }
                ],
                'OutputDataConfig': {
                    'S3OutputPath': f"s3://{self.artifacts_bucket}/tuning-output/{job_name}/"
                },
                'ResourceConfig': {
                    'InstanceType': tuning_config.get('instance_type', 'ml.m5.large'),
                    'InstanceCount': 1,
                    'VolumeSizeInGB': 20
                },
                'RoleArn': self.execution_role_arn,
                'StoppingCondition': {
                    'MaxRuntimeInSeconds': 3600
                },
                'StaticHyperParameters': {
                    'target-column': training_config.get('hyperparameters', {}).get('target-column', 'target')
                }
            },
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'Pipeline', 'Value': 'hyperparameter-tuning'},
                {'Key': 'FeatureStoreIntegrated', 'Value': 'true'}
            ]
        }
        
        try:
            response = sagemaker.create_hyper_parameter_tuning_job(**tuning_job_config)
            logger.info(f"Hyperparameter tuning job created: {job_name}")
            
            # Send notification
            self._send_notification(
                f"Hyperparameter tuning job started: {job_name}",
                "ML Pipeline - Hyperparameter Tuning Started"
            )
            
            return {
                'job_name': job_name,
                'job_arn': response['HyperParameterTuningJobArn'],
                'status': 'InProgress',
                'feature_store_integrated': True
            }
            
        except Exception as e:
            logger.error(f"Failed to create hyperparameter tuning job: {str(e)}")
            raise
    
    def trigger_model_evaluation(self, training_job_name: str, pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger model evaluation after training completion"""
        logger.info(f"Triggering model evaluation for training job: {training_job_name}")
        
        evaluation_config = pipeline_config.get('evaluation_config', {})
        
        # Get training job details
        training_job_details = sagemaker.describe_training_job(TrainingJobName=training_job_name)
        model_artifacts_uri = training_job_details['ModelArtifacts']['S3ModelArtifacts']
        
        # Create processing job for evaluation
        processing_job_name = f"{training_job_name}-evaluation"
        
        processing_job_config = {
            'ProcessingJobName': processing_job_name,
            'ProcessingResources': {
                'ClusterConfig': {
                    'InstanceCount': 1,
                    'InstanceType': 'ml.m5.large',
                    'VolumeSizeInGB': 20
                }
            },
            'AppSpecification': {
                'ImageUri': '763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-inference:0.23-1-cpu-py3',
                'ContainerEntrypoint': ['python3', '/opt/ml/processing/code/evaluate.py'],
                'ContainerArguments': [
                    '--model-path', '/opt/ml/processing/input/model',
                    '--test-data', '/opt/ml/processing/input/test',
                    '--output-dir', '/opt/ml/processing/output',
                    '--cross-validate' if evaluation_config.get('cross_validate', False) else '',
                    '--cv-folds', str(evaluation_config.get('cv_folds', 5)),
                    '--generate-plots' if evaluation_config.get('generate_plots', False) else ''
                ]
            },
            'ProcessingInputs': [
                {
                    'InputName': 'model',
                    'S3Input': {
                        'S3Uri': model_artifacts_uri,
                        'LocalPath': '/opt/ml/processing/input/model',
                        'S3DataType': 'S3Prefix',
                        'S3InputMode': 'File'
                    }
                },
                {
                    'InputName': 'test',
                    'S3Input': {
                        'S3Uri': evaluation_config.get('test_data_uri'),
                        'LocalPath': '/opt/ml/processing/input/test',
                        'S3DataType': 'S3Prefix',
                        'S3InputMode': 'File'
                    }
                },
                {
                    'InputName': 'code',
                    'S3Input': {
                        'S3Uri': f"s3://{self.artifacts_bucket}/code/evaluate.py",
                        'LocalPath': '/opt/ml/processing/code',
                        'S3DataType': 'S3Prefix',
                        'S3InputMode': 'File'
                    }
                }
            ],
            'ProcessingOutputs': [
                {
                    'OutputName': 'evaluation',
                    'S3Output': {
                        'S3Uri': f"s3://{self.artifacts_bucket}/evaluation/{training_job_name}/",
                        'LocalPath': '/opt/ml/processing/output',
                        'S3UploadMode': 'EndOfJob'
                    }
                }
            ],
            'RoleArn': self.execution_role_arn,
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'Pipeline', 'Value': 'model-evaluation'}
            ]
        }
        
        try:
            response = sagemaker.create_processing_job(**processing_job_config)
            logger.info(f"Model evaluation processing job created: {processing_job_name}")
            
            return {
                'evaluation_job_name': processing_job_name,
                'evaluation_job_arn': response['ProcessingJobArn'],
                'model_artifacts_uri': model_artifacts_uri,
                'status': 'InProgress'
            }
            
        except Exception as e:
            logger.error(f"Failed to create evaluation processing job: {str(e)}")
            raise
    
    def trigger_ab_testing(self, models_config: List[Dict[str, Any]], pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger A/B testing between models"""
        logger.info("Triggering A/B testing between models")
        
        ab_test_config = pipeline_config.get('ab_testing_config', {})
        ab_test_id = f"{self.project_name}-{self.environment}-abtest-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Create A/B test processing job
        processing_job_name = f"{ab_test_id}-processing"
        
        # Prepare models configuration file
        models_config_s3_uri = f"s3://{self.artifacts_bucket}/ab-testing/{ab_test_id}/models_config.json"
        s3.put_object(
            Bucket=self.artifacts_bucket,
            Key=f"ab-testing/{ab_test_id}/models_config.json",
            Body=json.dumps(models_config, indent=2),
            ContentType='application/json'
        )
        
        processing_job_config = {
            'ProcessingJobName': processing_job_name,
            'ProcessingResources': {
                'ClusterConfig': {
                    'InstanceCount': 1,
                    'InstanceType': 'ml.m5.large',
                    'VolumeSizeInGB': 20
                }
            },
            'AppSpecification': {
                'ImageUri': '763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-inference:0.23-1-cpu-py3',
                'ContainerEntrypoint': ['python3', '/opt/ml/processing/code/ab_testing.py'],
                'ContainerArguments': [
                    '--models', '/opt/ml/processing/input/config/models_config.json',
                    '--output-dir', '/opt/ml/processing/output',
                    '--alpha', str(ab_test_config.get('statistical_tests', {}).get('alpha', 0.05))
                ]
            },
            'ProcessingInputs': [
                {
                    'InputName': 'config',
                    'S3Input': {
                        'S3Uri': f"s3://{self.artifacts_bucket}/ab-testing/{ab_test_id}/",
                        'LocalPath': '/opt/ml/processing/input/config',
                        'S3DataType': 'S3Prefix',
                        'S3InputMode': 'File'
                    }
                },
                {
                    'InputName': 'code',
                    'S3Input': {
                        'S3Uri': f"s3://{self.artifacts_bucket}/code/ab_testing.py",
                        'LocalPath': '/opt/ml/processing/code',
                        'S3DataType': 'S3Prefix',
                        'S3InputMode': 'File'
                    }
                }
            ],
            'ProcessingOutputs': [
                {
                    'OutputName': 'results',
                    'S3Output': {
                        'S3Uri': f"s3://{self.artifacts_bucket}/ab-testing/{ab_test_id}/results/",
                        'LocalPath': '/opt/ml/processing/output',
                        'S3UploadMode': 'EndOfJob'
                    }
                }
            ],
            'RoleArn': self.execution_role_arn,
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'Pipeline', 'Value': 'ab-testing'}
            ]
        }
        
        try:
            response = sagemaker.create_processing_job(**processing_job_config)
            logger.info(f"A/B testing processing job created: {processing_job_name}")
            
            return {
                'ab_test_id': ab_test_id,
                'processing_job_name': processing_job_name,
                'processing_job_arn': response['ProcessingJobArn'],
                'models_config_s3_uri': models_config_s3_uri,
                'status': 'InProgress'
            }
            
        except Exception as e:
            logger.error(f"Failed to create A/B testing processing job: {str(e)}")
            raise
    
    def _send_notification(self, message: str, subject: str = "ML Pipeline Notification"):
        """Send notification via SNS"""
        if self.sns_topic_arn:
            try:
                sns.publish(
                    TopicArn=self.sns_topic_arn,
                    Message=message,
                    Subject=subject
                )
                logger.info("Notification sent successfully")
            except Exception as e:
                logger.error(f"Failed to send notification: {str(e)}")
    
    def orchestrate_complete_pipeline(self, pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrate the complete training pipeline with Feature Store integration"""
        logger.info("Starting complete training pipeline orchestration")
        
        pipeline_id = f"{self.project_name}-{self.environment}-pipeline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        results = {
            'pipeline_id': pipeline_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'feature_store_integrated': True,
            'steps': {}
        }
        
        try:
            # Step 1: Training or Hyperparameter Tuning
            if pipeline_config.get('tuning_config', {}).get('enable_hyperparameter_tuning', False):
                tuning_result = self.create_hyperparameter_tuning_job_with_feature_store(pipeline_config)
                results['steps']['hyperparameter_tuning'] = tuning_result
            else:
                training_result = self.create_training_job_with_feature_store(pipeline_config)
                results['steps']['training'] = training_result
            
            # Save pipeline configuration
            config_key = f"pipelines/{pipeline_id}/config.json"
            s3.put_object(
                Bucket=self.artifacts_bucket,
                Key=config_key,
                Body=json.dumps(results, indent=2, default=str),
                ContentType='application/json'
            )
            
            results['config_s3_uri'] = f"s3://{self.artifacts_bucket}/{config_key}"
            results['status'] = 'Started'
            
            logger.info(f"Complete training pipeline orchestration started: {pipeline_id}")
            return results
            
        except Exception as e:
            logger.error(f"Pipeline orchestration failed: {str(e)}")
            results['status'] = 'Failed'
            results['error'] = str(e)
            
            # Send error notification
            self._send_notification(
                f"Training Pipeline failed: {str(e)}",
                "ML Pipeline - Error"
            )
            
            raise

def lambda_handler(event, context):
    """Lambda handler function"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        orchestrator = TrainingPipelineOrchestrator()
        
        # Determine the action based on event
        action = event.get('action', 'orchestrate_complete_pipeline')
        
        if action == 'orchestrate_complete_pipeline':
            # Full pipeline orchestration with Feature Store
            pipeline_config = event.get('pipeline_config', {})
            result = orchestrator.orchestrate_complete_pipeline(pipeline_config)
            
        elif action == 'create_training_job':
            # Create training job with Feature Store integration
            pipeline_config = event.get('pipeline_config', {})
            result = orchestrator.create_training_job_with_feature_store(pipeline_config)
            
        elif action == 'create_tuning_job':
            # Create hyperparameter tuning job
            pipeline_config = event.get('pipeline_config', {})
            result = orchestrator.create_hyperparameter_tuning_job_with_feature_store(pipeline_config)
            
        elif action == 'trigger_evaluation':
            # Trigger model evaluation
            training_job_name = event.get('training_job_name')
            pipeline_config = event.get('pipeline_config', {})
            result = orchestrator.trigger_model_evaluation(training_job_name, pipeline_config)
            
        elif action == 'trigger_ab_testing':
            # Trigger A/B testing
            models_config = event.get('models_config', [])
            pipeline_config = event.get('pipeline_config', {})
            result = orchestrator.trigger_ab_testing(models_config, pipeline_config)
            
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
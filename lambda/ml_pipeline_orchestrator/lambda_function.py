#!/usr/bin/env python3
"""
ML Pipeline Orchestrator Lambda Function
Orchestrates automated model training, evaluation, and A/B testing
"""

import json
import logging
import os
import boto3
from datetime import datetime
from typing import Dict, Any, List

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
sagemaker = boto3.client('sagemaker')
s3 = boto3.client('s3')
stepfunctions = boto3.client('stepfunctions')
sns = boto3.client('sns')

class MLPipelineOrchestrator:
    """Orchestrates the ML pipeline including training, evaluation, and A/B testing"""
    
    def __init__(self):
        self.project_name = os.environ.get('PROJECT_NAME', 'snowflake-aws-pipeline')
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        self.artifacts_bucket = os.environ.get('SAGEMAKER_ARTIFACTS_BUCKET')
        self.data_lake_bucket = os.environ.get('DATA_LAKE_BUCKET')
        self.sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        self.execution_role_arn = os.environ.get('SAGEMAKER_EXECUTION_ROLE_ARN')
        
    def trigger_training_job(self, training_config: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a SageMaker training job"""
        logger.info("Triggering SageMaker training job")
        
        job_name = f"{self.project_name}-{self.environment}-training-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        training_job_config = {
            'TrainingJobName': job_name,
            'RoleArn': self.execution_role_arn,
            'AlgorithmSpecification': {
                'TrainingImage': training_config.get('training_image', 
                    '763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-inference:0.23-1-cpu-py3'),
                'TrainingInputMode': 'File'
            },
            'InputDataConfig': [
                {
                    'ChannelName': 'train',
                    'DataSource': {
                        'S3DataSource': {
                            'S3DataType': 'S3Prefix',
                            'S3Uri': f"s3://{self.data_lake_bucket}/gold/ml_features/",
                            'S3DataDistributionType': 'FullyReplicated'
                        }
                    },
                    'ContentType': 'application/x-parquet'
                }
            ],
            'OutputDataConfig': {
                'S3OutputPath': f"s3://{self.artifacts_bucket}/training-output/{job_name}/"
            },
            'ResourceConfig': {
                'InstanceType': training_config.get('instance_type', 'ml.m5.large'),
                'InstanceCount': training_config.get('instance_count', 1),
                'VolumeSizeInGB': training_config.get('volume_size', 20)
            },
            'StoppingCondition': {
                'MaxRuntimeInSeconds': training_config.get('max_runtime', 3600)
            },
            'HyperParameters': training_config.get('hyperparameters', {
                'model-type': 'random_forest',
                'n-estimators': '100',
                'target-column': 'target'
            }),
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'Pipeline', 'Value': 'automated-training'}
            ]
        }
        
        try:
            response = sagemaker.create_training_job(**training_job_config)
            logger.info(f"Training job created: {job_name}")
            return {
                'job_name': job_name,
                'job_arn': response['TrainingJobArn'],
                'status': 'InProgress'
            }
        except Exception as e:
            logger.error(f"Failed to create training job: {str(e)}")
            raise
    
    def trigger_hyperparameter_tuning(self, tuning_config: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a SageMaker hyperparameter tuning job"""
        logger.info("Triggering SageMaker hyperparameter tuning job")
        
        job_name = f"{self.project_name}-{self.environment}-tuning-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
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
                'ParameterRanges': {
                    'IntegerParameterRanges': [
                        {
                            'Name': 'n-estimators',
                            'MinValue': '50',
                            'MaxValue': '200',
                            'ScalingType': 'Linear'
                        },
                        {
                            'Name': 'max-depth',
                            'MinValue': '3',
                            'MaxValue': '20',
                            'ScalingType': 'Linear'
                        }
                    ],
                    'ContinuousParameterRanges': [
                        {
                            'Name': 'learning-rate',
                            'MinValue': '0.001',
                            'MaxValue': '0.3',
                            'ScalingType': 'Logarithmic'
                        }
                    ],
                    'CategoricalParameterRanges': [
                        {
                            'Name': 'model-type',
                            'Values': ['random_forest', 'gradient_boosting', 'logistic_regression']
                        }
                    ]
                }
            },
            'TrainingJobDefinition': {
                'AlgorithmSpecification': {
                    'TrainingImage': tuning_config.get('training_image',
                        '763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-inference:0.23-1-cpu-py3'),
                    'TrainingInputMode': 'File'
                },
                'InputDataConfig': [
                    {
                        'ChannelName': 'train',
                        'DataSource': {
                            'S3DataSource': {
                                'S3DataType': 'S3Prefix',
                                'S3Uri': f"s3://{self.data_lake_bucket}/gold/ml_features/",
                                'S3DataDistributionType': 'FullyReplicated'
                            }
                        },
                        'ContentType': 'application/x-parquet'
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
                    'target-column': 'target'
                }
            },
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'Pipeline', 'Value': 'hyperparameter-tuning'}
            ]
        }
        
        try:
            response = sagemaker.create_hyper_parameter_tuning_job(**tuning_job_config)
            logger.info(f"Hyperparameter tuning job created: {job_name}")
            return {
                'job_name': job_name,
                'job_arn': response['HyperParameterTuningJobArn'],
                'status': 'InProgress'
            }
        except Exception as e:
            logger.error(f"Failed to create hyperparameter tuning job: {str(e)}")
            raise
    
    def check_job_status(self, job_name: str, job_type: str = 'training') -> Dict[str, Any]:
        """Check the status of a SageMaker job"""
        try:
            if job_type == 'training':
                response = sagemaker.describe_training_job(TrainingJobName=job_name)
                status = response['TrainingJobStatus']
                
                return {
                    'job_name': job_name,
                    'status': status,
                    'model_artifacts': response.get('ModelArtifacts', {}).get('S3ModelArtifacts'),
                    'failure_reason': response.get('FailureReason'),
                    'training_start_time': response.get('TrainingStartTime'),
                    'training_end_time': response.get('TrainingEndTime')
                }
            
            elif job_type == 'tuning':
                response = sagemaker.describe_hyper_parameter_tuning_job(
                    HyperParameterTuningJobName=job_name
                )
                status = response['HyperParameterTuningJobStatus']
                
                return {
                    'job_name': job_name,
                    'status': status,
                    'best_training_job': response.get('BestTrainingJob'),
                    'failure_reason': response.get('FailureReason'),
                    'tuning_start_time': response.get('HyperParameterTuningStartTime'),
                    'tuning_end_time': response.get('HyperParameterTuningEndTime')
                }
                
        except Exception as e:
            logger.error(f"Failed to check job status: {str(e)}")
            return {'job_name': job_name, 'status': 'Unknown', 'error': str(e)}
    
    def trigger_model_evaluation(self, model_artifacts_s3_uri: str, test_data_s3_uri: str) -> Dict[str, Any]:
        """Trigger model evaluation using the evaluation script"""
        logger.info("Triggering model evaluation")
        
        # This would typically trigger a processing job or Lambda function
        # For now, we'll create a placeholder that would be implemented
        evaluation_job_name = f"{self.project_name}-{self.environment}-evaluation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # In a real implementation, this would trigger a SageMaker Processing Job
        # or another Lambda function that runs the evaluation script
        
        return {
            'evaluation_job_name': evaluation_job_name,
            'model_artifacts_uri': model_artifacts_s3_uri,
            'test_data_uri': test_data_s3_uri,
            'status': 'Triggered'
        }
    
    def trigger_ab_testing(self, models_config: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Trigger A/B testing between models"""
        logger.info("Triggering A/B testing")
        
        ab_test_id = f"{self.project_name}-{self.environment}-abtest-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Create configuration for A/B testing
        ab_test_config = {
            'ab_test_id': ab_test_id,
            'models': models_config,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save configuration to S3
        config_key = f"ab-testing/{ab_test_id}/config.json"
        s3.put_object(
            Bucket=self.artifacts_bucket,
            Key=config_key,
            Body=json.dumps(ab_test_config, indent=2),
            ContentType='application/json'
        )
        
        return {
            'ab_test_id': ab_test_id,
            'config_s3_uri': f"s3://{self.artifacts_bucket}/{config_key}",
            'status': 'Configured'
        }
    
    def send_notification(self, message: str, subject: str = "ML Pipeline Notification"):
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
    
    def orchestrate_pipeline(self, pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrate the complete ML pipeline"""
        logger.info("Starting ML pipeline orchestration")
        
        pipeline_id = f"{self.project_name}-{self.environment}-pipeline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        results = {
            'pipeline_id': pipeline_id,
            'timestamp': datetime.now().isoformat(),
            'steps': {}
        }
        
        try:
            # Step 1: Training or Hyperparameter Tuning
            if pipeline_config.get('enable_hyperparameter_tuning', False):
                tuning_result = self.trigger_hyperparameter_tuning(
                    pipeline_config.get('tuning_config', {})
                )
                results['steps']['hyperparameter_tuning'] = tuning_result
                
                # Send notification
                self.send_notification(
                    f"Hyperparameter tuning job started: {tuning_result['job_name']}",
                    "ML Pipeline - Hyperparameter Tuning Started"
                )
            else:
                training_result = self.trigger_training_job(
                    pipeline_config.get('training_config', {})
                )
                results['steps']['training'] = training_result
                
                # Send notification
                self.send_notification(
                    f"Training job started: {training_result['job_name']}",
                    "ML Pipeline - Training Started"
                )
            
            # Step 2: Schedule evaluation (would be triggered after training completes)
            if pipeline_config.get('enable_evaluation', True):
                evaluation_config = {
                    'test_data_uri': pipeline_config.get('test_data_uri', 
                        f"s3://{self.data_lake_bucket}/gold/ml_features/test/"),
                    'scheduled': True
                }
                results['steps']['evaluation'] = evaluation_config
            
            # Step 3: Schedule A/B testing (would be triggered after evaluation)
            if pipeline_config.get('enable_ab_testing', False):
                ab_test_config = pipeline_config.get('ab_test_models', [])
                if ab_test_config:
                    ab_test_result = self.trigger_ab_testing(ab_test_config)
                    results['steps']['ab_testing'] = ab_test_result
            
            # Save pipeline configuration
            config_key = f"pipelines/{pipeline_id}/config.json"
            s3.put_object(
                Bucket=self.artifacts_bucket,
                Key=config_key,
                Body=json.dumps(results, indent=2),
                ContentType='application/json'
            )
            
            results['config_s3_uri'] = f"s3://{self.artifacts_bucket}/{config_key}"
            results['status'] = 'Started'
            
            logger.info(f"ML pipeline orchestration completed: {pipeline_id}")
            return results
            
        except Exception as e:
            logger.error(f"Pipeline orchestration failed: {str(e)}")
            results['status'] = 'Failed'
            results['error'] = str(e)
            
            # Send error notification
            self.send_notification(
                f"ML Pipeline failed: {str(e)}",
                "ML Pipeline - Error"
            )
            
            raise

def lambda_handler(event, context):
    """Lambda handler function"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        orchestrator = MLPipelineOrchestrator()
        
        # Determine the action based on event
        action = event.get('action', 'orchestrate_pipeline')
        
        if action == 'orchestrate_pipeline':
            # Full pipeline orchestration
            pipeline_config = event.get('pipeline_config', {})
            result = orchestrator.orchestrate_pipeline(pipeline_config)
            
        elif action == 'check_job_status':
            # Check job status
            job_name = event.get('job_name')
            job_type = event.get('job_type', 'training')
            result = orchestrator.check_job_status(job_name, job_type)
            
        elif action == 'trigger_training':
            # Trigger training job only
            training_config = event.get('training_config', {})
            result = orchestrator.trigger_training_job(training_config)
            
        elif action == 'trigger_tuning':
            # Trigger hyperparameter tuning only
            tuning_config = event.get('tuning_config', {})
            result = orchestrator.trigger_hyperparameter_tuning(tuning_config)
            
        elif action == 'trigger_evaluation':
            # Trigger model evaluation
            model_artifacts_uri = event.get('model_artifacts_uri')
            test_data_uri = event.get('test_data_uri')
            result = orchestrator.trigger_model_evaluation(model_artifacts_uri, test_data_uri)
            
        elif action == 'trigger_ab_testing':
            # Trigger A/B testing
            models_config = event.get('models_config', [])
            result = orchestrator.trigger_ab_testing(models_config)
            
        else:
            raise ValueError(f"Unknown action: {action}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }
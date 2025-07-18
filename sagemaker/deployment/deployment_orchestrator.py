#!/usr/bin/env python3
"""
SageMaker Model Deployment and Inference Infrastructure
Handles real-time endpoints, batch transform jobs, and auto-scaling
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
application_autoscaling = boto3.client('application-autoscaling')
cloudwatch = boto3.client('cloudwatch')
s3 = boto3.client('s3')
sns = boto3.client('sns')

class ModelDeploymentOrchestrator:
    """Orchestrates model deployment and inference infrastructure"""
    
    def __init__(self):
        self.project_name = os.environ.get('PROJECT_NAME', 'snowflake-aws-pipeline')
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        self.artifacts_bucket = os.environ.get('SAGEMAKER_ARTIFACTS_BUCKET')
        self.execution_role_arn = os.environ.get('SAGEMAKER_EXECUTION_ROLE_ARN')
        self.sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        
    def create_model(self, model_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create SageMaker model from training artifacts"""
        logger.info("Creating SageMaker model")
        
        model_name = f"{self.project_name}-{self.environment}-model-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Model configuration
        create_model_config = {
            'ModelName': model_name,
            'PrimaryContainer': {
                'Image': model_config.get('inference_image', 
                    '763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-inference:0.23-1-cpu-py3'),
                'ModelDataUrl': model_config['model_artifacts_s3_uri'],
                'Environment': model_config.get('environment_variables', {})
            },
            'ExecutionRoleArn': self.execution_role_arn,
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'ModelType', 'Value': model_config.get('model_type', 'sklearn')},
                {'Key': 'CreatedBy', 'Value': 'deployment-orchestrator'}
            ]
        }
        
        # Add VPC configuration if specified
        if model_config.get('vpc_config'):
            create_model_config['VpcConfig'] = model_config['vpc_config']
        
        try:
            response = sagemaker.create_model(**create_model_config)
            logger.info(f"Model created: {model_name}")
            
            return {
                'model_name': model_name,
                'model_arn': response['ModelArn'],
                'status': 'Created'
            }
            
        except Exception as e:
            logger.error(f"Failed to create model: {str(e)}")
            raise
    
    def create_endpoint_config(self, endpoint_config: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """Create endpoint configuration"""
        logger.info("Creating endpoint configuration")
        
        config_name = f"{self.project_name}-{self.environment}-endpoint-config-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Production variants configuration
        production_variants = []
        
        if isinstance(endpoint_config.get('variants'), list):
            # Multi-model endpoint
            for i, variant in enumerate(endpoint_config['variants']):
                production_variants.append({
                    'VariantName': variant.get('variant_name', f'variant-{i}'),
                    'ModelName': variant.get('model_name', model_name),
                    'InitialInstanceCount': variant.get('initial_instance_count', 1),
                    'InstanceType': variant.get('instance_type', 'ml.t2.medium'),
                    'InitialVariantWeight': variant.get('initial_variant_weight', 1.0)
                })
        else:
            # Single model endpoint
            production_variants.append({
                'VariantName': 'primary',
                'ModelName': model_name,
                'InitialInstanceCount': endpoint_config.get('initial_instance_count', 1),
                'InstanceType': endpoint_config.get('instance_type', 'ml.t2.medium'),
                'InitialVariantWeight': 1.0
            })
        
        create_config = {
            'EndpointConfigName': config_name,
            'ProductionVariants': production_variants,
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'CreatedBy', 'Value': 'deployment-orchestrator'}
            ]
        }
        
        # Add data capture configuration if specified
        if endpoint_config.get('data_capture_config'):
            create_config['DataCaptureConfig'] = {
                'EnableCapture': endpoint_config['data_capture_config'].get('enable_capture', True),
                'InitialSamplingPercentage': endpoint_config['data_capture_config'].get('sampling_percentage', 100),
                'DestinationS3Uri': endpoint_config['data_capture_config'].get('s3_destination', 
                    f"s3://{self.artifacts_bucket}/data-capture/{config_name}/"),
                'CaptureOptions': [
                    {'CaptureMode': 'Input'},
                    {'CaptureMode': 'Output'}
                ]
            }
        
        try:
            response = sagemaker.create_endpoint_config(**create_config)
            logger.info(f"Endpoint configuration created: {config_name}")
            
            return {
                'endpoint_config_name': config_name,
                'endpoint_config_arn': response['EndpointConfigArn'],
                'status': 'Created'
            }
            
        except Exception as e:
            logger.error(f"Failed to create endpoint configuration: {str(e)}")
            raise
    
    def create_endpoint(self, endpoint_name: str, endpoint_config_name: str) -> Dict[str, Any]:
        """Create SageMaker endpoint"""
        logger.info(f"Creating endpoint: {endpoint_name}")
        
        create_endpoint_config = {
            'EndpointName': endpoint_name,
            'EndpointConfigName': endpoint_config_name,
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'CreatedBy', 'Value': 'deployment-orchestrator'}
            ]
        }
        
        try:
            response = sagemaker.create_endpoint(**create_endpoint_config)
            logger.info(f"Endpoint creation started: {endpoint_name}")
            
            # Send notification
            self._send_notification(
                f"Endpoint deployment started: {endpoint_name}",
                "ML Pipeline - Endpoint Deployment Started"
            )
            
            return {
                'endpoint_name': endpoint_name,
                'endpoint_arn': response['EndpointArn'],
                'status': 'Creating'
            }
            
        except Exception as e:
            logger.error(f"Failed to create endpoint: {str(e)}")
            raise
    
    def setup_auto_scaling(self, endpoint_name: str, auto_scaling_config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup auto-scaling for SageMaker endpoint"""
        logger.info(f"Setting up auto-scaling for endpoint: {endpoint_name}")
        
        variant_name = auto_scaling_config.get('variant_name', 'primary')
        resource_id = f"endpoint/{endpoint_name}/variant/{variant_name}"
        
        # Register scalable target
        register_target_config = {
            'ServiceNamespace': 'sagemaker',
            'ResourceId': resource_id,
            'ScalableDimension': 'sagemaker:variant:DesiredInstanceCount',
            'MinCapacity': auto_scaling_config.get('min_capacity', 1),
            'MaxCapacity': auto_scaling_config.get('max_capacity', 5),
            'RoleArn': self.execution_role_arn
        }
        
        try:
            application_autoscaling.register_scalable_target(**register_target_config)
            logger.info(f"Scalable target registered for {resource_id}")
            
            # Create scaling policy
            scaling_policy_config = {
                'PolicyName': f"{endpoint_name}-scaling-policy",
                'ServiceNamespace': 'sagemaker',
                'ResourceId': resource_id,
                'ScalableDimension': 'sagemaker:variant:DesiredInstanceCount',
                'PolicyType': 'TargetTrackingScaling',
                'TargetTrackingScalingPolicyConfiguration': {
                    'TargetValue': auto_scaling_config.get('target_invocations_per_instance', 100.0),
                    'PredefinedMetricSpecification': {
                        'PredefinedMetricType': 'SageMakerVariantInvocationsPerInstance'
                    },
                    'ScaleOutCooldown': auto_scaling_config.get('scale_out_cooldown', 300),
                    'ScaleInCooldown': auto_scaling_config.get('scale_in_cooldown', 300)
                }
            }
            
            policy_response = application_autoscaling.put_scaling_policy(**scaling_policy_config)
            logger.info(f"Scaling policy created: {policy_response['PolicyARN']}")
            
            return {
                'endpoint_name': endpoint_name,
                'resource_id': resource_id,
                'scaling_policy_arn': policy_response['PolicyARN'],
                'min_capacity': auto_scaling_config.get('min_capacity', 1),
                'max_capacity': auto_scaling_config.get('max_capacity', 5),
                'target_metric': auto_scaling_config.get('target_invocations_per_instance', 100.0),
                'status': 'Configured'
            }
            
        except Exception as e:
            logger.error(f"Failed to setup auto-scaling: {str(e)}")
            raise
    
    def create_batch_transform_job(self, transform_config: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """Create batch transform job for bulk predictions"""
        logger.info("Creating batch transform job")
        
        job_name = f"{self.project_name}-{self.environment}-transform-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        transform_job_config = {
            'TransformJobName': job_name,
            'ModelName': model_name,
            'TransformInput': {
                'DataSource': {
                    'S3DataSource': {
                        'S3DataType': 'S3Prefix',
                        'S3Uri': transform_config['input_s3_uri']
                    }
                },
                'ContentType': transform_config.get('content_type', 'application/x-parquet'),
                'CompressionType': transform_config.get('compression_type', 'None'),
                'SplitType': transform_config.get('split_type', 'Line')
            },
            'TransformOutput': {
                'S3OutputPath': transform_config.get('output_s3_uri', 
                    f"s3://{self.artifacts_bucket}/batch-transform/{job_name}/"),
                'Accept': transform_config.get('accept', 'application/json'),
                'AssembleWith': transform_config.get('assemble_with', 'Line')
            },
            'TransformResources': {
                'InstanceType': transform_config.get('instance_type', 'ml.m5.large'),
                'InstanceCount': transform_config.get('instance_count', 1)
            },
            'Tags': [
                {'Key': 'Project', 'Value': self.project_name},
                {'Key': 'Environment', 'Value': self.environment},
                {'Key': 'JobType', 'Value': 'batch-transform'}
            ]
        }
        
        # Add optional configurations
        if transform_config.get('max_concurrent_transforms'):
            transform_job_config['MaxConcurrentTransforms'] = transform_config['max_concurrent_transforms']
        
        if transform_config.get('max_payload_in_mb'):
            transform_job_config['MaxPayloadInMB'] = transform_config['max_payload_in_mb']
        
        if transform_config.get('batch_strategy'):
            transform_job_config['BatchStrategy'] = transform_config['batch_strategy']
        
        try:
            response = sagemaker.create_transform_job(**transform_job_config)
            logger.info(f"Batch transform job created: {job_name}")
            
            # Send notification
            self._send_notification(
                f"Batch transform job started: {job_name}",
                "ML Pipeline - Batch Transform Started"
            )
            
            return {
                'transform_job_name': job_name,
                'transform_job_arn': response['TransformJobArn'],
                'input_s3_uri': transform_config['input_s3_uri'],
                'output_s3_uri': transform_job_config['TransformOutput']['S3OutputPath'],
                'status': 'InProgress'
            }
            
        except Exception as e:
            logger.error(f"Failed to create batch transform job: {str(e)}")
            raise
    
    def setup_endpoint_monitoring(self, endpoint_name: str, monitoring_config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup CloudWatch monitoring and alarms for endpoint"""
        logger.info(f"Setting up monitoring for endpoint: {endpoint_name}")
        
        alarms_created = []
        
        # Model latency alarm
        if monitoring_config.get('enable_latency_alarm', True):
            latency_alarm_name = f"{endpoint_name}-high-latency"
            
            cloudwatch.put_metric_alarm(
                AlarmName=latency_alarm_name,
                ComparisonOperator='GreaterThanThreshold',
                EvaluationPeriods=2,
                MetricName='ModelLatency',
                Namespace='AWS/SageMaker',
                Period=300,
                Statistic='Average',
                Threshold=monitoring_config.get('latency_threshold_ms', 5000.0),
                ActionsEnabled=True,
                AlarmActions=[self.sns_topic_arn] if self.sns_topic_arn else [],
                AlarmDescription=f'High latency alarm for endpoint {endpoint_name}',
                Dimensions=[
                    {
                        'Name': 'EndpointName',
                        'Value': endpoint_name
                    },
                    {
                        'Name': 'VariantName',
                        'Value': monitoring_config.get('variant_name', 'primary')
                    }
                ]
            )
            alarms_created.append(latency_alarm_name)
        
        # Error rate alarm
        if monitoring_config.get('enable_error_alarm', True):
            error_alarm_name = f"{endpoint_name}-high-errors"
            
            cloudwatch.put_metric_alarm(
                AlarmName=error_alarm_name,
                ComparisonOperator='GreaterThanThreshold',
                EvaluationPeriods=2,
                MetricName='Invocation4XXErrors',
                Namespace='AWS/SageMaker',
                Period=300,
                Statistic='Sum',
                Threshold=monitoring_config.get('error_threshold', 10.0),
                ActionsEnabled=True,
                AlarmActions=[self.sns_topic_arn] if self.sns_topic_arn else [],
                AlarmDescription=f'High error rate alarm for endpoint {endpoint_name}',
                Dimensions=[
                    {
                        'Name': 'EndpointName',
                        'Value': endpoint_name
                    },
                    {
                        'Name': 'VariantName',
                        'Value': monitoring_config.get('variant_name', 'primary')
                    }
                ]
            )
            alarms_created.append(error_alarm_name)
        
        # Invocation rate alarm
        if monitoring_config.get('enable_invocation_alarm', True):
            invocation_alarm_name = f"{endpoint_name}-low-invocations"
            
            cloudwatch.put_metric_alarm(
                AlarmName=invocation_alarm_name,
                ComparisonOperator='LessThanThreshold',
                EvaluationPeriods=3,
                MetricName='Invocations',
                Namespace='AWS/SageMaker',
                Period=300,
                Statistic='Sum',
                Threshold=monitoring_config.get('min_invocations_threshold', 1.0),
                ActionsEnabled=True,
                AlarmActions=[self.sns_topic_arn] if self.sns_topic_arn else [],
                AlarmDescription=f'Low invocation rate alarm for endpoint {endpoint_name}',
                Dimensions=[
                    {
                        'Name': 'EndpointName',
                        'Value': endpoint_name
                    },
                    {
                        'Name': 'VariantName',
                        'Value': monitoring_config.get('variant_name', 'primary')
                    }
                ]
            )
            alarms_created.append(invocation_alarm_name)
        
        logger.info(f"Created {len(alarms_created)} CloudWatch alarms for endpoint {endpoint_name}")
        
        return {
            'endpoint_name': endpoint_name,
            'alarms_created': alarms_created,
            'monitoring_enabled': True
        }
    
    def get_endpoint_status(self, endpoint_name: str) -> Dict[str, Any]:
        """Get endpoint status and details"""
        try:
            response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
            
            return {
                'endpoint_name': endpoint_name,
                'endpoint_status': response['EndpointStatus'],
                'endpoint_config_name': response['EndpointConfigName'],
                'creation_time': response.get('CreationTime'),
                'last_modified_time': response.get('LastModifiedTime'),
                'production_variants': response.get('ProductionVariants', []),
                'failure_reason': response.get('FailureReason')
            }
            
        except Exception as e:
            logger.error(f"Failed to get endpoint status: {str(e)}")
            return {'endpoint_name': endpoint_name, 'status': 'Unknown', 'error': str(e)}
    
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
    
    def deploy_model_complete(self, deployment_config: Dict[str, Any]) -> Dict[str, Any]:
        """Complete model deployment with all configurations"""
        logger.info("Starting complete model deployment")
        
        deployment_id = f"{self.project_name}-{self.environment}-deployment-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        results = {
            'deployment_id': deployment_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'steps': {}
        }
        
        try:
            # Step 1: Create model
            model_result = self.create_model(deployment_config['model_config'])
            results['steps']['model_creation'] = model_result
            
            # Step 2: Create endpoint configuration
            endpoint_config_result = self.create_endpoint_config(
                deployment_config['endpoint_config'], 
                model_result['model_name']
            )
            results['steps']['endpoint_config_creation'] = endpoint_config_result
            
            # Step 3: Create endpoint
            endpoint_name = deployment_config.get('endpoint_name', 
                f"{self.project_name}-{self.environment}-endpoint")
            endpoint_result = self.create_endpoint(
                endpoint_name, 
                endpoint_config_result['endpoint_config_name']
            )
            results['steps']['endpoint_creation'] = endpoint_result
            
            # Step 4: Setup auto-scaling if configured
            if deployment_config.get('auto_scaling_config'):
                auto_scaling_result = self.setup_auto_scaling(
                    endpoint_name, 
                    deployment_config['auto_scaling_config']
                )
                results['steps']['auto_scaling_setup'] = auto_scaling_result
            
            # Step 5: Setup monitoring if configured
            if deployment_config.get('monitoring_config'):
                monitoring_result = self.setup_endpoint_monitoring(
                    endpoint_name, 
                    deployment_config['monitoring_config']
                )
                results['steps']['monitoring_setup'] = monitoring_result
            
            # Step 6: Create batch transform job if configured
            if deployment_config.get('batch_transform_config'):
                batch_transform_result = self.create_batch_transform_job(
                    deployment_config['batch_transform_config'],
                    model_result['model_name']
                )
                results['steps']['batch_transform_creation'] = batch_transform_result
            
            # Save deployment configuration
            config_key = f"deployments/{deployment_id}/config.json"
            s3.put_object(
                Bucket=self.artifacts_bucket,
                Key=config_key,
                Body=json.dumps(results, indent=2, default=str),
                ContentType='application/json'
            )
            
            results['config_s3_uri'] = f"s3://{self.artifacts_bucket}/{config_key}"
            results['status'] = 'Deployed'
            
            logger.info(f"Complete model deployment initiated: {deployment_id}")
            return results
            
        except Exception as e:
            logger.error(f"Model deployment failed: {str(e)}")
            results['status'] = 'Failed'
            results['error'] = str(e)
            
            # Send error notification
            self._send_notification(
                f"Model deployment failed: {str(e)}",
                "ML Pipeline - Deployment Error"
            )
            
            raise

def lambda_handler(event, context):
    """Lambda handler function"""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        orchestrator = ModelDeploymentOrchestrator()
        
        # Determine the action based on event
        action = event.get('action', 'deploy_model_complete')
        
        if action == 'deploy_model_complete':
            # Complete model deployment
            deployment_config = event.get('deployment_config', {})
            result = orchestrator.deploy_model_complete(deployment_config)
            
        elif action == 'create_model':
            # Create model only
            model_config = event.get('model_config', {})
            result = orchestrator.create_model(model_config)
            
        elif action == 'create_endpoint':
            # Create endpoint
            endpoint_name = event.get('endpoint_name')
            endpoint_config_name = event.get('endpoint_config_name')
            result = orchestrator.create_endpoint(endpoint_name, endpoint_config_name)
            
        elif action == 'setup_auto_scaling':
            # Setup auto-scaling
            endpoint_name = event.get('endpoint_name')
            auto_scaling_config = event.get('auto_scaling_config', {})
            result = orchestrator.setup_auto_scaling(endpoint_name, auto_scaling_config)
            
        elif action == 'create_batch_transform':
            # Create batch transform job
            transform_config = event.get('transform_config', {})
            model_name = event.get('model_name')
            result = orchestrator.create_batch_transform_job(transform_config, model_name)
            
        elif action == 'get_endpoint_status':
            # Get endpoint status
            endpoint_name = event.get('endpoint_name')
            result = orchestrator.get_endpoint_status(endpoint_name)
            
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
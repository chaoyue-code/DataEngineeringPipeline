"""
Pipeline Orchestrator Lambda Function

This Lambda function coordinates multi-stage ETL workflows, manages job dependencies,
tracks pipeline state, and integrates with AWS Step Functions for complex workflows.
"""

import json
import os
import logging
import boto3
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
import uuid

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

class PipelineOrchestrator:
    """Orchestrates multi-stage ETL workflows with dependency management"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.stepfunctions = boto3.client('stepfunctions')
        self.lambda_client = boto3.client('lambda')
        self.glue_client = boto3.client('glue')
        self.sns_client = boto3.client('sns')
        
        # Configuration from environment variables
        self.pipeline_state_table = os.environ.get('PIPELINE_STATE_TABLE')
        self.job_dependency_table = os.environ.get('JOB_DEPENDENCY_TABLE')
        self.step_function_arn = os.environ.get('STEP_FUNCTION_ARN')
        self.notification_topic_arn = os.environ.get('NOTIFICATION_TOPIC_ARN')
        
        # Initialize DynamoDB tables
        self.state_table = self.dynamodb.Table(self.pipeline_state_table) if self.pipeline_state_table else None
        self.dependency_table = self.dynamodb.Table(self.job_dependency_table) if self.job_dependency_table else None
    
    def create_pipeline_execution(self, pipeline_config: Dict) -> str:
        """Create a new pipeline execution with unique ID"""
        execution_id = str(uuid.uuid4())
        pipeline_name = pipeline_config.get('pipeline_name', 'default-pipeline')
        
        execution_record = {
            'execution_id': execution_id,
            'pipeline_name': pipeline_name,
            'status': 'INITIATED',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'config': pipeline_config,
            'jobs': {},
            'current_stage': 'initialization'
        }
        
        if self.state_table:
            self.state_table.put_item(Item=execution_record)
        
        logger.info(f"Created pipeline execution: {execution_id} for pipeline: {pipeline_name}")
        return execution_id
    
    def get_pipeline_execution(self, execution_id: str) -> Optional[Dict]:
        """Retrieve pipeline execution state"""
        if not self.state_table:
            return None
            
        try:
            response = self.state_table.get_item(Key={'execution_id': execution_id})
            return response.get('Item')
        except ClientError as e:
            logger.error(f"Failed to get pipeline execution {execution_id}: {str(e)}")
            return None
    
    def update_pipeline_execution(self, execution_id: str, updates: Dict):
        """Update pipeline execution state"""
        if not self.state_table:
            return
            
        try:
            updates['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Build update expression
            update_expression = "SET "
            expression_attribute_values = {}
            expression_attribute_names = {}
            
            for key, value in updates.items():
                if key in ['status', 'current_stage', 'updated_at']:
                    update_expression += f"#{key} = :{key}, "
                    expression_attribute_names[f'#{key}'] = key
                    expression_attribute_values[f':{key}'] = value
                elif key == 'jobs':
                    # Handle nested job updates
                    for job_id, job_data in value.items():
                        update_expression += f"jobs.#{job_id} = :{job_id}, "
                        expression_attribute_names[f'#{job_id}'] = job_id
                        expression_attribute_values[f':{job_id}'] = job_data
            
            update_expression = update_expression.rstrip(', ')
            
            self.state_table.update_item(
                Key={'execution_id': execution_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
            
            logger.info(f"Updated pipeline execution {execution_id}")
            
        except ClientError as e:
            logger.error(f"Failed to update pipeline execution {execution_id}: {str(e)}")
    
    def get_job_dependencies(self, job_id: str) -> List[str]:
        """Get list of job dependencies"""
        if not self.dependency_table:
            return []
            
        try:
            response = self.dependency_table.get_item(Key={'job_id': job_id})
            item = response.get('Item', {})
            return item.get('dependencies', [])
        except ClientError as e:
            logger.error(f"Failed to get dependencies for job {job_id}: {str(e)}")
            return []
    
    def check_dependencies_satisfied(self, execution_id: str, job_id: str) -> bool:
        """Check if all dependencies for a job are satisfied"""
        dependencies = self.get_job_dependencies(job_id)
        if not dependencies:
            return True
        
        execution = self.get_pipeline_execution(execution_id)
        if not execution:
            return False
        
        jobs = execution.get('jobs', {})
        
        for dep_job_id in dependencies:
            dep_job = jobs.get(dep_job_id, {})
            if dep_job.get('status') != 'COMPLETED':
                logger.info(f"Dependency {dep_job_id} not satisfied for job {job_id}")
                return False
        
        logger.info(f"All dependencies satisfied for job {job_id}")
        return True
    
    def execute_lambda_job(self, job_config: Dict) -> Dict:
        """Execute a Lambda function job"""
        function_name = job_config['function_name']
        payload = job_config.get('payload', {})
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            
            return {
                'status': 'COMPLETED' if response['StatusCode'] == 200 else 'FAILED',
                'result': result,
                'execution_time': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to execute Lambda job {function_name}: {str(e)}")
            return {
                'status': 'FAILED',
                'error': str(e),
                'execution_time': datetime.now(timezone.utc).isoformat()
            }
    
    def execute_glue_job(self, job_config: Dict) -> Dict:
        """Execute a Glue job"""
        job_name = job_config['job_name']
        arguments = job_config.get('arguments', {})
        
        try:
            response = self.glue_client.start_job_run(
                JobName=job_name,
                Arguments=arguments
            )
            
            job_run_id = response['JobRunId']
            
            return {
                'status': 'RUNNING',
                'job_run_id': job_run_id,
                'execution_time': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to execute Glue job {job_name}: {str(e)}")
            return {
                'status': 'FAILED',
                'error': str(e),
                'execution_time': datetime.now(timezone.utc).isoformat()
            }
    
    def check_glue_job_status(self, job_name: str, job_run_id: str) -> str:
        """Check the status of a running Glue job"""
        try:
            response = self.glue_client.get_job_run(
                JobName=job_name,
                RunId=job_run_id
            )
            
            job_run = response['JobRun']
            return job_run['JobRunState']
            
        except Exception as e:
            logger.error(f"Failed to check Glue job status {job_name}/{job_run_id}: {str(e)}")
            return 'FAILED'
    
    def execute_job(self, execution_id: str, job_config: Dict) -> Dict:
        """Execute a single job based on its type"""
        job_id = job_config['job_id']
        job_type = job_config['job_type']
        
        logger.info(f"Executing job {job_id} of type {job_type}")
        
        # Update job status to RUNNING
        self.update_pipeline_execution(execution_id, {
            'jobs': {
                job_id: {
                    'status': 'RUNNING',
                    'started_at': datetime.now(timezone.utc).isoformat(),
                    'job_type': job_type
                }
            }
        })
        
        # Execute based on job type
        if job_type == 'lambda':
            result = self.execute_lambda_job(job_config)
        elif job_type == 'glue':
            result = self.execute_glue_job(job_config)
        else:
            result = {
                'status': 'FAILED',
                'error': f"Unsupported job type: {job_type}",
                'execution_time': datetime.now(timezone.utc).isoformat()
            }
        
        # Update job status with result
        job_update = {
            'jobs': {
                job_id: {
                    **result,
                    'completed_at': datetime.now(timezone.utc).isoformat()
                }
            }
        }
        
        self.update_pipeline_execution(execution_id, job_update)
        
        return result
    
    def get_ready_jobs(self, execution_id: str, pipeline_config: Dict) -> List[Dict]:
        """Get list of jobs that are ready to execute (dependencies satisfied)"""
        ready_jobs = []
        jobs = pipeline_config.get('jobs', [])
        
        execution = self.get_pipeline_execution(execution_id)
        if not execution:
            return ready_jobs
        
        executed_jobs = execution.get('jobs', {})
        
        for job_config in jobs:
            job_id = job_config['job_id']
            
            # Skip if already executed or running
            if job_id in executed_jobs:
                job_status = executed_jobs[job_id].get('status')
                if job_status in ['COMPLETED', 'RUNNING', 'FAILED']:
                    continue
            
            # Check if dependencies are satisfied
            if self.check_dependencies_satisfied(execution_id, job_id):
                ready_jobs.append(job_config)
        
        return ready_jobs
    
    def execute_step_function_workflow(self, execution_id: str, workflow_config: Dict) -> Dict:
        """Execute complex workflow using AWS Step Functions"""
        if not self.step_function_arn:
            return {
                'status': 'FAILED',
                'error': 'Step Function ARN not configured'
            }
        
        try:
            # Prepare input for Step Function
            step_function_input = {
                'execution_id': execution_id,
                'workflow_config': workflow_config,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            response = self.stepfunctions.start_execution(
                stateMachineArn=self.step_function_arn,
                name=f"pipeline-{execution_id}-{int(datetime.now().timestamp())}",
                input=json.dumps(step_function_input)
            )
            
            return {
                'status': 'RUNNING',
                'execution_arn': response['executionArn'],
                'started_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to start Step Function workflow: {str(e)}")
            return {
                'status': 'FAILED',
                'error': str(e)
            }
    
    def send_notification(self, message: str, subject: str = "Pipeline Notification"):
        """Send notification via SNS"""
        if not self.notification_topic_arn:
            logger.warning("Notification topic ARN not configured")
            return
        
        try:
            self.sns_client.publish(
                TopicArn=self.notification_topic_arn,
                Message=message,
                Subject=subject
            )
            logger.info(f"Notification sent: {subject}")
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
    
    @xray_recorder.capture('orchestrate_pipeline')
    def orchestrate_pipeline(self, pipeline_config: Dict) -> Dict:
        """Main orchestration method"""
        # Create pipeline execution
        execution_id = self.create_pipeline_execution(pipeline_config)
        pipeline_name = pipeline_config.get('pipeline_name', 'default-pipeline')
        
        with xray_recorder.in_subsegment('pipeline_execution') as subsegment:
            subsegment.put_annotation("pipeline_name", pipeline_name)
            subsegment.put_annotation("execution_id", execution_id)
            
            try:
                # Update status to RUNNING
                self.update_pipeline_execution(execution_id, {
                    'status': 'RUNNING',
                    'current_stage': 'execution'
                })
                
                # Check if this is a Step Function workflow
                if pipeline_config.get('use_step_functions', False):
                    logger.info(f"Executing pipeline {pipeline_name} using Step Functions")
                    
                    workflow_result = self.execute_step_function_workflow(execution_id, pipeline_config)
                    
                    if workflow_result['status'] == 'RUNNING':
                        self.update_pipeline_execution(execution_id, {
                            'status': 'RUNNING',
                            'current_stage': 'step_function_execution',
                            'step_function_arn': workflow_result['execution_arn']
                        })
                        
                        return {
                            'execution_id': execution_id,
                            'status': 'RUNNING',
                            'message': 'Pipeline started with Step Functions',
                            'step_function_arn': workflow_result['execution_arn']
                        }
                    else:
                        raise Exception(f"Failed to start Step Function: {workflow_result.get('error')}")
                
                else:
                    # Execute jobs sequentially based on dependencies
                    logger.info(f"Executing pipeline {pipeline_name} with dependency management")
                    
                    max_iterations = 50  # Prevent infinite loops
                    iteration = 0
                    
                    while iteration < max_iterations:
                        ready_jobs = self.get_ready_jobs(execution_id, pipeline_config)
                        
                        if not ready_jobs:
                            # Check if all jobs are completed
                            execution = self.get_pipeline_execution(execution_id)
                            jobs = execution.get('jobs', {})
                            total_jobs = len(pipeline_config.get('jobs', []))
                            completed_jobs = len([j for j in jobs.values() if j.get('status') == 'COMPLETED'])
                            failed_jobs = len([j for j in jobs.values() if j.get('status') == 'FAILED'])
                            
                            if completed_jobs + failed_jobs >= total_jobs:
                                break
                            else:
                                logger.info("No ready jobs found, waiting for running jobs to complete")
                                break
                        
                        # Execute ready jobs
                        for job_config in ready_jobs:
                            with xray_recorder.in_subsegment(f"execute_job_{job_config['job_id']}") as job_subsegment:
                                job_subsegment.put_annotation("job_id", job_config['job_id'])
                                result = self.execute_job(execution_id, job_config)
                                job_subsegment.put_metadata('result', result)
                            
                            if result['status'] == 'FAILED':
                                logger.error(f"Job {job_config['job_id']} failed: {result.get('error')}")
                                
                                # Send failure notification
                                self.send_notification(
                                    f"Job {job_config['job_id']} failed in pipeline {pipeline_name}: {result.get('error')}",
                                    f"Pipeline Job Failure - {pipeline_name}"
                                )
                        
                        iteration += 1
                    
                    # Determine final pipeline status
                    execution = self.get_pipeline_execution(execution_id)
                    jobs = execution.get('jobs', {})
                    
                    failed_jobs = [j for j in jobs.values() if j.get('status') == 'FAILED']
                    completed_jobs = [j for j in jobs.values() if j.get('status') == 'COMPLETED']
                    
                    if failed_jobs:
                        final_status = 'FAILED'
                        self.send_notification(
                            f"Pipeline {pipeline_name} failed with {len(failed_jobs)} failed jobs",
                            f"Pipeline Failure - {pipeline_name}"
                        )
                    elif len(completed_jobs) == len(pipeline_config.get('jobs', [])):
                        final_status = 'COMPLETED'
                        self.send_notification(
                            f"Pipeline {pipeline_name} completed successfully",
                            f"Pipeline Success - {pipeline_name}"
                        )
                    else:
                        final_status = 'PARTIAL'
                    
                    self.update_pipeline_execution(execution_id, {
                        'status': final_status,
                        'current_stage': 'completed',
                        'completed_at': datetime.now(timezone.utc).isoformat()
                    })
                    
                    return {
                        'execution_id': execution_id,
                        'status': final_status,
                        'completed_jobs': len(completed_jobs),
                        'failed_jobs': len(failed_jobs),
                        'total_jobs': len(pipeline_config.get('jobs', []))
                    }
            
            except Exception as e:
                logger.error(f"Pipeline orchestration failed: {str(e)}")
                
                self.update_pipeline_execution(execution_id, {
                    'status': 'FAILED',
                    'current_stage': 'error',
                    'error': str(e),
                    'completed_at': datetime.now(timezone.utc).isoformat()
                })
                
                self.send_notification(
                    f"Pipeline {pipeline_name} orchestration failed: {str(e)}",
                    f"Pipeline Orchestration Failure - {pipeline_name}"
                )
                
                return {
                    'execution_id': execution_id,
                    'status': 'FAILED',
                    'error': str(e)
                }


@xray_recorder.capture('lambda_handler')
def lambda_handler(event, context):
    """AWS Lambda handler function"""
    extra_info = {
        'aws_request_id': getattr(context, 'aws_request_id', 'unknown'),
        'function_name': getattr(context, 'function_name', 'pipeline-orchestrator')
    }
    logger.info(f"Pipeline orchestrator started with event: {json.dumps(event, default=str)}", extra=extra_info)
    
    try:
        orchestrator = PipelineOrchestrator()
        
        # Parse pipeline configuration from event
        pipeline_config = event.get('pipeline_config')
        if not pipeline_config:
            raise ValueError("pipeline_config is required in event payload")
        
        # Handle different orchestration actions
        action = event.get('action', 'orchestrate')
        
        if action == 'orchestrate':
            result = orchestrator.orchestrate_pipeline(pipeline_config)
        elif action == 'get_status':
            execution_id = event.get('execution_id')
            if not execution_id:
                raise ValueError("execution_id is required for get_status action")
            result = orchestrator.get_pipeline_execution(execution_id)
        else:
            raise ValueError(f"Unsupported action: {action}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str)
        }
        
    except Exception as e:
        error_msg = f"Pipeline orchestration failed: {str(e)}"
        logger.error(error_msg, extra=extra_info)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'failed',
                'error': error_msg,
                'error_type': type(e).__name__
            })
        }
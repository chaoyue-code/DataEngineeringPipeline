"""
Glue Error Handler Lambda Function
This function handles Glue job failures, implements retry logic,
and sends notifications for persistent failures.
"""

import json
import os
import boto3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
glue_client = boto3.client('glue')
sns_client = boto3.client('sns')
cloudwatch_client = boto3.client('cloudwatch')

# Environment variables
PROJECT_NAME = "${project_name}"
ENVIRONMENT = "${environment}"
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
ENABLE_AUTO_RETRY = os.environ.get('ENABLE_AUTO_RETRY', 'false').lower() == 'true'
MAX_RETRY_ATTEMPTS = int(os.environ.get('MAX_RETRY_ATTEMPTS', '3'))

def lambda_handler(event, context):
    """
    Main Lambda handler for Glue error handling.
    
    Args:
        event: EventBridge event containing Glue job state change
        context: Lambda context object
        
    Returns:
        dict: Response with processing status
    """
    try:
        logger.info(f"Received event: {json.dumps(event, indent=2)}")
        
        # Extract job information from event
        detail = event.get('detail', {})
        job_name = detail.get('jobName')
        job_run_id = detail.get('jobRunId')
        state = detail.get('state')
        
        if not job_name or not job_run_id or not state:
            logger.error("Missing required job information in event")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required job information'})
            }
        
        logger.info(f"Processing job failure: {job_name} (Run ID: {job_run_id}, State: {state})")
        
        # Get job run details
        job_run_details = get_job_run_details(job_name, job_run_id)
        
        # Analyze the failure
        failure_analysis = analyze_failure(job_run_details)
        
        # Determine if retry is appropriate
        should_retry = should_retry_job(job_name, job_run_details, failure_analysis)
        
        # Handle the failure
        if should_retry and ENABLE_AUTO_RETRY:
            retry_result = retry_job(job_name, job_run_details)
            response_data = {
                'action': 'retry_attempted',
                'job_name': job_name,
                'original_run_id': job_run_id,
                'retry_run_id': retry_result.get('job_run_id'),
                'retry_success': retry_result.get('success', False)
            }
        else:
            # Send notification for persistent failure
            notification_result = send_failure_notification(
                job_name, job_run_id, failure_analysis
            )
            response_data = {
                'action': 'notification_sent',
                'job_name': job_name,
                'run_id': job_run_id,
                'notification_success': notification_result.get('success', False)
            }
        
        # Record custom metrics
        record_failure_metrics(job_name, state, failure_analysis)
        
        logger.info(f"Error handling completed: {json.dumps(response_data)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        logger.error(f"Error in lambda handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_job_run_details(job_name: str, job_run_id: str) -> Dict[str, Any]:
    """
    Get detailed information about the failed job run.
    
    Args:
        job_name: Name of the Glue job
        job_run_id: ID of the job run
        
    Returns:
        Dictionary with job run details
    """
    try:
        response = glue_client.get_job_run(JobName=job_name, RunId=job_run_id)
        job_run = response.get('JobRun', {})
        
        return {
            'job_name': job_name,
            'job_run_id': job_run_id,
            'job_run_state': job_run.get('JobRunState'),
            'started_on': job_run.get('StartedOn'),
            'completed_on': job_run.get('CompletedOn'),
            'execution_time': job_run.get('ExecutionTime'),
            'error_message': job_run.get('ErrorMessage'),
            'attempt': job_run.get('Attempt', 0),
            'max_retries': job_run.get('MaxRetries', 0),
            'timeout': job_run.get('Timeout'),
            'allocated_capacity': job_run.get('AllocatedCapacity'),
            'max_capacity': job_run.get('MaxCapacity'),
            'worker_type': job_run.get('WorkerType'),
            'number_of_workers': job_run.get('NumberOfWorkers'),
            'arguments': job_run.get('Arguments', {}),
            'log_group_name': job_run.get('LogGroupName')
        }
        
    except Exception as e:
        logger.error(f"Failed to get job run details: {str(e)}")
        return {
            'job_name': job_name,
            'job_run_id': job_run_id,
            'error': str(e)
        }

def analyze_failure(job_run_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze the job failure to determine the root cause and appropriate action.
    
    Args:
        job_run_details: Details of the failed job run
        
    Returns:
        Dictionary with failure analysis
    """
    analysis = {
        'failure_type': 'unknown',
        'is_transient': False,
        'retry_recommended': False,
        'root_cause': 'Unknown failure',
        'suggested_action': 'Manual investigation required'
    }
    
    try:
        error_message = job_run_details.get('error_message', '').lower()
        job_run_state = job_run_details.get('job_run_state', '')
        execution_time = job_run_details.get('execution_time', 0)
        timeout = job_run_details.get('timeout', 0)
        
        # Analyze based on error message patterns
        if 'timeout' in error_message or job_run_state == 'TIMEOUT':
            analysis.update({
                'failure_type': 'timeout',
                'is_transient': True,
                'retry_recommended': True,
                'root_cause': 'Job execution exceeded timeout limit',
                'suggested_action': 'Increase timeout or optimize job performance'
            })
        
        elif 'out of memory' in error_message or 'java.lang.outofmemoryerror' in error_message:
            analysis.update({
                'failure_type': 'memory',
                'is_transient': False,
                'retry_recommended': True,
                'root_cause': 'Insufficient memory allocation',
                'suggested_action': 'Increase worker capacity or optimize data processing'
            })
        
        elif 'connection' in error_message or 'network' in error_message:
            analysis.update({
                'failure_type': 'connectivity',
                'is_transient': True,
                'retry_recommended': True,
                'root_cause': 'Network or connection issues',
                'suggested_action': 'Retry with exponential backoff'
            })
        
        elif 'access denied' in error_message or 'permission' in error_message:
            analysis.update({
                'failure_type': 'permissions',
                'is_transient': False,
                'retry_recommended': False,
                'root_cause': 'Insufficient permissions',
                'suggested_action': 'Review and update IAM permissions'
            })
        
        elif 'no such file' in error_message or 'file not found' in error_message:
            analysis.update({
                'failure_type': 'data_missing',
                'is_transient': False,
                'retry_recommended': False,
                'root_cause': 'Required data files not found',
                'suggested_action': 'Verify data availability and pipeline dependencies'
            })
        
        elif 'schema' in error_message or 'column' in error_message:
            analysis.update({
                'failure_type': 'schema_mismatch',
                'is_transient': False,
                'retry_recommended': False,
                'root_cause': 'Data schema mismatch or evolution',
                'suggested_action': 'Update job to handle schema changes'
            })
        
        # Additional analysis based on execution characteristics
        if execution_time > 0 and timeout > 0 and execution_time >= (timeout * 0.9):
            analysis['failure_type'] = 'near_timeout'
            analysis['is_transient'] = True
            analysis['retry_recommended'] = True
        
        logger.info(f"Failure analysis completed: {analysis}")
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to analyze failure: {str(e)}")
        analysis['error'] = str(e)
        return analysis

def should_retry_job(job_name: str, job_run_details: Dict[str, Any], 
                    failure_analysis: Dict[str, Any]) -> bool:
    """
    Determine if the job should be automatically retried.
    
    Args:
        job_name: Name of the Glue job
        job_run_details: Details of the failed job run
        failure_analysis: Analysis of the failure
        
    Returns:
        True if job should be retried, False otherwise
    """
    try:
        # Check if retry is recommended by analysis
        if not failure_analysis.get('retry_recommended', False):
            logger.info(f"Retry not recommended for {job_name} based on failure analysis")
            return False
        
        # Check current attempt count
        current_attempt = job_run_details.get('attempt', 0)
        if current_attempt >= MAX_RETRY_ATTEMPTS:
            logger.info(f"Maximum retry attempts ({MAX_RETRY_ATTEMPTS}) reached for {job_name}")
            return False
        
        # Check if failure is transient
        if not failure_analysis.get('is_transient', False):
            logger.info(f"Failure is not transient for {job_name}, skipping retry")
            return False
        
        # Check recent failure history to avoid retry loops
        recent_failures = get_recent_failure_count(job_name)
        if recent_failures >= 5:  # Too many recent failures
            logger.info(f"Too many recent failures ({recent_failures}) for {job_name}")
            return False
        
        logger.info(f"Retry approved for {job_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error determining retry eligibility: {str(e)}")
        return False

def retry_job(job_name: str, job_run_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retry the failed Glue job with appropriate modifications.
    
    Args:
        job_name: Name of the Glue job
        job_run_details: Details of the original failed job run
        
    Returns:
        Dictionary with retry results
    """
    try:
        # Prepare job arguments with retry-specific modifications
        job_arguments = job_run_details.get('arguments', {}).copy()
        
        # Add retry metadata
        job_arguments['--retry-attempt'] = str(job_run_details.get('attempt', 0) + 1)
        job_arguments['--original-run-id'] = job_run_details.get('job_run_id')
        job_arguments['--retry-timestamp'] = datetime.now().isoformat()
        
        # Start the retry job
        response = glue_client.start_job_run(
            JobName=job_name,
            Arguments=job_arguments
        )
        
        retry_run_id = response.get('JobRunId')
        
        logger.info(f"Retry job started: {job_name} (Run ID: {retry_run_id})")
        
        return {
            'success': True,
            'job_run_id': retry_run_id,
            'retry_attempt': job_run_details.get('attempt', 0) + 1
        }
        
    except Exception as e:
        logger.error(f"Failed to retry job {job_name}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def send_failure_notification(job_name: str, job_run_id: str, 
                            failure_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send notification about job failure.
    
    Args:
        job_name: Name of the failed Glue job
        job_run_id: ID of the failed job run
        failure_analysis: Analysis of the failure
        
    Returns:
        Dictionary with notification results
    """
    try:
        if not SNS_TOPIC_ARN:
            logger.warning("SNS topic ARN not configured, skipping notification")
            return {'success': False, 'reason': 'SNS not configured'}
        
        # Prepare notification message
        message = {
            'alert_type': 'GLUE_JOB_FAILURE',
            'timestamp': datetime.now().isoformat(),
            'project': PROJECT_NAME,
            'environment': ENVIRONMENT,
            'job_name': job_name,
            'job_run_id': job_run_id,
            'failure_analysis': failure_analysis,
            'action_required': True
        }
        
        subject = f"[{ENVIRONMENT.upper()}] Glue Job Failure: {job_name}"
        
        # Send SNS notification
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=json.dumps(message, indent=2)
        )
        
        logger.info(f"Notification sent for {job_name} failure")
        
        return {
            'success': True,
            'message_id': response.get('MessageId')
        }
        
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def record_failure_metrics(job_name: str, state: str, failure_analysis: Dict[str, Any]):
    """
    Record custom CloudWatch metrics for job failures.
    
    Args:
        job_name: Name of the failed job
        state: Job state (FAILED, TIMEOUT, etc.)
        failure_analysis: Analysis of the failure
    """
    try:
        # Record failure count metric
        cloudwatch_client.put_metric_data(
            Namespace=f'{PROJECT_NAME}/{ENVIRONMENT}/Glue',
            MetricData=[
                {
                    'MetricName': 'JobFailures',
                    'Dimensions': [
                        {
                            'Name': 'JobName',
                            'Value': job_name
                        },
                        {
                            'Name': 'FailureType',
                            'Value': failure_analysis.get('failure_type', 'unknown')
                        }
                    ],
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.now()
                }
            ]
        )
        
        # Record failure by state
        cloudwatch_client.put_metric_data(
            Namespace=f'{PROJECT_NAME}/{ENVIRONMENT}/Glue',
            MetricData=[
                {
                    'MetricName': 'JobFailuresByState',
                    'Dimensions': [
                        {
                            'Name': 'JobName',
                            'Value': job_name
                        },
                        {
                            'Name': 'State',
                            'Value': state
                        }
                    ],
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.now()
                }
            ]
        )
        
        logger.info(f"Custom metrics recorded for {job_name} failure")
        
    except Exception as e:
        logger.error(f"Failed to record metrics: {str(e)}")

def get_recent_failure_count(job_name: str, hours: int = 24) -> int:
    """
    Get the count of recent failures for a job.
    
    Args:
        job_name: Name of the Glue job
        hours: Number of hours to look back
        
    Returns:
        Count of recent failures
    """
    try:
        # This is a simplified implementation
        # In a real scenario, you might query CloudWatch metrics or a database
        response = glue_client.get_job_runs(
            JobName=job_name,
            MaxResults=50
        )
        
        job_runs = response.get('JobRuns', [])
        recent_failures = 0
        
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        
        for job_run in job_runs:
            if job_run.get('StartedOn'):
                start_time = job_run['StartedOn'].timestamp()
                if start_time > cutoff_time and job_run.get('JobRunState') in ['FAILED', 'TIMEOUT', 'STOPPED']:
                    recent_failures += 1
        
        return recent_failures
        
    except Exception as e:
        logger.error(f"Failed to get recent failure count: {str(e)}")
        return 0
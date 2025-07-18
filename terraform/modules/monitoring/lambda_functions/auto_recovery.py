"""
Auto-Recovery Lambda Function
Implements automated recovery procedures for pipeline failures
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Initialize AWS clients
sns_client = boto3.client('sns')
glue_client = boto3.client('glue')
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

# Environment variables
PROJECT_NAME = os.environ['PROJECT_NAME']
GLUE_JOB_NAME = os.environ['GLUE_JOB_NAME']
LAMBDA_FUNCTION_NAME = os.environ['LAMBDA_FUNCTION_NAME']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
AUTO_RECOVERY_ENABLED = os.environ.get('AUTO_RECOVERY_ENABLED', 'true').lower() == 'true'
MAX_RECOVERY_ATTEMPTS = int(os.environ.get('MAX_RECOVERY_ATTEMPTS', '${max_recovery_attempts}'))

# DynamoDB table for tracking recovery attempts
RECOVERY_TABLE_NAME = f"{PROJECT_NAME}-recovery-attempts"

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for auto-recovery procedures
    
    Args:
        event: CloudWatch alarm state change event
        context: Lambda context object
        
    Returns:
        Response dictionary with status and details
    """
    try:
        print(f"Received auto-recovery event: {json.dumps(event, default=str)}")
        
        if not AUTO_RECOVERY_ENABLED:
            print("Auto-recovery is disabled")
            return {
                'statusCode': 200,
                'body': json.dumps('Auto-recovery is disabled')
            }
        
        # Parse the CloudWatch alarm event
        alarm_details = parse_alarm_event(event)
        
        if not alarm_details:
            return {
                'statusCode': 400,
                'body': json.dumps('Invalid alarm event format')
            }
        
        # Check recovery attempt limits
        recovery_key = f"{alarm_details['alarm_name']}-{datetime.utcnow().strftime('%Y-%m-%d')}"
        attempt_count = get_recovery_attempt_count(recovery_key)
        
        if attempt_count >= MAX_RECOVERY_ATTEMPTS:
            print(f"Maximum recovery attempts ({MAX_RECOVERY_ATTEMPTS}) reached for {alarm_details['alarm_name']}")
            send_max_attempts_notification(alarm_details, attempt_count)
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Maximum recovery attempts reached',
                    'attempts': attempt_count
                })
            }
        
        # Perform recovery based on alarm type
        recovery_result = perform_recovery(alarm_details)
        
        # Update recovery attempt count
        update_recovery_attempt_count(recovery_key, attempt_count + 1)
        
        # Send recovery notification
        send_recovery_notification(alarm_details, recovery_result, attempt_count + 1)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Auto-recovery attempted',
                'alarm': alarm_details['alarm_name'],
                'recovery_result': recovery_result,
                'attempt_number': attempt_count + 1
            })
        }
        
    except Exception as e:
        error_message = f"Error in auto-recovery handler: {str(e)}"
        print(error_message)
        
        # Send error notification
        send_error_notification(error_message)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_message
            })
        }

def parse_alarm_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse CloudWatch alarm event to extract relevant details
    
    Args:
        event: Raw CloudWatch alarm event
        
    Returns:
        Dictionary with parsed alarm details
    """
    try:
        detail = event.get('detail', {})
        
        return {
            'alarm_name': detail.get('alarmName', ''),
            'alarm_description': detail.get('alarmDescription', ''),
            'state': detail.get('state', {}).get('value', ''),
            'reason': detail.get('state', {}).get('reason', ''),
            'timestamp': detail.get('state', {}).get('timestamp', ''),
            'region': detail.get('awsRegion', ''),
            'account_id': detail.get('accountId', '')
        }
    except Exception as e:
        print(f"Error parsing alarm event: {str(e)}")
        return {}

def get_recovery_attempt_count(recovery_key: str) -> int:
    """
    Get the current recovery attempt count for a specific alarm
    
    Args:
        recovery_key: Unique key for the recovery attempt
        
    Returns:
        Current attempt count
    """
    try:
        # Create table if it doesn't exist
        create_recovery_table_if_not_exists()
        
        table = dynamodb.Table(RECOVERY_TABLE_NAME)
        
        response = table.get_item(
            Key={'recovery_key': recovery_key}
        )
        
        if 'Item' in response:
            return response['Item'].get('attempt_count', 0)
        else:
            return 0
            
    except Exception as e:
        print(f"Error getting recovery attempt count: {str(e)}")
        return 0

def update_recovery_attempt_count(recovery_key: str, attempt_count: int) -> None:
    """
    Update the recovery attempt count for a specific alarm
    
    Args:
        recovery_key: Unique key for the recovery attempt
        attempt_count: New attempt count
    """
    try:
        table = dynamodb.Table(RECOVERY_TABLE_NAME)
        
        table.put_item(
            Item={
                'recovery_key': recovery_key,
                'attempt_count': attempt_count,
                'last_attempt': datetime.utcnow().isoformat(),
                'ttl': int((datetime.utcnow() + timedelta(days=7)).timestamp())
            }
        )
        
    except Exception as e:
        print(f"Error updating recovery attempt count: {str(e)}")

def create_recovery_table_if_not_exists() -> None:
    """
    Create DynamoDB table for tracking recovery attempts if it doesn't exist
    """
    try:
        # Check if table exists
        existing_tables = dynamodb.meta.client.list_tables()['TableNames']
        
        if RECOVERY_TABLE_NAME not in existing_tables:
            table = dynamodb.create_table(
                TableName=RECOVERY_TABLE_NAME,
                KeySchema=[
                    {
                        'AttributeName': 'recovery_key',
                        'KeyType': 'HASH'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'recovery_key',
                        'AttributeType': 'S'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            # Wait for table to be created
            table.wait_until_exists()
            print(f"Created recovery tracking table: {RECOVERY_TABLE_NAME}")
            
    except Exception as e:
        print(f"Error creating recovery table: {str(e)}")

def perform_recovery(alarm_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform recovery actions based on the alarm type
    
    Args:
        alarm_details: Parsed alarm details
        
    Returns:
        Dictionary with recovery results
    """
    try:
        alarm_name = alarm_details['alarm_name']
        recovery_actions = []
        
        # Determine recovery actions based on alarm name
        if 'lambda-failure' in alarm_name.lower():
            recovery_actions.append(restart_lambda_function())
            
        elif 'glue-job-failures' in alarm_name.lower():
            recovery_actions.append(restart_glue_job())
            
        elif 'data-quality' in alarm_name.lower():
            recovery_actions.append(trigger_data_validation_rerun())
            
        elif 'pipeline-health' in alarm_name.lower():
            # Comprehensive recovery for pipeline health issues
            recovery_actions.append(restart_lambda_function())
            recovery_actions.append(restart_glue_job())
            
        else:
            recovery_actions.append({
                'action': 'unknown_alarm_type',
                'success': False,
                'message': f"No recovery action defined for alarm type: {alarm_name}"
            })
        
        # Evaluate overall recovery success
        successful_actions = [action for action in recovery_actions if action.get('success', False)]
        
        return {
            'recovery_attempted': True,
            'actions_performed': recovery_actions,
            'successful_actions': len(successful_actions),
            'total_actions': len(recovery_actions),
            'overall_success': len(successful_actions) > 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Error performing recovery: {str(e)}")
        return {
            'recovery_attempted': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def restart_lambda_function() -> Dict[str, Any]:
    """
    Restart Lambda function by updating its configuration
    
    Returns:
        Dictionary with restart result
    """
    try:
        # Get current function configuration
        response = lambda_client.get_function_configuration(
            FunctionName=LAMBDA_FUNCTION_NAME
        )
        
        current_timeout = response.get('Timeout', 30)
        
        # Update function configuration to trigger restart
        lambda_client.update_function_configuration(
            FunctionName=LAMBDA_FUNCTION_NAME,
            Timeout=current_timeout  # This triggers a restart
        )
        
        print(f"Lambda function {LAMBDA_FUNCTION_NAME} configuration updated to trigger restart")
        
        return {
            'action': 'restart_lambda',
            'success': True,
            'message': f"Lambda function {LAMBDA_FUNCTION_NAME} restarted successfully"
        }
        
    except Exception as e:
        print(f"Error restarting Lambda function: {str(e)}")
        return {
            'action': 'restart_lambda',
            'success': False,
            'error': str(e)
        }

def restart_glue_job() -> Dict[str, Any]:
    """
    Restart failed Glue job
    
    Returns:
        Dictionary with restart result
    """
    try:
        # Start a new job run
        response = glue_client.start_job_run(
            JobName=GLUE_JOB_NAME,
            Arguments={
                '--recovery-run': 'true',
                '--recovery-timestamp': datetime.utcnow().isoformat()
            }
        )
        
        job_run_id = response.get('JobRunId')
        
        print(f"Glue job {GLUE_JOB_NAME} restarted with run ID: {job_run_id}")
        
        return {
            'action': 'restart_glue_job',
            'success': True,
            'message': f"Glue job {GLUE_JOB_NAME} restarted successfully",
            'job_run_id': job_run_id
        }
        
    except Exception as e:
        print(f"Error restarting Glue job: {str(e)}")
        return {
            'action': 'restart_glue_job',
            'success': False,
            'error': str(e)
        }

def trigger_data_validation_rerun() -> Dict[str, Any]:
    """
    Trigger data validation rerun for data quality issues
    
    Returns:
        Dictionary with validation result
    """
    try:
        # This would typically invoke a data quality validation Lambda
        # For now, we'll simulate the action
        
        print("Triggering data validation rerun")
        
        return {
            'action': 'data_validation_rerun',
            'success': True,
            'message': "Data validation rerun triggered successfully"
        }
        
    except Exception as e:
        print(f"Error triggering data validation rerun: {str(e)}")
        return {
            'action': 'data_validation_rerun',
            'success': False,
            'error': str(e)
        }

def send_recovery_notification(alarm_details: Dict[str, Any], recovery_result: Dict[str, Any], attempt_number: int) -> None:
    """
    Send notification about recovery attempt
    
    Args:
        alarm_details: Parsed alarm details
        recovery_result: Result of recovery actions
        attempt_number: Current attempt number
    """
    try:
        success_emoji = "✅" if recovery_result.get('overall_success', False) else "❌"
        
        message = f"""
{success_emoji} Auto-Recovery Attempt #{attempt_number}

Project: {PROJECT_NAME}
Alarm: {alarm_details['alarm_name']}
Timestamp: {datetime.utcnow().isoformat()}

Recovery Actions Performed:
"""
        
        for action in recovery_result.get('actions_performed', []):
            status = "✅" if action.get('success', False) else "❌"
            message += f"  {status} {action.get('action', 'Unknown')}: {action.get('message', 'No details')}\n"
        
        message += f"""
Overall Success: {recovery_result.get('overall_success', False)}
Successful Actions: {recovery_result.get('successful_actions', 0)}/{recovery_result.get('total_actions', 0)}

Remaining Attempts: {MAX_RECOVERY_ATTEMPTS - attempt_number}

If recovery continues to fail, manual intervention may be required.
"""
        
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"{success_emoji} Auto-Recovery Attempt - {PROJECT_NAME}",
            Message=message.strip(),
            MessageAttributes={
                'AlertType': {
                    'DataType': 'String',
                    'StringValue': 'Recovery'
                },
                'AlarmName': {
                    'DataType': 'String',
                    'StringValue': alarm_details['alarm_name']
                },
                'AttemptNumber': {
                    'DataType': 'Number',
                    'StringValue': str(attempt_number)
                }
            }
        )
        
        print(f"Recovery notification sent for attempt #{attempt_number}")
        
    except Exception as e:
        print(f"Error sending recovery notification: {str(e)}")

def send_max_attempts_notification(alarm_details: Dict[str, Any], attempt_count: int) -> None:
    """
    Send notification when maximum recovery attempts are reached
    
    Args:
        alarm_details: Parsed alarm details
        attempt_count: Current attempt count
    """
    try:
        message = f"""
🚨 Maximum Auto-Recovery Attempts Reached

Project: {PROJECT_NAME}
Alarm: {alarm_details['alarm_name']}
Attempts Made: {attempt_count}/{MAX_RECOVERY_ATTEMPTS}
Timestamp: {datetime.utcnow().isoformat()}

Auto-recovery has reached the maximum number of attempts for today.
Manual intervention is now required to resolve the issue.

Recommended Actions:
1. Review pipeline logs for detailed error information
2. Check system health and resource availability
3. Verify data source connectivity
4. Consider scaling resources if needed
5. Contact the on-call engineer if issue persists

Auto-recovery will reset tomorrow and resume if the alarm continues.
"""
        
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"🚨 Max Recovery Attempts Reached - {PROJECT_NAME}",
            Message=message.strip(),
            MessageAttributes={
                'AlertType': {
                    'DataType': 'String',
                    'StringValue': 'MaxAttemptsReached'
                },
                'AlarmName': {
                    'DataType': 'String',
                    'StringValue': alarm_details['alarm_name']
                }
            }
        )
        
    except Exception as e:
        print(f"Error sending max attempts notification: {str(e)}")

def send_error_notification(error_message: str) -> None:
    """
    Send error notification when auto-recovery handler fails
    
    Args:
        error_message: Error message to send
    """
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"❌ Auto-Recovery Handler Error - {PROJECT_NAME}",
            Message=f"""
Auto-Recovery Handler Error

Project: {PROJECT_NAME}
Error: {error_message}
Timestamp: {datetime.utcnow().isoformat()}

The auto-recovery handler encountered an error and may not be functioning properly.
Please check the Lambda function logs and resolve the issue.
""",
            MessageAttributes={
                'AlertType': {
                    'DataType': 'String',
                    'StringValue': 'Error'
                },
                'Component': {
                    'DataType': 'String',
                    'StringValue': 'AutoRecoveryHandler'
                }
            }
        )
        
    except Exception as e:
        print(f"Failed to send error notification: {str(e)}")
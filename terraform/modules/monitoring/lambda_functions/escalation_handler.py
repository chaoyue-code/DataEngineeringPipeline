"""
Escalation Handler Lambda Function
Implements escalation procedures for persistent pipeline issues
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Initialize AWS clients
sns_client = boto3.client('sns')
cloudwatch_client = boto3.client('cloudwatch')

# Environment variables
ESCALATION_SNS_TOPIC_ARN = os.environ['ESCALATION_SNS_TOPIC_ARN']
CRITICAL_SNS_TOPIC_ARN = os.environ['CRITICAL_SNS_TOPIC_ARN']
PROJECT_NAME = os.environ['PROJECT_NAME']
ESCALATION_THRESHOLD = int(os.environ.get('ESCALATION_THRESHOLD', '${escalation_threshold}'))

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for escalation procedures
    
    Args:
        event: CloudWatch alarm state change event
        context: Lambda context object
        
    Returns:
        Response dictionary with status and details
    """
    try:
        print(f"Received escalation event: {json.dumps(event, default=str)}")
        
        # Parse the CloudWatch alarm event
        alarm_details = parse_alarm_event(event)
        
        if not alarm_details:
            return {
                'statusCode': 400,
                'body': json.dumps('Invalid alarm event format')
            }
        
        # Check if escalation is needed
        should_escalate = check_escalation_criteria(alarm_details)
        
        if should_escalate:
            # Perform escalation
            escalation_response = perform_escalation(alarm_details)
            
            # Log escalation action
            log_escalation_action(alarm_details, escalation_response)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Escalation performed successfully',
                    'alarm': alarm_details['alarm_name'],
                    'escalation_response': escalation_response
                })
            }
        else:
            print(f"Escalation criteria not met for alarm: {alarm_details['alarm_name']}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Escalation criteria not met',
                    'alarm': alarm_details['alarm_name']
                })
            }
            
    except Exception as e:
        error_message = f"Error in escalation handler: {str(e)}"
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

def check_escalation_criteria(alarm_details: Dict[str, Any]) -> bool:
    """
    Check if the alarm meets escalation criteria
    
    Args:
        alarm_details: Parsed alarm details
        
    Returns:
        Boolean indicating if escalation is needed
    """
    try:
        alarm_name = alarm_details['alarm_name']
        
        # Get alarm history to check duration in ALARM state
        alarm_history = get_alarm_history(alarm_name)
        
        # Calculate time in ALARM state
        alarm_duration_minutes = calculate_alarm_duration(alarm_history)
        
        print(f"Alarm {alarm_name} has been in ALARM state for {alarm_duration_minutes} minutes")
        
        # Escalate if alarm has been in ALARM state longer than threshold
        return alarm_duration_minutes >= ESCALATION_THRESHOLD
        
    except Exception as e:
        print(f"Error checking escalation criteria: {str(e)}")
        return False

def get_alarm_history(alarm_name: str) -> List[Dict[str, Any]]:
    """
    Get alarm history from CloudWatch
    
    Args:
        alarm_name: Name of the CloudWatch alarm
        
    Returns:
        List of alarm history records
    """
    try:
        response = cloudwatch_client.describe_alarm_history(
            AlarmName=alarm_name,
            HistoryItemType='StateUpdate',
            MaxRecords=10
        )
        
        return response.get('AlarmHistoryItems', [])
        
    except Exception as e:
        print(f"Error getting alarm history: {str(e)}")
        return []

def calculate_alarm_duration(alarm_history: List[Dict[str, Any]]) -> int:
    """
    Calculate how long the alarm has been in ALARM state
    
    Args:
        alarm_history: List of alarm history records
        
    Returns:
        Duration in minutes
    """
    try:
        if not alarm_history:
            return 0
        
        # Find the most recent state change to ALARM
        alarm_start_time = None
        
        for record in alarm_history:
            if 'ALARM' in record.get('HistorySummary', ''):
                alarm_start_time = record.get('Timestamp')
                break
        
        if not alarm_start_time:
            return 0
        
        # Calculate duration
        current_time = datetime.utcnow()
        if isinstance(alarm_start_time, str):
            alarm_start_time = datetime.fromisoformat(alarm_start_time.replace('Z', '+00:00'))
        
        duration = current_time - alarm_start_time.replace(tzinfo=None)
        return int(duration.total_seconds() / 60)
        
    except Exception as e:
        print(f"Error calculating alarm duration: {str(e)}")
        return 0

def perform_escalation(alarm_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform escalation actions
    
    Args:
        alarm_details: Parsed alarm details
        
    Returns:
        Dictionary with escalation response details
    """
    try:
        alarm_name = alarm_details['alarm_name']
        
        # Create escalation message
        escalation_message = create_escalation_message(alarm_details)
        
        # Send escalation notification
        escalation_response = sns_client.publish(
            TopicArn=ESCALATION_SNS_TOPIC_ARN,
            Subject=f"🚨 ESCALATION: {PROJECT_NAME} Pipeline Alert",
            Message=escalation_message,
            MessageAttributes={
                'AlertType': {
                    'DataType': 'String',
                    'StringValue': 'Escalation'
                },
                'AlarmName': {
                    'DataType': 'String',
                    'StringValue': alarm_name
                },
                'Severity': {
                    'DataType': 'String',
                    'StringValue': 'Critical'
                }
            }
        )
        
        print(f"Escalation notification sent for alarm: {alarm_name}")
        
        return {
            'escalation_sent': True,
            'message_id': escalation_response.get('MessageId'),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Error performing escalation: {str(e)}")
        return {
            'escalation_sent': False,
            'error': str(e)
        }

def create_escalation_message(alarm_details: Dict[str, Any]) -> str:
    """
    Create formatted escalation message
    
    Args:
        alarm_details: Parsed alarm details
        
    Returns:
        Formatted escalation message
    """
    message = f"""
🚨 PIPELINE ESCALATION ALERT 🚨

Project: {PROJECT_NAME}
Alarm: {alarm_details['alarm_name']}
State: {alarm_details['state']}
Timestamp: {alarm_details['timestamp']}

Description: {alarm_details['alarm_description']}
Reason: {alarm_details['reason']}

This alarm has been in ALARM state for more than {ESCALATION_THRESHOLD} minutes and requires immediate attention.

Recommended Actions:
1. Check pipeline logs for detailed error information
2. Verify data source connectivity (Snowflake)
3. Check AWS service health status
4. Review recent deployments or configuration changes
5. Consider manual intervention if auto-recovery has failed

Dashboard Links:
- Pipeline Overview: https://{alarm_details['region']}.console.aws.amazon.com/cloudwatch/home?region={alarm_details['region']}#dashboards:name={PROJECT_NAME}-pipeline-overview
- CloudWatch Alarms: https://{alarm_details['region']}.console.aws.amazon.com/cloudwatch/home?region={alarm_details['region']}#alarmsV2:

Account: {alarm_details['account_id']}
Region: {alarm_details['region']}

This is an automated escalation. Please acknowledge receipt and provide status updates.
"""
    
    return message.strip()

def log_escalation_action(alarm_details: Dict[str, Any], escalation_response: Dict[str, Any]) -> None:
    """
    Log escalation action for audit trail
    
    Args:
        alarm_details: Parsed alarm details
        escalation_response: Response from escalation action
    """
    try:
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'escalation',
            'alarm_name': alarm_details['alarm_name'],
            'escalation_threshold_minutes': ESCALATION_THRESHOLD,
            'escalation_sent': escalation_response.get('escalation_sent', False),
            'message_id': escalation_response.get('message_id', ''),
            'project': PROJECT_NAME
        }
        
        print(f"ESCALATION_LOG: {json.dumps(log_entry)}")
        
    except Exception as e:
        print(f"Error logging escalation action: {str(e)}")

def send_error_notification(error_message: str) -> None:
    """
    Send error notification when escalation handler fails
    
    Args:
        error_message: Error message to send
    """
    try:
        sns_client.publish(
            TopicArn=CRITICAL_SNS_TOPIC_ARN,
            Subject=f"❌ Escalation Handler Error - {PROJECT_NAME}",
            Message=f"""
Escalation Handler Error

Project: {PROJECT_NAME}
Error: {error_message}
Timestamp: {datetime.utcnow().isoformat()}

The escalation handler encountered an error and may not be functioning properly.
Please check the Lambda function logs and resolve the issue immediately.
""",
            MessageAttributes={
                'AlertType': {
                    'DataType': 'String',
                    'StringValue': 'Critical'
                },
                'Component': {
                    'DataType': 'String',
                    'StringValue': 'EscalationHandler'
                }
            }
        )
        
    except Exception as e:
        print(f"Failed to send error notification: {str(e)}")
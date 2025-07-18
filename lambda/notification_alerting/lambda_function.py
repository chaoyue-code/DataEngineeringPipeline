"""
Notification and Alerting Lambda Function

This Lambda function sends pipeline status notifications, integrates with SNS for 
multi-channel alerting, and creates dashboard update mechanisms for operational visibility.
"""

import json
import os
import logging
import boto3
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse

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

class NotificationAlertingService:
    """Comprehensive notification and alerting service"""
    
    def __init__(self):
        self.sns_client = boto3.client('sns')
        self.ses_client = boto3.client('ses')
        self.cloudwatch = boto3.client('cloudwatch')
        self.dynamodb = boto3.resource('dynamodb')
        self.lambda_client = boto3.client('lambda')
        
        # Configuration from environment variables
        self.sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        self.email_topic_arn = os.environ.get('EMAIL_TOPIC_ARN')
        self.slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        self.teams_webhook_url = os.environ.get('TEAMS_WEBHOOK_URL')
        self.dashboard_update_function = os.environ.get('DASHBOARD_UPDATE_FUNCTION')
        self.notification_history_table = os.environ.get('NOTIFICATION_HISTORY_TABLE')
        self.alert_rules_table = os.environ.get('ALERT_RULES_TABLE')
        
        # Initialize DynamoDB tables
        self.history_table = self.dynamodb.Table(self.notification_history_table) if self.notification_history_table else None
        self.rules_table = self.dynamodb.Table(self.alert_rules_table) if self.alert_rules_table else None
        
        # Alert severity levels
        self.severity_levels = {
            'INFO': {'priority': 1, 'color': '#36a64f', 'emoji': '✅'},
            'WARNING': {'priority': 2, 'color': '#ff9900', 'emoji': '⚠️'},
            'ERROR': {'priority': 3, 'color': '#ff0000', 'emoji': '❌'},
            'CRITICAL': {'priority': 4, 'color': '#8b0000', 'emoji': '🚨'}
        }
    
    def get_alert_rules(self, pipeline_name: str = None) -> List[Dict]:
        """Get alert rules for a specific pipeline or all pipelines"""
        if not self.rules_table:
            return []
        
        try:
            if pipeline_name:
                response = self.rules_table.get_item(Key={'pipeline_name': pipeline_name})
                return response.get('Item', {}).get('rules', [])
            else:
                response = self.rules_table.scan()
                rules = []
                for item in response.get('Items', []):
                    rules.extend(item.get('rules', []))
                return rules
        except ClientError as e:
            logger.error(f"Failed to get alert rules: {str(e)}")
            return []
    
    def should_send_alert(self, alert_data: Dict, rules: List[Dict]) -> bool:
        """Determine if alert should be sent based on rules"""
        if not rules:
            return True  # Send all alerts if no rules defined
        
        severity = alert_data.get('severity', 'INFO')
        pipeline_name = alert_data.get('pipeline_name', '')
        alert_type = alert_data.get('alert_type', '')
        
        for rule in rules:
            # Check if rule applies to this alert
            if rule.get('pipeline_pattern') and not re.match(rule['pipeline_pattern'], pipeline_name):
                continue
            
            if rule.get('alert_type') and rule['alert_type'] != alert_type:
                continue
            
            # Check severity threshold
            min_severity = rule.get('min_severity', 'INFO')
            if self.severity_levels[severity]['priority'] < self.severity_levels[min_severity]['priority']:
                continue
            
            # Check time-based rules (e.g., business hours only)
            if rule.get('business_hours_only', False):
                current_hour = datetime.now().hour
                if current_hour < 9 or current_hour > 17:  # Outside 9 AM - 5 PM
                    continue
            
            return True
        
        return False
    
    def format_sns_message(self, alert_data: Dict) -> Dict:
        """Format alert data for SNS message"""
        severity = alert_data.get('severity', 'INFO')
        severity_info = self.severity_levels.get(severity, self.severity_levels['INFO'])
        
        subject = f"{severity_info['emoji']} {severity}: {alert_data.get('title', 'Pipeline Alert')}"
        
        message_parts = [
            f"Severity: {severity}",
            f"Pipeline: {alert_data.get('pipeline_name', 'Unknown')}",
            f"Timestamp: {alert_data.get('timestamp', datetime.now(timezone.utc).isoformat())}",
            ""
        ]
        
        if alert_data.get('description'):
            message_parts.extend([
                "Description:",
                alert_data['description'],
                ""
            ])
        
        if alert_data.get('details'):
            message_parts.extend([
                "Details:",
                json.dumps(alert_data['details'], indent=2, default=str),
                ""
            ])
        
        if alert_data.get('actions'):
            message_parts.extend([
                "Recommended Actions:",
                *[f"- {action}" for action in alert_data['actions']],
                ""
            ])
        
        if alert_data.get('dashboard_url'):
            message_parts.append(f"Dashboard: {alert_data['dashboard_url']}")
        
        return {
            'subject': subject,
            'message': '\n'.join(message_parts)
        }
    
    def format_slack_message(self, alert_data: Dict) -> Dict:
        """Format alert data for Slack webhook"""
        severity = alert_data.get('severity', 'INFO')
        severity_info = self.severity_levels.get(severity, self.severity_levels['INFO'])
        
        # Create Slack attachment
        attachment = {
            'color': severity_info['color'],
            'title': f"{severity_info['emoji']} {alert_data.get('title', 'Pipeline Alert')}",
            'fields': [
                {
                    'title': 'Severity',
                    'value': severity,
                    'short': True
                },
                {
                    'title': 'Pipeline',
                    'value': alert_data.get('pipeline_name', 'Unknown'),
                    'short': True
                },
                {
                    'title': 'Timestamp',
                    'value': alert_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
                    'short': False
                }
            ],
            'footer': 'Pipeline Monitoring System',
            'ts': int(datetime.now().timestamp())
        }
        
        if alert_data.get('description'):
            attachment['text'] = alert_data['description']
        
        if alert_data.get('dashboard_url'):
            attachment['actions'] = [
                {
                    'type': 'button',
                    'text': 'View Dashboard',
                    'url': alert_data['dashboard_url']
                }
            ]
        
        return {
            'text': f"Pipeline Alert: {alert_data.get('pipeline_name', 'Unknown')}",
            'attachments': [attachment]
        }
    
    def format_teams_message(self, alert_data: Dict) -> Dict:
        """Format alert data for Microsoft Teams webhook"""
        severity = alert_data.get('severity', 'INFO')
        severity_info = self.severity_levels.get(severity, self.severity_levels['INFO'])
        
        # Create Teams card
        card = {
            '@type': 'MessageCard',
            '@context': 'http://schema.org/extensions',
            'themeColor': severity_info['color'].replace('#', ''),
            'summary': f"{severity}: {alert_data.get('title', 'Pipeline Alert')}",
            'sections': [
                {
                    'activityTitle': f"{severity_info['emoji']} {alert_data.get('title', 'Pipeline Alert')}",
                    'activitySubtitle': f"Pipeline: {alert_data.get('pipeline_name', 'Unknown')}",
                    'facts': [
                        {
                            'name': 'Severity',
                            'value': severity
                        },
                        {
                            'name': 'Timestamp',
                            'value': alert_data.get('timestamp', datetime.now(timezone.utc).isoformat())
                        }
                    ]
                }
            ]
        }
        
        if alert_data.get('description'):
            card['sections'][0]['text'] = alert_data['description']
        
        if alert_data.get('dashboard_url'):
            card['potentialAction'] = [
                {
                    '@type': 'OpenUri',
                    'name': 'View Dashboard',
                    'targets': [
                        {
                            'os': 'default',
                            'uri': alert_data['dashboard_url']
                        }
                    ]
                }
            ]
        
        return card
    
    def send_sns_notification(self, alert_data: Dict) -> bool:
        """Send notification via SNS"""
        if not self.sns_topic_arn:
            logger.warning("SNS topic ARN not configured")
            return False
        
        try:
            formatted_message = self.format_sns_message(alert_data)
            
            response = self.sns_client.publish(
                TopicArn=self.sns_topic_arn,
                Message=formatted_message['message'],
                Subject=formatted_message['subject']
            )
            
            logger.info(f"SNS notification sent: {response['MessageId']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SNS notification: {str(e)}")
            return False
    
    def send_email_notification(self, alert_data: Dict, recipients: List[str]) -> bool:
        """Send email notification via SES"""
        try:
            formatted_message = self.format_sns_message(alert_data)
            
            # Create HTML version
            html_body = f"""
            <html>
            <body>
                <h2 style="color: {self.severity_levels.get(alert_data.get('severity', 'INFO'), {}).get('color', '#000000')}">
                    {formatted_message['subject']}
                </h2>
                <pre>{formatted_message['message']}</pre>
            </body>
            </html>
            """
            
            response = self.ses_client.send_email(
                Source=os.environ.get('SES_FROM_EMAIL', 'noreply@example.com'),
                Destination={'ToAddresses': recipients},
                Message={
                    'Subject': {'Data': formatted_message['subject']},
                    'Body': {
                        'Text': {'Data': formatted_message['message']},
                        'Html': {'Data': html_body}
                    }
                }
            )
            
            logger.info(f"Email notification sent: {response['MessageId']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
            return False
    
    def send_slack_notification(self, alert_data: Dict) -> bool:
        """Send notification to Slack via webhook"""
        if not self.slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
        
        try:
            import urllib.request
            
            slack_message = self.format_slack_message(alert_data)
            
            req = urllib.request.Request(
                self.slack_webhook_url,
                data=json.dumps(slack_message).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    logger.info("Slack notification sent successfully")
                    return True
                else:
                    logger.error(f"Slack notification failed with status: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
            return False
    
    def send_teams_notification(self, alert_data: Dict) -> bool:
        """Send notification to Microsoft Teams via webhook"""
        if not self.teams_webhook_url:
            logger.warning("Teams webhook URL not configured")
            return False
        
        try:
            import urllib.request
            
            teams_message = self.format_teams_message(alert_data)
            
            req = urllib.request.Request(
                self.teams_webhook_url,
                data=json.dumps(teams_message).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    logger.info("Teams notification sent successfully")
                    return True
                else:
                    logger.error(f"Teams notification failed with status: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Teams notification: {str(e)}")
            return False
    
    def update_cloudwatch_metrics(self, alert_data: Dict):
        """Update CloudWatch custom metrics"""
        try:
            severity = alert_data.get('severity', 'INFO')
            pipeline_name = alert_data.get('pipeline_name', 'Unknown')
            
            # Send alert count metric
            self.cloudwatch.put_metric_data(
                Namespace='Pipeline/Alerts',
                MetricData=[
                    {
                        'MetricName': 'AlertCount',
                        'Dimensions': [
                            {
                                'Name': 'Severity',
                                'Value': severity
                            },
                            {
                                'Name': 'Pipeline',
                                'Value': pipeline_name
                            }
                        ],
                        'Value': 1,
                        'Unit': 'Count',
                        'Timestamp': datetime.now(timezone.utc)
                    }
                ]
            )
            
            # Send severity-specific metrics
            severity_metric_name = f'{severity}AlertCount'
            self.cloudwatch.put_metric_data(
                Namespace='Pipeline/Alerts',
                MetricData=[
                    {
                        'MetricName': severity_metric_name,
                        'Dimensions': [
                            {
                                'Name': 'Pipeline',
                                'Value': pipeline_name
                            }
                        ],
                        'Value': 1,
                        'Unit': 'Count',
                        'Timestamp': datetime.now(timezone.utc)
                    }
                ]
            )
            
            logger.info(f"CloudWatch metrics updated for {severity} alert")
            
        except Exception as e:
            logger.error(f"Failed to update CloudWatch metrics: {str(e)}")
    
    def update_dashboard(self, alert_data: Dict):
        """Trigger dashboard update"""
        if not self.dashboard_update_function:
            logger.warning("Dashboard update function not configured")
            return
        
        try:
            payload = {
                'action': 'update_alert_status',
                'alert_data': alert_data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            self.lambda_client.invoke(
                FunctionName=self.dashboard_update_function,
                InvocationType='Event',  # Async invocation
                Payload=json.dumps(payload)
            )
            
            logger.info("Dashboard update triggered")
            
        except Exception as e:
            logger.error(f"Failed to trigger dashboard update: {str(e)}")
    
    def save_notification_history(self, alert_data: Dict, delivery_results: Dict):
        """Save notification delivery history"""
        if not self.history_table:
            return
        
        try:
            history_record = {
                'notification_id': f"notif_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{alert_data.get('pipeline_name', 'unknown')}",
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'alert_data': alert_data,
                'delivery_results': delivery_results,
                'total_channels': len(delivery_results),
                'successful_channels': len([r for r in delivery_results.values() if r]),
                'ttl': int((datetime.now(timezone.utc).timestamp() + (30 * 24 * 3600)))  # 30 days TTL
            }
            
            self.history_table.put_item(Item=history_record)
            logger.info(f"Notification history saved: {history_record['notification_id']}")
            
        except Exception as e:
            logger.error(f"Failed to save notification history: {str(e)}")
    
    @xray_recorder.capture('process_alert')
    def process_alert(self, alert_data: Dict) -> Dict:
        """Process and send alert through multiple channels"""
        with xray_recorder.in_subsegment('process_alert_execution') as subsegment:
            subsegment.put_annotation("pipeline_name", alert_data.get('pipeline_name'))
            subsegment.put_annotation("severity", alert_data.get('severity'))
            
            # Validate required fields
            if not alert_data.get('title') and not alert_data.get('description'):
                raise ValueError("Alert must have either title or description")
            
            # Set default values
            alert_data.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
            alert_data.setdefault('severity', 'INFO')
            alert_data.setdefault('pipeline_name', 'Unknown')
            
            # Get alert rules
            rules = self.get_alert_rules(alert_data.get('pipeline_name'))
            
            # Check if alert should be sent
            if not self.should_send_alert(alert_data, rules):
                logger.info(f"Alert suppressed by rules: {alert_data.get('title')}")
                return {
                    'status': 'suppressed',
                    'reason': 'Alert suppressed by configured rules'
                }
            
            # Send notifications through various channels
            delivery_results = {}
            
            # SNS notification
            with xray_recorder.in_subsegment('send_sns') as sns_subsegment:
                delivery_results['sns'] = self.send_sns_notification(alert_data)
                sns_subsegment.put_metadata('result', delivery_results['sns'])
            
            # Email notification (if recipients specified)
            email_recipients = alert_data.get('email_recipients', [])
            if email_recipients:
                with xray_recorder.in_subsegment('send_email') as email_subsegment:
                    delivery_results['email'] = self.send_email_notification(alert_data, email_recipients)
                    email_subsegment.put_metadata('result', delivery_results['email'])
            
            # Slack notification
            with xray_recorder.in_subsegment('send_slack') as slack_subsegment:
                delivery_results['slack'] = self.send_slack_notification(alert_data)
                slack_subsegment.put_metadata('result', delivery_results['slack'])
            
            # Teams notification
            with xray_recorder.in_subsegment('send_teams') as teams_subsegment:
                delivery_results['teams'] = self.send_teams_notification(alert_data)
                teams_subsegment.put_metadata('result', delivery_results['teams'])
            
            # Update CloudWatch metrics
            self.update_cloudwatch_metrics(alert_data)
            
            # Update dashboard
            self.update_dashboard(alert_data)
            
            # Save notification history
            self.save_notification_history(alert_data, delivery_results)
            
            # Calculate success rate
            successful_channels = len([r for r in delivery_results.values() if r])
            total_channels = len([r for r in delivery_results.values() if r is not None])
            
            result = {
                'status': 'success' if successful_channels > 0 else 'failed',
                'delivery_results': delivery_results,
                'successful_channels': successful_channels,
                'total_channels': total_channels,
                'success_rate': (successful_channels / total_channels * 100) if total_channels > 0 else 0
            }
            
            logger.info(f"Alert processed: {alert_data.get('title')}, Success rate: {result['success_rate']:.1f}%")
            
            subsegment.put_metadata('final_result', result)
            return result
    
    def process_pipeline_status_update(self, status_data: Dict) -> Dict:
        """Process pipeline status updates and generate appropriate alerts"""
        pipeline_name = status_data.get('pipeline_name', 'Unknown')
        status = status_data.get('status', 'UNKNOWN')
        
        # Generate alert based on status
        alert_data = {
            'pipeline_name': pipeline_name,
            'alert_type': 'pipeline_status',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if status == 'COMPLETED':
            alert_data.update({
                'severity': 'INFO',
                'title': f'Pipeline Completed Successfully',
                'description': f'Pipeline {pipeline_name} has completed successfully.',
                'details': status_data
            })
        elif status == 'FAILED':
            alert_data.update({
                'severity': 'ERROR',
                'title': f'Pipeline Failed',
                'description': f'Pipeline {pipeline_name} has failed.',
                'details': status_data,
                'actions': [
                    'Check pipeline logs for error details',
                    'Verify data source connectivity',
                    'Review pipeline configuration'
                ]
            })
        elif status == 'PARTIAL':
            alert_data.update({
                'severity': 'WARNING',
                'title': f'Pipeline Partially Completed',
                'description': f'Pipeline {pipeline_name} completed with some failures.',
                'details': status_data,
                'actions': [
                    'Review failed job details',
                    'Check data quality reports',
                    'Consider rerunning failed jobs'
                ]
            })
        else:
            alert_data.update({
                'severity': 'INFO',
                'title': f'Pipeline Status Update',
                'description': f'Pipeline {pipeline_name} status: {status}',
                'details': status_data
            })
        
        return self.process_alert(alert_data)


@xray_recorder.capture('lambda_handler')
def lambda_handler(event, context):
    """AWS Lambda handler function"""
    extra_info = {
        'aws_request_id': getattr(context, 'aws_request_id', 'unknown'),
        'function_name': getattr(context, 'function_name', 'notification-alerting')
    }
    logger.info(f"Notification service started with event: {json.dumps(event, default=str)}", extra=extra_info)
    
    try:
        service = NotificationAlertingService()
        
        # Determine the type of notification request
        request_type = event.get('request_type', 'alert')
        
        if request_type == 'alert':
            # Direct alert processing
            alert_data = event.get('alert_data')
            if not alert_data:
                raise ValueError("alert_data is required for alert request type")
            
            result = service.process_alert(alert_data)
            
        elif request_type == 'pipeline_status':
            # Pipeline status update processing
            status_data = event.get('status_data')
            if not status_data:
                raise ValueError("status_data is required for pipeline_status request type")
            
            result = service.process_pipeline_status_update(status_data)
            
        else:
            raise ValueError(f"Unsupported request type: {request_type}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str)
        }
        
    except Exception as e:
        error_msg = f"Notification service failed: {str(e)}"
        logger.error(error_msg, extra=extra_info)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'failed',
                'error': error_msg,
                'error_type': type(e).__name__
            })
        }
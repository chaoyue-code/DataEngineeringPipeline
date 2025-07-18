"""
Advanced Error Handling and Retry Mechanisms

This module implements exponential backoff retry logic for transient failures,
dead letter queue handling for persistent failures, and comprehensive logging
and monitoring integration.
"""

import logging
import time
import random
import json
import boto3
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
from botocore.exceptions import ClientError
import snowflake.connector.errors as sf_errors

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """Classification of error types for appropriate handling"""
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    CONFIGURATION = "configuration"
    DATA_QUALITY = "data_quality"
    RESOURCE_LIMIT = "resource_limit"
    AUTHENTICATION = "authentication"

class RetryStrategy:
    """Implements various retry strategies with exponential backoff"""
    
    def __init__(self, 
                 max_retries: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 backoff_multiplier: float = 2.0,
                 jitter: bool = True):
        """
        Initialize retry strategy
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            backoff_multiplier: Multiplier for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        delay = self.base_delay * (self.backoff_multiplier ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add random jitter (±25% of delay)
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if operation should be retried"""
        if attempt >= self.max_retries:
            return False
        
        error_type = ErrorClassifier.classify_error(error)
        
        # Only retry transient errors and some resource limit errors
        return error_type in [ErrorType.TRANSIENT, ErrorType.RESOURCE_LIMIT]

class ErrorClassifier:
    """Classifies errors to determine appropriate handling strategy"""
    
    @staticmethod
    def classify_error(error: Exception) -> ErrorType:
        """
        Classify error type based on exception details
        
        Args:
            error: Exception to classify
            
        Returns:
            ErrorType enum value
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Snowflake-specific errors
        if isinstance(error, sf_errors.DatabaseError):
            if 'timeout' in error_str or 'connection' in error_str:
                return ErrorType.TRANSIENT
            elif 'authentication' in error_str or 'credential' in error_str:
                return ErrorType.AUTHENTICATION
            elif 'warehouse' in error_str and 'suspended' in error_str:
                return ErrorType.RESOURCE_LIMIT
            else:
                return ErrorType.PERMANENT
        
        # AWS-specific errors
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', '')
            
            if error_code in ['Throttling', 'ThrottlingException', 'RequestLimitExceeded']:
                return ErrorType.RESOURCE_LIMIT
            elif error_code in ['ServiceUnavailable', 'InternalError']:
                return ErrorType.TRANSIENT
            elif error_code in ['AccessDenied', 'UnauthorizedOperation']:
                return ErrorType.AUTHENTICATION
            elif error_code in ['InvalidParameterValue', 'ValidationException']:
                return ErrorType.CONFIGURATION
            else:
                return ErrorType.PERMANENT
        
        # Network and connection errors
        if any(keyword in error_str for keyword in ['timeout', 'connection', 'network', 'dns']):
            return ErrorType.TRANSIENT
        
        # Memory and resource errors
        if any(keyword in error_str for keyword in ['memory', 'resource', 'limit']):
            return ErrorType.RESOURCE_LIMIT
        
        # Configuration errors
        if any(keyword in error_str for keyword in ['config', 'parameter', 'invalid']):
            return ErrorType.CONFIGURATION
        
        # Default to permanent for unknown errors
        return ErrorType.PERMANENT

class DeadLetterQueueHandler:
    """Handles persistent failures using SQS Dead Letter Queue"""
    
    def __init__(self, dlq_url: str, region_name: str = None):
        """
        Initialize DLQ handler
        
        Args:
            dlq_url: SQS Dead Letter Queue URL
            region_name: AWS region name
        """
        self.dlq_url = dlq_url
        self.sqs = boto3.client('sqs', region_name=region_name)
    
    def send_to_dlq(self, 
                    original_event: Dict,
                    error_details: Dict,
                    retry_count: int) -> bool:
        """
        Send failed message to Dead Letter Queue
        
        Args:
            original_event: Original Lambda event that failed
            error_details: Details about the error
            retry_count: Number of retry attempts made
            
        Returns:
            True if message was sent successfully
        """
        try:
            dlq_message = {
                'original_event': original_event,
                'error_details': error_details,
                'retry_count': retry_count,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'lambda_request_id': error_details.get('lambda_request_id'),
                'function_name': error_details.get('function_name')
            }
            
            response = self.sqs.send_message(
                QueueUrl=self.dlq_url,
                MessageBody=json.dumps(dlq_message, default=str),
                MessageAttributes={
                    'ErrorType': {
                        'StringValue': error_details.get('error_type', 'unknown'),
                        'DataType': 'String'
                    },
                    'RetryCount': {
                        'StringValue': str(retry_count),
                        'DataType': 'Number'
                    }
                }
            )
            
            logger.info(f"Sent message to DLQ: {response['MessageId']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to DLQ: {str(e)}")
            return False

class CircuitBreaker:
    """Implements circuit breaker pattern to prevent cascading failures"""
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds before attempting recovery
            expected_exception: Exception type to monitor
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or raises exception
        """
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful execution"""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'

class ComprehensiveErrorHandler:
    """Main error handler that orchestrates all error handling mechanisms"""
    
    def __init__(self, 
                 retry_strategy: RetryStrategy = None,
                 dlq_handler: DeadLetterQueueHandler = None,
                 circuit_breaker: CircuitBreaker = None,
                 cloudwatch_client = None):
        """
        Initialize comprehensive error handler
        
        Args:
            retry_strategy: Retry strategy instance
            dlq_handler: Dead letter queue handler
            circuit_breaker: Circuit breaker instance
            cloudwatch_client: CloudWatch client for metrics
        """
        self.retry_strategy = retry_strategy or RetryStrategy()
        self.dlq_handler = dlq_handler
        self.circuit_breaker = circuit_breaker
        self.cloudwatch = cloudwatch_client or boto3.client('cloudwatch')
        
    def execute_with_retry(self, 
                          func: Callable,
                          *args,
                          context: Dict = None,
                          **kwargs) -> Tuple[Any, Dict]:
        """
        Execute function with comprehensive error handling
        
        Args:
            func: Function to execute
            *args: Function arguments
            context: Execution context (Lambda context, event, etc.)
            **kwargs: Function keyword arguments
            
        Returns:
            Tuple of (result, execution_metadata)
        """
        context = context or {}
        execution_metadata = {
            'attempts': 0,
            'total_duration': 0,
            'errors': [],
            'success': False
        }
        
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.retry_strategy.max_retries + 1):
            execution_metadata['attempts'] = attempt + 1
            attempt_start = time.time()
            
            try:
                logger.info(f"Executing function, attempt {attempt + 1}")
                
                # Use circuit breaker if available
                if self.circuit_breaker:
                    result = self.circuit_breaker.call(func, *args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                execution_metadata['success'] = True
                execution_metadata['total_duration'] = time.time() - start_time
                
                # Log success metrics
                self._log_success_metrics(execution_metadata, context)
                
                logger.info(f"Function executed successfully on attempt {attempt + 1}")
                return result, execution_metadata
                
            except Exception as e:
                last_error = e
                attempt_duration = time.time() - attempt_start
                
                error_type = ErrorClassifier.classify_error(e)
                error_details = {
                    'error_type': error_type.value,
                    'error_message': str(e),
                    'error_class': type(e).__name__,
                    'attempt': attempt + 1,
                    'attempt_duration': attempt_duration
                }
                
                execution_metadata['errors'].append(error_details)
                
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                
                # Check if we should retry
                if not self.retry_strategy.should_retry(attempt, e):
                    logger.error(f"Not retrying due to error type: {error_type.value}")
                    break
                
                if attempt < self.retry_strategy.max_retries:
                    delay = self.retry_strategy.calculate_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
        
        # All retries exhausted
        execution_metadata['total_duration'] = time.time() - start_time
        
        # Send to DLQ if handler is available
        if self.dlq_handler and context:
            self._handle_persistent_failure(context, execution_metadata, last_error)
        
        # Log failure metrics
        self._log_failure_metrics(execution_metadata, context)
        
        # Re-raise the last error
        raise last_error
    
    def _handle_persistent_failure(self, 
                                 context: Dict,
                                 execution_metadata: Dict,
                                 error: Exception):
        """Handle persistent failures by sending to DLQ"""
        try:
            error_details = {
                'error_message': str(error),
                'error_type': ErrorClassifier.classify_error(error).value,
                'error_class': type(error).__name__,
                'execution_metadata': execution_metadata,
                'lambda_request_id': context.get('aws_request_id'),
                'function_name': context.get('function_name')
            }
            
            original_event = context.get('event', {})
            retry_count = execution_metadata['attempts']
            
            success = self.dlq_handler.send_to_dlq(original_event, error_details, retry_count)
            
            if success:
                logger.info("Successfully sent failed message to DLQ")
            else:
                logger.error("Failed to send message to DLQ")
                
        except Exception as e:
            logger.error(f"Error handling persistent failure: {str(e)}")
    
    def _log_success_metrics(self, execution_metadata: Dict, context: Dict):
        """Log success metrics to CloudWatch"""
        try:
            self.cloudwatch.put_metric_data(
                Namespace='SnowflakeExtractor',
                MetricData=[
                    {
                        'MetricName': 'ExecutionSuccess',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {
                                'Name': 'FunctionName',
                                'Value': context.get('function_name', 'unknown')
                            }
                        ]
                    },
                    {
                        'MetricName': 'ExecutionDuration',
                        'Value': execution_metadata['total_duration'],
                        'Unit': 'Seconds'
                    },
                    {
                        'MetricName': 'RetryAttempts',
                        'Value': execution_metadata['attempts'],
                        'Unit': 'Count'
                    }
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to log success metrics: {str(e)}")
    
    def _log_failure_metrics(self, execution_metadata: Dict, context: Dict):
        """Log failure metrics to CloudWatch"""
        try:
            self.cloudwatch.put_metric_data(
                Namespace='SnowflakeExtractor',
                MetricData=[
                    {
                        'MetricName': 'ExecutionFailure',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {
                                'Name': 'FunctionName',
                                'Value': context.get('function_name', 'unknown')
                            }
                        ]
                    },
                    {
                        'MetricName': 'ExecutionDuration',
                        'Value': execution_metadata['total_duration'],
                        'Unit': 'Seconds'
                    },
                    {
                        'MetricName': 'RetryAttempts',
                        'Value': execution_metadata['attempts'],
                        'Unit': 'Count'
                    }
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to log failure metrics: {str(e)}")

class MonitoringIntegration:
    """Integrates with AWS monitoring services for comprehensive observability"""
    
    def __init__(self, 
                 cloudwatch_client = None,
                 sns_client = None,
                 alert_topic_arn: str = None):
        """
        Initialize monitoring integration
        
        Args:
            cloudwatch_client: CloudWatch client
            sns_client: SNS client for alerts
            alert_topic_arn: SNS topic ARN for alerts
        """
        self.cloudwatch = cloudwatch_client or boto3.client('cloudwatch')
        self.sns = sns_client or boto3.client('sns')
        self.alert_topic_arn = alert_topic_arn
    
    def send_alert(self, 
                   alert_type: str,
                   message: str,
                   details: Dict = None):
        """
        Send alert notification
        
        Args:
            alert_type: Type of alert (ERROR, WARNING, INFO)
            message: Alert message
            details: Additional alert details
        """
        if not self.alert_topic_arn:
            logger.warning("No alert topic configured, skipping alert")
            return
        
        try:
            alert_payload = {
                'alert_type': alert_type,
                'message': message,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'details': details or {}
            }
            
            self.sns.publish(
                TopicArn=self.alert_topic_arn,
                Subject=f"Snowflake Extractor Alert: {alert_type}",
                Message=json.dumps(alert_payload, indent=2, default=str)
            )
            
            logger.info(f"Sent {alert_type} alert: {message}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {str(e)}")
    
    def log_custom_metric(self, 
                         metric_name: str,
                         value: float,
                         unit: str = 'Count',
                         dimensions: List[Dict] = None):
        """
        Log custom metric to CloudWatch
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Metric unit
            dimensions: Metric dimensions
        """
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit
            }
            
            if dimensions:
                metric_data['Dimensions'] = dimensions
            
            self.cloudwatch.put_metric_data(
                Namespace='SnowflakeExtractor/Custom',
                MetricData=[metric_data]
            )
            
        except Exception as e:
            logger.warning(f"Failed to log custom metric {metric_name}: {str(e)}")
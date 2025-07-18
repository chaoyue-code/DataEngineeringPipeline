# Variables for CloudWatch Monitoring Module

variable "project_name" {
  description = "Name of the project for resource naming"
  type        = string
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

# Lambda Function Names
variable "snowflake_extractor_function_name" {
  description = "Name of the Snowflake extractor Lambda function"
  type        = string
}

variable "pipeline_orchestrator_function_name" {
  description = "Name of the pipeline orchestrator Lambda function"
  type        = string
}

variable "data_quality_monitor_function_name" {
  description = "Name of the data quality monitor Lambda function"
  type        = string
}

# Glue Job Names
variable "bronze_to_silver_job_name" {
  description = "Name of the bronze to silver Glue ETL job"
  type        = string
}

variable "silver_to_gold_job_name" {
  description = "Name of the silver to gold Glue ETL job"
  type        = string
}

# S3 Bucket Names
variable "data_lake_bucket_name" {
  description = "Name of the S3 data lake bucket"
  type        = string
}

# SageMaker Resources
variable "sagemaker_endpoint_name" {
  description = "Name of the SageMaker inference endpoint"
  type        = string
  default     = ""
}

# SNS Topic ARNs for Alerting (optional - will create if not provided)
variable "critical_sns_topic_arn" {
  description = "ARN of SNS topic for critical alerts (optional - will create if empty)"
  type        = string
  default     = ""
}

variable "warning_sns_topic_arn" {
  description = "ARN of SNS topic for warning alerts (optional - will create if empty)"
  type        = string
  default     = ""
}

variable "info_sns_topic_arn" {
  description = "ARN of SNS topic for info notifications (optional - will create if empty)"
  type        = string
  default     = ""
}

# SNS Encryption
variable "sns_kms_key_id" {
  description = "KMS key ID for SNS topic encryption"
  type        = string
  default     = "alias/aws/sns"
}

# Alert Subscription Configuration
variable "critical_alert_emails" {
  description = "List of email addresses for critical alerts"
  type        = list(string)
  default     = []
}

variable "critical_alert_phone_numbers" {
  description = "List of phone numbers for critical SMS alerts (format: +1234567890)"
  type        = list(string)
  default     = []
}

variable "warning_alert_emails" {
  description = "List of email addresses for warning alerts"
  type        = list(string)
  default     = []
}

variable "info_notification_emails" {
  description = "List of email addresses for info notifications"
  type        = list(string)
  default     = []
}

variable "escalation_alert_emails" {
  description = "List of email addresses for escalation alerts"
  type        = list(string)
  default     = []
}

variable "escalation_alert_phone_numbers" {
  description = "List of phone numbers for escalation SMS alerts (format: +1234567890)"
  type        = list(string)
  default     = []
}

# Third-party Integration
variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  default     = ""
  sensitive   = true
}

variable "pagerduty_endpoint" {
  description = "PagerDuty integration endpoint URL"
  type        = string
  default     = ""
  sensitive   = true
}

# CloudWatch Configuration
variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 30
}

variable "metric_filter_enabled" {
  description = "Enable custom metric filters"
  type        = bool
  default     = true
}

# Dashboard Configuration
variable "dashboard_period_seconds" {
  description = "Default period for dashboard metrics in seconds"
  type        = number
  default     = 300
}

# Alarm Configuration
variable "alarm_evaluation_periods" {
  description = "Number of periods to evaluate for alarms"
  type        = number
  default     = 2
}

variable "lambda_error_threshold" {
  description = "Threshold for Lambda error alarms"
  type        = number
  default     = 5
}

variable "data_quality_threshold" {
  description = "Minimum acceptable data quality score"
  type        = number
  default     = 0.8
}

# Cost Monitoring
variable "enable_cost_monitoring" {
  description = "Enable cost monitoring and alerting"
  type        = bool
  default     = true
}

variable "daily_cost_threshold" {
  description = "Daily cost threshold for alerts (USD)"
  type        = number
  default     = 100
}

# Performance Monitoring
variable "lambda_duration_threshold_ms" {
  description = "Lambda duration threshold in milliseconds"
  type        = number
  default     = 30000
}

variable "glue_job_duration_threshold_minutes" {
  description = "Glue job duration threshold in minutes"
  type        = number
  default     = 60
}

# Tags
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# X-Ray Tracing Configuration
variable "enable_xray_tracing" {
  description = "Enable AWS X-Ray tracing for distributed tracing"
  type        = bool
  default     = true
}

variable "xray_sampling_rate" {
  description = "X-Ray sampling rate (0.0 to 1.0)"
  type        = number
  default     = 0.1
}

# Custom Metrics Configuration
variable "custom_metrics_namespace" {
  description = "Namespace for custom CloudWatch metrics"
  type        = string
  default     = "Pipeline"
}

variable "enable_detailed_monitoring" {
  description = "Enable detailed monitoring for all resources"
  type        = bool
  default     = true
}

# Additional Alerting Thresholds
variable "s3_storage_threshold_bytes" {
  description = "S3 storage threshold in bytes for critical alerts"
  type        = number
  default     = 1073741824000 # 1TB
}

variable "pipeline_latency_threshold_ms" {
  description = "Pipeline latency threshold in milliseconds"
  type        = number
  default     = 300000 # 5 minutes
}

variable "sagemaker_error_threshold" {
  description = "SageMaker endpoint error threshold"
  type        = number
  default     = 10
}

# Escalation Configuration
variable "escalation_threshold_minutes" {
  description = "Time in minutes before escalating persistent alarms"
  type        = number
  default     = 30
}

# Auto-Recovery Configuration
variable "enable_auto_recovery" {
  description = "Enable automated recovery procedures"
  type        = bool
  default     = true
}

variable "max_recovery_attempts" {
  description = "Maximum number of auto-recovery attempts per day"
  type        = number
  default     = 3
}

# SLA Monitoring
variable "sla_latency_threshold_ms" {
  description = "SLA for pipeline end-to-end latency in milliseconds"
  type        = number
  default     = 600000 # 10 minutes
}

variable "sla_data_freshness_threshold_hours" {
  description = "SLA for data freshness in hours"
  type        = number
  default     = 24
}

variable "sla_uptime_percentage_threshold" {
  description = "SLA for pipeline uptime percentage"
  type        = number
  default     = 99.9
}

# Lambda Auto-Scaling
variable "enable_lambda_autoscaling" {
  description = "Enable auto-scaling for Lambda provisioned concurrency"
  type        = bool
  default     = false
}

variable "lambda_provisioned_concurrency" {
  description = "Initial provisioned concurrency for the Lambda function"
  type        = number
  default     = 10
}

variable "lambda_min_concurrency" {
  description = "Minimum provisioned concurrency for Lambda auto-scaling"
  type        = number
  default     = 10
}

variable "lambda_max_concurrency" {
  description = "Maximum provisioned concurrency for Lambda auto-scaling"
  type        = number
  default     = 100
}

variable "snowflake_extractor_function_alias" {
  description = "Alias of the Snowflake extractor Lambda function"
  type        = string
  default     = "live"
}

# SageMaker Auto-Scaling
variable "enable_sagemaker_autoscaling" {
  description = "Enable auto-scaling for the SageMaker endpoint"
  type        = bool
  default     = false
}

variable "sagemaker_max_instances" {
  description = "Maximum number of instances for the SageMaker endpoint"
  type        = number
  default     = 10
}

variable "sagemaker_min_instances" {
  description = "Minimum number of instances for the SageMaker endpoint"
  type        = number
  default     = 1
}

variable "sagemaker_invocations_per_instance" {
  description = "Target number of invocations per instance for SageMaker auto-scaling"
  type        = number
  default     = 100
}

# Failover
variable "enable_failover" {
  description = "Enable Route 53 DNS failover for the SageMaker endpoint"
  type        = bool
  default     = false
}

variable "route53_zone_id" {
  description = "Route 53 zone ID for DNS failover"
  type        = string
  default     = ""
}

variable "domain_name" {
  description = "Domain name for the SageMaker endpoint"
  type        = string
  default     = ""
}

variable "sagemaker_endpoint_url" {
  description = "URL of the primary SageMaker endpoint"
  type        = string
  default     = ""
}

variable "secondary_sagemaker_endpoint_url" {
  description = "URL of the secondary SageMaker endpoint in the failover region"
  type        = string
  default     = ""
}
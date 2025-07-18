# Example usage of the monitoring module with alerting system
# This example shows how to configure the comprehensive alerting and notification system

module "pipeline_monitoring" {
  source = "../"

  # Basic Configuration
  project_name = "my-snowflake-pipeline"
  aws_region   = "us-east-1"
  environment  = "production"

  # Lambda Function Names
  snowflake_extractor_function_name    = "my-snowflake-extractor"
  pipeline_orchestrator_function_name  = "my-pipeline-orchestrator"
  data_quality_monitor_function_name   = "my-data-quality-monitor"

  # Glue Job Names
  bronze_to_silver_job_name = "bronze-to-silver-etl"
  silver_to_gold_job_name   = "silver-to-gold-etl"

  # S3 Configuration
  data_lake_bucket_name = "my-data-lake-bucket"

  # SageMaker Configuration (optional)
  sagemaker_endpoint_name = "my-ml-endpoint"

  # ============================================================================
  # ALERTING CONFIGURATION
  # ============================================================================

  # Critical Alert Recipients (for pipeline failures, data corruption)
  critical_alert_emails = [
    "oncall-engineer@company.com",
    "data-team-lead@company.com"
  ]

  critical_alert_phone_numbers = [
    "+1234567890",  # On-call engineer
    "+0987654321"   # Data team lead
  ]

  # Warning Alert Recipients (for performance issues, cost thresholds)
  warning_alert_emails = [
    "data-team@company.com",
    "devops-team@company.com"
  ]

  # Info Notification Recipients (for successful completions, reports)
  info_notification_emails = [
    "data-team@company.com",
    "business-stakeholders@company.com"
  ]

  # Escalation Alert Recipients (for persistent issues)
  escalation_alert_emails = [
    "engineering-manager@company.com",
    "cto@company.com"
  ]

  escalation_alert_phone_numbers = [
    "+1111111111"  # Engineering manager
  ]

  # Third-party Integrations
  slack_webhook_url = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
  pagerduty_endpoint = "https://events.pagerduty.com/integration/YOUR_INTEGRATION_KEY/enqueue"

  # ============================================================================
  # ALERTING THRESHOLDS
  # ============================================================================

  # Lambda Configuration
  lambda_error_threshold        = 3    # Number of errors before alerting
  lambda_duration_threshold_ms  = 60000 # 1 minute timeout threshold

  # Glue Configuration
  glue_job_duration_threshold_minutes = 120 # 2 hours

  # Data Quality Configuration
  data_quality_threshold = 0.85 # Minimum acceptable quality score (85%)

  # Storage Configuration
  s3_storage_threshold_bytes = 2147483648000 # 2TB threshold

  # Performance Configuration
  pipeline_latency_threshold_ms = 600000 # 10 minutes

  # SageMaker Configuration
  sagemaker_error_threshold = 5 # Number of endpoint errors

  # Cost Configuration
  enable_cost_monitoring = true
  daily_cost_threshold   = 200 # $200 per day

  # ============================================================================
  # ESCALATION CONFIGURATION
  # ============================================================================

  # Escalation timing (how long to wait before escalating)
  escalation_threshold_minutes = 45 # Escalate after 45 minutes in ALARM state

  # Auto-recovery configuration
  enable_auto_recovery    = true
  max_recovery_attempts   = 5 # Maximum attempts per day

  # ============================================================================
  # MONITORING CONFIGURATION
  # ============================================================================

  # Log retention
  log_retention_days = 30

  # CloudWatch configuration
  alarm_evaluation_periods = 2
  enable_detailed_monitoring = true

  # X-Ray tracing
  enable_xray_tracing = true
  xray_sampling_rate  = 0.1 # 10% sampling

  # Encryption
  sns_kms_key_id = "alias/aws/sns"

  # Tags
  tags = {
    Environment = "production"
    Project     = "snowflake-pipeline"
    Owner       = "data-team"
    CostCenter  = "engineering"
  }
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "monitoring_dashboard_urls" {
  description = "URLs for CloudWatch dashboards"
  value = {
    pipeline_overview = module.pipeline_monitoring.pipeline_overview_dashboard_url
    data_quality     = module.pipeline_monitoring.data_quality_dashboard_url
    cost_performance = module.pipeline_monitoring.cost_performance_dashboard_url
  }
}

output "sns_topic_arns" {
  description = "SNS topic ARNs for alerting"
  value       = module.pipeline_monitoring.sns_topic_arns
}

output "alerting_lambda_functions" {
  description = "Lambda functions for alerting system"
  value       = module.pipeline_monitoring.alerting_lambda_functions
}

output "critical_alarms" {
  description = "Critical CloudWatch alarms"
  value       = module.pipeline_monitoring.alerting_alarms
}

output "escalation_config" {
  description = "Escalation system configuration"
  value       = module.pipeline_monitoring.escalation_configuration
}

# ============================================================================
# ADDITIONAL SNS TOPIC POLICIES (Optional)
# ============================================================================

# Example: Allow cross-account access to SNS topics
resource "aws_sns_topic_policy" "critical_alerts_policy" {
  arn = module.pipeline_monitoring.sns_topic_arns.critical_alerts

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCrossAccountPublish"
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::ACCOUNT-ID:root"  # Replace with actual account ID
          ]
        }
        Action = [
          "sns:Publish"
        ]
        Resource = module.pipeline_monitoring.sns_topic_arns.critical_alerts
        Condition = {
          StringEquals = {
            "sns:Protocol" = ["email", "sms", "https"]
          }
        }
      }
    ]
  })
}

# ============================================================================
# CLOUDWATCH ALARM ACTIONS (Optional customization)
# ============================================================================

# Example: Custom alarm for specific business metric
resource "aws_cloudwatch_metric_alarm" "business_sla_violation" {
  alarm_name          = "business-sla-violation"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "pipeline_sla_violation_count"
  namespace           = "Pipeline/Business"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Business SLA violation detected"

  alarm_actions = [
    module.pipeline_monitoring.sns_topic_arns.critical_alerts
  ]

  ok_actions = [
    module.pipeline_monitoring.sns_topic_arns.info_notifications
  ]

  tags = {
    Environment = "production"
    AlertType   = "BusinessCritical"
  }
}

# ============================================================================
# INTEGRATION WITH EXTERNAL SYSTEMS
# ============================================================================

# Example: Lambda function to integrate with external ticketing system
resource "aws_lambda_function" "ticket_integration" {
  filename         = "ticket_integration.zip"
  function_name    = "pipeline-ticket-integration"
  role            = aws_iam_role.ticket_integration_role.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 60

  environment {
    variables = {
      JIRA_URL    = "https://your-company.atlassian.net"
      JIRA_TOKEN  = var.jira_api_token  # Store in AWS Secrets Manager
    }
  }
}

resource "aws_iam_role" "ticket_integration_role" {
  name = "pipeline-ticket-integration-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Subscribe the ticket integration Lambda to critical alerts
resource "aws_sns_topic_subscription" "ticket_integration" {
  topic_arn = module.pipeline_monitoring.sns_topic_arns.critical_alerts
  protocol  = "lambda"
  endpoint  = aws_lambda_function.ticket_integration.arn
}

resource "aws_lambda_permission" "allow_sns_ticket_integration" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ticket_integration.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = module.pipeline_monitoring.sns_topic_arns.critical_alerts
}
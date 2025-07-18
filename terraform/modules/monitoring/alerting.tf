# Alerting and Notification System
# This file implements task 7.2: Create SNS topics and subscriptions for different alert types,
# Write CloudWatch alarms for critical pipeline metrics, and implement escalation procedures

# ============================================================================
# SNS Topics for Different Alert Types
# ============================================================================

# Critical Alerts - Pipeline failures, data corruption, security issues
resource "aws_sns_topic" "critical_alerts" {
  name         = "${var.project_name}-critical-alerts"
  display_name = "Critical Pipeline Alerts"

  # Enable message encryption
  kms_master_key_id = var.sns_kms_key_id

  # Delivery policy for retries
  delivery_policy = jsonencode({
    "http" : {
      "defaultHealthyRetryPolicy" : {
        "minDelayTarget" : 20,
        "maxDelayTarget" : 20,
        "numRetries" : 3,
        "numMaxDelayRetries" : 0,
        "numMinDelayRetries" : 0,
        "numNoDelayRetries" : 0,
        "backoffFunction" : "linear"
      },
      "disableSubscriptionOverrides" : false
    }
  })

  tags = merge(var.tags, {
    AlertType = "Critical"
    Purpose   = "Pipeline Critical Alerts"
  })
}

# Warning Alerts - Performance degradation, cost thresholds, capacity issues
resource "aws_sns_topic" "warning_alerts" {
  name         = "${var.project_name}-warning-alerts"
  display_name = "Warning Pipeline Alerts"

  kms_master_key_id = var.sns_kms_key_id

  delivery_policy = jsonencode({
    "http" : {
      "defaultHealthyRetryPolicy" : {
        "minDelayTarget" : 20,
        "maxDelayTarget" : 20,
        "numRetries" : 3,
        "numMaxDelayRetries" : 0,
        "numMinDelayRetries" : 0,
        "numNoDelayRetries" : 0,
        "backoffFunction" : "linear"
      },
      "disableSubscriptionOverrides" : false
    }
  })

  tags = merge(var.tags, {
    AlertType = "Warning"
    Purpose   = "Pipeline Warning Alerts"
  })
}

# Info Notifications - Successful completions, scheduled reports, status updates
resource "aws_sns_topic" "info_notifications" {
  name         = "${var.project_name}-info-notifications"
  display_name = "Pipeline Info Notifications"

  kms_master_key_id = var.sns_kms_key_id

  tags = merge(var.tags, {
    AlertType = "Info"
    Purpose   = "Pipeline Info Notifications"
  })
}

# Escalation Topic - For persistent issues requiring immediate attention
resource "aws_sns_topic" "escalation_alerts" {
  name         = "${var.project_name}-escalation-alerts"
  display_name = "Pipeline Escalation Alerts"

  kms_master_key_id = var.sns_kms_key_id

  delivery_policy = jsonencode({
    "http" : {
      "defaultHealthyRetryPolicy" : {
        "minDelayTarget" : 10,
        "maxDelayTarget" : 10,
        "numRetries" : 5,
        "numMaxDelayRetries" : 0,
        "numMinDelayRetries" : 0,
        "numNoDelayRetries" : 0,
        "backoffFunction" : "exponential"
      },
      "disableSubscriptionOverrides" : false
    }
  })

  tags = merge(var.tags, {
    AlertType = "Escalation"
    Purpose   = "Pipeline Escalation Alerts"
  })
}

# ============================================================================
# SNS Topic Subscriptions for Different Alert Types
# ============================================================================

# Critical Alert Subscriptions
resource "aws_sns_topic_subscription" "critical_email" {
  count     = length(var.critical_alert_emails)
  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "email"
  endpoint  = var.critical_alert_emails[count.index]

  # Require confirmation for email subscriptions
  confirmation_timeout_in_minutes = 5
}

resource "aws_sns_topic_subscription" "critical_sms" {
  count     = length(var.critical_alert_phone_numbers)
  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "sms"
  endpoint  = var.critical_alert_phone_numbers[count.index]
}

resource "aws_sns_topic_subscription" "critical_slack" {
  count     = var.slack_webhook_url != "" ? 1 : 0
  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "https"
  endpoint  = var.slack_webhook_url

  # Slack webhook configuration
  delivery_policy = jsonencode({
    "http" : {
      "defaultHealthyRetryPolicy" : {
        "minDelayTarget" : 20,
        "maxDelayTarget" : 20,
        "numRetries" : 3,
        "numMaxDelayRetries" : 0,
        "numMinDelayRetries" : 0,
        "numNoDelayRetries" : 0,
        "backoffFunction" : "linear"
      }
    }
  })
}

# Warning Alert Subscriptions
resource "aws_sns_topic_subscription" "warning_email" {
  count     = length(var.warning_alert_emails)
  topic_arn = aws_sns_topic.warning_alerts.arn
  protocol  = "email"
  endpoint  = var.warning_alert_emails[count.index]
}

resource "aws_sns_topic_subscription" "warning_slack" {
  count     = var.slack_webhook_url != "" ? 1 : 0
  topic_arn = aws_sns_topic.warning_alerts.arn
  protocol  = "https"
  endpoint  = var.slack_webhook_url
}

# Info Notification Subscriptions
resource "aws_sns_topic_subscription" "info_email" {
  count     = length(var.info_notification_emails)
  topic_arn = aws_sns_topic.info_notifications.arn
  protocol  = "email"
  endpoint  = var.info_notification_emails[count.index]
}

# Escalation Alert Subscriptions
resource "aws_sns_topic_subscription" "escalation_email" {
  count     = length(var.escalation_alert_emails)
  topic_arn = aws_sns_topic.escalation_alerts.arn
  protocol  = "email"
  endpoint  = var.escalation_alert_emails[count.index]
}

resource "aws_sns_topic_subscription" "escalation_sms" {
  count     = length(var.escalation_alert_phone_numbers)
  topic_arn = aws_sns_topic.escalation_alerts.arn
  protocol  = "sms"
  endpoint  = var.escalation_alert_phone_numbers[count.index]
}

# PagerDuty integration for escalation
resource "aws_sns_topic_subscription" "escalation_pagerduty" {
  count     = var.pagerduty_endpoint != "" ? 1 : 0
  topic_arn = aws_sns_topic.escalation_alerts.arn
  protocol  = "https"
  endpoint  = var.pagerduty_endpoint
}

# ============================================================================
# CloudWatch Alarms for Critical Pipeline Metrics
# ============================================================================

# Lambda Function Failure Rate Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_failure_rate" {
  alarm_name          = "${var.project_name}-lambda-failure-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.alarm_evaluation_periods
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = var.lambda_error_threshold
  alarm_description   = "Lambda function failure rate is too high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.snowflake_extractor_function_name
  }

  alarm_actions = [aws_sns_topic.critical_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = var.tags
}

# Lambda Function Duration Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_duration_critical" {
  alarm_name          = "${var.project_name}-lambda-duration-critical"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.alarm_evaluation_periods
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = var.lambda_duration_threshold_ms
  alarm_description   = "Lambda function duration exceeds critical threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.snowflake_extractor_function_name
  }

  alarm_actions = [aws_sns_topic.warning_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = var.tags
}

# Glue Job Failure Alarm
resource "aws_cloudwatch_metric_alarm" "glue_job_failures" {
  alarm_name          = "${var.project_name}-glue-job-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "glue.driver.aggregate.numFailedTasks"
  namespace           = "AWS/Glue"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Glue ETL job has failed tasks"
  treat_missing_data  = "notBreaching"

  dimensions = {
    JobName = var.bronze_to_silver_job_name
  }

  alarm_actions = [aws_sns_topic.critical_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = var.tags
}

# Data Quality Score Degradation Alarm
resource "aws_cloudwatch_metric_alarm" "data_quality_degradation" {
  alarm_name          = "${var.project_name}-data-quality-degradation"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = var.alarm_evaluation_periods
  metric_name         = "pipeline_data_quality_score"
  namespace           = "Pipeline/DataQuality"
  period              = "300"
  statistic           = "Average"
  threshold           = var.data_quality_threshold
  alarm_description   = "Data quality score has degraded below acceptable threshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.warning_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = var.tags
}

# S3 Data Lake Storage Growth Alarm
resource "aws_cloudwatch_metric_alarm" "s3_storage_critical" {
  alarm_name          = "${var.project_name}-s3-storage-critical"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BucketSizeBytes"
  namespace           = "AWS/S3"
  period              = "86400"
  statistic           = "Average"
  threshold           = var.s3_storage_threshold_bytes
  alarm_description   = "S3 data lake storage has exceeded critical threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    BucketName  = var.data_lake_bucket_name
    StorageType = "StandardStorage"
  }

  alarm_actions = [aws_sns_topic.warning_alerts.arn]

  tags = var.tags
}

# Pipeline Processing Latency Alarm
resource "aws_cloudwatch_metric_alarm" "pipeline_latency_critical" {
  alarm_name          = "${var.project_name}-pipeline-latency-critical"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.alarm_evaluation_periods
  metric_name         = "pipeline_stage_latency"
  namespace           = "Pipeline/Performance"
  period              = "300"
  statistic           = "Average"
  threshold           = var.pipeline_latency_threshold_ms
  alarm_description   = "Pipeline processing latency exceeds critical threshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.warning_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = var.tags
}

# SageMaker Endpoint Failure Alarm
resource "aws_cloudwatch_metric_alarm" "sagemaker_endpoint_failures" {
  count = var.sagemaker_endpoint_name != "" ? 1 : 0

  alarm_name          = "${var.project_name}-sagemaker-endpoint-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.alarm_evaluation_periods
  metric_name         = "Invocation4XXErrors"
  namespace           = "AWS/SageMaker/Endpoints"
  period              = "300"
  statistic           = "Sum"
  threshold           = var.sagemaker_error_threshold
  alarm_description   = "SageMaker endpoint is experiencing high error rates"
  treat_missing_data  = "notBreaching"

  dimensions = {
    EndpointName = var.sagemaker_endpoint_name
  }

  alarm_actions = [aws_sns_topic.critical_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = var.tags
}

# Cost Threshold Alarm
resource "aws_cloudwatch_metric_alarm" "daily_cost_threshold" {
  count = var.enable_cost_monitoring ? 1 : 0

  alarm_name          = "${var.project_name}-daily-cost-threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "pipeline_cost_estimate"
  namespace           = "Pipeline/Cost"
  period              = "86400"
  statistic           = "Sum"
  threshold           = var.daily_cost_threshold
  alarm_description   = "Daily pipeline costs exceed threshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.warning_alerts.arn]

  tags = var.tags
}

# ============================================================================
# Composite Alarms for Complex Monitoring Scenarios
# ============================================================================

# Pipeline Health Composite Alarm
resource "aws_cloudwatch_composite_alarm" "pipeline_health" {
  alarm_name        = "${var.project_name}-pipeline-health"
  alarm_description = "Composite alarm monitoring overall pipeline health"

  alarm_rule = join(" OR ", compact([
    "ALARM(${aws_cloudwatch_metric_alarm.lambda_failure_rate.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.glue_job_failures.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.data_quality_degradation.alarm_name})",
    var.sagemaker_endpoint_name != "" ? "ALARM(${aws_cloudwatch_metric_alarm.sagemaker_endpoint_failures[0].alarm_name})" : null
  ]))

  actions_enabled = true
  alarm_actions   = [aws_sns_topic.critical_alerts.arn]
  ok_actions      = [aws_sns_topic.info_notifications.arn]

  tags = var.tags
}

# Performance Degradation Composite Alarm
resource "aws_cloudwatch_composite_alarm" "performance_degradation" {
  alarm_name        = "${var.project_name}-performance-degradation"
  alarm_description = "Composite alarm monitoring pipeline performance degradation"

  alarm_rule = join(" OR ", [
    "ALARM(${aws_cloudwatch_metric_alarm.lambda_duration_critical.alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.pipeline_latency_critical.alarm_name})"
  ])

  actions_enabled = true
  alarm_actions   = [aws_sns_topic.warning_alerts.arn]
  ok_actions      = [aws_sns_topic.info_notifications.arn]

  tags = var.tags
}

# ============================================================================
# Escalation Procedures for Persistent Issues
# ============================================================================

# Lambda function for escalation logic
resource "aws_lambda_function" "escalation_handler" {
  filename         = data.archive_file.escalation_handler_zip.output_path
  function_name    = "${var.project_name}-escalation-handler"
  role            = aws_iam_role.escalation_handler_role.arn
  handler         = "escalation_handler.lambda_handler"
  runtime         = "python3.9"
  timeout         = 60
  source_code_hash = data.archive_file.escalation_handler_zip.output_base64sha256

  environment {
    variables = {
      ESCALATION_SNS_TOPIC_ARN = aws_sns_topic.escalation_alerts.arn
      CRITICAL_SNS_TOPIC_ARN   = aws_sns_topic.critical_alerts.arn
      PROJECT_NAME             = var.project_name
      ESCALATION_THRESHOLD     = var.escalation_threshold_minutes
    }
  }

  tags = var.tags
}

# IAM role for escalation handler
resource "aws_iam_role" "escalation_handler_role" {
  name = "${var.project_name}-escalation-handler-role"

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

  tags = var.tags
}

# IAM policy for escalation handler
resource "aws_iam_role_policy" "escalation_handler_policy" {
  name = "${var.project_name}-escalation-handler-policy"
  role = aws_iam_role.escalation_handler_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = [
          aws_sns_topic.escalation_alerts.arn,
          aws_sns_topic.critical_alerts.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:DescribeAlarms",
          "cloudwatch:GetMetricStatistics"
        ]
        Resource = "*"
      }
    ]
  })
}

# CloudWatch Event Rule for escalation trigger
resource "aws_events_rule" "escalation_trigger" {
  name        = "${var.project_name}-escalation-trigger"
  description = "Trigger escalation for persistent alarm states"

  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      state = {
        value = ["ALARM"]
      }
      alarmName = [
        aws_cloudwatch_composite_alarm.pipeline_health.alarm_name,
        aws_cloudwatch_metric_alarm.lambda_failure_rate.alarm_name,
        aws_cloudwatch_metric_alarm.glue_job_failures.alarm_name
      ]
    }
  })

  tags = var.tags
}

# EventBridge target for escalation
resource "aws_events_target" "escalation_lambda_target" {
  rule      = aws_events_rule.escalation_trigger.name
  target_id = "EscalationLambdaTarget"
  arn       = aws_lambda_function.escalation_handler.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge_escalation" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.escalation_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_events_rule.escalation_trigger.arn
}

# ============================================================================
# Auto-Recovery Mechanisms
# ============================================================================

# Lambda function for auto-recovery actions
resource "aws_lambda_function" "auto_recovery" {
  filename         = data.archive_file.auto_recovery_zip.output_path
  function_name    = "${var.project_name}-auto-recovery"
  role            = aws_iam_role.auto_recovery_role.arn
  handler         = "auto_recovery.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300
  source_code_hash = data.archive_file.auto_recovery_zip.output_base64sha256

  environment {
    variables = {
      PROJECT_NAME                = var.project_name
      GLUE_JOB_NAME              = var.bronze_to_silver_job_name
      LAMBDA_FUNCTION_NAME       = var.snowflake_extractor_function_name
      SNS_TOPIC_ARN              = aws_sns_topic.info_notifications.arn
      AUTO_RECOVERY_ENABLED      = var.enable_auto_recovery
      MAX_RECOVERY_ATTEMPTS      = var.max_recovery_attempts
    }
  }

  tags = var.tags
}

# IAM role for auto-recovery
resource "aws_iam_role" "auto_recovery_role" {
  name = "${var.project_name}-auto-recovery-role"

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

  tags = var.tags
}

# IAM policy for auto-recovery
resource "aws_iam_role_policy" "auto_recovery_policy" {
  name = "${var.project_name}-auto-recovery-policy"
  role = aws_iam_role.auto_recovery_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.info_notifications.arn
      },
      {
        Effect = "Allow"
        Action = [
          "glue:StartJobRun",
          "glue:GetJobRun",
          "glue:GetJobRuns"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:*:function:${var.snowflake_extractor_function_name}"
      }
    ]
  })
}

# EventBridge rule for auto-recovery trigger
resource "aws_events_rule" "auto_recovery_trigger" {
  count = var.enable_auto_recovery ? 1 : 0

  name        = "${var.project_name}-auto-recovery-trigger"
  description = "Trigger auto-recovery for specific failure patterns"

  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      state = {
        value = ["ALARM"]
      }
      alarmName = [
        aws_cloudwatch_metric_alarm.lambda_failure_rate.alarm_name,
        aws_cloudwatch_metric_alarm.glue_job_failures.alarm_name
      ]
    }
  })

  tags = var.tags
}

# EventBridge target for auto-recovery
resource "aws_events_target" "auto_recovery_lambda_target" {
  count = var.enable_auto_recovery ? 1 : 0

  rule      = aws_events_rule.auto_recovery_trigger[0].name
  target_id = "AutoRecoveryLambdaTarget"
  arn       = aws_lambda_function.auto_recovery.arn
}

# Lambda permission for auto-recovery EventBridge
resource "aws_lambda_permission" "allow_eventbridge_auto_recovery" {
  count = var.enable_auto_recovery ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auto_recovery.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_events_rule.auto_recovery_trigger[0].arn
}

# ============================================================================
# Data Sources for Lambda Function Code
# ============================================================================

# Escalation handler Lambda code
data "archive_file" "escalation_handler_zip" {
  type        = "zip"
  output_path = "${path.module}/escalation_handler.zip"
  source {
    content = templatefile("${path.module}/lambda_functions/escalation_handler.py", {
      escalation_threshold = var.escalation_threshold_minutes
    })
    filename = "escalation_handler.py"
  }
}

# Auto-recovery Lambda code
data "archive_file" "auto_recovery_zip" {
  type        = "zip"
  output_path = "${path.module}/auto_recovery.zip"
  source {
    content = templatefile("${path.module}/lambda_functions/auto_recovery.py", {
      max_recovery_attempts = var.max_recovery_attempts
    })
    filename = "auto_recovery.py"
  }
}
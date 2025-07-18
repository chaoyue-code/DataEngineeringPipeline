# Example: Advanced Monitoring Configuration
# This example shows how to configure the monitoring module with advanced settings
# including external SNS topics, custom thresholds, and production-ready settings

# External SNS Topics (created separately)
resource "aws_sns_topic" "critical_alerts" {
  name = "snowflake-pipeline-prod-critical-alerts"

  tags = {
    Environment = "prod"
    Purpose     = "critical-alerts"
  }
}

resource "aws_sns_topic" "warning_alerts" {
  name = "snowflake-pipeline-prod-warning-alerts"

  tags = {
    Environment = "prod"
    Purpose     = "warning-alerts"
  }
}

resource "aws_sns_topic" "info_notifications" {
  name = "snowflake-pipeline-prod-info-notifications"

  tags = {
    Environment = "prod"
    Purpose     = "info-notifications"
  }
}

# SNS Topic Subscriptions
resource "aws_sns_topic_subscription" "critical_email" {
  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "email"
  endpoint  = "data-team-critical@company.com"
}

resource "aws_sns_topic_subscription" "critical_slack" {
  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "https"
  endpoint  = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
}

resource "aws_sns_topic_subscription" "warning_email" {
  topic_arn = aws_sns_topic.warning_alerts.arn
  protocol  = "email"
  endpoint  = "data-team-warnings@company.com"
}

# Advanced Monitoring Configuration
module "monitoring" {
  source = "../"

  project_name = "snowflake-pipeline"
  environment  = "prod"
  aws_region   = "us-east-1"

  # Lambda Function Names
  snowflake_extractor_function_name   = "snowflake-pipeline-prod-snowflake-extractor"
  pipeline_orchestrator_function_name = "snowflake-pipeline-prod-pipeline-orchestrator"
  data_quality_monitor_function_name  = "snowflake-pipeline-prod-data-quality-monitor"

  # Glue Job Names
  bronze_to_silver_job_name = "snowflake-pipeline-prod-bronze-to-silver"
  silver_to_gold_job_name   = "snowflake-pipeline-prod-silver-to-gold"

  # S3 Resources
  data_lake_bucket_name = "snowflake-pipeline-prod-data-lake"

  # SageMaker Resources
  sagemaker_endpoint_name = "snowflake-pipeline-prod-ml-endpoint"

  # External SNS Topics
  critical_sns_topic_arn = aws_sns_topic.critical_alerts.arn
  warning_sns_topic_arn  = aws_sns_topic.warning_alerts.arn
  info_sns_topic_arn     = aws_sns_topic.info_notifications.arn

  # Production Configuration
  log_retention_days         = 90
  enable_cost_monitoring     = true
  enable_xray_tracing        = true
  enable_detailed_monitoring = true

  # Production-tuned Thresholds
  lambda_error_threshold              = 3
  data_quality_threshold              = 0.9
  daily_cost_threshold                = 500
  lambda_duration_threshold_ms        = 45000
  glue_job_duration_threshold_minutes = 120

  # Advanced Settings
  dashboard_period_seconds = 300
  alarm_evaluation_periods = 3
  xray_sampling_rate       = 0.05
  custom_metrics_namespace = "SnowflakePipeline"

  tags = {
    Environment = "prod"
    Team        = "data-engineering"
    Project     = "snowflake-pipeline"
    CostCenter  = "data-platform"
    Compliance  = "required"
  }
}

# Additional CloudWatch Alarms for Production
resource "aws_cloudwatch_metric_alarm" "high_lambda_concurrency" {
  alarm_name          = "snowflake-pipeline-prod-high-lambda-concurrency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ConcurrentExecutions"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Maximum"
  threshold           = "800"
  alarm_description   = "Lambda concurrency is approaching limits"

  alarm_actions = [aws_sns_topic.warning_alerts.arn]
  ok_actions    = [aws_sns_topic.warning_alerts.arn]

  tags = {
    Environment = "prod"
    Purpose     = "capacity-monitoring"
  }
}

resource "aws_cloudwatch_metric_alarm" "glue_dpu_hours" {
  alarm_name          = "snowflake-pipeline-prod-glue-dpu-hours"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "glue.driver.aggregate.elapsedTime"
  namespace           = "AWS/Glue"
  period              = "3600"
  statistic           = "Sum"
  threshold           = "7200000" # 2 hours in milliseconds
  alarm_description   = "Glue job running longer than expected"

  dimensions = {
    JobName = module.monitoring.bronze_to_silver_job_name
  }

  alarm_actions = [aws_sns_topic.warning_alerts.arn]

  tags = {
    Environment = "prod"
    Purpose     = "cost-optimization"
  }
}

# Custom Dashboard for Business Metrics
resource "aws_cloudwatch_dashboard" "business_metrics" {
  dashboard_name = "snowflake-pipeline-prod-business-metrics"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["SnowflakePipeline/Processing", "pipeline_records_processed", "PipelineStage", "bronze"],
            ["SnowflakePipeline/Processing", "pipeline_records_processed", "PipelineStage", "silver"],
            ["SnowflakePipeline/Processing", "pipeline_records_processed", "PipelineStage", "gold"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "Daily Data Processing Volume"
          period  = 86400
          stat    = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["SnowflakePipeline/DataQuality", "pipeline_data_quality_score", "PipelineStage", "bronze"],
            ["SnowflakePipeline/DataQuality", "pipeline_data_quality_score", "PipelineStage", "silver"],
            ["SnowflakePipeline/DataQuality", "pipeline_data_quality_score", "PipelineStage", "gold"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "Data Quality Trends"
          period  = 3600
          yAxis = {
            left = {
              min = 0
              max = 1
            }
          }
        }
      }
    ]
  })

  tags = {
    Environment = "prod"
    Purpose     = "business-monitoring"
  }
}

# Outputs
output "monitoring_summary" {
  description = "Complete monitoring setup summary"
  value = {
    dashboards = {
      technical_dashboards = module.monitoring.monitoring_dashboard_names
      business_dashboard   = aws_cloudwatch_dashboard.business_metrics.dashboard_name
    }
    alerting = {
      sns_topics   = module.monitoring.sns_topic_arns
      alarms_count = length(module.monitoring.monitoring_summary.alarms_created) + 2
    }
    logging = {
      log_groups     = module.monitoring.monitoring_log_groups
      retention_days = 90
    }
    tracing = {
      xray_enabled  = true
      sampling_rate = 0.05
    }
    cost_monitoring = {
      enabled         = true
      daily_threshold = 500
    }
  }
}

output "dashboard_urls" {
  description = "All dashboard URLs for easy access"
  value = {
    pipeline_overview = module.monitoring.pipeline_overview_dashboard_url
    data_quality      = module.monitoring.data_quality_dashboard_url
    cost_performance  = module.monitoring.cost_performance_dashboard_url
    business_metrics  = "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=${aws_cloudwatch_dashboard.business_metrics.dashboard_name}"
  }
}

output "operational_runbook" {
  description = "Operational information for the monitoring setup"
  value = {
    critical_alerts_email = "data-team-critical@company.com"
    warning_alerts_email  = "data-team-warnings@company.com"
    slack_integration     = "Configured for critical alerts"
    escalation_procedure  = "Critical alerts -> Immediate response, Warnings -> Next business day"
    dashboard_refresh     = "Auto-refresh every 5 minutes"
    log_retention         = "90 days for production compliance"
    cost_monitoring       = "Daily threshold: $500, Storage growth alerts enabled"
  }
}
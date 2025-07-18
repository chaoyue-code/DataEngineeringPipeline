# CloudWatch Dashboards and Metrics Module
# This module creates comprehensive monitoring for the Snowflake-AWS pipeline

# SNS Topics are now defined in alerting.tf
# Local values for backward compatibility with existing alarms
locals {
  critical_sns_topic_arn = aws_sns_topic.critical_alerts.arn
  warning_sns_topic_arn  = aws_sns_topic.warning_alerts.arn
  info_sns_topic_arn     = aws_sns_topic.info_notifications.arn
}

# CloudWatch Dashboard for Pipeline Overview
resource "aws_cloudwatch_dashboard" "pipeline_overview" {
  dashboard_name = "${var.project_name}-pipeline-overview"

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
            ["AWS/Lambda", "Duration", "FunctionName", var.snowflake_extractor_function_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.snowflake_extractor_function_name],
            ["AWS/Lambda", "Invocations", "FunctionName", var.snowflake_extractor_function_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Snowflake Extractor Lambda Metrics"
          period  = 300
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
            ["AWS/Glue", "glue.driver.aggregate.numCompletedTasks", "JobName", var.bronze_to_silver_job_name],
            ["AWS/Glue", "glue.driver.aggregate.numFailedTasks", "JobName", var.bronze_to_silver_job_name],
            ["AWS/Glue", "glue.ALL.s3.filesystem.read_bytes", "JobName", var.bronze_to_silver_job_name],
            ["AWS/Glue", "glue.ALL.s3.filesystem.write_bytes", "JobName", var.bronze_to_silver_job_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Glue ETL Job Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/S3", "BucketSizeBytes", "BucketName", var.data_lake_bucket_name, "StorageType", "StandardStorage"],
            ["AWS/S3", "NumberOfObjects", "BucketName", var.data_lake_bucket_name, "StorageType", "AllStorageTypes"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "S3 Data Lake Storage Metrics"
          period  = 86400
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 6
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/SageMaker/Endpoints", "Invocations", "EndpointName", var.sagemaker_endpoint_name],
            ["AWS/SageMaker/Endpoints", "ModelLatency", "EndpointName", var.sagemaker_endpoint_name],
            ["AWS/SageMaker/Endpoints", "InvocationsPerInstance", "EndpointName", var.sagemaker_endpoint_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "SageMaker Endpoint Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 6
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["CWAgent", "pipeline_data_quality_score", "PipelineStage", "bronze"],
            ["CWAgent", "pipeline_data_quality_score", "PipelineStage", "silver"],
            ["CWAgent", "pipeline_data_quality_score", "PipelineStage", "gold"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Data Quality Scores by Stage"
          period  = 300
        }
      }
    ]
  })

  tags = var.tags
}

# CloudWatch Dashboard for Data Quality Monitoring
resource "aws_cloudwatch_dashboard" "data_quality" {
  dashboard_name = "${var.project_name}-data-quality"

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
            ["CWAgent", "pipeline_records_processed", "PipelineStage", "bronze"],
            ["CWAgent", "pipeline_records_processed", "PipelineStage", "silver"],
            ["CWAgent", "pipeline_records_processed", "PipelineStage", "gold"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Records Processed by Pipeline Stage"
          period  = 300
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
            ["CWAgent", "pipeline_data_validation_failures", "ValidationRule", "null_check"],
            ["CWAgent", "pipeline_data_validation_failures", "ValidationRule", "schema_validation"],
            ["CWAgent", "pipeline_data_validation_failures", "ValidationRule", "range_validation"],
            ["CWAgent", "pipeline_data_validation_failures", "ValidationRule", "referential_integrity"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Data Validation Failures by Rule Type"
          period  = 300
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 6
        width  = 24
        height = 6

        properties = {
          query  = "SOURCE '/aws/lambda/${var.data_quality_monitor_function_name}' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 100"
          region = var.aws_region
          title  = "Recent Data Quality Errors"
        }
      }
    ]
  })

  tags = var.tags
}

# CloudWatch Dashboard for Cost and Performance
resource "aws_cloudwatch_dashboard" "cost_performance" {
  dashboard_name = "${var.project_name}-cost-performance"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.snowflake_extractor_function_name],
            ["AWS/Lambda", "Duration", "FunctionName", var.pipeline_orchestrator_function_name],
            ["AWS/Lambda", "Duration", "FunctionName", var.data_quality_monitor_function_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda Function Execution Duration"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 0
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/Glue", "glue.driver.ExecutorRunTime", "JobName", var.bronze_to_silver_job_name],
            ["AWS/Glue", "glue.driver.ExecutorRunTime", "JobName", var.silver_to_gold_job_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Glue Job Execution Time"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 0
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["CWAgent", "pipeline_cost_estimate", "Service", "lambda"],
            ["CWAgent", "pipeline_cost_estimate", "Service", "glue"],
            ["CWAgent", "pipeline_cost_estimate", "Service", "s3"],
            ["CWAgent", "pipeline_cost_estimate", "Service", "sagemaker"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Estimated Daily Costs by Service"
          period  = 86400
        }
      }
    ]
  })

  tags = var.tags
}

# Custom CloudWatch Log Groups for centralized logging
resource "aws_cloudwatch_log_group" "pipeline_logs" {
  name              = "/aws/pipeline/${var.project_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "data_quality_logs" {
  name              = "/aws/pipeline/${var.project_name}/data-quality"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "performance_logs" {
  name              = "/aws/pipeline/${var.project_name}/performance"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# CloudWatch Log Group for SageMaker logs
resource "aws_cloudwatch_log_group" "sagemaker_logs" {
  name              = "/aws/sagemaker/${var.project_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# CloudWatch Log Metric Filters for custom metrics
resource "aws_cloudwatch_log_metric_filter" "data_quality_score" {
  name           = "${var.project_name}-data-quality-score"
  log_group_name = aws_cloudwatch_log_group.data_quality_logs.name
  pattern        = "[timestamp, request_id, stage, score]"

  metric_transformation {
    name      = "pipeline_data_quality_score"
    namespace = "Pipeline/DataQuality"
    value     = "$score"

    default_value = 0

    dimensions = {
      PipelineStage = "$stage"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "records_processed" {
  name           = "${var.project_name}-records-processed"
  log_group_name = aws_cloudwatch_log_group.pipeline_logs.name
  pattern        = "[timestamp, request_id, stage, \"RECORDS_PROCESSED\", count]"

  metric_transformation {
    name      = "pipeline_records_processed"
    namespace = "Pipeline/Processing"
    value     = "$count"

    default_value = 0

    dimensions = {
      PipelineStage = "$stage"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "validation_failures" {
  name           = "${var.project_name}-validation-failures"
  log_group_name = aws_cloudwatch_log_group.data_quality_logs.name
  pattern        = "[timestamp, request_id, \"VALIDATION_FAILURE\", rule, count]"

  metric_transformation {
    name      = "pipeline_data_validation_failures"
    namespace = "Pipeline/DataQuality"
    value     = "$count"

    default_value = 0

    dimensions = {
      ValidationRule = "$rule"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "cost_estimates" {
  name           = "${var.project_name}-cost-estimates"
  log_group_name = aws_cloudwatch_log_group.performance_logs.name
  pattern        = "[timestamp, request_id, \"COST_ESTIMATE\", service, amount]"

  metric_transformation {
    name      = "pipeline_cost_estimate"
    namespace = "Pipeline/Cost"
    value     = "$amount"

    default_value = 0

    dimensions = {
      Service = "$service"
    }
  }
}

# Composite alarms and critical alerting are now handled in alerting.tf
# Keeping only basic alarms for backward compatibility

# Basic Lambda errors alarm (legacy)
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-lambda-errors-basic"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Basic Lambda errors monitoring (legacy)"

  dimensions = {
    FunctionName = var.snowflake_extractor_function_name
  }

  alarm_actions = [local.warning_sns_topic_arn]
  ok_actions    = [local.warning_sns_topic_arn]

  tags = merge(var.tags, {
    AlertType = "Legacy"
  })
}

# X-Ray Tracing Configuration
resource "aws_xray_sampling_rule" "pipeline_sampling" {
  count = var.enable_xray_tracing ? 1 : 0

  rule_name      = "${var.project_name}-pipeline-sampling"
  priority       = 9000
  version        = 1
  reservoir_size = 1
  fixed_rate     = var.xray_sampling_rate
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"

  tags = var.tags
}

# Additional CloudWatch Alarms for comprehensive monitoring
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.project_name}-lambda-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.alarm_evaluation_periods
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = var.lambda_duration_threshold_ms
  alarm_description   = "This metric monitors Lambda function duration"

  dimensions = {
    FunctionName = var.snowflake_extractor_function_name
  }

  alarm_actions = [local.warning_sns_topic_arn]
  ok_actions    = [local.warning_sns_topic_arn]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "glue_job_duration" {
  alarm_name          = "${var.project_name}-glue-job-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "glue.driver.ExecutorRunTime"
  namespace           = "AWS/Glue"
  period              = "300"
  statistic           = "Maximum"
  threshold           = var.glue_job_duration_threshold_minutes * 60 # Convert to seconds
  alarm_description   = "This metric monitors Glue job execution duration"

  dimensions = {
    JobName = var.bronze_to_silver_job_name
  }

  alarm_actions = [local.warning_sns_topic_arn]
  ok_actions    = [local.warning_sns_topic_arn]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "s3_storage_growth" {
  count = var.enable_cost_monitoring ? 1 : 0

  alarm_name          = "${var.project_name}-s3-storage-growth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BucketSizeBytes"
  namespace           = "AWS/S3"
  period              = "86400"
  statistic           = "Average"
  threshold           = 1073741824000 # 1TB in bytes
  alarm_description   = "This metric monitors S3 storage growth"

  dimensions = {
    BucketName  = var.data_lake_bucket_name
    StorageType = "StandardStorage"
  }

  alarm_actions = [local.info_sns_topic_arn]

  tags = var.tags
}

# Cost monitoring is now handled in alerting.tf with more comprehensive logic

# CloudWatch Insights Queries for log analysis
resource "aws_cloudwatch_query_definition" "error_analysis" {
  name = "${var.project_name}-error-analysis"

  log_group_names = [
    aws_cloudwatch_log_group.pipeline_logs.name,
    aws_cloudwatch_log_group.data_quality_logs.name,
    aws_cloudwatch_log_group.performance_logs.name
  ]

  query_string = <<EOF
fields @timestamp, @message, @logStream
| filter @message like /ERROR/
| stats count() by bin(5m)
| sort @timestamp desc
EOF
}

resource "aws_cloudwatch_query_definition" "performance_analysis" {
  name = "${var.project_name}-performance-analysis"

  log_group_names = [
    aws_cloudwatch_log_group.performance_logs.name
  ]

  query_string = <<EOF
fields @timestamp, @message
| filter @message like /PERFORMANCE/
| parse @message "PERFORMANCE * duration=* memory=*" as component, duration, memory
| stats avg(duration), max(duration), min(duration) by component
| sort avg(duration) desc
EOF
}

resource "aws_cloudwatch_query_definition" "data_quality_trends" {
  name = "${var.project_name}-data-quality-trends"

  log_group_names = [
    aws_cloudwatch_log_group.data_quality_logs.name
  ]

  query_string = <<EOF
fields @timestamp, @message
| parse @message "* * * *" as timestamp, request_id, stage, score
| filter ispresent(score)
| stats avg(score) by bin(1h), stage
| sort @timestamp desc
EOF
}

# EventBridge Rules for automated responses
resource "aws_events_rule" "pipeline_failure" {
  name        = "${var.project_name}-pipeline-failure"
  description = "Capture pipeline failure events"

  event_pattern = jsonencode({
    source      = ["aws.glue", "aws.lambda"]
    detail-type = ["Glue Job State Change", "Lambda Function Invocation Result"]
    detail = {
      state = ["FAILED", "ERROR"]
    }
  })

  tags = var.tags
}

resource "aws_events_target" "pipeline_failure_sns" {
  rule      = aws_events_rule.pipeline_failure.name
  target_id = "SendToSNS"
  arn       = local.critical_sns_topic_arn
}

# CloudWatch Log Streams for structured logging
resource "aws_cloudwatch_log_stream" "pipeline_orchestrator" {
  name           = "orchestrator-stream"
  log_group_name = aws_cloudwatch_log_group.pipeline_logs.name
}

resource "aws_cloudwatch_log_stream" "data_extraction" {
  name           = "extraction-stream"
  log_group_name = aws_cloudwatch_log_group.pipeline_logs.name
}

resource "aws_cloudwatch_log_stream" "data_transformation" {
  name           = "transformation-stream"
  log_group_name = aws_cloudwatch_log_group.pipeline_logs.name
}

# CloudWatch Log Group for SageMaker logs
resource "aws_cloudwatch_log_group" "sagemaker_logs" {
  name              = "/aws/sagemaker/${var.project_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# Additional metric filters for enhanced monitoring
resource "aws_cloudwatch_log_metric_filter" "pipeline_latency" {
  name           = "${var.project_name}-pipeline-latency"
  log_group_name = aws_cloudwatch_log_group.performance_logs.name
  pattern        = "[timestamp, request_id, \"PIPELINE_LATENCY\", stage, latency_ms]"

  metric_transformation {
    name      = "pipeline_stage_latency"
    namespace = "Pipeline/Performance"
    value     = "$latency_ms"

    default_value = 0

    dimensions = {
      PipelineStage = "$stage"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "memory_utilization" {
  name           = "${var.project_name}-memory-utilization"
  log_group_name = aws_cloudwatch_log_group.performance_logs.name
  pattern        = "[timestamp, request_id, \"MEMORY_USAGE\", component, memory_mb]"

  metric_transformation {
    name      = "pipeline_memory_utilization"
    namespace = "Pipeline/Performance"
    value     = "$memory_mb"

    default_value = 0

    dimensions = {
      Component = "$component"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "throughput_metrics" {
  name           = "${var.project_name}-throughput-metrics"
  log_group_name = aws_cloudwatch_log_group.pipeline_logs.name
  pattern        = "[timestamp, request_id, \"THROUGHPUT\", stage, records_per_second]"

  metric_transformation {
    name      = "pipeline_throughput"
    namespace = "Pipeline/Performance"
    value     = "$records_per_second"

    default_value = 0

    dimensions = {
      PipelineStage = "$stage"
    }
  }
}
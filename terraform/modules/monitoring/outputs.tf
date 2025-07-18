# Outputs for CloudWatch Monitoring Module

# Dashboard URLs
output "pipeline_overview_dashboard_url" {
  description = "URL for the pipeline overview CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.pipeline_overview.dashboard_name}"
}

output "data_quality_dashboard_url" {
  description = "URL for the data quality CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.data_quality.dashboard_name}"
}

output "cost_performance_dashboard_url" {
  description = "URL for the cost and performance CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.cost_performance.dashboard_name}"
}

# Dashboard Names
output "pipeline_overview_dashboard_name" {
  description = "Name of the pipeline overview dashboard"
  value       = aws_cloudwatch_dashboard.pipeline_overview.dashboard_name
}

output "data_quality_dashboard_name" {
  description = "Name of the data quality dashboard"
  value       = aws_cloudwatch_dashboard.data_quality.dashboard_name
}

output "cost_performance_dashboard_name" {
  description = "Name of the cost and performance dashboard"
  value       = aws_cloudwatch_dashboard.cost_performance.dashboard_name
}

# Log Group Information
output "pipeline_log_group_name" {
  description = "Name of the main pipeline log group"
  value       = aws_cloudwatch_log_group.pipeline_logs.name
}

output "pipeline_log_group_arn" {
  description = "ARN of the main pipeline log group"
  value       = aws_cloudwatch_log_group.pipeline_logs.arn
}

output "data_quality_log_group_name" {
  description = "Name of the data quality log group"
  value       = aws_cloudwatch_log_group.data_quality_logs.name
}

output "data_quality_log_group_arn" {
  description = "ARN of the data quality log group"
  value       = aws_cloudwatch_log_group.data_quality_logs.arn
}

output "performance_log_group_name" {
  description = "Name of the performance log group"
  value       = aws_cloudwatch_log_group.performance_logs.name
}

output "performance_log_group_arn" {
  description = "ARN of the performance log group"
  value       = aws_cloudwatch_log_group.performance_logs.arn
}

# Alarm Information
output "composite_alarm_name" {
  description = "Name of the composite pipeline health alarm"
  value       = aws_cloudwatch_composite_alarm.pipeline_health.alarm_name
}

output "composite_alarm_arn" {
  description = "ARN of the composite pipeline health alarm"
  value       = aws_cloudwatch_composite_alarm.pipeline_health.arn
}

output "lambda_errors_alarm_name" {
  description = "Name of the Lambda errors alarm"
  value       = aws_cloudwatch_metric_alarm.lambda_errors.alarm_name
}

output "lambda_errors_alarm_arn" {
  description = "ARN of the Lambda errors alarm"
  value       = aws_cloudwatch_metric_alarm.lambda_errors.arn
}

output "glue_job_failures_alarm_name" {
  description = "Name of the Glue job failures alarm"
  value       = aws_cloudwatch_metric_alarm.glue_job_failures.alarm_name
}

output "glue_job_failures_alarm_arn" {
  description = "ARN of the Glue job failures alarm"
  value       = aws_cloudwatch_metric_alarm.glue_job_failures.arn
}

output "data_quality_alarm_name" {
  description = "Name of the data quality degradation alarm"
  value       = aws_cloudwatch_metric_alarm.data_quality_degradation.alarm_name
}

output "data_quality_alarm_arn" {
  description = "ARN of the data quality degradation alarm"
  value       = aws_cloudwatch_metric_alarm.data_quality_degradation.arn
}

# Metric Filter Information
output "data_quality_score_metric_filter_name" {
  description = "Name of the data quality score metric filter"
  value       = aws_cloudwatch_log_metric_filter.data_quality_score.name
}

output "records_processed_metric_filter_name" {
  description = "Name of the records processed metric filter"
  value       = aws_cloudwatch_log_metric_filter.records_processed.name
}

output "validation_failures_metric_filter_name" {
  description = "Name of the validation failures metric filter"
  value       = aws_cloudwatch_log_metric_filter.validation_failures.name
}

output "cost_estimates_metric_filter_name" {
  description = "Name of the cost estimates metric filter"
  value       = aws_cloudwatch_log_metric_filter.cost_estimates.name
}

# Custom Metrics Namespaces
output "data_quality_metrics_namespace" {
  description = "CloudWatch namespace for data quality metrics"
  value       = "Pipeline/DataQuality"
}

output "processing_metrics_namespace" {
  description = "CloudWatch namespace for processing metrics"
  value       = "Pipeline/Processing"
}

output "cost_metrics_namespace" {
  description = "CloudWatch namespace for cost metrics"
  value       = "Pipeline/Cost"
}

# Monitoring Configuration Summary
# SNS Topic Information
output "sns_topic_arns" {
  description = "ARNs of SNS topics created for alerting"
  value = {
    critical_alerts    = aws_sns_topic.critical_alerts.arn
    warning_alerts     = aws_sns_topic.warning_alerts.arn
    info_notifications = aws_sns_topic.info_notifications.arn
    escalation_alerts  = aws_sns_topic.escalation_alerts.arn
  }
}

output "sns_topic_names" {
  description = "Names of SNS topics created for alerting"
  value = {
    critical_alerts    = aws_sns_topic.critical_alerts.name
    warning_alerts     = aws_sns_topic.warning_alerts.name
    info_notifications = aws_sns_topic.info_notifications.name
    escalation_alerts  = aws_sns_topic.escalation_alerts.name
  }
}

# X-Ray Tracing Information
output "xray_sampling_rule_name" {
  description = "Name of the X-Ray sampling rule"
  value       = var.enable_xray_tracing ? aws_xray_sampling_rule.pipeline_sampling[0].rule_name : null
}

output "xray_sampling_rule_arn" {
  description = "ARN of the X-Ray sampling rule"
  value       = var.enable_xray_tracing ? aws_xray_sampling_rule.pipeline_sampling[0].arn : null
}

# Additional Alarm Information
output "additional_alarms" {
  description = "Additional CloudWatch alarms created"
  value = {
    lambda_duration      = aws_cloudwatch_metric_alarm.lambda_duration.alarm_name
    glue_job_duration    = aws_cloudwatch_metric_alarm.glue_job_duration.alarm_name
    s3_storage_growth    = var.enable_cost_monitoring ? aws_cloudwatch_metric_alarm.s3_storage_growth[0].alarm_name : null
    daily_cost_threshold = var.enable_cost_monitoring ? aws_cloudwatch_metric_alarm.daily_cost_threshold[0].alarm_name : null
  }
}

# CloudWatch Insights Queries
output "cloudwatch_insights_queries" {
  description = "CloudWatch Insights query definitions"
  value = {
    error_analysis       = aws_cloudwatch_query_definition.error_analysis.name
    performance_analysis = aws_cloudwatch_query_definition.performance_analysis.name
    data_quality_trends  = aws_cloudwatch_query_definition.data_quality_trends.name
  }
}

# EventBridge Rules
output "eventbridge_rules" {
  description = "EventBridge rules for automated responses"
  value = {
    pipeline_failure = aws_events_rule.pipeline_failure.name
  }
}

# Log Streams
output "log_streams" {
  description = "CloudWatch log streams created"
  value = {
    pipeline_orchestrator = aws_cloudwatch_log_stream.pipeline_orchestrator.name
    data_extraction       = aws_cloudwatch_log_stream.data_extraction.name
    data_transformation   = aws_cloudwatch_log_stream.data_transformation.name
  }
}

# Enhanced Metric Filters
output "enhanced_metric_filters" {
  description = "Enhanced metric filters for performance monitoring"
  value = {
    pipeline_latency   = aws_cloudwatch_log_metric_filter.pipeline_latency.name
    memory_utilization = aws_cloudwatch_log_metric_filter.memory_utilization.name
    throughput_metrics = aws_cloudwatch_log_metric_filter.throughput_metrics.name
  }
}

# Performance Metrics Namespaces
output "performance_metrics_namespace" {
  description = "CloudWatch namespace for performance metrics"
  value       = "Pipeline/Performance"
}

# Alerting System Outputs
output "alerting_lambda_functions" {
  description = "Lambda functions created for alerting system"
  value = {
    escalation_handler = aws_lambda_function.escalation_handler.function_name
    auto_recovery      = aws_lambda_function.auto_recovery.function_name
  }
}

output "alerting_lambda_function_arns" {
  description = "ARNs of Lambda functions created for alerting system"
  value = {
    escalation_handler = aws_lambda_function.escalation_handler.arn
    auto_recovery      = aws_lambda_function.auto_recovery.arn
  }
}

output "alerting_alarms" {
  description = "CloudWatch alarms created for critical pipeline metrics"
  value = {
    lambda_failure_rate        = aws_cloudwatch_metric_alarm.lambda_failure_rate.alarm_name
    lambda_duration_critical   = aws_cloudwatch_metric_alarm.lambda_duration_critical.alarm_name
    glue_job_failures         = aws_cloudwatch_metric_alarm.glue_job_failures.alarm_name
    data_quality_degradation  = aws_cloudwatch_metric_alarm.data_quality_degradation.alarm_name
    s3_storage_critical       = aws_cloudwatch_metric_alarm.s3_storage_critical.alarm_name
    pipeline_latency_critical = aws_cloudwatch_metric_alarm.pipeline_latency_critical.alarm_name
    sagemaker_endpoint_failures = var.sagemaker_endpoint_name != "" ? aws_cloudwatch_metric_alarm.sagemaker_endpoint_failures[0].alarm_name : null
    daily_cost_threshold      = var.enable_cost_monitoring ? aws_cloudwatch_metric_alarm.daily_cost_threshold[0].alarm_name : null
  }
}

output "composite_alarms" {
  description = "Composite alarms for complex monitoring scenarios"
  value = {
    pipeline_health         = aws_cloudwatch_composite_alarm.pipeline_health.alarm_name
    performance_degradation = aws_cloudwatch_composite_alarm.performance_degradation.alarm_name
  }
}

output "escalation_configuration" {
  description = "Escalation system configuration"
  value = {
    escalation_threshold_minutes = var.escalation_threshold_minutes
    auto_recovery_enabled       = var.enable_auto_recovery
    max_recovery_attempts       = var.max_recovery_attempts
    escalation_sns_topic_arn    = aws_sns_topic.escalation_alerts.arn
  }
}

output "sns_subscriptions_summary" {
  description = "Summary of SNS topic subscriptions created"
  value = {
    critical_email_subscriptions    = length(var.critical_alert_emails)
    critical_sms_subscriptions      = length(var.critical_alert_phone_numbers)
    warning_email_subscriptions     = length(var.warning_alert_emails)
    info_email_subscriptions        = length(var.info_notification_emails)
    escalation_email_subscriptions  = length(var.escalation_alert_emails)
    escalation_sms_subscriptions    = length(var.escalation_alert_phone_numbers)
    slack_integration_enabled       = var.slack_webhook_url != ""
    pagerduty_integration_enabled   = var.pagerduty_endpoint != ""
  }
}

output "monitoring_summary" {
  description = "Summary of monitoring resources created"
  value = {
    dashboards_created = [
      aws_cloudwatch_dashboard.pipeline_overview.dashboard_name,
      aws_cloudwatch_dashboard.data_quality.dashboard_name,
      aws_cloudwatch_dashboard.cost_performance.dashboard_name
    ]
    log_groups_created = [
      aws_cloudwatch_log_group.pipeline_logs.name,
      aws_cloudwatch_log_group.data_quality_logs.name,
      aws_cloudwatch_log_group.performance_logs.name
    ]
    alarms_created = concat([
      aws_cloudwatch_composite_alarm.pipeline_health.alarm_name,
      aws_cloudwatch_metric_alarm.lambda_errors.alarm_name,
      aws_cloudwatch_metric_alarm.glue_job_failures.alarm_name,
      aws_cloudwatch_metric_alarm.data_quality_degradation.alarm_name,
      aws_cloudwatch_metric_alarm.lambda_duration.alarm_name,
      aws_cloudwatch_metric_alarm.glue_job_duration.alarm_name,
      # New alerting alarms
      aws_cloudwatch_metric_alarm.lambda_failure_rate.alarm_name,
      aws_cloudwatch_metric_alarm.lambda_duration_critical.alarm_name,
      aws_cloudwatch_metric_alarm.s3_storage_critical.alarm_name,
      aws_cloudwatch_metric_alarm.pipeline_latency_critical.alarm_name,
      aws_cloudwatch_composite_alarm.performance_degradation.alarm_name
      ], var.enable_cost_monitoring ? [
      aws_cloudwatch_metric_alarm.s3_storage_growth[0].alarm_name,
      aws_cloudwatch_metric_alarm.daily_cost_threshold[0].alarm_name
    ] : [], var.sagemaker_endpoint_name != "" ? [
      aws_cloudwatch_metric_alarm.sagemaker_endpoint_failures[0].alarm_name
    ] : [])
    metric_filters_created = [
      aws_cloudwatch_log_metric_filter.data_quality_score.name,
      aws_cloudwatch_log_metric_filter.records_processed.name,
      aws_cloudwatch_log_metric_filter.validation_failures.name,
      aws_cloudwatch_log_metric_filter.cost_estimates.name,
      aws_cloudwatch_log_metric_filter.pipeline_latency.name,
      aws_cloudwatch_log_metric_filter.memory_utilization.name,
      aws_cloudwatch_log_metric_filter.throughput_metrics.name
    ]
    sns_topics_created = [
      aws_sns_topic.critical_alerts.arn,
      aws_sns_topic.warning_alerts.arn,
      aws_sns_topic.info_notifications.arn,
      aws_sns_topic.escalation_alerts.arn
    ]
    lambda_functions_created = [
      aws_lambda_function.escalation_handler.function_name,
      aws_lambda_function.auto_recovery.function_name
    ]
    xray_enabled            = var.enable_xray_tracing
    cost_monitoring_enabled = var.enable_cost_monitoring
    auto_recovery_enabled   = var.enable_auto_recovery
    insights_queries_created = [
      aws_cloudwatch_query_definition.error_analysis.name,
      aws_cloudwatch_query_definition.performance_analysis.name,
      aws_cloudwatch_query_definition.data_quality_trends.name
    ]
    eventbridge_rules_created = concat([
      aws_events_rule.pipeline_failure.name,
      aws_events_rule.escalation_trigger.name
    ], var.enable_auto_recovery ? [
      aws_events_rule.auto_recovery_trigger[0].name
    ] : [])
  }
}
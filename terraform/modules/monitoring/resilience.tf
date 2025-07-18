# ============================================================================
# SLA Monitoring and Automatic Resource Scaling Triggers
# ============================================================================

# This section implements task 7.4.3: Write SLA monitoring and automatic resource scaling triggers

# CloudWatch Alarm for SLA Breach - High Latency
resource "aws_cloudwatch_metric_alarm" "sla_latency_breach" {
  alarm_name          = "${var.project_name}-sla-latency-breach"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "5"
  metric_name         = "pipeline_end_to_end_latency"
  namespace           = "Pipeline/SLA"
  period              = "300"
  statistic           = "Average"
  threshold           = var.sla_latency_threshold_ms
  alarm_description   = "Pipeline end-to-end latency has breached the SLA"
  treat_missing_data  = "breaching"

  alarm_actions = [aws_sns_topic.escalation_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = merge(var.tags, {
    SLA_Metric = "Latency"
  })
}

# CloudWatch Alarm for SLA Breach - Data Freshness
resource "aws_cloudwatch_metric_alarm" "sla_data_freshness_breach" {
  alarm_name          = "${var.project_name}-sla-data-freshness-breach"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "pipeline_data_freshness"
  namespace           = "Pipeline/SLA"
  period              = "3600"
  statistic           = "Maximum"
  threshold           = var.sla_data_freshness_threshold_hours
  alarm_description   = "Data freshness has breached the SLA"
  treat_missing_data  = "breaching"

  alarm_actions = [aws_sns_topic.escalation_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = merge(var.tags, {
    SLA_Metric = "DataFreshness"
  })
}

# CloudWatch Alarm for SLA Breach - Uptime
resource "aws_cloudwatch_metric_alarm" "sla_uptime_breach" {
  alarm_name          = "${var.project_name}-sla-uptime-breach"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "pipeline_uptime_percentage"
  namespace           = "Pipeline/SLA"
  period              = "86400" # Daily check
  statistic           = "Average"
  threshold           = var.sla_uptime_percentage_threshold
  alarm_description   = "Pipeline uptime has breached the SLA"
  treat_missing_data  = "breaching"

  alarm_actions = [aws_sns_topic.escalation_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = merge(var.tags, {
    SLA_Metric = "Uptime"
  })
}

# ============================================================================
# Auto-Scaling Policies for Lambda and SageMaker
# ============================================================================

# This section implements task 7.4.1: Create auto-scaling policies for Lambda and SageMaker resources

# Lambda Provisioned Concurrency for Snowflake Extractor
resource "aws_lambda_provisioned_concurrency_config" "snowflake_extractor_concurrency" {
  count = var.enable_lambda_autoscaling ? 1 : 0

  function_name                     = var.snowflake_extractor_function_name
  provisioned_concurrent_executions = var.lambda_provisioned_concurrency
  qualifier                         = var.snowflake_extractor_function_alias

  lifecycle {
    ignore_changes = [provisioned_concurrent_executions]
  }
}

# Application Auto Scaling for Lambda Provisioned Concurrency
resource "aws_appautoscaling_target" "lambda_concurrency_target" {
  count = var.enable_lambda_autoscaling ? 1 : 0

  max_capacity       = var.lambda_max_concurrency
  min_capacity       = var.lambda_min_concurrency
  resource_id        = "function:${var.snowflake_extractor_function_name}:${var.snowflake_extractor_function_alias}"
  scalable_dimension = "lambda:function:ProvisionedConcurrency"
  service_namespace  = "lambda"

  depends_on = [aws_lambda_provisioned_concurrency_config.snowflake_extractor_concurrency]
}

resource "aws_appautoscaling_policy" "lambda_concurrency_scaling_policy" {
  count = var.enable_lambda_autoscaling ? 1 : 0

  name               = "${var.project_name}-lambda-concurrency-scaling-policy"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.lambda_concurrency_target[0].resource_id
  scalable_dimension = aws_appautoscaling_target.lambda_concurrency_target[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.lambda_concurrency_target[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "LambdaProvisionedConcurrencyUtilization"
    }
    target_value       = 0.75
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# Application Auto Scaling for SageMaker Endpoint
resource "aws_appautoscaling_target" "sagemaker_endpoint_target" {
  count = var.enable_sagemaker_autoscaling ? 1 : 0

  max_capacity       = var.sagemaker_max_instances
  min_capacity       = var.sagemaker_min_instances
  resource_id        = "endpoint/${var.sagemaker_endpoint_name}/variant/primary"
  scalable_dimension = "sagemaker:variant:DesiredInstanceCount"
  service_namespace  = "sagemaker"
}

resource "aws_appautoscaling_policy" "sagemaker_endpoint_scaling_policy" {
  count = var.enable_sagemaker_autoscaling ? 1 : 0

  name               = "${var.project_name}-sagemaker-endpoint-scaling-policy"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.sagemaker_endpoint_target[0].resource_id
  scalable_dimension = aws_appautoscaling_target.sagemaker_endpoint_target[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.sagemaker_endpoint_target[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "SageMakerVariantInvocationsPerInstance"
    }
    target_value       = var.sagemaker_invocations_per_instance
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# ============================================================================
# Failover Procedures for Critical Pipeline Components
# ============================================================================

# This section implements task 7.4.2: Implement failover procedures for critical pipeline components

# Route 53 Health Check for Primary Region Endpoint
resource "aws_route53_health_check" "primary_endpoint_health_check" {
  count = var.enable_failover ? 1 : 0

  fqdn              = var.sagemaker_endpoint_url
  port              = 443
  type              = "HTTPS"
  resource_path     = "/ping" # Assuming a /ping endpoint on the model for health checks
  failure_threshold = 3
  request_interval  = 30

  tags = merge(var.tags, {
    Name = "${var.project_name}-primary-endpoint-health-check"
  })
}

# Route 53 DNS Failover Record for SageMaker Endpoint
resource "aws_route53_record" "sagemaker_failover_record" {
  count = var.enable_failover ? 1 : 0

  zone_id = var.route53_zone_id
  name    = "sagemaker-endpoint.${var.domain_name}"
  type    = "CNAME"
  ttl     = "60"

  failover_routing_policy {
    type = "PRIMARY"
  }

  set_identifier = "${var.project_name}-primary"
  health_check_id = aws_route53_health_check.primary_endpoint_health_check[0].id
  records         = [var.sagemaker_endpoint_url]
}

resource "aws_route53_record" "sagemaker_secondary_failover_record" {
  count = var.enable_failover ? 1 : 0

  zone_id = var.route53_zone_id
  name    = "sagemaker-endpoint.${var.domain_name}"
  type    = "CNAME"
  ttl     = "60"

  failover_routing_policy {
    type = "SECONDARY"
  }

  set_identifier = "${var.project_name}-secondary"
  records         = [var.secondary_sagemaker_endpoint_url] # URL of the endpoint in the failover region
}

# CloudWatch Alarm for Failover Event
resource "aws_cloudwatch_metric_alarm" "failover_event_alarm" {
  count = var.enable_failover ? 1 : 0

  alarm_name          = "${var.project_name}-failover-event"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = "60"
  statistic           = "Minimum"
  threshold           = "1" # Alarm when health check fails
  alarm_description   = "A failover event has occurred for the SageMaker endpoint"

  dimensions = {
    HealthCheckId = aws_route53_health_check.primary_endpoint_health_check[0].id
  }

  alarm_actions = [aws_sns_topic.escalation_alerts.arn]
  ok_actions    = [aws_sns_topic.info_notifications.arn]

  tags = merge(var.tags, {
    Name = "${var.project_name}-failover-alarm"
  })
}

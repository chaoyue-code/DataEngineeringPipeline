# Example: Basic Monitoring Configuration
# This example shows how to configure the monitoring module with basic settings

module "monitoring" {
  source = "../"

  project_name = "snowflake-pipeline"
  environment  = "dev"
  aws_region   = "us-east-1"

  # Lambda Function Names (these should match your actual function names)
  snowflake_extractor_function_name   = "snowflake-pipeline-dev-snowflake-extractor"
  pipeline_orchestrator_function_name = "snowflake-pipeline-dev-pipeline-orchestrator"
  data_quality_monitor_function_name  = "snowflake-pipeline-dev-data-quality-monitor"

  # Glue Job Names (these should match your actual job names)
  bronze_to_silver_job_name = "snowflake-pipeline-dev-bronze-to-silver"
  silver_to_gold_job_name   = "snowflake-pipeline-dev-silver-to-gold"

  # S3 Resources
  data_lake_bucket_name = "snowflake-pipeline-dev-data-lake"

  # SageMaker Resources (optional - leave empty if not using SageMaker)
  sagemaker_endpoint_name = ""

  # SNS Topics (leave empty to create new topics automatically)
  critical_sns_topic_arn = ""
  warning_sns_topic_arn  = ""
  info_sns_topic_arn     = ""

  # Basic Configuration
  log_retention_days         = 14
  enable_cost_monitoring     = true
  enable_xray_tracing        = true
  enable_detailed_monitoring = true

  # Conservative Thresholds for Development
  lambda_error_threshold       = 10
  data_quality_threshold       = 0.7
  daily_cost_threshold         = 50
  lambda_duration_threshold_ms = 60000

  tags = {
    Environment = "dev"
    Team        = "data-engineering"
    Project     = "snowflake-pipeline"
  }
}

# Output the dashboard URLs for easy access
output "dashboard_urls" {
  description = "URLs to access CloudWatch dashboards"
  value = {
    pipeline_overview = module.monitoring.pipeline_overview_dashboard_url
    data_quality      = module.monitoring.data_quality_dashboard_url
    cost_performance  = module.monitoring.cost_performance_dashboard_url
  }
}

# Output SNS topic ARNs for manual subscription setup
output "sns_topics" {
  description = "SNS topic ARNs for setting up subscriptions"
  value       = module.monitoring.sns_topic_arns
}
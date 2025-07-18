# Global Outputs
output "aws_region" {
  description = "AWS region"
  value       = data.aws_region.current.name
}

output "aws_account_id" {
  description = "AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "project_name" {
  description = "Project name"
  value       = var.project_name
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

# Networking Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = module.networking.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.networking.private_subnet_ids
}

output "database_subnet_ids" {
  description = "IDs of the database subnets"
  value       = module.networking.database_subnet_ids
}

output "nat_gateway_ids" {
  description = "IDs of the NAT Gateways"
  value       = module.networking.nat_gateway_ids
}

# Storage Outputs
output "data_lake_bucket_name" {
  description = "Name of the S3 data lake bucket"
  value       = module.storage.data_lake_bucket_name
}

output "data_lake_bucket_arn" {
  description = "ARN of the S3 data lake bucket"
  value       = module.storage.data_lake_bucket_arn
}

output "data_lake_bucket_domain_name" {
  description = "Domain name of the S3 data lake bucket"
  value       = module.storage.data_lake_bucket_domain_name
}

# Compute Outputs
output "lambda_functions" {
  description = "Lambda function details"
  value       = module.compute.lambda_functions
  sensitive   = true
}

output "glue_catalog_database_name" {
  description = "Name of the Glue catalog database"
  value       = module.compute.glue_catalog_database_name
}

output "glue_crawlers" {
  description = "Glue crawler details"
  value       = module.compute.glue_crawlers
}

output "glue_jobs" {
  description = "Glue job details"
  value       = module.compute.glue_jobs
}

# ML Outputs
output "sagemaker_domain_id" {
  description = "SageMaker domain ID"
  value       = module.ml.sagemaker_domain_id
}

# Note: SageMaker execution role ARN is now available in the IAM module outputs

output "feature_store_details" {
  description = "SageMaker Feature Store details"
  value       = module.ml.feature_store_details
}

# Encryption Outputs
output "encryption_config" {
  description = "Complete encryption configuration"
  value       = module.encryption.encryption_config
  sensitive   = true
}

output "kms_key_arns" {
  description = "Map of all KMS key ARNs"
  value       = module.encryption.kms_key_arns
}

output "snowflake_secret_arn" {
  description = "ARN of the Snowflake credentials secret"
  value       = module.encryption.snowflake_secret_arn
  sensitive   = true
}

output "encryption_summary" {
  description = "Summary of encryption configuration"
  value       = module.encryption.encryption_summary
}

# IAM Outputs
output "lambda_roles" {
  description = "Lambda IAM role ARNs"
  value       = module.iam.lambda_roles
}

output "glue_roles" {
  description = "Glue IAM role ARNs"
  value       = module.iam.glue_roles
}

output "sagemaker_roles" {
  description = "SageMaker IAM role ARNs"
  value       = module.iam.sagemaker_roles
}

output "orchestration_roles" {
  description = "Orchestration service IAM role ARNs"
  value       = module.iam.orchestration_roles
}

output "iam_summary" {
  description = "Summary of IAM resources created"
  value       = module.iam.iam_summary
}

# Glue Data Catalog and ETL Outputs
output "glue_database_names" {
  description = "Names of Glue databases by layer"
  value       = module.glue.database_names
}

output "bronze_crawler_names" {
  description = "Names of bronze layer crawlers"
  value       = module.glue.bronze_crawler_names
}

output "silver_crawler_names" {
  description = "Names of silver layer crawlers"
  value       = module.glue.silver_crawler_names
}

output "gold_crawler_names" {
  description = "Names of gold layer crawlers"
  value       = module.glue.gold_crawler_names
}

output "all_crawler_names" {
  description = "List of all crawler names"
  value       = module.glue.all_crawler_names
}

output "crawler_trigger_lambda_arn" {
  description = "ARN of the Lambda function that triggers crawlers"
  value       = module.glue.crawler_trigger_lambda_arn
}

output "glue_configuration_summary" {
  description = "Summary of Glue configuration"
  value       = module.glue.crawler_configuration_summary
}

# Monitoring Outputs
output "monitoring_dashboard_urls" {
  description = "URLs for CloudWatch dashboards"
  value = {
    pipeline_overview  = module.monitoring.pipeline_overview_dashboard_url
    data_quality      = module.monitoring.data_quality_dashboard_url
    cost_performance  = module.monitoring.cost_performance_dashboard_url
  }
}

output "monitoring_dashboard_names" {
  description = "Names of CloudWatch dashboards"
  value = {
    pipeline_overview  = module.monitoring.pipeline_overview_dashboard_name
    data_quality      = module.monitoring.data_quality_dashboard_name
    cost_performance  = module.monitoring.cost_performance_dashboard_name
  }
}

output "monitoring_log_groups" {
  description = "CloudWatch log group information"
  value = {
    pipeline_logs      = module.monitoring.pipeline_log_group_name
    data_quality_logs  = module.monitoring.data_quality_log_group_name
    performance_logs   = module.monitoring.performance_log_group_name
  }
}

output "monitoring_alarms" {
  description = "CloudWatch alarm information"
  value = {
    composite_alarm     = module.monitoring.composite_alarm_name
    lambda_errors      = module.monitoring.lambda_errors_alarm_name
    glue_job_failures  = module.monitoring.glue_job_failures_alarm_name
    data_quality       = module.monitoring.data_quality_alarm_name
  }
}

output "monitoring_metrics_namespaces" {
  description = "Custom CloudWatch metrics namespaces"
  value = {
    data_quality = module.monitoring.data_quality_metrics_namespace
    processing   = module.monitoring.processing_metrics_namespace
    cost         = module.monitoring.cost_metrics_namespace
  }
}

output "monitoring_summary" {
  description = "Complete monitoring configuration summary"
  value       = module.monitoring.monitoring_summary
}

output "monitoring_sns_topics" {
  description = "SNS topic ARNs for alerting"
  value       = module.monitoring.sns_topic_arns
}

output "monitoring_insights_queries" {
  description = "CloudWatch Insights queries for log analysis"
  value       = module.monitoring.cloudwatch_insights_queries
}

output "monitoring_xray_config" {
  description = "X-Ray tracing configuration"
  value = {
    enabled      = var.enable_xray_tracing
    sampling_rule = module.monitoring.xray_sampling_rule_name
    sampling_rate = var.xray_sampling_rate
  }
}
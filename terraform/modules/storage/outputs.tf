# Storage Module Outputs

output "data_lake_bucket_name" {
  description = "Name of the S3 data lake bucket"
  value       = aws_s3_bucket.data_lake.bucket
}

output "data_lake_bucket_id" {
  description = "ID of the S3 data lake bucket"
  value       = aws_s3_bucket.data_lake.id
}

output "data_lake_bucket_arn" {
  description = "ARN of the S3 data lake bucket"
  value       = aws_s3_bucket.data_lake.arn
}

output "data_lake_bucket_domain_name" {
  description = "Domain name of the S3 data lake bucket"
  value       = aws_s3_bucket.data_lake.bucket_domain_name
}

output "data_lake_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 data lake bucket"
  value       = aws_s3_bucket.data_lake.bucket_regional_domain_name
}

output "access_logs_bucket_name" {
  description = "Name of the S3 access logs bucket"
  value       = aws_s3_bucket.access_logs.bucket
}

output "access_logs_bucket_arn" {
  description = "ARN of the S3 access logs bucket"
  value       = aws_s3_bucket.access_logs.arn
}

output "bucket_folders" {
  description = "S3 bucket folder structure"
  value = {
    bronze_folders  = [for k, v in local.medallion_folders : k if startswith(k, "bronze/")]
    silver_folders  = [for k, v in local.medallion_folders : k if startswith(k, "silver/")]
    gold_folders    = [for k, v in local.medallion_folders : k if startswith(k, "gold/")]
    scripts_folders = [for k, v in local.medallion_folders : k if startswith(k, "scripts/")]
    temp_folders    = [for k, v in local.medallion_folders : k if startswith(k, "temp/")]
    logs_folders    = [for k, v in local.medallion_folders : k if startswith(k, "logs/")]
    metadata_folders = [for k, v in local.medallion_folders : k if startswith(k, "metadata/")]
  }
}

output "lifecycle_configuration" {
  description = "S3 bucket lifecycle configuration details"
  value = {
    bronze_lifecycle_days = var.bronze_lifecycle_days
    silver_lifecycle_days = var.silver_lifecycle_days
    gold_lifecycle_days   = var.gold_lifecycle_days
  }
}

output "kms_key_arn" {
  description = "ARN of the KMS key for S3 encryption"
  value       = var.enable_encryption ? aws_kms_key.data_lake_key[0].arn : null
}

output "kms_key_id" {
  description = "ID of the KMS key for S3 encryption"
  value       = var.enable_encryption ? aws_kms_key.data_lake_key[0].key_id : null
}

output "medallion_folders" {
  description = "Medallion architecture folder structure"
  value       = local.medallion_folders
}

output "bucket_policy" {
  description = "S3 bucket policy details"
  value = {
    policy_attached = true
    secure_transport_enforced = true
    pipeline_access_enabled = true
  }
}

output "event_notifications" {
  description = "Event notification configuration details"
  value = {
    eventbridge_enabled = true
    custom_event_bus_name = aws_cloudwatch_event_bus.data_pipeline.name
    custom_event_bus_arn = aws_cloudwatch_event_bus.data_pipeline.arn
    event_rules = {
      bronze_data_arrival = aws_cloudwatch_event_rule.bronze_data_arrival.name
      silver_data_ready = aws_cloudwatch_event_rule.silver_data_ready.name
      gold_data_published = aws_cloudwatch_event_rule.gold_data_published.name
      pipeline_failure = aws_cloudwatch_event_rule.pipeline_failure.name
    }
    sns_topics = {
      data_pipeline_notifications = aws_sns_topic.data_pipeline_notifications.arn
      pipeline_alerts = aws_sns_topic.pipeline_alerts.arn
    }
  }
}
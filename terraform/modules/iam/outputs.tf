# IAM Module Outputs

# =============================================================================
# LAMBDA ROLE OUTPUTS
# =============================================================================

output "snowflake_extractor_role_arn" {
  description = "ARN of the Snowflake extractor Lambda role"
  value       = aws_iam_role.snowflake_extractor_role.arn
}

output "snowflake_extractor_role_name" {
  description = "Name of the Snowflake extractor Lambda role"
  value       = aws_iam_role.snowflake_extractor_role.name
}

output "pipeline_orchestrator_role_arn" {
  description = "ARN of the pipeline orchestrator Lambda role"
  value       = aws_iam_role.pipeline_orchestrator_role.arn
}

output "pipeline_orchestrator_role_name" {
  description = "Name of the pipeline orchestrator Lambda role"
  value       = aws_iam_role.pipeline_orchestrator_role.name
}

output "data_quality_monitor_role_arn" {
  description = "ARN of the data quality monitor Lambda role"
  value       = aws_iam_role.data_quality_monitor_role.arn
}

output "data_quality_monitor_role_name" {
  description = "Name of the data quality monitor Lambda role"
  value       = aws_iam_role.data_quality_monitor_role.name
}

output "notification_handler_role_arn" {
  description = "ARN of the notification handler Lambda role"
  value       = aws_iam_role.notification_handler_role.arn
}

output "notification_handler_role_name" {
  description = "Name of the notification handler Lambda role"
  value       = aws_iam_role.notification_handler_role.name
}

# =============================================================================
# GLUE ROLE OUTPUTS
# =============================================================================

output "glue_service_role_arn" {
  description = "ARN of the Glue service role"
  value       = aws_iam_role.glue_service_role.arn
}

output "glue_service_role_name" {
  description = "Name of the Glue service role"
  value       = aws_iam_role.glue_service_role.name
}

output "glue_crawler_role_arn" {
  description = "ARN of the Glue crawler role"
  value       = aws_iam_role.glue_crawler_role.arn
}

output "glue_crawler_role_name" {
  description = "Name of the Glue crawler role"
  value       = aws_iam_role.glue_crawler_role.name
}

# =============================================================================
# SAGEMAKER ROLE OUTPUTS
# =============================================================================

output "sagemaker_execution_role_arn" {
  description = "ARN of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_execution_role.arn
}

output "sagemaker_execution_role_name" {
  description = "Name of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_execution_role.name
}

output "sagemaker_feature_store_role_arn" {
  description = "ARN of the SageMaker Feature Store role"
  value       = aws_iam_role.sagemaker_feature_store_role.arn
}

output "sagemaker_feature_store_role_name" {
  description = "Name of the SageMaker Feature Store role"
  value       = aws_iam_role.sagemaker_feature_store_role.name
}

# =============================================================================
# ORCHESTRATION ROLE OUTPUTS
# =============================================================================

output "eventbridge_role_arn" {
  description = "ARN of the EventBridge role"
  value       = aws_iam_role.eventbridge_role.arn
}

output "eventbridge_role_name" {
  description = "Name of the EventBridge role"
  value       = aws_iam_role.eventbridge_role.name
}

output "step_functions_role_arn" {
  description = "ARN of the Step Functions role"
  value       = aws_iam_role.step_functions_role.arn
}

output "step_functions_role_name" {
  description = "Name of the Step Functions role"
  value       = aws_iam_role.step_functions_role.name
}

# =============================================================================
# MONITORING ROLE OUTPUTS
# =============================================================================

output "cloudwatch_role_arn" {
  description = "ARN of the CloudWatch role"
  value       = aws_iam_role.cloudwatch_role.arn
}

output "cloudwatch_role_name" {
  description = "Name of the CloudWatch role"
  value       = aws_iam_role.cloudwatch_role.name
}

# =============================================================================
# CROSS-SERVICE ROLE OUTPUTS
# =============================================================================

output "s3_lambda_trigger_role_arn" {
  description = "ARN of the S3 Lambda trigger role"
  value       = aws_iam_role.s3_lambda_trigger_role.arn
}

output "s3_lambda_trigger_role_name" {
  description = "Name of the S3 Lambda trigger role"
  value       = aws_iam_role.s3_lambda_trigger_role.name
}

# =============================================================================
# KMS KEY OUTPUTS
# =============================================================================

output "iam_kms_key_arn" {
  description = "ARN of the IAM KMS key"
  value       = var.enable_kms_encryption ? aws_kms_key.iam_key[0].arn : null
}

output "iam_kms_key_id" {
  description = "ID of the IAM KMS key"
  value       = var.enable_kms_encryption ? aws_kms_key.iam_key[0].key_id : null
}

output "iam_kms_alias_name" {
  description = "Alias name of the IAM KMS key"
  value       = var.enable_kms_encryption ? aws_kms_alias.iam_key_alias[0].name : null
}

# =============================================================================
# ROLE COLLECTIONS FOR CONVENIENCE
# =============================================================================

output "lambda_roles" {
  description = "Map of all Lambda role ARNs"
  value = {
    snowflake_extractor  = aws_iam_role.snowflake_extractor_role.arn
    pipeline_orchestrator = aws_iam_role.pipeline_orchestrator_role.arn
    data_quality_monitor = aws_iam_role.data_quality_monitor_role.arn
    notification_handler = aws_iam_role.notification_handler_role.arn
  }
}

output "glue_roles" {
  description = "Map of all Glue role ARNs"
  value = {
    service = aws_iam_role.glue_service_role.arn
    crawler = aws_iam_role.glue_crawler_role.arn
  }
}

output "sagemaker_roles" {
  description = "Map of all SageMaker role ARNs"
  value = {
    execution     = aws_iam_role.sagemaker_execution_role.arn
    feature_store = aws_iam_role.sagemaker_feature_store_role.arn
  }
}

output "orchestration_roles" {
  description = "Map of all orchestration role ARNs"
  value = {
    eventbridge     = aws_iam_role.eventbridge_role.arn
    step_functions  = aws_iam_role.step_functions_role.arn
  }
}

# =============================================================================
# SUMMARY OUTPUT
# =============================================================================

output "iam_summary" {
  description = "Summary of all IAM resources created"
  value = {
    lambda_roles_count      = 4
    glue_roles_count       = 2
    sagemaker_roles_count  = 2
    orchestration_roles_count = 2
    monitoring_roles_count = 1
    cross_service_roles_count = 1
    total_roles_count      = 12
    kms_encryption_enabled = var.enable_kms_encryption
    vpc_access_enabled     = var.enable_vpc_access
  }
}
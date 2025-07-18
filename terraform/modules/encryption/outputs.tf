# Encryption Module Outputs

# =============================================================================
# MASTER KMS KEY OUTPUTS
# =============================================================================

output "pipeline_master_key_arn" {
  description = "ARN of the pipeline master KMS key"
  value       = aws_kms_key.pipeline_master_key.arn
}

output "pipeline_master_key_id" {
  description = "ID of the pipeline master KMS key"
  value       = aws_kms_key.pipeline_master_key.key_id
}

output "pipeline_master_key_alias" {
  description = "Alias of the pipeline master KMS key"
  value       = aws_kms_alias.pipeline_master_key_alias.name
}

# =============================================================================
# SERVICE-SPECIFIC KMS KEY OUTPUTS
# =============================================================================

output "s3_key_arn" {
  description = "ARN of the S3 KMS key"
  value       = var.create_service_specific_keys ? aws_kms_key.s3_data_lake_key[0].arn : aws_kms_key.pipeline_master_key.arn
}

output "s3_key_id" {
  description = "ID of the S3 KMS key"
  value       = var.create_service_specific_keys ? aws_kms_key.s3_data_lake_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
}

output "s3_key_alias" {
  description = "Alias of the S3 KMS key"
  value       = var.create_service_specific_keys ? aws_kms_alias.s3_data_lake_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
}

output "glue_key_arn" {
  description = "ARN of the Glue KMS key"
  value       = var.create_service_specific_keys ? aws_kms_key.glue_etl_key[0].arn : aws_kms_key.pipeline_master_key.arn
}

output "glue_key_id" {
  description = "ID of the Glue KMS key"
  value       = var.create_service_specific_keys ? aws_kms_key.glue_etl_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
}

output "glue_key_alias" {
  description = "Alias of the Glue KMS key"
  value       = var.create_service_specific_keys ? aws_kms_alias.glue_etl_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
}

output "sagemaker_key_arn" {
  description = "ARN of the SageMaker KMS key"
  value       = var.create_service_specific_keys ? aws_kms_key.sagemaker_key[0].arn : aws_kms_key.pipeline_master_key.arn
}

output "sagemaker_key_id" {
  description = "ID of the SageMaker KMS key"
  value       = var.create_service_specific_keys ? aws_kms_key.sagemaker_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
}

output "sagemaker_key_alias" {
  description = "Alias of the SageMaker KMS key"
  value       = var.create_service_specific_keys ? aws_kms_alias.sagemaker_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
}

output "secrets_manager_key_arn" {
  description = "ARN of the Secrets Manager KMS key"
  value       = var.create_service_specific_keys ? aws_kms_key.secrets_manager_key[0].arn : aws_kms_key.pipeline_master_key.arn
}

output "secrets_manager_key_id" {
  description = "ID of the Secrets Manager KMS key"
  value       = var.create_service_specific_keys ? aws_kms_key.secrets_manager_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
}

output "secrets_manager_key_alias" {
  description = "Alias of the Secrets Manager KMS key"
  value       = var.create_service_specific_keys ? aws_kms_alias.secrets_manager_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
}

output "cloudwatch_logs_key_arn" {
  description = "ARN of the CloudWatch Logs KMS key"
  value       = var.encrypt_cloudwatch_logs ? aws_kms_key.cloudwatch_logs_key[0].arn : null
}

output "cloudwatch_logs_key_id" {
  description = "ID of the CloudWatch Logs KMS key"
  value       = var.encrypt_cloudwatch_logs ? aws_kms_key.cloudwatch_logs_key[0].key_id : null
}

output "cloudwatch_logs_key_alias" {
  description = "Alias of the CloudWatch Logs KMS key"
  value       = var.encrypt_cloudwatch_logs ? aws_kms_alias.cloudwatch_logs_key_alias[0].name : null
}

# =============================================================================
# SECRETS MANAGER OUTPUTS
# =============================================================================

output "snowflake_secret_arn" {
  description = "ARN of the Snowflake credentials secret"
  value       = aws_secretsmanager_secret.snowflake_credentials.arn
}

output "snowflake_secret_name" {
  description = "Name of the Snowflake credentials secret"
  value       = aws_secretsmanager_secret.snowflake_credentials.name
}

output "database_secrets" {
  description = "Map of database secret ARNs"
  value = {
    for k, v in aws_secretsmanager_secret.database_credentials : k => {
      arn  = v.arn
      name = v.name
    }
  }
}

output "api_secrets" {
  description = "Map of API secret ARNs"
  value = {
    for k, v in aws_secretsmanager_secret.api_credentials : k => {
      arn  = v.arn
      name = v.name
    }
  }
}

# =============================================================================
# ENCRYPTION CONFIGURATION OUTPUT
# =============================================================================

output "encryption_config" {
  description = "Complete encryption configuration for other modules"
  value       = local.encryption_config
}

# =============================================================================
# COMPLIANCE AND MONITORING OUTPUTS
# =============================================================================

output "key_rotation_enabled" {
  description = "Whether key rotation is enabled"
  value       = var.enable_key_rotation
}

output "compliance_standards" {
  description = "List of compliance standards being adhered to"
  value       = var.compliance_standards
}

output "encryption_summary" {
  description = "Summary of encryption configuration"
  value = {
    master_key_created           = true
    service_specific_keys        = var.create_service_specific_keys
    key_rotation_enabled         = var.enable_key_rotation
    cloudwatch_logs_encrypted    = var.encrypt_cloudwatch_logs
    secrets_manager_encrypted    = true
    cross_account_access_enabled = length(var.trusted_account_ids) > 0
    compliance_monitoring        = var.enable_compliance_monitoring
    key_usage_monitoring         = var.enable_key_usage_monitoring
  }
}

# =============================================================================
# INTEGRATION OUTPUTS FOR OTHER MODULES
# =============================================================================

output "kms_key_arns" {
  description = "Map of all KMS key ARNs for easy reference"
  value = {
    master_key        = aws_kms_key.pipeline_master_key.arn
    s3_key           = var.create_service_specific_keys ? aws_kms_key.s3_data_lake_key[0].arn : aws_kms_key.pipeline_master_key.arn
    glue_key         = var.create_service_specific_keys ? aws_kms_key.glue_etl_key[0].arn : aws_kms_key.pipeline_master_key.arn
    sagemaker_key    = var.create_service_specific_keys ? aws_kms_key.sagemaker_key[0].arn : aws_kms_key.pipeline_master_key.arn
    secrets_key      = var.create_service_specific_keys ? aws_kms_key.secrets_manager_key[0].arn : aws_kms_key.pipeline_master_key.arn
    cloudwatch_key   = var.encrypt_cloudwatch_logs ? aws_kms_key.cloudwatch_logs_key[0].arn : null
  }
}

output "kms_key_ids" {
  description = "Map of all KMS key IDs for easy reference"
  value = {
    master_key        = aws_kms_key.pipeline_master_key.key_id
    s3_key           = var.create_service_specific_keys ? aws_kms_key.s3_data_lake_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
    glue_key         = var.create_service_specific_keys ? aws_kms_key.glue_etl_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
    sagemaker_key    = var.create_service_specific_keys ? aws_kms_key.sagemaker_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
    secrets_key      = var.create_service_specific_keys ? aws_kms_key.secrets_manager_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
    cloudwatch_key   = var.encrypt_cloudwatch_logs ? aws_kms_key.cloudwatch_logs_key[0].key_id : null
  }
}

output "kms_key_aliases" {
  description = "Map of all KMS key aliases for easy reference"
  value = {
    master_key        = aws_kms_alias.pipeline_master_key_alias.name
    s3_key           = var.create_service_specific_keys ? aws_kms_alias.s3_data_lake_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
    glue_key         = var.create_service_specific_keys ? aws_kms_alias.glue_etl_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
    sagemaker_key    = var.create_service_specific_keys ? aws_kms_alias.sagemaker_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
    secrets_key      = var.create_service_specific_keys ? aws_kms_alias.secrets_manager_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
    cloudwatch_key   = var.encrypt_cloudwatch_logs ? aws_kms_alias.cloudwatch_logs_key_alias[0].name : null
  }
}
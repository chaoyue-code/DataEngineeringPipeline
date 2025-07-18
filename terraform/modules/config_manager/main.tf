/**
 * # Configuration Management Module
 *
 * This module manages environment-specific configurations and parameter validation
 * for the Snowflake AWS Pipeline project. It provides:
 *
 * - Parameter validation with default values
 * - Environment-specific configuration management
 * - Centralized configuration storage
 * - Configuration documentation
 */

# Local variables for configuration management
locals {
  # Environment-specific configuration paths
  config_paths = {
    dev     = "${path.module}/../../config/dev"
    staging = "${path.module}/../../config/staging"
    prod    = "${path.module}/../../config/prod"
  }

  # Default configuration values
  default_config = {
    # Snowflake extraction configuration
    snowflake_extraction = {
      batch_size   = 10000
      max_batches  = 100
      max_retries  = 3
      output_format = "parquet"
    }

    # Glue job configuration
    glue_jobs = {
      bronze_to_silver = {
        timeout_minutes = 60
        max_retries     = 2
        max_concurrent  = 5
      }
      silver_to_gold = {
        timeout_minutes = 90
        max_retries     = 2
        max_concurrent  = 3
      }
    }

    # Lambda function configuration
    lambda_functions = {
      snowflake_extractor = {
        memory_size = 1024
        timeout     = 900
      }
      pipeline_orchestrator = {
        memory_size = 512
        timeout     = 300
      }
      data_quality_monitor = {
        memory_size = 1024
        timeout     = 600
      }
      feature_store_integration = {
        memory_size = 1024
        timeout     = 600
      }
      notification_alerting = {
        memory_size = 256
        timeout     = 60
      }
    }

    # SageMaker configuration
    sagemaker = {
      training_instance_type = "ml.m5.xlarge"
      inference_instance_type = "ml.t3.medium"
      endpoint_auto_scaling = {
        min_capacity = 1
        max_capacity = 3
        scale_in_cooldown = 300
        scale_out_cooldown = 300
        target_value = 70.0
      }
    }

    # Monitoring configuration
    monitoring = {
      alarm_evaluation_periods = 2
      lambda_error_threshold = 5
      data_quality_threshold = 0.8
      lambda_duration_threshold_ms = 30000
      glue_job_duration_threshold_minutes = 60
    }
  }

  # Merge environment-specific configuration with defaults
  config = merge(local.default_config, var.override_config)
}

# SSM Parameters for storing configuration
resource "aws_ssm_parameter" "config" {
  for_each = {
    "snowflake_extraction" = jsonencode(local.config.snowflake_extraction)
    "glue_jobs"           = jsonencode(local.config.glue_jobs)
    "lambda_functions"    = jsonencode(local.config.lambda_functions)
    "sagemaker"           = jsonencode(local.config.sagemaker)
    "monitoring"          = jsonencode(local.config.monitoring)
  }

  name        = "/${var.project_name}/${var.environment}/config/${each.key}"
  description = "Configuration for ${each.key} in ${var.environment} environment"
  type        = "String"
  value       = each.value
  tier        = "Standard"
  
  tags = merge(var.tags, {
    ConfigType = each.key
  })
}

# KMS key for encrypting sensitive configuration values
resource "aws_kms_key" "config_encryption" {
  description             = "KMS key for encrypting sensitive configuration values"
  deletion_window_in_days = var.key_deletion_window
  enable_key_rotation     = var.enable_key_rotation
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-config-encryption"
  })
}

resource "aws_kms_alias" "config_encryption" {
  name          = "alias/${var.project_name}-${var.environment}-config-encryption"
  target_key_id = aws_kms_key.config_encryption.key_id
}

# Secure parameter for sensitive configuration values
resource "aws_ssm_parameter" "secure_config" {
  for_each = var.secure_config

  name        = "/${var.project_name}/${var.environment}/secure-config/${each.key}"
  description = "Secure configuration for ${each.key} in ${var.environment} environment"
  type        = "SecureString"
  value       = each.value
  key_id      = aws_kms_key.config_encryption.key_id
  
  tags = merge(var.tags, {
    ConfigType = "secure"
  })
}

# Configuration validation using null_resource
resource "null_resource" "config_validation" {
  # This resource will be recreated whenever the configuration changes
  triggers = {
    config_hash = sha256(jsonencode(local.config))
  }

  # Use local-exec provisioner to run validation script
  provisioner "local-exec" {
    command = "${path.module}/scripts/validate_config.sh '${jsonencode(local.config)}'"
  }
}
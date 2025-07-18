# Encryption Module - Centralized KMS key management and encryption configurations

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# =============================================================================
# MASTER KMS KEY FOR PIPELINE ENCRYPTION
# =============================================================================

# Master KMS Key for the entire pipeline
resource "aws_kms_key" "pipeline_master_key" {
  description             = "Master KMS key for ${var.project_name} ${var.environment} pipeline encryption"
  deletion_window_in_days = var.key_deletion_window
  enable_key_rotation     = var.enable_key_rotation

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Pipeline Services"
        Effect = "Allow"
        Principal = {
          Service = [
            "s3.amazonaws.com",
            "glue.amazonaws.com",
            "sagemaker.amazonaws.com",
            "lambda.amazonaws.com",
            "secretsmanager.amazonaws.com",
            "logs.amazonaws.com"
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = [
              "s3.${data.aws_region.current.name}.amazonaws.com",
              "glue.${data.aws_region.current.name}.amazonaws.com",
              "sagemaker.${data.aws_region.current.name}.amazonaws.com",
              "lambda.${data.aws_region.current.name}.amazonaws.com",
              "secretsmanager.${data.aws_region.current.name}.amazonaws.com",
              "logs.${data.aws_region.current.name}.amazonaws.com"
            ]
          }
        }
      },
      {
        Sid    = "Allow Cross-Account Access"
        Effect = "Allow"
        Principal = {
          AWS = [for account_id in var.trusted_account_ids : "arn:aws:iam::${account_id}:root"]
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = [
              "s3.${data.aws_region.current.name}.amazonaws.com"
            ]
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-pipeline-master-key"
    Purpose     = "Pipeline Master Encryption"
    Environment = var.environment
    KeyType     = "Master"
  })
}

resource "aws_kms_alias" "pipeline_master_key_alias" {
  name          = "alias/${var.project_name}-${var.environment}-pipeline-master"
  target_key_id = aws_kms_key.pipeline_master_key.key_id
}

# =============================================================================
# SERVICE-SPECIFIC KMS KEYS
# =============================================================================

# S3 Data Lake KMS Key
resource "aws_kms_key" "s3_data_lake_key" {
  count = var.create_service_specific_keys ? 1 : 0

  description             = "KMS key for S3 data lake encryption in ${var.project_name} ${var.environment}"
  deletion_window_in_days = var.key_deletion_window
  enable_key_rotation     = var.enable_key_rotation

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow S3 Service"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      },
      {
        Sid    = "Allow Pipeline Roles"
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-*"
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-s3-data-lake-key"
    Purpose     = "S3 Data Lake Encryption"
    Environment = var.environment
    Service     = "S3"
  })
}

resource "aws_kms_alias" "s3_data_lake_key_alias" {
  count = var.create_service_specific_keys ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-s3-data-lake"
  target_key_id = aws_kms_key.s3_data_lake_key[0].key_id
}

# Glue ETL KMS Key
resource "aws_kms_key" "glue_etl_key" {
  count = var.create_service_specific_keys ? 1 : 0

  description             = "KMS key for Glue ETL encryption in ${var.project_name} ${var.environment}"
  deletion_window_in_days = var.key_deletion_window
  enable_key_rotation     = var.enable_key_rotation

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Glue Service"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "glue.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      },
      {
        Sid    = "Allow Glue Roles"
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-glue-*"
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-glue-etl-key"
    Purpose     = "Glue ETL Encryption"
    Environment = var.environment
    Service     = "Glue"
  })
}

resource "aws_kms_alias" "glue_etl_key_alias" {
  count = var.create_service_specific_keys ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-glue-etl"
  target_key_id = aws_kms_key.glue_etl_key[0].key_id
}

# SageMaker KMS Key
resource "aws_kms_key" "sagemaker_key" {
  count = var.create_service_specific_keys ? 1 : 0

  description             = "KMS key for SageMaker encryption in ${var.project_name} ${var.environment}"
  deletion_window_in_days = var.key_deletion_window
  enable_key_rotation     = var.enable_key_rotation

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow SageMaker Service"
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "sagemaker.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      },
      {
        Sid    = "Allow SageMaker Roles"
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-sagemaker-*"
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-sagemaker-key"
    Purpose     = "SageMaker Encryption"
    Environment = var.environment
    Service     = "SageMaker"
  })
}

resource "aws_kms_alias" "sagemaker_key_alias" {
  count = var.create_service_specific_keys ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-sagemaker"
  target_key_id = aws_kms_key.sagemaker_key[0].key_id
}

# Secrets Manager KMS Key
resource "aws_kms_key" "secrets_manager_key" {
  count = var.create_service_specific_keys ? 1 : 0

  description             = "KMS key for Secrets Manager encryption in ${var.project_name} ${var.environment}"
  deletion_window_in_days = var.key_deletion_window
  enable_key_rotation     = var.enable_key_rotation

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Secrets Manager Service"
        Effect = "Allow"
        Principal = {
          Service = "secretsmanager.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      },
      {
        Sid    = "Allow Lambda Functions"
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-*-lambda-*"
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-secrets-manager-key"
    Purpose     = "Secrets Manager Encryption"
    Environment = var.environment
    Service     = "SecretsManager"
  })
}

resource "aws_kms_alias" "secrets_manager_key_alias" {
  count = var.create_service_specific_keys ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-secrets-manager"
  target_key_id = aws_kms_key.secrets_manager_key[0].key_id
}

# =============================================================================
# AWS SECRETS MANAGER SECRETS
# =============================================================================

# Snowflake Connection Credentials
resource "aws_secretsmanager_secret" "snowflake_credentials" {
  name                    = "${var.project_name}/${var.environment}/snowflake/connection"
  description             = "Snowflake connection credentials for ${var.project_name} ${var.environment}"
  kms_key_id              = var.create_service_specific_keys ? aws_kms_key.secrets_manager_key[0].arn : aws_kms_key.pipeline_master_key.arn
  recovery_window_in_days = var.secret_recovery_window

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-snowflake-credentials"
    Purpose     = "Snowflake Connection"
    Environment = var.environment
    Service     = "Snowflake"
  })
}

# Snowflake Secret Version with placeholder values
resource "aws_secretsmanager_secret_version" "snowflake_credentials" {
  secret_id = aws_secretsmanager_secret.snowflake_credentials.id
  secret_string = jsonencode({
    account   = var.snowflake_account != "" ? var.snowflake_account : "your-snowflake-account"
    username  = var.snowflake_username != "" ? var.snowflake_username : "your-snowflake-username"
    password  = var.snowflake_password != "" ? var.snowflake_password : "your-snowflake-password"
    warehouse = var.snowflake_warehouse != "" ? var.snowflake_warehouse : "your-snowflake-warehouse"
    database  = var.snowflake_database != "" ? var.snowflake_database : "your-snowflake-database"
    schema    = var.snowflake_schema != "" ? var.snowflake_schema : "your-snowflake-schema"
    role      = var.snowflake_role != "" ? var.snowflake_role : "your-snowflake-role"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Database Connection Credentials (for other databases if needed)
resource "aws_secretsmanager_secret" "database_credentials" {
  for_each = var.additional_database_secrets

  name                    = "${var.project_name}/${var.environment}/database/${each.key}"
  description             = "Database connection credentials for ${each.key} in ${var.project_name} ${var.environment}"
  kms_key_id              = var.create_service_specific_keys ? aws_kms_key.secrets_manager_key[0].arn : aws_kms_key.pipeline_master_key.arn
  recovery_window_in_days = var.secret_recovery_window

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-${each.key}-credentials"
    Purpose     = "Database Connection"
    Environment = var.environment
    Database    = each.key
  })
}

# API Keys and External Service Credentials
resource "aws_secretsmanager_secret" "api_credentials" {
  for_each = var.api_secrets

  name                    = "${var.project_name}/${var.environment}/api/${each.key}"
  description             = "API credentials for ${each.key} in ${var.project_name} ${var.environment}"
  kms_key_id              = var.create_service_specific_keys ? aws_kms_key.secrets_manager_key[0].arn : aws_kms_key.pipeline_master_key.arn
  recovery_window_in_days = var.secret_recovery_window

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-${each.key}-api-credentials"
    Purpose     = "API Access"
    Environment = var.environment
    Service     = each.key
  })
}

# =============================================================================
# CLOUDWATCH LOGS ENCRYPTION
# =============================================================================

# CloudWatch Logs KMS Key
resource "aws_kms_key" "cloudwatch_logs_key" {
  count = var.encrypt_cloudwatch_logs ? 1 : 0

  description             = "KMS key for CloudWatch Logs encryption in ${var.project_name} ${var.environment}"
  deletion_window_in_days = var.key_deletion_window
  enable_key_rotation     = var.enable_key_rotation

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${data.aws_region.current.name}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:*"
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-cloudwatch-logs-key"
    Purpose     = "CloudWatch Logs Encryption"
    Environment = var.environment
    Service     = "CloudWatch"
  })
}

resource "aws_kms_alias" "cloudwatch_logs_key_alias" {
  count = var.encrypt_cloudwatch_logs ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-cloudwatch-logs"
  target_key_id = aws_kms_key.cloudwatch_logs_key[0].key_id
}

# =============================================================================
# KEY ROTATION MONITORING
# =============================================================================

# CloudWatch Alarm for Key Rotation
resource "aws_cloudwatch_metric_alarm" "kms_key_rotation" {
  count = var.enable_key_rotation_monitoring ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-kms-key-rotation-alarm"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "NumberOfKeysRotated"
  namespace           = "AWS/KMS"
  period              = "86400" # 24 hours
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors KMS key rotation for ${var.project_name} ${var.environment}"
  alarm_actions       = var.alarm_notification_arns

  dimensions = {
    KeyId = aws_kms_key.pipeline_master_key.key_id
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-kms-rotation-alarm"
    Purpose     = "KMS Key Rotation Monitoring"
    Environment = var.environment
  })
}

# =============================================================================
# ENCRYPTION CONFIGURATION OUTPUTS FOR OTHER MODULES
# =============================================================================

# Create a local map of encryption configurations for easy reference
locals {
  encryption_config = {
    master_key_arn    = aws_kms_key.pipeline_master_key.arn
    master_key_id     = aws_kms_key.pipeline_master_key.key_id
    master_key_alias  = aws_kms_alias.pipeline_master_key_alias.name
    
    s3_key_arn       = var.create_service_specific_keys ? aws_kms_key.s3_data_lake_key[0].arn : aws_kms_key.pipeline_master_key.arn
    s3_key_id        = var.create_service_specific_keys ? aws_kms_key.s3_data_lake_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
    s3_key_alias     = var.create_service_specific_keys ? aws_kms_alias.s3_data_lake_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
    
    glue_key_arn     = var.create_service_specific_keys ? aws_kms_key.glue_etl_key[0].arn : aws_kms_key.pipeline_master_key.arn
    glue_key_id      = var.create_service_specific_keys ? aws_kms_key.glue_etl_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
    glue_key_alias   = var.create_service_specific_keys ? aws_kms_alias.glue_etl_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
    
    sagemaker_key_arn    = var.create_service_specific_keys ? aws_kms_key.sagemaker_key[0].arn : aws_kms_key.pipeline_master_key.arn
    sagemaker_key_id     = var.create_service_specific_keys ? aws_kms_key.sagemaker_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
    sagemaker_key_alias  = var.create_service_specific_keys ? aws_kms_alias.sagemaker_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
    
    secrets_key_arn      = var.create_service_specific_keys ? aws_kms_key.secrets_manager_key[0].arn : aws_kms_key.pipeline_master_key.arn
    secrets_key_id       = var.create_service_specific_keys ? aws_kms_key.secrets_manager_key[0].key_id : aws_kms_key.pipeline_master_key.key_id
    secrets_key_alias    = var.create_service_specific_keys ? aws_kms_alias.secrets_manager_key_alias[0].name : aws_kms_alias.pipeline_master_key_alias.name
    
    cloudwatch_key_arn   = var.encrypt_cloudwatch_logs ? aws_kms_key.cloudwatch_logs_key[0].arn : null
    cloudwatch_key_id    = var.encrypt_cloudwatch_logs ? aws_kms_key.cloudwatch_logs_key[0].key_id : null
    cloudwatch_key_alias = var.encrypt_cloudwatch_logs ? aws_kms_alias.cloudwatch_logs_key_alias[0].name : null
  }
}
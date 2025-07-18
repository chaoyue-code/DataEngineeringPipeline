# Encryption Module Variables

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# =============================================================================
# KMS KEY CONFIGURATION
# =============================================================================

variable "enable_key_rotation" {
  description = "Enable automatic key rotation for KMS keys"
  type        = bool
  default     = true
}

variable "key_deletion_window" {
  description = "Number of days to wait before deleting KMS keys"
  type        = number
  default     = 7
  validation {
    condition     = var.key_deletion_window >= 7 && var.key_deletion_window <= 30
    error_message = "Key deletion window must be between 7 and 30 days."
  }
}

variable "create_service_specific_keys" {
  description = "Create separate KMS keys for each service instead of using master key"
  type        = bool
  default     = true
}

variable "trusted_account_ids" {
  description = "List of trusted AWS account IDs for cross-account KMS access"
  type        = list(string)
  default     = []
}

variable "enable_key_rotation_monitoring" {
  description = "Enable CloudWatch monitoring for key rotation"
  type        = bool
  default     = true
}

variable "alarm_notification_arns" {
  description = "List of SNS topic ARNs for KMS alarm notifications"
  type        = list(string)
  default     = []
}

# =============================================================================
# SECRETS MANAGER CONFIGURATION
# =============================================================================

variable "secret_recovery_window" {
  description = "Number of days to retain deleted secrets for recovery"
  type        = number
  default     = 7
  validation {
    condition     = var.secret_recovery_window >= 7 && var.secret_recovery_window <= 30
    error_message = "Secret recovery window must be between 7 and 30 days."
  }
}

# Snowflake Connection Parameters
variable "snowflake_account" {
  description = "Snowflake account identifier"
  type        = string
  default     = ""
  sensitive   = true
}

variable "snowflake_username" {
  description = "Snowflake username"
  type        = string
  default     = ""
  sensitive   = true
}

variable "snowflake_password" {
  description = "Snowflake password"
  type        = string
  default     = ""
  sensitive   = true
}

variable "snowflake_warehouse" {
  description = "Snowflake warehouse name"
  type        = string
  default     = ""
}

variable "snowflake_database" {
  description = "Snowflake database name"
  type        = string
  default     = ""
}

variable "snowflake_schema" {
  description = "Snowflake schema name"
  type        = string
  default     = ""
}

variable "snowflake_role" {
  description = "Snowflake role name"
  type        = string
  default     = ""
}

# Additional Database Secrets
variable "additional_database_secrets" {
  description = "Map of additional database secrets to create"
  type        = map(object({
    description = string
  }))
  default = {}
}

# API Secrets
variable "api_secrets" {
  description = "Map of API secrets to create"
  type        = map(object({
    description = string
  }))
  default = {}
}

# =============================================================================
# CLOUDWATCH LOGS ENCRYPTION
# =============================================================================

variable "encrypt_cloudwatch_logs" {
  description = "Enable encryption for CloudWatch Logs"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14
  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch Logs retention period."
  }
}

# =============================================================================
# ENCRYPTION POLICIES
# =============================================================================

variable "enforce_encryption_in_transit" {
  description = "Enforce encryption in transit for all services"
  type        = bool
  default     = true
}

variable "enforce_encryption_at_rest" {
  description = "Enforce encryption at rest for all services"
  type        = bool
  default     = true
}

variable "minimum_tls_version" {
  description = "Minimum TLS version for encryption in transit"
  type        = string
  default     = "1.2"
  validation {
    condition     = contains(["1.0", "1.1", "1.2", "1.3"], var.minimum_tls_version)
    error_message = "TLS version must be one of: 1.0, 1.1, 1.2, 1.3."
  }
}

# =============================================================================
# COMPLIANCE AND GOVERNANCE
# =============================================================================

variable "enable_compliance_monitoring" {
  description = "Enable compliance monitoring for encryption"
  type        = bool
  default     = true
}

variable "compliance_standards" {
  description = "List of compliance standards to adhere to"
  type        = list(string)
  default     = ["SOC2", "PCI-DSS", "GDPR"]
}

variable "enable_key_usage_monitoring" {
  description = "Enable monitoring of KMS key usage"
  type        = bool
  default     = true
}

variable "key_usage_alarm_threshold" {
  description = "Threshold for KMS key usage alarms (requests per day)"
  type        = number
  default     = 1000
}

# =============================================================================
# BACKUP AND DISASTER RECOVERY
# =============================================================================

variable "enable_cross_region_backup" {
  description = "Enable cross-region backup for secrets"
  type        = bool
  default     = false
}

variable "backup_region" {
  description = "AWS region for cross-region backups"
  type        = string
  default     = ""
}

variable "enable_secret_versioning" {
  description = "Enable versioning for secrets"
  type        = bool
  default     = true
}

variable "max_secret_versions" {
  description = "Maximum number of secret versions to retain"
  type        = number
  default     = 10
  validation {
    condition     = var.max_secret_versions >= 1 && var.max_secret_versions <= 100
    error_message = "Maximum secret versions must be between 1 and 100."
  }
}
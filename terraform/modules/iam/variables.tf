# IAM Module Variables

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

# S3 Bucket ARNs for IAM policies
variable "data_lake_bucket_arn" {
  description = "ARN of the data lake S3 bucket"
  type        = string
}

variable "sagemaker_bucket_arn" {
  description = "ARN of the SageMaker artifacts S3 bucket"
  type        = string
}

# Security Configuration
variable "enable_kms_encryption" {
  description = "Enable KMS encryption for IAM resources"
  type        = bool
  default     = true
}

variable "enable_vpc_access" {
  description = "Enable VPC access for Lambda functions"
  type        = bool
  default     = true
}

# Cross-service access configuration
variable "enable_cross_account_access" {
  description = "Enable cross-account access patterns"
  type        = bool
  default     = false
}

variable "trusted_account_ids" {
  description = "List of trusted AWS account IDs for cross-account access"
  type        = list(string)
  default     = []
}

# Resource naming patterns
variable "resource_prefix" {
  description = "Prefix for resource names (defaults to project_name-environment)"
  type        = string
  default     = ""
}

# IAM Policy customization
variable "custom_lambda_policies" {
  description = "Map of custom IAM policies to attach to Lambda roles"
  type        = map(string)
  default     = {}
}

variable "custom_glue_policies" {
  description = "Map of custom IAM policies to attach to Glue roles"
  type        = map(string)
  default     = {}
}

variable "custom_sagemaker_policies" {
  description = "Map of custom IAM policies to attach to SageMaker roles"
  type        = map(string)
  default     = {}
}

# Compliance and security settings
variable "enforce_mfa" {
  description = "Enforce MFA for sensitive operations"
  type        = bool
  default     = false
}

variable "session_duration" {
  description = "Maximum session duration for assumed roles (in seconds)"
  type        = number
  default     = 3600
  validation {
    condition     = var.session_duration >= 900 && var.session_duration <= 43200
    error_message = "Session duration must be between 900 and 43200 seconds."
  }
}

variable "external_id" {
  description = "External ID for cross-account role assumption (optional)"
  type        = string
  default     = ""
}

# Monitoring and logging
variable "enable_access_logging" {
  description = "Enable access logging for IAM roles"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14
}


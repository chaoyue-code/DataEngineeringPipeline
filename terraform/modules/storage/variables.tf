# Storage Module Variables

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "data_lake_bucket_name" {
  description = "Name for the S3 data lake bucket (will be auto-generated if null)"
  type        = string
  default     = null
}

variable "enable_versioning" {
  description = "Enable S3 bucket versioning"
  type        = bool
  default     = true
}

variable "enable_encryption" {
  description = "Enable S3 bucket encryption"
  type        = bool
  default     = true
}

variable "bronze_lifecycle_days" {
  description = "Number of days to keep bronze layer data"
  type        = number
  default     = 90
  validation {
    condition     = var.bronze_lifecycle_days > 0
    error_message = "Bronze lifecycle days must be greater than 0."
  }
}

variable "silver_lifecycle_days" {
  description = "Number of days to keep silver layer data"
  type        = number
  default     = 365
  validation {
    condition     = var.silver_lifecycle_days > 0
    error_message = "Silver lifecycle days must be greater than 0."
  }
}

variable "gold_lifecycle_days" {
  description = "Number of days to keep gold layer data"
  type        = number
  default     = 2555 # 7 years
  validation {
    condition     = var.gold_lifecycle_days > 0
    error_message = "Gold lifecycle days must be greater than 0."
  }
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
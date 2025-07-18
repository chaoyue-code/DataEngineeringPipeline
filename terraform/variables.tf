# Global Variables
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "snowflake-aws-pipeline"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "ap-southeast-2"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Networking Variables
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets"
  type        = list(string)
  default     = ["10.0.30.0/24", "10.0.40.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets"
  type        = bool
  default     = true
}

variable "enable_vpn_gateway" {
  description = "Enable VPN Gateway"
  type        = bool
  default     = false
}

# Storage Variables
variable "data_lake_bucket_name" {
  description = "Name for the S3 data lake bucket"
  type        = string
  default     = null
}

variable "enable_s3_versioning" {
  description = "Enable S3 bucket versioning"
  type        = bool
  default     = true
}

variable "enable_s3_encryption" {
  description = "Enable S3 bucket encryption"
  type        = bool
  default     = true
}

variable "bronze_lifecycle_days" {
  description = "Number of days to keep bronze layer data"
  type        = number
  default     = 90
}

variable "silver_lifecycle_days" {
  description = "Number of days to keep silver layer data"
  type        = number
  default     = 365
}

variable "gold_lifecycle_days" {
  description = "Number of days to keep gold layer data"
  type        = number
  default     = 2555 # 7 years
}

# Compute Variables
variable "lambda_runtime" {
  description = "Lambda runtime version"
  type        = string
  default     = "python3.11"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 900
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 1024
}

variable "glue_version" {
  description = "AWS Glue version"
  type        = string
  default     = "4.0"
}

variable "glue_worker_type" {
  description = "Glue worker type"
  type        = string
  default     = "G.1X"
  validation {
    condition     = contains(["Standard", "G.1X", "G.2X", "G.025X"], var.glue_worker_type)
    error_message = "Glue worker type must be one of: Standard, G.1X, G.2X, G.025X."
  }
}

variable "glue_number_of_workers" {
  description = "Number of Glue workers"
  type        = number
  default     = 2
}

# ML Variables
variable "sagemaker_instance_type" {
  description = "SageMaker instance type"
  type        = string
  default     = "ml.t3.medium"
}

variable "sagemaker_volume_size" {
  description = "SageMaker EBS volume size in GB"
  type        = number
  default     = 20
}

variable "enable_sagemaker_encryption" {
  description = "Enable SageMaker encryption"
  type        = bool
  default     = true
}

variable "feature_store_online_enabled" {
  description = "Enable SageMaker Feature Store online store"
  type        = bool
  default     = true
}

variable "feature_store_offline_enabled" {
  description = "Enable SageMaker Feature Store offline store"
  type        = bool
  default     = true
}

# IAM Variables
variable "enable_iam_kms_encryption" {
  description = "Enable KMS encryption for IAM resources"
  type        = bool
  default     = true
}

variable "enable_lambda_vpc_access" {
  description = "Enable VPC access for Lambda functions"
  type        = bool
  default     = true
}

# Encryption Variables
variable "enable_key_rotation" {
  description = "Enable automatic key rotation for KMS keys"
  type        = bool
  default     = true
}

variable "create_service_specific_keys" {
  description = "Create separate KMS keys for each service instead of using master key"
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

variable "secret_recovery_window" {
  description = "Number of days to retain deleted secrets for recovery"
  type        = number
  default     = 7
  validation {
    condition     = var.secret_recovery_window >= 7 && var.secret_recovery_window <= 30
    error_message = "Secret recovery window must be between 7 and 30 days."
  }
}

# Snowflake Configuration Variables
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

# CloudWatch Logs Encryption
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

# Compliance and Monitoring
variable "enable_compliance_monitoring" {
  description = "Enable compliance monitoring for encryption"
  type        = bool
  default     = true
}

variable "enable_key_usage_monitoring" {
  description = "Enable monitoring of KMS key usage"
  type        = bool
  default     = true
}

# Network Security Variables
variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs for network monitoring"
  type        = bool
  default     = true
}

variable "flow_log_retention_days" {
  description = "Number of days to retain VPC Flow Logs"
  type        = number
  default     = 14
  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.flow_log_retention_days)
    error_message = "Flow log retention days must be a valid CloudWatch Logs retention period."
  }
}

variable "enable_network_acls" {
  description = "Enable custom Network ACLs for additional security"
  type        = bool
  default     = true
}

variable "enable_vpc_endpoints" {
  description = "Enable VPC endpoints for AWS services"
  type        = bool
  default     = true
}

variable "vpc_endpoint_policy_restrictive" {
  description = "Use restrictive policies for VPC endpoints"
  type        = bool
  default     = true
}

# Glue Data Catalog and Crawler Variables
variable "glue_crawler_schedule" {
  description = "Cron expression for Glue crawler scheduling (optional)"
  type        = string
  default     = null
  
  validation {
    condition = var.glue_crawler_schedule == null || can(regex("^cron\\(.*\\)$", var.glue_crawler_schedule))
    error_message = "Glue crawler schedule must be a valid cron expression starting with 'cron('."
  }
}

variable "glue_crawler_schema_change_policy" {
  description = "Schema change policy for Glue crawlers"
  type = object({
    update_behavior = string
    delete_behavior = string
  })
  default = {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }
  
  validation {
    condition = contains(["UPDATE_IN_DATABASE", "LOG"], var.glue_crawler_schema_change_policy.update_behavior)
    error_message = "Update behavior must be either 'UPDATE_IN_DATABASE' or 'LOG'."
  }
  
  validation {
    condition = contains(["DELETE_FROM_DATABASE", "DEPRECATE_IN_DATABASE", "LOG"], var.glue_crawler_schema_change_policy.delete_behavior)
    error_message = "Delete behavior must be 'DELETE_FROM_DATABASE', 'DEPRECATE_IN_DATABASE', or 'LOG'."
  }
}

variable "glue_crawler_recrawl_policy" {
  description = "Recrawl policy for Glue crawlers"
  type = object({
    recrawl_behavior = string
  })
  default = {
    recrawl_behavior = "CRAWL_EVERYTHING"
  }
  
  validation {
    condition = contains(["CRAWL_EVERYTHING", "CRAWL_NEW_FOLDERS_ONLY"], var.glue_crawler_recrawl_policy.recrawl_behavior)
    error_message = "Recrawl behavior must be either 'CRAWL_EVERYTHING' or 'CRAWL_NEW_FOLDERS_ONLY'."
  }
}

variable "enable_glue_data_lineage" {
  description = "Enable data lineage tracking for Glue crawlers"
  type        = bool
  default     = true
}

variable "enable_event_driven_crawlers" {
  description = "Enable event-driven crawler triggers using EventBridge"
  type        = bool
  default     = true
}

# Monitoring and Alerting Variables
variable "critical_sns_topic_arn" {
  description = "ARN of SNS topic for critical alerts"
  type        = string
  default     = ""
}

variable "warning_sns_topic_arn" {
  description = "ARN of SNS topic for warning alerts"
  type        = string
  default     = ""
}

variable "info_sns_topic_arn" {
  description = "ARN of SNS topic for info notifications"
  type        = string
  default     = ""
}

variable "enable_custom_metrics" {
  description = "Enable custom CloudWatch metric filters"
  type        = bool
  default     = true
}

variable "dashboard_period_seconds" {
  description = "Default period for dashboard metrics in seconds"
  type        = number
  default     = 300
  validation {
    condition     = contains([60, 300, 900, 3600, 21600, 86400], var.dashboard_period_seconds)
    error_message = "Dashboard period must be one of: 60, 300, 900, 3600, 21600, 86400 seconds."
  }
}

variable "alarm_evaluation_periods" {
  description = "Number of periods to evaluate for CloudWatch alarms"
  type        = number
  default     = 2
  validation {
    condition     = var.alarm_evaluation_periods >= 1 && var.alarm_evaluation_periods <= 5
    error_message = "Alarm evaluation periods must be between 1 and 5."
  }
}

variable "lambda_error_threshold" {
  description = "Threshold for Lambda error alarms"
  type        = number
  default     = 5
}

variable "data_quality_threshold" {
  description = "Minimum acceptable data quality score (0.0 to 1.0)"
  type        = number
  default     = 0.8
  validation {
    condition     = var.data_quality_threshold >= 0.0 && var.data_quality_threshold <= 1.0
    error_message = "Data quality threshold must be between 0.0 and 1.0."
  }
}

variable "enable_cost_monitoring" {
  description = "Enable cost monitoring and alerting"
  type        = bool
  default     = true
}

variable "daily_cost_threshold" {
  description = "Daily cost threshold for alerts (USD)"
  type        = number
  default     = 100
  validation {
    condition     = var.daily_cost_threshold > 0
    error_message = "Daily cost threshold must be greater than 0."
  }
}

variable "lambda_duration_threshold_ms" {
  description = "Lambda duration threshold in milliseconds"
  type        = number
  default     = 30000
  validation {
    condition     = var.lambda_duration_threshold_ms > 0 && var.lambda_duration_threshold_ms <= 900000
    error_message = "Lambda duration threshold must be between 1 and 900000 milliseconds."
  }
}

variable "glue_job_duration_threshold_minutes" {
  description = "Glue job duration threshold in minutes"
  type        = number
  default     = 60
  validation {
    condition     = var.glue_job_duration_threshold_minutes > 0
    error_message = "Glue job duration threshold must be greater than 0 minutes."
  }
}

variable "enable_xray_tracing" {
  description = "Enable AWS X-Ray tracing for distributed tracing"
  type        = bool
  default     = true
}

variable "xray_sampling_rate" {
  description = "X-Ray sampling rate (0.0 to 1.0)"
  type        = number
  default     = 0.1
  validation {
    condition     = var.xray_sampling_rate >= 0.0 && var.xray_sampling_rate <= 1.0
    error_message = "X-Ray sampling rate must be between 0.0 and 1.0."
  }
}

variable "custom_metrics_namespace" {
  description = "Namespace for custom CloudWatch metrics"
  type        = string
  default     = "Pipeline"
  validation {
    condition     = can(regex("^[a-zA-Z0-9._/#-]+$", var.custom_metrics_namespace))
    error_message = "Custom metrics namespace must contain only alphanumeric characters, periods, underscores, forward slashes, hashes, and hyphens."
  }
}

variable "enable_detailed_monitoring" {
  description = "Enable detailed monitoring for all resources"
  type        = bool
  default     = true
}
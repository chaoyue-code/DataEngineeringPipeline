# Main Terraform configuration for Snowflake AWS Pipeline

# Configure the AWS Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources for common AWS resources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# Configuration Management Module
module "config_manager" {
  source = "./modules/config_manager"

  project_name = var.project_name
  environment  = var.environment
  
  # KMS Configuration
  enable_key_rotation = var.enable_key_rotation
  key_deletion_window = var.key_deletion_window
  
  # Override configuration with environment-specific values
  override_config = {
    # Lambda function configuration
    lambda_functions = {
      snowflake_extractor = {
        memory_size = var.lambda_memory_size
        timeout     = var.lambda_timeout
      }
    }
    
    # Glue job configuration
    glue_jobs = {
      bronze_to_silver = {
        timeout_minutes = 60
        max_retries     = 2
        max_concurrent  = var.glue_number_of_workers
      }
      silver_to_gold = {
        timeout_minutes = 90
        max_retries     = 2
        max_concurrent  = var.glue_number_of_workers
      }
    }
    
    # SageMaker configuration
    sagemaker = {
      training_instance_type = var.sagemaker_instance_type
      inference_instance_type = var.sagemaker_instance_type
    }
    
    # Monitoring configuration
    monitoring = {
      alarm_evaluation_periods = var.alarm_evaluation_periods
      lambda_error_threshold = var.lambda_error_threshold
      data_quality_threshold = var.data_quality_threshold
      lambda_duration_threshold_ms = var.lambda_duration_threshold_ms
      glue_job_duration_threshold_minutes = var.glue_job_duration_threshold_minutes
    }
  }
  
  # Secure configuration values
  secure_config = {
    snowflake_credentials = jsonencode({
      account   = var.snowflake_account
      username  = var.snowflake_username
      password  = var.snowflake_password
      warehouse = var.snowflake_warehouse
      database  = var.snowflake_database
      schema    = var.snowflake_schema
      role      = var.snowflake_role
    })
  }
  
  tags = var.common_tags
}

# Networking Module
module "networking" {
  source = "./modules/networking"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr

  availability_zones    = data.aws_availability_zones.available.names
  public_subnet_cidrs   = var.public_subnet_cidrs
  private_subnet_cidrs  = var.private_subnet_cidrs
  database_subnet_cidrs = var.database_subnet_cidrs

  enable_nat_gateway = var.enable_nat_gateway
  enable_vpn_gateway = var.enable_vpn_gateway

  # Network Security Configuration
  enable_vpc_flow_logs             = var.enable_vpc_flow_logs
  flow_log_retention_days          = var.flow_log_retention_days
  enable_network_acls              = var.enable_network_acls
  enable_vpc_endpoints             = var.enable_vpc_endpoints
  vpc_endpoint_policy_restrictive  = var.vpc_endpoint_policy_restrictive

  tags = var.common_tags
}

# Storage Module
module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment

  # S3 Configuration
  data_lake_bucket_name = var.data_lake_bucket_name
  enable_versioning     = var.enable_s3_versioning
  enable_encryption     = var.enable_s3_encryption

  # Lifecycle policies
  bronze_lifecycle_days = var.bronze_lifecycle_days
  silver_lifecycle_days = var.silver_lifecycle_days
  gold_lifecycle_days   = var.gold_lifecycle_days

  tags = var.common_tags
}

# Encryption Module
module "encryption" {
  source = "./modules/encryption"

  project_name = var.project_name
  environment  = var.environment

  # KMS Configuration
  enable_key_rotation           = var.enable_key_rotation
  create_service_specific_keys  = var.create_service_specific_keys
  key_deletion_window          = var.key_deletion_window

  # Secrets Manager Configuration
  secret_recovery_window = var.secret_recovery_window

  # Snowflake Configuration (if provided)
  snowflake_account   = var.snowflake_account
  snowflake_username  = var.snowflake_username
  snowflake_password  = var.snowflake_password
  snowflake_warehouse = var.snowflake_warehouse
  snowflake_database  = var.snowflake_database
  snowflake_schema    = var.snowflake_schema
  snowflake_role      = var.snowflake_role

  # CloudWatch Logs Encryption
  encrypt_cloudwatch_logs = var.encrypt_cloudwatch_logs
  log_retention_days     = var.log_retention_days

  # Compliance and Monitoring
  enable_compliance_monitoring = var.enable_compliance_monitoring
  enable_key_usage_monitoring  = var.enable_key_usage_monitoring

  tags = var.common_tags
}

# IAM Module
module "iam" {
  source = "./modules/iam"

  project_name = var.project_name
  environment  = var.environment

  # S3 Bucket ARNs for IAM policies
  data_lake_bucket_arn  = module.storage.data_lake_bucket_arn
  sagemaker_bucket_arn  = module.storage.data_lake_bucket_arn # Using data lake bucket for now, will be updated when SageMaker bucket is created separately

  # Security Configuration
  enable_kms_encryption = var.enable_iam_kms_encryption
  enable_vpc_access     = var.enable_lambda_vpc_access

  tags = var.common_tags
}

# Compute Module
module "compute" {
  source = "./modules/compute"

  project_name = var.project_name
  environment  = var.environment

  # VPC Configuration
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  database_subnet_ids = module.networking.database_subnet_ids

  # Lambda Configuration
  lambda_runtime     = var.lambda_runtime
  lambda_timeout     = var.lambda_timeout
  lambda_memory_size = var.lambda_memory_size

  # Glue Configuration
  glue_version           = var.glue_version
  glue_worker_type       = var.glue_worker_type
  glue_number_of_workers = var.glue_number_of_workers

  # Storage references
  data_lake_bucket_name = module.storage.data_lake_bucket_name
  data_lake_bucket_arn  = module.storage.data_lake_bucket_arn

  # IAM Role references
  lambda_roles = module.iam.lambda_roles
  glue_roles   = module.iam.glue_roles

  tags = var.common_tags
}

# Glue Module
module "glue" {
  source = "./modules/glue"

  project_name = var.project_name
  environment  = var.environment

  # Storage Configuration
  data_lake_bucket_name = module.storage.data_lake_bucket_name

  # IAM Role Configuration
  glue_service_role_arn       = module.iam.glue_service_role_arn
  lambda_execution_role_arn   = module.iam.pipeline_orchestrator_role_arn

  # Crawler Configuration
  crawler_schedule                = var.glue_crawler_schedule
  crawler_schema_change_policy    = var.glue_crawler_schema_change_policy
  crawler_recrawl_policy         = var.glue_crawler_recrawl_policy
  enable_data_lineage            = var.enable_glue_data_lineage
  enable_event_driven_crawlers   = var.enable_event_driven_crawlers

  # Data Catalog Configuration
  catalog_id = data.aws_caller_identity.current.account_id

  tags = var.common_tags
}

# ML Module
module "ml" {
  source = "./modules/ml"

  project_name = var.project_name
  environment  = var.environment

  # VPC Configuration
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids

  # SageMaker Configuration
  sagemaker_instance_type     = var.sagemaker_instance_type
  sagemaker_volume_size       = var.sagemaker_volume_size
  enable_sagemaker_encryption = var.enable_sagemaker_encryption

  # Feature Store Configuration
  feature_store_online_enabled  = var.feature_store_online_enabled
  feature_store_offline_enabled = var.feature_store_offline_enabled

  # Storage references
  data_lake_bucket_name = module.storage.data_lake_bucket_name
  data_lake_bucket_arn  = module.storage.data_lake_bucket_arn

  # IAM Role references
  sagemaker_roles = module.iam.sagemaker_roles

  tags = var.common_tags
}

# Monitoring Module
module "monitoring" {
  source = "./modules/monitoring"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region

  # Lambda Function Names from Compute Module
  snowflake_extractor_function_name     = module.compute.snowflake_extractor_function_name
  pipeline_orchestrator_function_name   = module.compute.pipeline_orchestrator_function_name
  data_quality_monitor_function_name    = module.compute.data_quality_monitor_function_name

  # Glue Job Names from Glue Module
  bronze_to_silver_job_name = module.glue.bronze_to_silver_job_name
  silver_to_gold_job_name   = module.glue.silver_to_gold_job_name

  # S3 Bucket Names from Storage Module
  data_lake_bucket_name = module.storage.data_lake_bucket_name

  # SageMaker Resources from ML Module
  sagemaker_endpoint_name = try(module.ml.sagemaker_endpoint_name, "")

  # SNS Topic ARNs (will be created by monitoring module or passed from external)
  critical_sns_topic_arn = var.critical_sns_topic_arn
  warning_sns_topic_arn  = var.warning_sns_topic_arn
  info_sns_topic_arn     = var.info_sns_topic_arn

  # CloudWatch Configuration
  log_retention_days                    = var.log_retention_days
  metric_filter_enabled                 = var.enable_custom_metrics
  dashboard_period_seconds              = var.dashboard_period_seconds
  alarm_evaluation_periods              = var.alarm_evaluation_periods
  lambda_error_threshold                = var.lambda_error_threshold
  data_quality_threshold                = var.data_quality_threshold
  enable_cost_monitoring                = var.enable_cost_monitoring
  daily_cost_threshold                  = var.daily_cost_threshold
  lambda_duration_threshold_ms          = var.lambda_duration_threshold_ms
  glue_job_duration_threshold_minutes   = var.glue_job_duration_threshold_minutes
  enable_xray_tracing                   = var.enable_xray_tracing
  xray_sampling_rate                    = var.xray_sampling_rate
  custom_metrics_namespace              = var.custom_metrics_namespace
  enable_detailed_monitoring            = var.enable_detailed_monitoring

  tags = var.common_tags
}
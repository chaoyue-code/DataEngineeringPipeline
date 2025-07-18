# ML Module Variables

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for SageMaker resources"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for SageMaker"
  type        = list(string)
}

variable "data_lake_bucket_name" {
  description = "Name of the S3 data lake bucket"
  type        = string
}

variable "data_lake_bucket_arn" {
  description = "ARN of the S3 data lake bucket"
  type        = string
}

variable "sagemaker_instance_type" {
  description = "SageMaker instance type"
  type        = string
  default     = "ml.t3.medium"
}

variable "sagemaker_volume_size" {
  description = "SageMaker EBS volume size in GB"
  type        = number
  default     = 20
  validation {
    condition     = var.sagemaker_volume_size >= 5 && var.sagemaker_volume_size <= 16384
    error_message = "SageMaker volume size must be between 5 and 16384 GB."
  }
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

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# IAM Role references from IAM module
variable "sagemaker_roles" {
  description = "Map of SageMaker role ARNs from IAM module"
  type        = map(string)
}

# Automated Training Configuration
variable "enable_automated_training" {
  description = "Enable automated SageMaker training jobs"
  type        = bool
  default     = false
}

variable "training_image_uri" {
  description = "Docker image URI for training jobs"
  type        = string
  default     = "763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-inference:0.23-1-cpu-py3"
}

variable "training_instance_type" {
  description = "Instance type for training jobs"
  type        = string
  default     = "ml.m5.large"
}

variable "training_instance_count" {
  description = "Number of instances for training jobs"
  type        = number
  default     = 1
}

variable "max_training_time" {
  description = "Maximum training time in seconds"
  type        = number
  default     = 3600
}

variable "training_hyperparameters" {
  description = "Hyperparameters for training jobs"
  type        = map(string)
  default = {
    "model-type"     = "random_forest"
    "n-estimators"   = "100"
    "max-depth"      = "10"
    "target-column"  = "target"
  }
}

variable "enable_vpc_training" {
  description = "Enable VPC configuration for training jobs"
  type        = bool
  default     = false
}

# Hyperparameter Tuning Configuration
variable "enable_hyperparameter_tuning" {
  description = "Enable SageMaker hyperparameter tuning"
  type        = bool
  default     = false
}

variable "tuning_objective_metric" {
  description = "Objective metric for hyperparameter tuning"
  type        = string
  default     = "validation:accuracy"
}

variable "max_tuning_jobs" {
  description = "Maximum number of tuning jobs"
  type        = number
  default     = 10
}

variable "max_parallel_tuning_jobs" {
  description = "Maximum number of parallel tuning jobs"
  type        = number
  default     = 2
}

variable "continuous_parameters" {
  description = "Continuous parameters for hyperparameter tuning"
  type = list(object({
    name         = string
    min_value    = string
    max_value    = string
    scaling_type = string
  }))
  default = [
    {
      name         = "learning-rate"
      min_value    = "0.001"
      max_value    = "0.3"
      scaling_type = "Logarithmic"
    }
  ]
}

variable "integer_parameters" {
  description = "Integer parameters for hyperparameter tuning"
  type = list(object({
    name         = string
    min_value    = string
    max_value    = string
    scaling_type = string
  }))
  default = [
    {
      name         = "n-estimators"
      min_value    = "50"
      max_value    = "200"
      scaling_type = "Linear"
    },
    {
      name         = "max-depth"
      min_value    = "3"
      max_value    = "20"
      scaling_type = "Linear"
    }
  ]
}

variable "categorical_parameters" {
  description = "Categorical parameters for hyperparameter tuning"
  type = list(object({
    name   = string
    values = list(string)
  }))
  default = [
    {
      name   = "model-type"
      values = ["random_forest", "gradient_boosting", "logistic_regression"]
    }
  ]
}

variable "static_hyperparameters" {
  description = "Static hyperparameters for tuning jobs"
  type        = map(string)
  default = {
    "target-column" = "target"
  }
}

# Model Deployment Configuration
variable "enable_model_deployment" {
  description = "Enable model deployment to SageMaker endpoints"
  type        = bool
  default     = false
}

variable "inference_image_uri" {
  description = "Docker image URI for inference"
  type        = string
  default     = "763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-inference:0.23-1-cpu-py3"
}

variable "model_data_url" {
  description = "S3 URL for model artifacts (optional, will use training output if empty)"
  type        = string
  default     = ""
}

variable "model_environment_variables" {
  description = "Environment variables for the model container"
  type        = map(string)
  default     = {}
}

variable "enable_vpc_inference" {
  description = "Enable VPC configuration for inference endpoints"
  type        = bool
  default     = false
}

variable "endpoint_instance_type" {
  description = "Instance type for inference endpoints"
  type        = string
  default     = "ml.t2.medium"
}

variable "endpoint_instance_count" {
  description = "Number of instances for inference endpoints"
  type        = number
  default     = 1
}

# Data Capture Configuration
variable "enable_data_capture" {
  description = "Enable data capture for model monitoring"
  type        = bool
  default     = false
}

variable "data_capture_sampling_percentage" {
  description = "Percentage of requests to capture for monitoring"
  type        = number
  default     = 100
  validation {
    condition     = var.data_capture_sampling_percentage >= 0 && var.data_capture_sampling_percentage <= 100
    error_message = "Data capture sampling percentage must be between 0 and 100."
  }
}

# Model Monitoring Configuration
variable "enable_model_monitoring" {
  description = "Enable CloudWatch alarms for model monitoring"
  type        = bool
  default     = false
}

variable "latency_threshold_ms" {
  description = "Latency threshold in milliseconds for alarms"
  type        = number
  default     = 1000
}
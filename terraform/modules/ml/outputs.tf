# ML Module Outputs

# Note: SageMaker IAM roles are now managed by the dedicated IAM module

output "sagemaker_security_group_id" {
  description = "Security group ID for SageMaker"
  value       = aws_security_group.sagemaker_sg.id
}

output "sagemaker_domain_id" {
  description = "SageMaker domain ID"
  value       = aws_sagemaker_domain.main.id
}

output "sagemaker_domain_arn" {
  description = "SageMaker domain ARN"
  value       = aws_sagemaker_domain.main.arn
}

output "sagemaker_domain_url" {
  description = "SageMaker domain URL"
  value       = aws_sagemaker_domain.main.url
}

output "sagemaker_artifacts_bucket_name" {
  description = "Name of the SageMaker artifacts S3 bucket"
  value       = aws_s3_bucket.sagemaker_artifacts.bucket
}

output "sagemaker_artifacts_bucket_arn" {
  description = "ARN of the SageMaker artifacts S3 bucket"
  value       = aws_s3_bucket.sagemaker_artifacts.arn
}

output "kms_key_arn" {
  description = "ARN of the KMS key for SageMaker encryption"
  value       = var.enable_sagemaker_encryption ? aws_kms_key.sagemaker_key[0].arn : null
}

output "kms_key_id" {
  description = "ID of the KMS key for SageMaker encryption"
  value       = var.enable_sagemaker_encryption ? aws_kms_key.sagemaker_key[0].key_id : null
}

output "feature_store_details" {
  description = "SageMaker Feature Store details"
  value = {
    online_feature_group_name = var.feature_store_online_enabled ? aws_sagemaker_feature_group.online_feature_group[0].feature_group_name : null
    online_feature_group_arn  = var.feature_store_online_enabled ? aws_sagemaker_feature_group.online_feature_group[0].arn : null
    online_enabled            = var.feature_store_online_enabled
    offline_enabled           = var.feature_store_offline_enabled
  }
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group details"
  value = {
    name = aws_cloudwatch_log_group.sagemaker_logs.name
    arn  = aws_cloudwatch_log_group.sagemaker_logs.arn
  }
}

output "model_package_group" {
  description = "SageMaker Model Package Group details"
  value = {
    name = aws_sagemaker_model_package_group.model_package_group.model_package_group_name
    arn  = aws_sagemaker_model_package_group.model_package_group.arn
  }
}

output "training_job_details" {
  description = "SageMaker training job details"
  value = var.enable_automated_training ? {
    name = aws_sagemaker_training_job.automated_training[0].training_job_name
    arn  = aws_sagemaker_training_job.automated_training[0].arn
  } : null
}

output "hyperparameter_tuning_job_details" {
  description = "SageMaker hyperparameter tuning job details"
  value = var.enable_hyperparameter_tuning ? {
    name = aws_sagemaker_hyperparameter_tuning_job.hyperparameter_tuning[0].hyperparameter_tuning_job_name
    arn  = aws_sagemaker_hyperparameter_tuning_job.hyperparameter_tuning[0].arn
  } : null
}

output "model_details" {
  description = "SageMaker model details"
  value = var.enable_model_deployment ? {
    name = aws_sagemaker_model.trained_model[0].name
    arn  = aws_sagemaker_model.trained_model[0].arn
  } : null
}

output "endpoint_details" {
  description = "SageMaker endpoint details"
  value = var.enable_model_deployment ? {
    name = aws_sagemaker_endpoint.model_endpoint[0].name
    arn  = aws_sagemaker_endpoint.model_endpoint[0].arn
    url  = "https://runtime.sagemaker.${data.aws_region.current.name}.amazonaws.com/endpoints/${aws_sagemaker_endpoint.model_endpoint[0].name}/invocations"
  } : null
}

output "endpoint_configuration_details" {
  description = "SageMaker endpoint configuration details"
  value = var.enable_model_deployment ? {
    name = aws_sagemaker_endpoint_configuration.model_endpoint_config[0].name
    arn  = aws_sagemaker_endpoint_configuration.model_endpoint_config[0].arn
  } : null
}

output "monitoring_alarms" {
  description = "CloudWatch monitoring alarms"
  value = var.enable_model_deployment && var.enable_model_monitoring ? {
    invocation_errors_alarm = aws_cloudwatch_metric_alarm.model_invocation_errors[0].arn
    latency_alarm          = aws_cloudwatch_metric_alarm.model_latency[0].arn
  } : null
}
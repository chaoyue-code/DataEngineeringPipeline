output "config" {
  description = "Merged configuration with defaults and overrides"
  value       = local.config
}

output "config_parameters" {
  description = "Map of SSM parameter ARNs for configuration values"
  value = {
    for key, param in aws_ssm_parameter.config : key => param.arn
  }
}

output "secure_config_parameters" {
  description = "Map of SSM parameter ARNs for secure configuration values"
  value = {
    for key, param in aws_ssm_parameter.secure_config : key => param.arn
  }
}

output "config_encryption_key_arn" {
  description = "ARN of the KMS key used for encrypting configuration values"
  value       = aws_kms_key.config_encryption.arn
}
# ML Module - SageMaker and ML-related resources

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Note: SageMaker IAM roles are now managed by the dedicated IAM module
# SageMaker resources will use roles from var.sagemaker_roles

# Security Group for SageMaker
resource "aws_security_group" "sagemaker_sg" {
  name_prefix = "${var.project_name}-${var.environment}-sagemaker"
  vpc_id      = var.vpc_id

  ingress {
    from_port = 443
    to_port   = 443
    protocol  = "tcp"
    self      = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-sagemaker-sg"
  })
}

# KMS Key for SageMaker encryption
resource "aws_kms_key" "sagemaker_key" {
  count = var.enable_sagemaker_encryption ? 1 : 0

  description             = "KMS key for SageMaker encryption in ${var.project_name} ${var.environment}"
  deletion_window_in_days = 7

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-sagemaker-key"
  })
}

resource "aws_kms_alias" "sagemaker_key_alias" {
  count = var.enable_sagemaker_encryption ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-sagemaker"
  target_key_id = aws_kms_key.sagemaker_key[0].key_id
}

# SageMaker Domain
resource "aws_sagemaker_domain" "main" {
  domain_name = "${var.project_name}-${var.environment}-domain"
  auth_mode   = "IAM"
  vpc_id      = var.vpc_id
  subnet_ids  = var.private_subnet_ids

  default_user_settings {
    execution_role = var.sagemaker_roles.execution

    security_groups = [aws_security_group.sagemaker_sg.id]

    dynamic "jupyter_server_app_settings" {
      for_each = var.enable_sagemaker_encryption ? [1] : []
      content {
        default_resource_spec {
          instance_type       = var.sagemaker_instance_type
          sagemaker_image_arn = "arn:aws:sagemaker:${data.aws_region.current.name}:081325390199:image/datascience-1.0"
        }
      }
    }

    dynamic "kernel_gateway_app_settings" {
      for_each = var.enable_sagemaker_encryption ? [1] : []
      content {
        default_resource_spec {
          instance_type       = var.sagemaker_instance_type
          sagemaker_image_arn = "arn:aws:sagemaker:${data.aws_region.current.name}:081325390199:image/datascience-1.0"
        }
      }
    }
  }

  default_space_settings {
    execution_role = var.sagemaker_roles.execution

    dynamic "jupyter_server_app_settings" {
      for_each = var.enable_sagemaker_encryption ? [1] : []
      content {
        default_resource_spec {
          instance_type       = var.sagemaker_instance_type
          sagemaker_image_arn = "arn:aws:sagemaker:${data.aws_region.current.name}:081325390199:image/datascience-1.0"
        }
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-sagemaker-domain"
  })
}

# SageMaker Feature Store - Feature Group for online store
resource "aws_sagemaker_feature_group" "online_feature_group" {
  count = var.feature_store_online_enabled ? 1 : 0

  feature_group_name             = "${var.project_name}-${var.environment}-online-features"
  record_identifier_feature_name = "record_id"
  event_time_feature_name        = "event_time"
  role_arn                       = var.sagemaker_roles.feature_store

  feature_definition {
    feature_name = "record_id"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "event_time"
    feature_type = "String"
  }

  online_store_config {
    enable_online_store = true

    dynamic "security_config" {
      for_each = var.enable_sagemaker_encryption ? [1] : []
      content {
        kms_key_id = aws_kms_key.sagemaker_key[0].arn
      }
    }
  }

  dynamic "offline_store_config" {
    for_each = var.feature_store_offline_enabled ? [1] : []
    content {
      s3_storage_config {
        s3_uri     = "s3://${var.data_lake_bucket_name}/feature-store/"
        kms_key_id = var.enable_sagemaker_encryption ? aws_kms_key.sagemaker_key[0].arn : null
      }

      disable_glue_table_creation = false
      data_catalog_config {
        table_name = "${var.project_name}_${var.environment}_features"
        catalog    = "AwsDataCatalog"
        database   = "${var.project_name}_${var.environment}_feature_store"
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-online-features"
  })
}

# S3 Bucket for SageMaker artifacts
resource "aws_s3_bucket" "sagemaker_artifacts" {
  bucket = "${var.project_name}-${var.environment}-sagemaker-artifacts-${random_id.sagemaker_suffix.hex}"

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-sagemaker-artifacts"
    Purpose = "SageMaker Artifacts"
  })
}

resource "random_id" "sagemaker_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_public_access_block" "sagemaker_artifacts" {
  bucket = aws_s3_bucket.sagemaker_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket encryption for SageMaker artifacts
resource "aws_s3_bucket_server_side_encryption_configuration" "sagemaker_artifacts" {
  count  = var.enable_sagemaker_encryption ? 1 : 0
  bucket = aws_s3_bucket.sagemaker_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.sagemaker_key[0].arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# CloudWatch Log Group for SageMaker
resource "aws_cloudwatch_log_group" "sagemaker_logs" {
  name              = "/aws/sagemaker/${var.project_name}-${var.environment}"
  retention_in_days = 14

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-sagemaker-logs"
  })
}

# SageMaker Model Registry
resource "aws_sagemaker_model_package_group" "model_package_group" {
  model_package_group_name        = "${var.project_name}-${var.environment}-models"
  model_package_group_description = "Model package group for ${var.project_name} ${var.environment}"

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-model-package-group"
  })
}

# SageMaker Training Job Configuration
resource "aws_sagemaker_training_job" "automated_training" {
  count = var.enable_automated_training ? 1 : 0

  training_job_name = "${var.project_name}-${var.environment}-training-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  role_arn          = var.sagemaker_roles.execution

  algorithm_specification {
    training_image     = var.training_image_uri
    training_input_mode = "File"
  }

  input_data_config {
    channel_name = "train"
    data_source {
      s3_data_source {
        s3_data_type         = "S3Prefix"
        s3_uri               = "s3://${var.data_lake_bucket_name}/gold/ml_features/"
        s3_data_distribution_type = "FullyReplicated"
      }
    }
    content_type = "application/x-parquet"
  }

  output_data_config {
    s3_output_path = "s3://${aws_s3_bucket.sagemaker_artifacts.bucket}/training-output/"
    
    dynamic "kms_key_id" {
      for_each = var.enable_sagemaker_encryption ? [1] : []
      content {
        kms_key_id = aws_kms_key.sagemaker_key[0].arn
      }
    }
  }

  resource_config {
    instance_type   = var.training_instance_type
    instance_count  = var.training_instance_count
    volume_size_in_gb = var.sagemaker_volume_size
    
    dynamic "volume_kms_key_id" {
      for_each = var.enable_sagemaker_encryption ? [1] : []
      content {
        volume_kms_key_id = aws_kms_key.sagemaker_key[0].arn
      }
    }
  }

  stopping_condition {
    max_runtime_in_seconds = var.max_training_time
  }

  hyper_parameters = var.training_hyperparameters

  dynamic "vpc_config" {
    for_each = var.enable_vpc_training ? [1] : []
    content {
      security_group_ids = [aws_security_group.sagemaker_sg.id]
      subnets           = var.private_subnet_ids
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-training-job"
  })

  lifecycle {
    ignore_changes = [training_job_name]
  }
}

# SageMaker Hyperparameter Tuning Job
resource "aws_sagemaker_hyperparameter_tuning_job" "hyperparameter_tuning" {
  count = var.enable_hyperparameter_tuning ? 1 : 0

  hyperparameter_tuning_job_name = "${var.project_name}-${var.environment}-tuning-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  role_arn                      = var.sagemaker_roles.execution

  hyperparameter_tuning_job_config {
    strategy = "Bayesian"
    
    hyperparameter_tuning_job_objective {
      type        = "Maximize"
      metric_name = var.tuning_objective_metric
    }

    resource_limits {
      max_number_of_training_jobs = var.max_tuning_jobs
      max_parallel_training_jobs  = var.max_parallel_tuning_jobs
    }

    parameter_ranges {
      dynamic "continuous_parameter_ranges" {
        for_each = var.continuous_parameters
        content {
          name        = continuous_parameter_ranges.value.name
          min_value   = continuous_parameter_ranges.value.min_value
          max_value   = continuous_parameter_ranges.value.max_value
          scaling_type = continuous_parameter_ranges.value.scaling_type
        }
      }

      dynamic "integer_parameter_ranges" {
        for_each = var.integer_parameters
        content {
          name        = integer_parameter_ranges.value.name
          min_value   = integer_parameter_ranges.value.min_value
          max_value   = integer_parameter_ranges.value.max_value
          scaling_type = integer_parameter_ranges.value.scaling_type
        }
      }

      dynamic "categorical_parameter_ranges" {
        for_each = var.categorical_parameters
        content {
          name   = categorical_parameter_ranges.value.name
          values = categorical_parameter_ranges.value.values
        }
      }
    }
  }

  training_job_definition {
    algorithm_specification {
      training_image     = var.training_image_uri
      training_input_mode = "File"
    }

    input_data_config {
      channel_name = "train"
      data_source {
        s3_data_source {
          s3_data_type         = "S3Prefix"
          s3_uri               = "s3://${var.data_lake_bucket_name}/gold/ml_features/"
          s3_data_distribution_type = "FullyReplicated"
        }
      }
      content_type = "application/x-parquet"
    }

    output_data_config {
      s3_output_path = "s3://${aws_s3_bucket.sagemaker_artifacts.bucket}/tuning-output/"
      
      dynamic "kms_key_id" {
        for_each = var.enable_sagemaker_encryption ? [1] : []
        content {
          kms_key_id = aws_kms_key.sagemaker_key[0].arn
        }
      }
    }

    resource_config {
      instance_type   = var.training_instance_type
      instance_count  = var.training_instance_count
      volume_size_in_gb = var.sagemaker_volume_size
      
      dynamic "volume_kms_key_id" {
        for_each = var.enable_sagemaker_encryption ? [1] : []
        content {
          volume_kms_key_id = aws_kms_key.sagemaker_key[0].arn
        }
      }
    }

    stopping_condition {
      max_runtime_in_seconds = var.max_training_time
    }

    static_hyper_parameters = var.static_hyperparameters

    dynamic "vpc_config" {
      for_each = var.enable_vpc_training ? [1] : []
      content {
        security_group_ids = [aws_security_group.sagemaker_sg.id]
        subnets           = var.private_subnet_ids
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-tuning-job"
  })

  lifecycle {
    ignore_changes = [hyperparameter_tuning_job_name]
  }
}

# SageMaker Model for deployment
resource "aws_sagemaker_model" "trained_model" {
  count = var.enable_model_deployment ? 1 : 0

  name               = "${var.project_name}-${var.environment}-model-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  execution_role_arn = var.sagemaker_roles.execution

  primary_container {
    image          = var.inference_image_uri
    model_data_url = var.model_data_url != "" ? var.model_data_url : "s3://${aws_s3_bucket.sagemaker_artifacts.bucket}/training-output/model.tar.gz"
    
    environment = var.model_environment_variables
  }

  dynamic "vpc_config" {
    for_each = var.enable_vpc_inference ? [1] : []
    content {
      security_group_ids = [aws_security_group.sagemaker_sg.id]
      subnets           = var.private_subnet_ids
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-model"
  })

  lifecycle {
    ignore_changes = [name]
  }
}

# SageMaker Endpoint Configuration
resource "aws_sagemaker_endpoint_configuration" "model_endpoint_config" {
  count = var.enable_model_deployment ? 1 : 0

  name = "${var.project_name}-${var.environment}-endpoint-config-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  production_variants {
    variant_name           = "primary"
    model_name            = aws_sagemaker_model.trained_model[0].name
    initial_instance_count = var.endpoint_instance_count
    instance_type         = var.endpoint_instance_type
    initial_variant_weight = 1
  }

  dynamic "data_capture_config" {
    for_each = var.enable_data_capture ? [1] : []
    content {
      enable_capture              = true
      initial_sampling_percentage = var.data_capture_sampling_percentage
      destination_s3_uri          = "s3://${aws_s3_bucket.sagemaker_artifacts.bucket}/data-capture/"
      
      capture_options {
        capture_mode = "Input"
      }
      
      capture_options {
        capture_mode = "Output"
      }
      
      dynamic "kms_key_id" {
        for_each = var.enable_sagemaker_encryption ? [1] : []
        content {
          kms_key_id = aws_kms_key.sagemaker_key[0].arn
        }
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-endpoint-config"
  })

  lifecycle {
    ignore_changes = [name]
  }
}

# SageMaker Endpoint
resource "aws_sagemaker_endpoint" "model_endpoint" {
  count = var.enable_model_deployment ? 1 : 0

  name                 = "${var.project_name}-${var.environment}-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.model_endpoint_config[0].name

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-endpoint"
  })
}

# CloudWatch Alarms for Model Monitoring
resource "aws_cloudwatch_metric_alarm" "model_invocation_errors" {
  count = var.enable_model_deployment && var.enable_model_monitoring ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-model-invocation-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ModelInvocation4XXErrors"
  namespace           = "AWS/SageMaker"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors SageMaker model invocation errors"

  dimensions = {
    EndpointName = aws_sagemaker_endpoint.model_endpoint[0].name
    VariantName  = "primary"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-model-errors-alarm"
  })
}

resource "aws_cloudwatch_metric_alarm" "model_latency" {
  count = var.enable_model_deployment && var.enable_model_monitoring ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-model-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ModelLatency"
  namespace           = "AWS/SageMaker"
  period              = "300"
  statistic           = "Average"
  threshold           = var.latency_threshold_ms
  alarm_description   = "This metric monitors SageMaker model latency"

  dimensions = {
    EndpointName = aws_sagemaker_endpoint.model_endpoint[0].name
    VariantName  = "primary"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-model-latency-alarm"
  })
}
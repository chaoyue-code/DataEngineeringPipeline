# Storage Module - S3 Data Lake and related resources

# Data sources
data "aws_caller_identity" "current" {}

# Generate bucket name if not provided
locals {
  bucket_name = var.data_lake_bucket_name != null ? var.data_lake_bucket_name : "${var.project_name}-${var.environment}-data-lake-${random_id.bucket_suffix.hex}"
}

# Random ID for bucket naming
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# S3 Bucket for Data Lake
resource "aws_s3_bucket" "data_lake" {
  bucket = local.bucket_name

  tags = merge(var.tags, {
    Name        = local.bucket_name
    Purpose     = "Data Lake"
    Environment = var.environment
  })
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

# KMS Key for S3 Encryption
resource "aws_kms_key" "data_lake_key" {
  count = var.enable_encryption ? 1 : 0

  description             = "KMS key for S3 data lake encryption in ${var.project_name} ${var.environment}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-data-lake-key"
    Purpose     = "S3 Data Lake Encryption"
    Environment = var.environment
  })
}

resource "aws_kms_alias" "data_lake_key_alias" {
  count = var.enable_encryption ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-data-lake"
  target_key_id = aws_kms_key.data_lake_key[0].key_id
}

# S3 Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake" {
  count  = var.enable_encryption ? 1 : 0
  bucket = aws_s3_bucket.data_lake.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data_lake_key[0].arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket Lifecycle Configuration
resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  # Bronze Layer Lifecycle
  rule {
    id     = "bronze-layer-lifecycle"
    status = "Enabled"

    filter {
      prefix = "bronze/"
    }

    expiration {
      days = var.bronze_lifecycle_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  # Silver Layer Lifecycle
  rule {
    id     = "silver-layer-lifecycle"
    status = "Enabled"

    filter {
      prefix = "silver/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = var.silver_lifecycle_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  # Gold Layer Lifecycle
  rule {
    id     = "gold-layer-lifecycle"
    status = "Enabled"

    filter {
      prefix = "gold/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = var.gold_lifecycle_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  # Incomplete Multipart Upload Cleanup
  rule {
    id     = "cleanup-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# S3 Bucket Policy for Data Lake
resource "aws_s3_bucket_policy" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyInsecureConnections"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:*"
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid    = "AllowDataPipelineAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      }
    ]
  })
}

# EventBridge Custom Bus for Data Pipeline Events
resource "aws_cloudwatch_event_bus" "data_pipeline" {
  name = "${var.project_name}-${var.environment}-data-pipeline"

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-data-pipeline-bus"
    Purpose     = "Data Pipeline Event Bus"
    Environment = var.environment
  })
}

# S3 Bucket Notification Configuration with EventBridge
resource "aws_s3_bucket_notification" "data_lake" {
  bucket      = aws_s3_bucket.data_lake.id
  eventbridge = true
}

# EventBridge Rules for S3 Events
resource "aws_cloudwatch_event_rule" "bronze_data_arrival" {
  name           = "${var.project_name}-${var.environment}-bronze-data-arrival"
  description    = "Trigger when new data arrives in bronze layer"
  event_bus_name = aws_cloudwatch_event_bus.data_pipeline.name

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [aws_s3_bucket.data_lake.bucket]
      }
      object = {
        key = [{
          prefix = "bronze/"
        }]
      }
    }
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-bronze-data-arrival"
    Purpose     = "Bronze Layer Data Arrival Detection"
    Environment = var.environment
  })
}

resource "aws_cloudwatch_event_rule" "silver_data_ready" {
  name           = "${var.project_name}-${var.environment}-silver-data-ready"
  description    = "Trigger when processed data is ready in silver layer"
  event_bus_name = aws_cloudwatch_event_bus.data_pipeline.name

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [aws_s3_bucket.data_lake.bucket]
      }
      object = {
        key = [{
          prefix = "silver/"
        }]
      }
    }
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-silver-data-ready"
    Purpose     = "Silver Layer Data Ready Detection"
    Environment = var.environment
  })
}

resource "aws_cloudwatch_event_rule" "gold_data_published" {
  name           = "${var.project_name}-${var.environment}-gold-data-published"
  description    = "Trigger when business-ready data is published to gold layer"
  event_bus_name = aws_cloudwatch_event_bus.data_pipeline.name

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [aws_s3_bucket.data_lake.bucket]
      }
      object = {
        key = [{
          prefix = "gold/"
        }]
      }
    }
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-gold-data-published"
    Purpose     = "Gold Layer Data Published Detection"
    Environment = var.environment
  })
}

# EventBridge Rule for Pipeline Failures
resource "aws_cloudwatch_event_rule" "pipeline_failure" {
  name           = "${var.project_name}-${var.environment}-pipeline-failure"
  description    = "Trigger when pipeline failures occur"
  event_bus_name = aws_cloudwatch_event_bus.data_pipeline.name

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [aws_s3_bucket.data_lake.bucket]
      }
      object = {
        key = [{
          prefix = "logs/errors/"
        }]
      }
    }
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-pipeline-failure"
    Purpose     = "Pipeline Failure Detection"
    Environment = var.environment
  })
}

# SNS Topics for Event Notifications
resource "aws_sns_topic" "data_pipeline_notifications" {
  name = "${var.project_name}-${var.environment}-data-pipeline-notifications"

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-data-pipeline-notifications"
    Purpose     = "Data Pipeline Notifications"
    Environment = var.environment
  })
}

resource "aws_sns_topic" "pipeline_alerts" {
  name = "${var.project_name}-${var.environment}-pipeline-alerts"

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-pipeline-alerts"
    Purpose     = "Pipeline Alert Notifications"
    Environment = var.environment
  })
}

# SNS Topic Policies to allow EventBridge to publish
resource "aws_sns_topic_policy" "data_pipeline_notifications" {
  arn = aws_sns_topic.data_pipeline_notifications.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeToPublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sns:Publish"
        Resource = aws_sns_topic.data_pipeline_notifications.arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

resource "aws_sns_topic_policy" "pipeline_alerts" {
  arn = aws_sns_topic.pipeline_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeToPublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sns:Publish"
        Resource = aws_sns_topic.pipeline_alerts.arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# EventBridge Targets for SNS Notifications
resource "aws_cloudwatch_event_target" "bronze_data_notification" {
  rule           = aws_cloudwatch_event_rule.bronze_data_arrival.name
  event_bus_name = aws_cloudwatch_event_bus.data_pipeline.name
  target_id      = "BronzeDataNotification"
  arn            = aws_sns_topic.data_pipeline_notifications.arn

  input_transformer {
    input_paths = {
      bucket = "$.detail.bucket.name"
      key    = "$.detail.object.key"
      time   = "$.time"
    }
    input_template = jsonencode({
      event_type = "bronze_data_arrival"
      bucket     = "<bucket>"
      object_key = "<key>"
      timestamp  = "<time>"
      message    = "New data arrived in bronze layer: <key>"
    })
  }
}

resource "aws_cloudwatch_event_target" "pipeline_failure_alert" {
  rule           = aws_cloudwatch_event_rule.pipeline_failure.name
  event_bus_name = aws_cloudwatch_event_bus.data_pipeline.name
  target_id      = "PipelineFailureAlert"
  arn            = aws_sns_topic.pipeline_alerts.arn

  input_transformer {
    input_paths = {
      bucket = "$.detail.bucket.name"
      key    = "$.detail.object.key"
      time   = "$.time"
    }
    input_template = jsonencode({
      event_type = "pipeline_failure"
      bucket     = "<bucket>"
      object_key = "<key>"
      timestamp  = "<time>"
      message    = "Pipeline failure detected: <key>"
      severity   = "HIGH"
    })
  }
}

# S3 Bucket Logging
resource "aws_s3_bucket" "access_logs" {
  bucket = "${local.bucket_name}-access-logs"

  tags = merge(var.tags, {
    Name    = "${local.bucket_name}-access-logs"
    Purpose = "Access Logs"
  })
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "access-logs/"
}

# Create comprehensive folder structure for medallion architecture
locals {
  # Define medallion architecture folder structure
  medallion_folders = {
    # Bronze Layer - Raw data from Snowflake
    "bronze/snowflake/raw/"                    = "Raw Snowflake extracts"
    "bronze/snowflake/incremental/"            = "Incremental Snowflake data"
    "bronze/snowflake/full/"                   = "Full Snowflake snapshots"
    "bronze/external/api/"                     = "External API data"
    "bronze/external/files/"                   = "External file uploads"
    
    # Silver Layer - Cleaned and validated data
    "silver/cleaned/"                          = "Cleaned and validated data"
    "silver/standardized/"                     = "Standardized schema data"
    "silver/deduplicated/"                     = "Deduplicated records"
    "silver/enriched/"                         = "Enriched with business logic"
    
    # Gold Layer - Business-ready aggregated data
    "gold/aggregated/"                         = "Aggregated business metrics"
    "gold/features/"                           = "ML feature sets"
    "gold/reports/"                            = "Report-ready datasets"
    "gold/analytics/"                          = "Analytics-ready data"
    
    # Supporting folders
    "scripts/glue/"                            = "Glue ETL scripts"
    "scripts/lambda/"                          = "Lambda function code"
    "scripts/sql/"                             = "SQL transformation scripts"
    "temp/processing/"                         = "Temporary processing files"
    "temp/staging/"                            = "Staging area for transformations"
    "logs/pipeline/"                           = "Pipeline execution logs"
    "logs/errors/"                             = "Error logs and failed records"
    "metadata/schemas/"                        = "Data schemas and metadata"
    "metadata/lineage/"                        = "Data lineage information"
  }
}

# Create medallion architecture folder structure
resource "aws_s3_object" "medallion_folders" {
  for_each = local.medallion_folders
  
  bucket = aws_s3_bucket.data_lake.id
  key    = each.key

  tags = merge(var.tags, {
    Purpose     = each.value
    Layer       = split("/", each.key)[0]
    Environment = var.environment
  })
}
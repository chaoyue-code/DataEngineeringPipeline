# Additional Access Controls and Compliance Features for IAM Module

# =============================================================================
# RESOURCE-BASED POLICIES FOR ENHANCED SECURITY
# =============================================================================

# S3 Bucket Policy for Data Lake with Least Privilege Access
resource "aws_s3_bucket_policy" "data_lake_access_control" {
  bucket = replace(var.data_lake_bucket_arn, "arn:aws:s3:::", "")

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyInsecureConnections"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:*"
        Resource = [
          var.data_lake_bucket_arn,
          "${var.data_lake_bucket_arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid    = "AllowSnowflakeExtractorAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.snowflake_extractor_role.arn
        }
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${var.data_lake_bucket_arn}/bronze/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      },
      {
        Sid    = "AllowGlueETLAccess"
        Effect = "Allow"
        Principal = {
          AWS = [
            aws_iam_role.glue_service_role.arn,
            aws_iam_role.glue_crawler_role.arn
          ]
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.data_lake_bucket_arn,
          "${var.data_lake_bucket_arn}/*"
        ]
        Condition = {
          StringLike = {
            "aws:userid" = [
              "${aws_iam_role.glue_service_role.unique_id}:*",
              "${aws_iam_role.glue_crawler_role.unique_id}:*"
            ]
          }
        }
      },
      {
        Sid    = "AllowSageMakerReadAccess"
        Effect = "Allow"
        Principal = {
          AWS = [
            aws_iam_role.sagemaker_execution_role.arn,
            aws_iam_role.sagemaker_feature_store_role.arn
          ]
        }
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${var.data_lake_bucket_arn}/gold/*",
          "${var.data_lake_bucket_arn}/feature-store/*"
        ]
        Condition = {
          StringLike = {
            "aws:userid" = [
              "${aws_iam_role.sagemaker_execution_role.unique_id}:*",
              "${aws_iam_role.sagemaker_feature_store_role.unique_id}:*"
            ]
          }
        }
      },
      {
        Sid    = "DenyUnencryptedObjectUploads"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:PutObject"
        Resource = "${var.data_lake_bucket_arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      },
      {
        Sid    = "RequireMFAForDeletion"
        Effect = "Deny"
        Principal = "*"
        Action = [
          "s3:DeleteObject",
          "s3:DeleteBucket"
        ]
        Resource = [
          var.data_lake_bucket_arn,
          "${var.data_lake_bucket_arn}/*"
        ]
        Condition = {
          BoolIfExists = {
            "aws:MultiFactorAuthPresent" = "false"
          }
        }
      }
    ]
  })
}

# =============================================================================
# CROSS-ACCOUNT ACCESS PATTERNS
# =============================================================================

# Cross-Account Role for External Access (if needed)
resource "aws_iam_role" "cross_account_access_role" {
  count = var.enable_cross_account_access ? 1 : 0

  name = "${var.project_name}-${var.environment}-cross-account-access-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = [for account_id in var.trusted_account_ids : "arn:aws:iam::${account_id}:root"]
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = var.external_id != "" ? var.external_id : null
          }
          NumericLessThan = {
            "aws:TokenIssueTime" = "${formatdate("YYYY-MM-DD'T'hh:mm:ss'Z'", timeadd(timestamp(), "${var.session_duration}s"))}"
          }
          Bool = var.enforce_mfa ? {
            "aws:MultiFactorAuthPresent" = "true"
          } : {}
        }
      }
    ]
  })

  max_session_duration = var.session_duration

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-cross-account-access-role"
    Purpose = "Cross-Account Access"
  })
}

# Cross-Account Access Policy
resource "aws_iam_role_policy" "cross_account_access_policy" {
  count = var.enable_cross_account_access ? 1 : 0

  name = "${var.project_name}-${var.environment}-cross-account-access-policy"
  role = aws_iam_role.cross_account_access_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${var.data_lake_bucket_arn}/gold/*",
          var.data_lake_bucket_arn
        ]
        Condition = {
          StringEquals = {
            "s3:ExistingObjectTag/Environment" = var.environment
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetTable",
          "glue:GetPartitions",
          "glue:GetDatabase"
        ]
        Resource = [
          "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:catalog",
          "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:database/${var.project_name}_${var.environment}_*",
          "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.project_name}_${var.environment}_*/*"
        ]
      }
    ]
  })
}

# =============================================================================
# ACCESS LOGGING AND AUDIT MECHANISMS
# =============================================================================

# CloudTrail for API Logging
resource "aws_cloudtrail" "access_audit" {
  count = var.enable_access_logging ? 1 : 0

  name           = "${var.project_name}-${var.environment}-access-audit-trail"
  s3_bucket_name = aws_s3_bucket.audit_logs[0].bucket

  event_selector {
    read_write_type                 = "All"
    include_management_events       = true
    exclude_management_event_sources = []

    data_resource {
      type   = "AWS::S3::Object"
      values = ["${var.data_lake_bucket_arn}/*"]
    }

    data_resource {
      type   = "AWS::S3::Bucket"
      values = [var.data_lake_bucket_arn]
    }
  }

  insight_selector {
    insight_type = "ApiCallRateInsight"
  }

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-access-audit-trail"
    Purpose = "Access Audit Logging"
  })
}

# S3 Bucket for Audit Logs
resource "aws_s3_bucket" "audit_logs" {
  count = var.enable_access_logging ? 1 : 0

  bucket = "${var.project_name}-${var.environment}-audit-logs-${random_id.audit_suffix[0].hex}"

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-audit-logs"
    Purpose = "Access Audit Logs"
  })
}

resource "random_id" "audit_suffix" {
  count = var.enable_access_logging ? 1 : 0

  byte_length = 4
}

# Audit Logs Bucket Policy
resource "aws_s3_bucket_policy" "audit_logs" {
  count = var.enable_access_logging ? 1 : 0

  bucket = aws_s3_bucket.audit_logs[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.audit_logs[0].arn
      },
      {
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.audit_logs[0].arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      }
    ]
  })
}

# =============================================================================
# ACCESS REVIEW AND COMPLIANCE MONITORING
# =============================================================================

# IAM Access Analyzer
resource "aws_accessanalyzer_analyzer" "pipeline_analyzer" {
  analyzer_name = "${var.project_name}-${var.environment}-access-analyzer"
  type          = "ACCOUNT"

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-access-analyzer"
    Purpose = "Access Analysis and Compliance"
  })
}

# CloudWatch Alarms for Unusual Access Patterns
resource "aws_cloudwatch_metric_alarm" "unusual_api_calls" {
  count = var.enable_access_logging ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-unusual-api-calls"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ErrorCount"
  namespace           = "AWS/CloudTrail"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors unusual API call patterns"

  dimensions = {
    TrailName = var.enable_access_logging ? aws_cloudtrail.access_audit[0].name : ""
  }

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-unusual-api-calls-alarm"
    Purpose = "Security Monitoring"
  })
}

# Lambda Function for Access Review Automation
resource "aws_lambda_function" "access_review" {
  count = var.enable_access_logging ? 1 : 0

  filename         = data.archive_file.access_review_lambda[0].output_path
  function_name    = "${var.project_name}-${var.environment}-access-review"
  role            = aws_iam_role.access_review_lambda[0].arn
  handler         = "index.handler"
  source_code_hash = data.archive_file.access_review_lambda[0].output_base64sha256
  runtime         = "python3.11"
  timeout         = 300

  environment {
    variables = {
      PROJECT_NAME = var.project_name
      ENVIRONMENT  = var.environment
      SNS_TOPIC_ARN = aws_sns_topic.access_review_notifications[0].arn
    }
  }

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-access-review"
    Purpose = "Access Review Automation"
  })
}

# Lambda Function Code for Access Review
data "archive_file" "access_review_lambda" {
  count = var.enable_access_logging ? 1 : 0

  type        = "zip"
  output_path = "/tmp/access_review_lambda.zip"
  source {
    content = templatefile("${path.module}/lambda/access_review.py", {
      project_name = var.project_name
      environment  = var.environment
    })
    filename = "index.py"
  }
}

# IAM Role for Access Review Lambda
resource "aws_iam_role" "access_review_lambda" {
  count = var.enable_access_logging ? 1 : 0

  name = "${var.project_name}-${var.environment}-access-review-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-access-review-lambda-role"
    Purpose = "Access Review Lambda"
  })
}

# IAM Policy for Access Review Lambda
resource "aws_iam_role_policy" "access_review_lambda" {
  count = var.enable_access_logging ? 1 : 0

  name = "${var.project_name}-${var.environment}-access-review-lambda-policy"
  role = aws_iam_role.access_review_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-${var.environment}-access-review*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:ListRoles",
          "iam:ListPolicies",
          "iam:ListAttachedRolePolicies",
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:GetPolicy",
          "iam:GetPolicyVersion"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "accessanalyzer:ListFindings",
          "accessanalyzer:GetFinding"
        ]
        Resource = aws_accessanalyzer_analyzer.pipeline_analyzer.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.access_review_notifications[0].arn
      }
    ]
  })
}

# SNS Topic for Access Review Notifications
resource "aws_sns_topic" "access_review_notifications" {
  count = var.enable_access_logging ? 1 : 0

  name = "${var.project_name}-${var.environment}-access-review-notifications"

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-access-review-notifications"
    Purpose = "Access Review Notifications"
  })
}

# EventBridge Rule for Scheduled Access Reviews
resource "aws_cloudwatch_event_rule" "access_review_schedule" {
  count = var.enable_access_logging ? 1 : 0

  name                = "${var.project_name}-${var.environment}-access-review-schedule"
  description         = "Trigger access review on a schedule"
  schedule_expression = "rate(7 days)" # Weekly access review

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-access-review-schedule"
    Purpose = "Access Review Scheduling"
  })
}

# EventBridge Target for Access Review Lambda
resource "aws_cloudwatch_event_target" "access_review_lambda_target" {
  count = var.enable_access_logging ? 1 : 0

  rule      = aws_cloudwatch_event_rule.access_review_schedule[0].name
  target_id = "AccessReviewLambdaTarget"
  arn       = aws_lambda_function.access_review[0].arn
}

# Lambda Permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge" {
  count = var.enable_access_logging ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.access_review[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.access_review_schedule[0].arn
}

# =============================================================================
# COMPLIANCE REPORTING
# =============================================================================

# S3 Bucket for Compliance Reports
resource "aws_s3_bucket" "compliance_reports" {
  count = var.enable_access_logging ? 1 : 0

  bucket = "${var.project_name}-${var.environment}-compliance-reports-${random_id.compliance_suffix[0].hex}"

  tags = merge(var.tags, {
    Name    = "${var.project_name}-${var.environment}-compliance-reports"
    Purpose = "Compliance Reporting"
  })
}

resource "random_id" "compliance_suffix" {
  count = var.enable_access_logging ? 1 : 0

  byte_length = 4
}

# Compliance Reports Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "compliance_reports" {
  count = var.enable_access_logging ? 1 : 0

  bucket = aws_s3_bucket.compliance_reports[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Compliance Reports Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "compliance_reports" {
  count = var.enable_access_logging ? 1 : 0

  bucket = aws_s3_bucket.compliance_reports[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
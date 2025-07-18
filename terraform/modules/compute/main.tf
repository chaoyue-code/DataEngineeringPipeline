# Compute Module - Lambda, Glue, and related compute resources

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Note: IAM roles are now managed by the dedicated IAM module
# Lambda functions will use roles from var.lambda_roles

# Security Group for Lambda Functions
resource "aws_security_group" "lambda_sg" {
  name_prefix = "${var.project_name}-${var.environment}-lambda"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-lambda-sg"
  })
}

# Note: Glue IAM roles are now managed by the dedicated IAM module
# Glue resources will use roles from var.glue_roles

# Glue Catalog Database
resource "aws_glue_catalog_database" "main" {
  name        = "${var.project_name}_${var.environment}_catalog"
  description = "Glue catalog database for ${var.project_name} ${var.environment}"

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-catalog"
  })
}

# Glue Crawler for Bronze Layer
resource "aws_glue_crawler" "bronze_crawler" {
  database_name = aws_glue_catalog_database.main.name
  name          = "${var.project_name}-${var.environment}-bronze-crawler"
  role          = var.glue_roles.crawler

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/bronze/"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })

  tags = merge(var.tags, {
    Name  = "${var.project_name}-${var.environment}-bronze-crawler"
    Layer = "Bronze"
  })
}

# Glue Crawler for Silver Layer
resource "aws_glue_crawler" "silver_crawler" {
  database_name = aws_glue_catalog_database.main.name
  name          = "${var.project_name}-${var.environment}-silver-crawler"
  role          = var.glue_roles.crawler

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/silver/"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })

  tags = merge(var.tags, {
    Name  = "${var.project_name}-${var.environment}-silver-crawler"
    Layer = "Silver"
  })
}

# Glue Crawler for Gold Layer
resource "aws_glue_crawler" "gold_crawler" {
  database_name = aws_glue_catalog_database.main.name
  name          = "${var.project_name}-${var.environment}-gold-crawler"
  role          = var.glue_roles.crawler

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/gold/"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })

  tags = merge(var.tags, {
    Name  = "${var.project_name}-${var.environment}-gold-crawler"
    Layer = "Gold"
  })
}

# CloudWatch Log Groups for Lambda Functions
resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = toset([
    "snowflake-extractor",
    "pipeline-orchestrator",
    "data-quality-monitor",
    "notification-handler"
  ])

  name              = "/aws/lambda/${var.project_name}-${var.environment}-${each.key}"
  retention_in_days = 14

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-${each.key}-logs"
  })
}

resource "aws_lambda_function" "snowflake_extractor" {
  function_name = "${var.project_name}-${var.environment}-snowflake-extractor"
  role          = var.lambda_roles.snowflake_extractor_role_arn

  package_type = "Zip"
  filename     = "../../lambda/snowflake_extractor/dist/lambda_function.zip"
  handler      = "lambda_function.lambda_handler"
  runtime      = var.lambda_runtime

  tracing_config {
    mode = var.lambda_tracing_config_mode
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-snowflake-extractor"
  })
}

resource "aws_lambda_function" "pipeline_orchestrator" {
  function_name = "${var.project_name}-${var.environment}-pipeline-orchestrator"
  role          = var.lambda_roles.pipeline_orchestrator_role_arn

  package_type = "Zip"
  filename     = "../../lambda/pipeline_orchestrator/dist/lambda_function.zip"
  handler      = "lambda_function.lambda_handler"
  runtime      = var.lambda_runtime

  tracing_config {
    mode = var.lambda_tracing_config_mode
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-pipeline-orchestrator"
  })
}

resource "aws_lambda_function" "data_quality_monitor" {
  function_name = "${var.project_name}-${var.environment}-data-quality-monitor"
  role          = var.lambda_roles.data_quality_monitor_role_arn

  package_type = "Zip"
  filename     = "../../lambda/data_quality_monitor/dist/lambda_function.zip"
  handler      = "lambda_function.lambda_handler"
  runtime      = var.lambda_runtime

  tracing_config {
    mode = var.lambda_tracing_config_mode
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-data-quality-monitor"
  })
}

resource "aws_lambda_function" "notification_alerting" {
  function_name = "${var.project_name}-${var.environment}-notification-alerting"
  role          = var.lambda_roles.notification_handler_role_arn

  package_type = "Zip"
  filename     = "../../lambda/notification_alerting/dist/lambda_function.zip"
  handler      = "lambda_function.lambda_handler"
  runtime      = var.lambda_runtime

  tracing_config {
    mode = var.lambda_tracing_config_mode
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-notification-alerting"
  })
}
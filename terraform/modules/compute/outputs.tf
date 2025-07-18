# Compute Module Outputs

# Note: Lambda IAM roles are now managed by the dedicated IAM module

output "lambda_security_group_id" {
  description = "Security group ID for Lambda functions"
  value       = aws_security_group.lambda_sg.id
}

# Note: Glue IAM roles are now managed by the dedicated IAM module

output "glue_catalog_database_name" {
  description = "Name of the Glue catalog database"
  value       = aws_glue_catalog_database.main.name
}

output "glue_catalog_database_arn" {
  description = "ARN of the Glue catalog database"
  value       = aws_glue_catalog_database.main.arn
}

output "glue_crawlers" {
  description = "Glue crawler details"
  value = {
    bronze_crawler = {
      name = aws_glue_crawler.bronze_crawler.name
      arn  = aws_glue_crawler.bronze_crawler.arn
    }
    silver_crawler = {
      name = aws_glue_crawler.silver_crawler.name
      arn  = aws_glue_crawler.silver_crawler.arn
    }
    gold_crawler = {
      name = aws_glue_crawler.gold_crawler.name
      arn  = aws_glue_crawler.gold_crawler.arn
    }
  }
}

output "lambda_functions" {
  description = "Lambda function configuration details"
  value = {
    security_group_id  = aws_security_group.lambda_sg.id
    subnet_ids         = var.private_subnet_ids
    runtime            = var.lambda_runtime
    timeout            = var.lambda_timeout
    memory_size        = var.lambda_memory_size
  }
}

output "glue_jobs" {
  description = "Glue job configuration details"
  value = {
    glue_version      = var.glue_version
    worker_type       = var.glue_worker_type
    number_of_workers = var.glue_number_of_workers
    database_name     = aws_glue_catalog_database.main.name
  }
}

output "cloudwatch_log_groups" {
  description = "CloudWatch log group details"
  value = {
    for k, v in aws_cloudwatch_log_group.lambda_logs : k => {
      name = v.name
      arn  = v.arn
    }
  }
}
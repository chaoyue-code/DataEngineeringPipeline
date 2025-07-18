# Outputs for AWS Glue Data Catalog and ETL Infrastructure

# Database Outputs
output "bronze_database_name" {
  description = "Name of the bronze layer Glue database"
  value       = aws_glue_catalog_database.bronze.name
}

output "silver_database_name" {
  description = "Name of the silver layer Glue database"
  value       = aws_glue_catalog_database.silver.name
}

output "gold_database_name" {
  description = "Name of the gold layer Glue database"
  value       = aws_glue_catalog_database.gold.name
}

output "database_names" {
  description = "Map of all Glue database names by layer"
  value = {
    bronze = aws_glue_catalog_database.bronze.name
    silver = aws_glue_catalog_database.silver.name
    gold   = aws_glue_catalog_database.gold.name
  }
}

# Bronze Layer Crawler Outputs
output "bronze_crawler_names" {
  description = "Names of bronze layer crawlers"
  value = {
    customers = aws_glue_crawler.bronze_customers.name
    orders    = aws_glue_crawler.bronze_orders.name
    products  = aws_glue_crawler.bronze_products.name
  }
}

output "bronze_crawler_arns" {
  description = "ARNs of bronze layer crawlers"
  value = {
    customers = aws_glue_crawler.bronze_customers.arn
    orders    = aws_glue_crawler.bronze_orders.arn
    products  = aws_glue_crawler.bronze_products.arn
  }
}

# Silver Layer Crawler Outputs
output "silver_crawler_names" {
  description = "Names of silver layer crawlers"
  value = {
    dim_customers = aws_glue_crawler.silver_dim_customers.name
    fact_orders   = aws_glue_crawler.silver_fact_orders.name
    dim_products  = aws_glue_crawler.silver_dim_products.name
  }
}

output "silver_crawler_arns" {
  description = "ARNs of silver layer crawlers"
  value = {
    dim_customers = aws_glue_crawler.silver_dim_customers.arn
    fact_orders   = aws_glue_crawler.silver_fact_orders.arn
    dim_products  = aws_glue_crawler.silver_dim_products.arn
  }
}

# Gold Layer Crawler Outputs
output "gold_crawler_names" {
  description = "Names of gold layer crawlers"
  value = {
    customer_analytics = aws_glue_crawler.gold_customer_analytics.name
    sales_summary      = aws_glue_crawler.gold_sales_summary.name
    ml_features        = aws_glue_crawler.gold_ml_features.name
  }
}

output "gold_crawler_arns" {
  description = "ARNs of gold layer crawlers"
  value = {
    customer_analytics = aws_glue_crawler.gold_customer_analytics.arn
    sales_summary      = aws_glue_crawler.gold_sales_summary.arn
    ml_features        = aws_glue_crawler.gold_ml_features.arn
  }
}

# All Crawler Names (for easy reference)
output "all_crawler_names" {
  description = "List of all crawler names"
  value = concat(
    values(local.bronze_crawler_names),
    values(local.silver_crawler_names),
    values(local.gold_crawler_names)
  )
}

# EventBridge Rule Outputs
output "bronze_data_arrival_rule_arn" {
  description = "ARN of the EventBridge rule for bronze data arrival"
  value       = var.enable_event_driven_crawlers ? aws_cloudwatch_event_rule.bronze_data_arrival[0].arn : null
}

output "crawler_trigger_lambda_arn" {
  description = "ARN of the Lambda function that triggers crawlers"
  value       = var.enable_event_driven_crawlers ? aws_lambda_function.crawler_trigger[0].arn : null
}

output "crawler_trigger_lambda_name" {
  description = "Name of the Lambda function that triggers crawlers"
  value       = var.enable_event_driven_crawlers ? aws_lambda_function.crawler_trigger[0].function_name : null
}

# Data Catalog Information
output "catalog_id" {
  description = "AWS account ID used for the Glue Data Catalog"
  value       = var.catalog_id != null ? var.catalog_id : data.aws_caller_identity.current.account_id
}

output "data_catalog_encryption_settings" {
  description = "Data catalog encryption settings"
  value = var.enable_crawler_security_configuration ? {
    encryption_at_rest = {
      catalog_encryption_mode = "SSE-KMS"
    }
    connection_password_encryption = {
      return_connection_password_encrypted = true
    }
  } : null
}

# Crawler Configuration Summary
output "crawler_configuration_summary" {
  description = "Summary of crawler configurations"
  value = {
    total_crawlers = length(local.all_crawler_names)
    bronze_crawlers = length(local.bronze_crawler_names)
    silver_crawlers = length(local.silver_crawler_names)
    gold_crawlers   = length(local.gold_crawler_names)
    
    schedule_enabled        = var.crawler_schedule != null
    event_driven_enabled    = var.enable_event_driven_crawlers
    data_lineage_enabled    = var.enable_data_lineage
    security_config_enabled = var.enable_crawler_security_configuration
    
    schema_change_policy = var.crawler_schema_change_policy
    recrawl_policy      = var.crawler_recrawl_policy
  }
}

# Local values for internal use
locals {
  bronze_crawler_names = {
    customers = aws_glue_crawler.bronze_customers.name
    orders    = aws_glue_crawler.bronze_orders.name
    products  = aws_glue_crawler.bronze_products.name
  }
  
  silver_crawler_names = {
    dim_customers = aws_glue_crawler.silver_dim_customers.name
    fact_orders   = aws_glue_crawler.silver_fact_orders.name
    dim_products  = aws_glue_crawler.silver_dim_products.name
  }
  
  gold_crawler_names = {
    customer_analytics = aws_glue_crawler.gold_customer_analytics.name
    sales_summary      = aws_glue_crawler.gold_sales_summary.name
    ml_features        = aws_glue_crawler.gold_ml_features.name
  }
  
  all_crawler_names = merge(
    local.bronze_crawler_names,
    local.silver_crawler_names,
    local.gold_crawler_names
  )
}

# ETL Job Outputs
output "bronze_to_silver_job_names" {
  description = "Names of bronze to silver ETL jobs"
  value = {
    customers = aws_glue_job.bronze_to_silver_customers.name
    orders    = aws_glue_job.bronze_to_silver_orders.name
    products  = aws_glue_job.bronze_to_silver_products.name
  }
}

output "bronze_to_silver_job_arns" {
  description = "ARNs of bronze to silver ETL jobs"
  value = {
    customers = aws_glue_job.bronze_to_silver_customers.arn
    orders    = aws_glue_job.bronze_to_silver_orders.arn
    products  = aws_glue_job.bronze_to_silver_products.arn
  }
}

# Silver to Gold ETL Job Outputs
output "silver_to_gold_job_names" {
  description = "Names of silver to gold ETL jobs"
  value = {
    customer_analytics = aws_glue_job.silver_to_gold_customer_analytics.name
    sales_summary      = aws_glue_job.silver_to_gold_sales_summary.name
    ml_features        = aws_glue_job.silver_to_gold_ml_features.name
  }
}

output "silver_to_gold_job_arns" {
  description = "ARNs of silver to gold ETL jobs"
  value = {
    customer_analytics = aws_glue_job.silver_to_gold_customer_analytics.arn
    sales_summary      = aws_glue_job.silver_to_gold_sales_summary.arn
    ml_features        = aws_glue_job.silver_to_gold_ml_features.arn
  }
}

output "all_etl_job_names" {
  description = "List of all ETL job names"
  value = [
    aws_glue_job.bronze_to_silver_customers.name,
    aws_glue_job.bronze_to_silver_orders.name,
    aws_glue_job.bronze_to_silver_products.name,
    aws_glue_job.silver_to_gold_customer_analytics.name,
    aws_glue_job.silver_to_gold_sales_summary.name,
    aws_glue_job.silver_to_gold_ml_features.name
  ]
}

output "etl_job_configuration_summary" {
  description = "Summary of ETL job configurations"
  value = {
    total_jobs = 6
    bronze_to_silver_jobs = 3
    silver_to_gold_jobs = 3
    glue_version = var.glue_version
    worker_type = var.glue_worker_type
    number_of_workers = var.glue_number_of_workers
    number_of_workers_gold = var.glue_number_of_workers_gold
    job_timeout = var.glue_job_timeout
    job_timeout_gold = var.glue_job_timeout_gold
    max_retries = var.glue_job_max_retries
    job_bookmarks_enabled = var.enable_job_bookmarks
    max_concurrent_runs = var.max_concurrent_runs
  }
}

# Monitoring and Error Handling Outputs
output "sns_topic_arn" {
  description = "ARN of the SNS topic for Glue alerts"
  value       = var.enable_sns_alerts ? aws_sns_topic.glue_alerts[0].arn : null
}

output "error_handler_lambda_arn" {
  description = "ARN of the error handler Lambda function"
  value       = var.enable_enhanced_error_handling ? aws_lambda_function.glue_error_handler[0].arn : null
}

output "error_handler_lambda_name" {
  description = "Name of the error handler Lambda function"
  value       = var.enable_enhanced_error_handling ? aws_lambda_function.glue_error_handler[0].function_name : null
}

output "monitoring_dashboard_url" {
  description = "URL of the CloudWatch monitoring dashboard"
  value = var.enable_monitoring_dashboard ? "https://${data.aws_region.current.name}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.glue_monitoring[0].dashboard_name}" : null
}

output "cloudwatch_log_groups" {
  description = "CloudWatch log groups for Glue jobs and crawlers"
  value = {
    job_log_groups = {
      for k, v in aws_cloudwatch_log_group.glue_jobs : k => v.name
    }
    crawler_log_groups = {
      for k, v in aws_cloudwatch_log_group.glue_crawlers : k => v.name
    }
  }
}

output "monitoring_configuration_summary" {
  description = "Summary of monitoring and error handling configuration"
  value = {
    sns_alerts_enabled = var.enable_sns_alerts
    enhanced_error_handling_enabled = var.enable_enhanced_error_handling
    monitoring_dashboard_enabled = var.enable_monitoring_dashboard
    auto_retry_enabled = var.enable_auto_retry
    max_retry_attempts = var.max_retry_attempts
    job_duration_threshold_seconds = var.job_duration_threshold_seconds
    log_retention_days = var.crawler_log_group_retention_days
    total_alarms = length(aws_cloudwatch_metric_alarm.glue_job_failures) + length(aws_cloudwatch_metric_alarm.glue_job_duration) + length(aws_cloudwatch_metric_alarm.crawler_failures)
  }
}

# Data sources
data "aws_region" "current" {}

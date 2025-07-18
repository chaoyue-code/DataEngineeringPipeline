# Variables for AWS Glue Data Catalog and ETL Infrastructure

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "data_lake_bucket_name" {
  description = "Name of the S3 bucket for the data lake"
  type        = string
}

variable "glue_service_role_arn" {
  description = "ARN of the IAM role for Glue services"
  type        = string
}

variable "lambda_execution_role_arn" {
  description = "ARN of the IAM role for Lambda execution (for crawler trigger function)"
  type        = string
  default     = null
}

variable "catalog_id" {
  description = "AWS account ID for the Glue Data Catalog"
  type        = string
  default     = null
}

variable "crawler_schedule" {
  description = "Cron expression for crawler scheduling (optional)"
  type        = string
  default     = null
  
  validation {
    condition = var.crawler_schedule == null || can(regex("^cron\\(.*\\)$", var.crawler_schedule))
    error_message = "Crawler schedule must be a valid cron expression starting with 'cron('."
  }
}

variable "crawler_schema_change_policy" {
  description = "Schema change policy for crawlers"
  type = object({
    update_behavior = string
    delete_behavior = string
  })
  default = {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }
  
  validation {
    condition = contains(["UPDATE_IN_DATABASE", "LOG"], var.crawler_schema_change_policy.update_behavior)
    error_message = "Update behavior must be either 'UPDATE_IN_DATABASE' or 'LOG'."
  }
  
  validation {
    condition = contains(["DELETE_FROM_DATABASE", "DEPRECATE_IN_DATABASE", "LOG"], var.crawler_schema_change_policy.delete_behavior)
    error_message = "Delete behavior must be 'DELETE_FROM_DATABASE', 'DEPRECATE_IN_DATABASE', or 'LOG'."
  }
}

variable "crawler_recrawl_policy" {
  description = "Recrawl policy for crawlers"
  type = object({
    recrawl_behavior = string
  })
  default = {
    recrawl_behavior = "CRAWL_EVERYTHING"
  }
  
  validation {
    condition = contains(["CRAWL_EVERYTHING", "CRAWL_NEW_FOLDERS_ONLY"], var.crawler_recrawl_policy.recrawl_behavior)
    error_message = "Recrawl behavior must be either 'CRAWL_EVERYTHING' or 'CRAWL_NEW_FOLDERS_ONLY'."
  }
}

variable "enable_data_lineage" {
  description = "Enable data lineage tracking for crawlers"
  type        = bool
  default     = true
}

variable "enable_event_driven_crawlers" {
  description = "Enable event-driven crawler triggers using EventBridge"
  type        = bool
  default     = true
}

variable "bronze_data_sources" {
  description = "List of data sources in the bronze layer"
  type        = list(string)
  default     = ["customers", "orders", "products"]
}

variable "silver_data_sources" {
  description = "List of data sources in the silver layer"
  type        = list(string)
  default     = ["dim_customers", "fact_orders", "dim_products"]
}

variable "gold_data_sources" {
  description = "List of data sources in the gold layer"
  type        = list(string)
  default     = ["customer_analytics", "sales_summary", "ml_features"]
}

variable "crawler_exclusions" {
  description = "List of file patterns to exclude from crawling"
  type        = list(string)
  default = [
    "**/_SUCCESS",
    "**/_started_*",
    "**/_committed_*",
    "**/.DS_Store",
    "**/Thumbs.db"
  ]
}

variable "crawler_configuration" {
  description = "Advanced crawler configuration settings"
  type = object({
    version                    = number
    add_or_update_behavior    = string
    table_grouping_policy     = string
    enable_sample_path        = bool
    sample_size               = number
  })
  default = {
    version                   = 1.0
    add_or_update_behavior   = "MergeNewColumns"
    table_grouping_policy    = "CombineCompatibleSchemas"
    enable_sample_path       = false
    sample_size              = 100
  }
}

variable "enable_crawler_security_configuration" {
  description = "Enable security configuration for crawlers"
  type        = bool
  default     = true
}

variable "crawler_security_configuration_name" {
  description = "Name of the security configuration for crawlers"
  type        = string
  default     = null
}

variable "enable_crawler_cloudwatch_encryption" {
  description = "Enable CloudWatch logs encryption for crawlers"
  type        = bool
  default     = true
}

variable "crawler_log_group_retention_days" {
  description = "Retention period for crawler CloudWatch logs in days"
  type        = number
  default     = 14
  
  validation {
    condition = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.crawler_log_group_retention_days)
    error_message = "Log retention days must be a valid CloudWatch Logs retention period."
  }
}

variable "enable_partition_indexing" {
  description = "Enable partition indexing for improved query performance"
  type        = bool
  default     = true
}

variable "partition_index_keys" {
  description = "List of partition keys for indexing"
  type        = list(string)
  default     = ["year", "month", "day"]
}

variable "enable_table_optimization" {
  description = "Enable table optimization features"
  type        = bool
  default     = true
}

variable "table_optimization_config" {
  description = "Configuration for table optimization"
  type = object({
    enable_compaction     = bool
    compaction_schedule   = string
    retention_days        = number
    enable_clustering     = bool
    clustering_keys       = list(string)
  })
  default = {
    enable_compaction   = true
    compaction_schedule = "cron(0 2 * * ? *)"  # Daily at 2 AM
    retention_days      = 30
    enable_clustering   = false
    clustering_keys     = []
  }
}

variable "tags" {
  description = "A map of tags to assign to the resources"
  type        = map(string)
  default     = {}
}

# Glue ETL Job Variables
variable "glue_version" {
  description = "AWS Glue version for ETL jobs"
  type        = string
  default     = "4.0"
}

variable "glue_worker_type" {
  description = "Glue worker type for ETL jobs"
  type        = string
  default     = "G.1X"
  
  validation {
    condition     = contains(["Standard", "G.1X", "G.2X", "G.025X"], var.glue_worker_type)
    error_message = "Glue worker type must be one of: Standard, G.1X, G.2X, G.025X."
  }
}

variable "glue_number_of_workers" {
  description = "Number of Glue workers for ETL jobs"
  type        = number
  default     = 2
}

variable "glue_job_timeout" {
  description = "Timeout for Glue ETL jobs in minutes"
  type        = number
  default     = 60
}

variable "glue_job_max_retries" {
  description = "Maximum number of retries for Glue ETL jobs"
  type        = number
  default     = 1
}

variable "enable_job_bookmarks" {
  description = "Enable job bookmarks for incremental processing"
  type        = bool
  default     = true
}

variable "max_concurrent_runs" {
  description = "Maximum number of concurrent runs for each Glue job"
  type        = number
  default     = 1
}

variable "data_quality_rules" {
  description = "Data quality rules for each data source"
  type = object({
    customers = list(object({
      name        = string
      description = string
      rule_type   = string
      expression  = string
      threshold   = number
    }))
    orders = list(object({
      name        = string
      description = string
      rule_type   = string
      expression  = string
      threshold   = number
    }))
    products = list(object({
      name        = string
      description = string
      rule_type   = string
      expression  = string
      threshold   = number
    }))
  })
  default = {
    customers = [
      {
        name        = "customer_id_not_null"
        description = "Customer ID should not be null"
        rule_type   = "not_null"
        expression  = "customer_id IS NOT NULL"
        threshold   = 0.95
      },
      {
        name        = "email_format_valid"
        description = "Email should be in valid format"
        rule_type   = "regex"
        expression  = "email RLIKE '^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'"
        threshold   = 0.90
      }
    ]
    orders = [
      {
        name        = "order_id_not_null"
        description = "Order ID should not be null"
        rule_type   = "not_null"
        expression  = "order_id IS NOT NULL"
        threshold   = 1.0
      },
      {
        name        = "order_amount_positive"
        description = "Order amount should be positive"
        rule_type   = "range"
        expression  = "order_amount > 0"
        threshold   = 0.99
      }
    ]
    products = [
      {
        name        = "product_id_not_null"
        description = "Product ID should not be null"
        rule_type   = "not_null"
        expression  = "product_id IS NOT NULL"
        threshold   = 1.0
      },
      {
        name        = "product_price_valid"
        description = "Product price should be non-negative"
        rule_type   = "range"
        expression  = "price >= 0"
        threshold   = 0.95
      }
    ]
  }
}

# Silver to Gold ETL Job Variables
variable "glue_number_of_workers_gold" {
  description = "Number of Glue workers for gold layer ETL jobs (typically more for aggregation)"
  type        = number
  default     = 4
}

variable "glue_job_timeout_gold" {
  description = "Timeout for gold layer Glue ETL jobs in minutes (typically longer for aggregation)"
  type        = number
  default     = 120
}

variable "aggregation_rules" {
  description = "Aggregation rules for silver to gold transformations"
  type = object({
    customer_analytics = list(object({
      name        = string
      description = string
      aggregation_type = string
      group_by_columns = list(string)
      aggregate_columns = list(object({
        column = string
        function = string
        alias = string
      }))
      filters = list(string)
    }))
    sales_summary = list(object({
      name        = string
      description = string
      aggregation_type = string
      group_by_columns = list(string)
      aggregate_columns = list(object({
        column = string
        function = string
        alias = string
      }))
      filters = list(string)
    }))
  })
  default = {
    customer_analytics = [
      {
        name = "customer_lifetime_value"
        description = "Calculate customer lifetime value metrics"
        aggregation_type = "customer_level"
        group_by_columns = ["customer_id"]
        aggregate_columns = [
          {
            column = "total_order_value"
            function = "sum"
            alias = "lifetime_value"
          },
          {
            column = "order_id"
            function = "count"
            alias = "total_orders"
          },
          {
            column = "total_order_value"
            function = "avg"
            alias = "avg_order_value"
          }
        ]
        filters = ["is_complete_order = true"]
      }
    ]
    sales_summary = [
      {
        name = "daily_sales_summary"
        description = "Daily sales aggregation"
        aggregation_type = "time_series"
        group_by_columns = ["order_date"]
        aggregate_columns = [
          {
            column = "total_order_value"
            function = "sum"
            alias = "daily_revenue"
          },
          {
            column = "order_id"
            function = "count"
            alias = "daily_orders"
          }
        ]
        filters = ["order_status_standardized != 'CANCELLED'"]
      }
    ]
  }
}

variable "feature_engineering_config" {
  description = "Feature engineering configuration for ML workloads"
  type = object({
    customer_analytics = list(object({
      feature_name = string
      feature_type = string
      calculation = string
      description = string
    }))
    ml_features = list(object({
      feature_name = string
      feature_type = string
      calculation = string
      description = string
    }))
  })
  default = {
    customer_analytics = [
      {
        feature_name = "customer_segment"
        feature_type = "categorical"
        calculation = "CASE WHEN lifetime_value > 1000 THEN 'HIGH_VALUE' WHEN lifetime_value > 500 THEN 'MEDIUM_VALUE' ELSE 'LOW_VALUE' END"
        description = "Customer value segmentation"
      },
      {
        feature_name = "churn_risk_score"
        feature_type = "numerical"
        calculation = "CASE WHEN days_since_last_order > 365 THEN 0.9 WHEN days_since_last_order > 180 THEN 0.6 WHEN days_since_last_order > 90 THEN 0.3 ELSE 0.1 END"
        description = "Customer churn risk probability"
      }
    ]
    ml_features = [
      {
        feature_name = "recency_score"
        feature_type = "numerical"
        calculation = "1.0 / (1.0 + days_since_last_order / 30.0)"
        description = "Recency score for RFM analysis"
      },
      {
        feature_name = "frequency_score"
        feature_type = "numerical"
        calculation = "LOG(1 + total_orders)"
        description = "Frequency score for RFM analysis"
      },
      {
        feature_name = "monetary_score"
        feature_type = "numerical"
        calculation = "LOG(1 + lifetime_value)"
        description = "Monetary score for RFM analysis"
      }
    ]
  }
}

variable "ml_pipeline_config" {
  description = "Configuration for ML pipeline integration"
  type = object({
    enable_feature_store = bool
    feature_store_name = string
    target_variables = list(string)
    feature_selection_method = string
    data_split_ratio = object({
      train = number
      validation = number
      test = number
    })
    enable_auto_scaling = bool
  })
  default = {
    enable_feature_store = true
    feature_store_name = "customer-analytics-features"
    target_variables = ["churn_risk_score", "customer_segment"]
    feature_selection_method = "correlation_threshold"
    data_split_ratio = {
      train = 0.7
      validation = 0.2
      test = 0.1
    }
    enable_auto_scaling = true
  }
}

# Monitoring and Error Handling Variables
variable "enable_sns_alerts" {
  description = "Enable SNS alerts for Glue job failures"
  type        = bool
  default     = true
}

variable "enable_enhanced_error_handling" {
  description = "Enable enhanced error handling with Lambda functions"
  type        = bool
  default     = true
}

variable "enable_monitoring_dashboard" {
  description = "Enable CloudWatch dashboard for Glue monitoring"
  type        = bool
  default     = true
}

variable "job_duration_threshold_seconds" {
  description = "Threshold in seconds for job duration alarms"
  type        = number
  default     = 3600  # 1 hour
}

variable "enable_auto_retry" {
  description = "Enable automatic retry for failed jobs"
  type        = bool
  default     = true
}

variable "max_retry_attempts" {
  description = "Maximum number of automatic retry attempts"
  type        = number
  default     = 3
  
  validation {
    condition     = var.max_retry_attempts >= 1 && var.max_retry_attempts <= 10
    error_message = "Max retry attempts must be between 1 and 10."
  }
}
# AWS Glue Data Catalog and ETL Infrastructure
# This module creates Glue databases, crawlers, and ETL jobs for the medallion architecture

# Local variables for common configurations
locals {
  bronze_database_name = "${var.project_name}-${var.environment}-bronze"
  silver_database_name = "${var.project_name}-${var.environment}-silver"
  gold_database_name   = "${var.project_name}-${var.environment}-gold"
  
  common_crawler_configuration = {
    role                   = var.glue_service_role_arn
    database_name         = local.bronze_database_name
    schedule              = var.crawler_schedule
    schema_change_policy  = var.crawler_schema_change_policy
    recrawl_policy       = var.crawler_recrawl_policy
  }
}

# Glue Data Catalog Databases
resource "aws_glue_catalog_database" "bronze" {
  name        = local.bronze_database_name
  description = "Bronze layer database for raw data from Snowflake extracts"

  catalog_id = var.catalog_id

  create_table_default_permission {
    permissions = ["ALL"]
    principal   = var.glue_service_role_arn
  }

  tags = merge(var.tags, {
    Layer = "bronze"
    Type  = "raw-data"
  })
}

resource "aws_glue_catalog_database" "silver" {
  name        = local.silver_database_name
  description = "Silver layer database for cleaned and validated data"

  catalog_id = var.catalog_id

  create_table_default_permission {
    permissions = ["ALL"]
    principal   = var.glue_service_role_arn
  }

  tags = merge(var.tags, {
    Layer = "silver"
    Type  = "cleaned-data"
  })
}

resource "aws_glue_catalog_database" "gold" {
  name        = local.gold_database_name
  description = "Gold layer database for business-ready aggregated data"

  catalog_id = var.catalog_id

  create_table_default_permission {
    permissions = ["ALL"]
    principal   = var.glue_service_role_arn
  }

  tags = merge(var.tags, {
    Layer = "gold"
    Type  = "business-data"
  })
}

# Bronze Layer Crawlers - for raw Snowflake extracts
resource "aws_glue_crawler" "bronze_customers" {
  name          = "${var.project_name}-${var.environment}-bronze-customers-crawler"
  role          = var.glue_service_role_arn
  database_name = aws_glue_catalog_database.bronze.name
  description   = "Crawler for bronze layer customer data from Snowflake"

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/bronze/customers/"
    
    exclusions = [
      "**/_SUCCESS",
      "**/_started_*",
      "**/_committed_*"
    ]
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  schema_change_policy {
    update_behavior = var.crawler_schema_change_policy.update_behavior
    delete_behavior = var.crawler_schema_change_policy.delete_behavior
  }

  recrawl_policy {
    recrawl_behavior = var.crawler_recrawl_policy.recrawl_behavior
  }

  lineage_configuration {
    crawler_lineage_settings = var.enable_data_lineage ? "ENABLE" : "DISABLE"
  }

  dynamic "schedule" {
    for_each = var.crawler_schedule != null ? [1] : []
    content {
      schedule_expression = var.crawler_schedule
    }
  }

  tags = merge(var.tags, {
    Layer      = "bronze"
    DataSource = "customers"
    Type       = "crawler"
  })
}

resource "aws_glue_crawler" "bronze_orders" {
  name          = "${var.project_name}-${var.environment}-bronze-orders-crawler"
  role          = var.glue_service_role_arn
  database_name = aws_glue_catalog_database.bronze.name
  description   = "Crawler for bronze layer order data from Snowflake"

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/bronze/orders/"
    
    exclusions = [
      "**/_SUCCESS",
      "**/_started_*",
      "**/_committed_*"
    ]
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  schema_change_policy {
    update_behavior = var.crawler_schema_change_policy.update_behavior
    delete_behavior = var.crawler_schema_change_policy.delete_behavior
  }

  recrawl_policy {
    recrawl_behavior = var.crawler_recrawl_policy.recrawl_behavior
  }

  lineage_configuration {
    crawler_lineage_settings = var.enable_data_lineage ? "ENABLE" : "DISABLE"
  }

  dynamic "schedule" {
    for_each = var.crawler_schedule != null ? [1] : []
    content {
      schedule_expression = var.crawler_schedule
    }
  }

  tags = merge(var.tags, {
    Layer      = "bronze"
    DataSource = "orders"
    Type       = "crawler"
  })
}

resource "aws_glue_crawler" "bronze_products" {
  name          = "${var.project_name}-${var.environment}-bronze-products-crawler"
  role          = var.glue_service_role_arn
  database_name = aws_glue_catalog_database.bronze.name
  description   = "Crawler for bronze layer product data from Snowflake"

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/bronze/products/"
    
    exclusions = [
      "**/_SUCCESS",
      "**/_started_*",
      "**/_committed_*"
    ]
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  schema_change_policy {
    update_behavior = var.crawler_schema_change_policy.update_behavior
    delete_behavior = var.crawler_schema_change_policy.delete_behavior
  }

  recrawl_policy {
    recrawl_behavior = var.crawler_recrawl_policy.recrawl_behavior
  }

  lineage_configuration {
    crawler_lineage_settings = var.enable_data_lineage ? "ENABLE" : "DISABLE"
  }

  dynamic "schedule" {
    for_each = var.crawler_schedule != null ? [1] : []
    content {
      schedule_expression = var.crawler_schedule
    }
  }

  tags = merge(var.tags, {
    Layer      = "bronze"
    DataSource = "products"
    Type       = "crawler"
  })
}

# Silver Layer Crawlers - for cleaned and validated data
resource "aws_glue_crawler" "silver_dim_customers" {
  name          = "${var.project_name}-${var.environment}-silver-dim-customers-crawler"
  role          = var.glue_service_role_arn
  database_name = aws_glue_catalog_database.silver.name
  description   = "Crawler for silver layer customer dimension data"

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/silver/dim_customers/"
    
    exclusions = [
      "**/_SUCCESS",
      "**/_started_*",
      "**/_committed_*"
    ]
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  schema_change_policy {
    update_behavior = var.crawler_schema_change_policy.update_behavior
    delete_behavior = var.crawler_schema_change_policy.delete_behavior
  }

  recrawl_policy {
    recrawl_behavior = var.crawler_recrawl_policy.recrawl_behavior
  }

  lineage_configuration {
    crawler_lineage_settings = var.enable_data_lineage ? "ENABLE" : "DISABLE"
  }

  tags = merge(var.tags, {
    Layer      = "silver"
    DataSource = "dim_customers"
    Type       = "crawler"
  })
}

resource "aws_glue_crawler" "silver_fact_orders" {
  name          = "${var.project_name}-${var.environment}-silver-fact-orders-crawler"
  role          = var.glue_service_role_arn
  database_name = aws_glue_catalog_database.silver.name
  description   = "Crawler for silver layer order fact data"

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/silver/fact_orders/"
    
    exclusions = [
      "**/_SUCCESS",
      "**/_started_*",
      "**/_committed_*"
    ]
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  schema_change_policy {
    update_behavior = var.crawler_schema_change_policy.update_behavior
    delete_behavior = var.crawler_schema_change_policy.delete_behavior
  }

  recrawl_policy {
    recrawl_behavior = var.crawler_recrawl_policy.recrawl_behavior
  }

  lineage_configuration {
    crawler_lineage_settings = var.enable_data_lineage ? "ENABLE" : "DISABLE"
  }

  tags = merge(var.tags, {
    Layer      = "silver"
    DataSource = "fact_orders"
    Type       = "crawler"
  })
}

resource "aws_glue_crawler" "silver_dim_products" {
  name          = "${var.project_name}-${var.environment}-silver-dim-products-crawler"
  role          = var.glue_service_role_arn
  database_name = aws_glue_catalog_database.silver.name
  description   = "Crawler for silver layer product dimension data"

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/silver/dim_products/"
    
    exclusions = [
      "**/_SUCCESS",
      "**/_started_*",
      "**/_committed_*"
    ]
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  schema_change_policy {
    update_behavior = var.crawler_schema_change_policy.update_behavior
    delete_behavior = var.crawler_schema_change_policy.delete_behavior
  }

  recrawl_policy {
    recrawl_behavior = var.crawler_recrawl_policy.recrawl_behavior
  }

  lineage_configuration {
    crawler_lineage_settings = var.enable_data_lineage ? "ENABLE" : "DISABLE"
  }

  tags = merge(var.tags, {
    Layer      = "silver"
    DataSource = "dim_products"
    Type       = "crawler"
  })
}

# Gold Layer Crawlers - for business-ready aggregated data
resource "aws_glue_crawler" "gold_customer_analytics" {
  name          = "${var.project_name}-${var.environment}-gold-customer-analytics-crawler"
  role          = var.glue_service_role_arn
  database_name = aws_glue_catalog_database.gold.name
  description   = "Crawler for gold layer customer analytics data"

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/gold/customer_analytics/"
    
    exclusions = [
      "**/_SUCCESS",
      "**/_started_*",
      "**/_committed_*"
    ]
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  schema_change_policy {
    update_behavior = var.crawler_schema_change_policy.update_behavior
    delete_behavior = var.crawler_schema_change_policy.delete_behavior
  }

  recrawl_policy {
    recrawl_behavior = var.crawler_recrawl_policy.recrawl_behavior
  }

  lineage_configuration {
    crawler_lineage_settings = var.enable_data_lineage ? "ENABLE" : "DISABLE"
  }

  tags = merge(var.tags, {
    Layer      = "gold"
    DataSource = "customer_analytics"
    Type       = "crawler"
  })
}

resource "aws_glue_crawler" "gold_sales_summary" {
  name          = "${var.project_name}-${var.environment}-gold-sales-summary-crawler"
  role          = var.glue_service_role_arn
  database_name = aws_glue_catalog_database.gold.name
  description   = "Crawler for gold layer sales summary data"

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/gold/sales_summary/"
    
    exclusions = [
      "**/_SUCCESS",
      "**/_started_*",
      "**/_committed_*"
    ]
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  schema_change_policy {
    update_behavior = var.crawler_schema_change_policy.update_behavior
    delete_behavior = var.crawler_schema_change_policy.delete_behavior
  }

  recrawl_policy {
    recrawl_behavior = var.crawler_recrawl_policy.recrawl_behavior
  }

  lineage_configuration {
    crawler_lineage_settings = var.enable_data_lineage ? "ENABLE" : "DISABLE"
  }

  tags = merge(var.tags, {
    Layer      = "gold"
    DataSource = "sales_summary"
    Type       = "crawler"
  })
}

resource "aws_glue_crawler" "gold_ml_features" {
  name          = "${var.project_name}-${var.environment}-gold-ml-features-crawler"
  role          = var.glue_service_role_arn
  database_name = aws_glue_catalog_database.gold.name
  description   = "Crawler for gold layer ML feature data"

  s3_target {
    path = "s3://${var.data_lake_bucket_name}/gold/ml_features/"
    
    exclusions = [
      "**/_SUCCESS",
      "**/_started_*",
      "**/_committed_*"
    ]
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = {
        AddOrUpdateBehavior = "InheritFromTable"
      }
      Tables = {
        AddOrUpdateBehavior = "MergeNewColumns"
      }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  schema_change_policy {
    update_behavior = var.crawler_schema_change_policy.update_behavior
    delete_behavior = var.crawler_schema_change_policy.delete_behavior
  }

  recrawl_policy {
    recrawl_behavior = var.crawler_recrawl_policy.recrawl_behavior
  }

  lineage_configuration {
    crawler_lineage_settings = var.enable_data_lineage ? "ENABLE" : "DISABLE"
  }

  tags = merge(var.tags, {
    Layer      = "gold"
    DataSource = "ml_features"
    Type       = "crawler"
  })
}

# EventBridge Rules for Crawler Triggers
resource "aws_cloudwatch_event_rule" "bronze_data_arrival" {
  count = var.enable_event_driven_crawlers ? 1 : 0
  
  name        = "${var.project_name}-${var.environment}-bronze-data-arrival"
  description = "Trigger crawlers when new data arrives in bronze layer"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [var.data_lake_bucket_name]
      }
      object = {
        key = [
          {
            prefix = "bronze/"
          }
        ]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "trigger_bronze_crawlers" {
  count = var.enable_event_driven_crawlers ? 1 : 0
  
  rule      = aws_cloudwatch_event_rule.bronze_data_arrival[0].name
  target_id = "TriggerBronzeCrawlers"
  arn       = aws_lambda_function.crawler_trigger[0].arn
}

# Lambda function to trigger appropriate crawlers based on S3 events
resource "aws_lambda_function" "crawler_trigger" {
  count = var.enable_event_driven_crawlers ? 1 : 0
  
  filename         = data.archive_file.crawler_trigger_zip[0].output_path
  function_name    = "${var.project_name}-${var.environment}-crawler-trigger"
  role            = var.lambda_execution_role_arn
  handler         = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.crawler_trigger_zip[0].output_base64sha256
  runtime         = "python3.9"
  timeout         = 60

  environment {
    variables = {
      BRONZE_CUSTOMERS_CRAWLER = aws_glue_crawler.bronze_customers.name
      BRONZE_ORDERS_CRAWLER    = aws_glue_crawler.bronze_orders.name
      BRONZE_PRODUCTS_CRAWLER  = aws_glue_crawler.bronze_products.name
      SILVER_DIM_CUSTOMERS_CRAWLER = aws_glue_crawler.silver_dim_customers.name
      SILVER_FACT_ORDERS_CRAWLER   = aws_glue_crawler.silver_fact_orders.name
      SILVER_DIM_PRODUCTS_CRAWLER  = aws_glue_crawler.silver_dim_products.name
      GOLD_CUSTOMER_ANALYTICS_CRAWLER = aws_glue_crawler.gold_customer_analytics.name
      GOLD_SALES_SUMMARY_CRAWLER      = aws_glue_crawler.gold_sales_summary.name
      GOLD_ML_FEATURES_CRAWLER        = aws_glue_crawler.gold_ml_features.name
    }
  }

  tags = merge(var.tags, {
    Type = "crawler-trigger"
  })
}

# Create the Lambda deployment package
data "archive_file" "crawler_trigger_zip" {
  count = var.enable_event_driven_crawlers ? 1 : 0
  
  type        = "zip"
  output_path = "${path.module}/crawler_trigger.zip"
  
  source {
    content = templatefile("${path.module}/templates/crawler_trigger.py", {
      project_name = var.project_name
      environment  = var.environment
    })
    filename = "lambda_function.py"
  }
}

# Lambda permission for EventBridge to invoke the function
resource "aws_lambda_permission" "allow_eventbridge" {
  count = var.enable_event_driven_crawlers ? 1 : 0
  
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.crawler_trigger[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.bronze_data_arrival[0].arn
}

# =============================================================================
# GLUE ETL JOBS
# =============================================================================

# Bronze to Silver ETL Jobs
resource "aws_glue_job" "bronze_to_silver_customers" {
  name         = "${var.project_name}-${var.environment}-bronze-to-silver-customers"
  role_arn     = var.glue_service_role_arn
  description  = "ETL job to transform bronze customer data to silver layer"
  
  glue_version      = var.glue_version
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_number_of_workers
  timeout           = var.glue_job_timeout
  max_retries       = var.glue_job_max_retries

  command {
    script_location = "s3://${var.data_lake_bucket_name}/artifacts/glue_scripts/bronze_to_silver_customers.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = var.enable_job_bookmarks ? "job-bookmark-enable" : "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"           = "s3://${var.data_lake_bucket_name}/artifacts/spark-logs/"
    "--enable-continuous-cloudwatch-log" = "true"
    "--TempDir"                         = "s3://${var.data_lake_bucket_name}/artifacts/temp/"
    
    # Job-specific parameters
    "--source_database"    = aws_glue_catalog_database.bronze.name
    "--source_table"       = "customers"
    "--target_database"    = aws_glue_catalog_database.silver.name
    "--target_table"       = "dim_customers"
    "--target_path"        = "s3://${var.data_lake_bucket_name}/silver/dim_customers/"
    "--data_quality_rules" = jsonencode(var.data_quality_rules.customers)
  }

  execution_property {
    max_concurrent_runs = var.max_concurrent_runs
  }

  tags = merge(var.tags, {
    Layer      = "bronze-to-silver"
    DataSource = "customers"
    Type       = "etl-job"
  })
}

resource "aws_glue_job" "bronze_to_silver_orders" {
  name         = "${var.project_name}-${var.environment}-bronze-to-silver-orders"
  role_arn     = var.glue_service_role_arn
  description  = "ETL job to transform bronze order data to silver layer"
  
  glue_version      = var.glue_version
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_number_of_workers
  timeout           = var.glue_job_timeout
  max_retries       = var.glue_job_max_retries

  command {
    script_location = "s3://${var.data_lake_bucket_name}/artifacts/glue_scripts/bronze_to_silver_orders.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = var.enable_job_bookmarks ? "job-bookmark-enable" : "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"           = "s3://${var.data_lake_bucket_name}/artifacts/spark-logs/"
    "--enable-continuous-cloudwatch-log" = "true"
    "--TempDir"                         = "s3://${var.data_lake_bucket_name}/artifacts/temp/"
    
    # Job-specific parameters
    "--source_database"    = aws_glue_catalog_database.bronze.name
    "--source_table"       = "orders"
    "--target_database"    = aws_glue_catalog_database.silver.name
    "--target_table"       = "fact_orders"
    "--target_path"        = "s3://${var.data_lake_bucket_name}/silver/fact_orders/"
    "--data_quality_rules" = jsonencode(var.data_quality_rules.orders)
  }

  execution_property {
    max_concurrent_runs = var.max_concurrent_runs
  }

  tags = merge(var.tags, {
    Layer      = "bronze-to-silver"
    DataSource = "orders"
    Type       = "etl-job"
  })
}

resource "aws_glue_job" "bronze_to_silver_products" {
  name         = "${var.project_name}-${var.environment}-bronze-to-silver-products"
  role_arn     = var.glue_service_role_arn
  description  = "ETL job to transform bronze product data to silver layer"
  
  glue_version      = var.glue_version
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_number_of_workers
  timeout           = var.glue_job_timeout
  max_retries       = var.glue_job_max_retries

  command {
    script_location = "s3://${var.data_lake_bucket_name}/artifacts/glue_scripts/bronze_to_silver_products.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = var.enable_job_bookmarks ? "job-bookmark-enable" : "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"           = "s3://${var.data_lake_bucket_name}/artifacts/spark-logs/"
    "--enable-continuous-cloudwatch-log" = "true"
    "--TempDir"                         = "s3://${var.data_lake_bucket_name}/artifacts/temp/"
    
    # Job-specific parameters
    "--source_database"    = aws_glue_catalog_database.bronze.name
    "--source_table"       = "products"
    "--target_database"    = aws_glue_catalog_database.silver.name
    "--target_table"       = "dim_products"
    "--target_path"        = "s3://${var.data_lake_bucket_name}/silver/dim_products/"
    "--data_quality_rules" = jsonencode(var.data_quality_rules.products)
  }

  execution_property {
    max_concurrent_runs = var.max_concurrent_runs
  }

  tags = merge(var.tags, {
    Layer      = "bronze-to-silver"
    DataSource = "products"
    Type       = "etl-job"
  })
}

# Silver to Gold ETL Jobs
resource "aws_glue_job" "silver_to_gold_customer_analytics" {
  name         = "${var.project_name}-${var.environment}-silver-to-gold-customer-analytics"
  role_arn     = var.glue_service_role_arn
  description  = "ETL job to create customer analytics from silver layer data"
  
  glue_version      = var.glue_version
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_number_of_workers_gold
  timeout           = var.glue_job_timeout_gold
  max_retries       = var.glue_job_max_retries

  command {
    script_location = "s3://${var.data_lake_bucket_name}/artifacts/glue_scripts/silver_to_gold_customer_analytics.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = var.enable_job_bookmarks ? "job-bookmark-enable" : "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"           = "s3://${var.data_lake_bucket_name}/artifacts/spark-logs/"
    "--enable-continuous-cloudwatch-log" = "true"
    "--TempDir"                         = "s3://${var.data_lake_bucket_name}/artifacts/temp/"
    
    # Job-specific parameters
    "--source_database"        = aws_glue_catalog_database.silver.name
    "--customers_table"        = "dim_customers"
    "--orders_table"          = "fact_orders"
    "--products_table"        = "dim_products"
    "--target_database"       = aws_glue_catalog_database.gold.name
    "--target_table"          = "customer_analytics"
    "--target_path"           = "s3://${var.data_lake_bucket_name}/gold/customer_analytics/"
    "--aggregation_rules"     = jsonencode(var.aggregation_rules.customer_analytics)
    "--feature_engineering"   = jsonencode(var.feature_engineering_config.customer_analytics)
  }

  execution_property {
    max_concurrent_runs = var.max_concurrent_runs
  }

  tags = merge(var.tags, {
    Layer      = "silver-to-gold"
    DataSource = "customer_analytics"
    Type       = "etl-job"
  })
}

resource "aws_glue_job" "silver_to_gold_sales_summary" {
  name         = "${var.project_name}-${var.environment}-silver-to-gold-sales-summary"
  role_arn     = var.glue_service_role_arn
  description  = "ETL job to create sales summary from silver layer data"
  
  glue_version      = var.glue_version
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_number_of_workers_gold
  timeout           = var.glue_job_timeout_gold
  max_retries       = var.glue_job_max_retries

  command {
    script_location = "s3://${var.data_lake_bucket_name}/artifacts/glue_scripts/silver_to_gold_sales_summary.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = var.enable_job_bookmarks ? "job-bookmark-enable" : "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"           = "s3://${var.data_lake_bucket_name}/artifacts/spark-logs/"
    "--enable-continuous-cloudwatch-log" = "true"
    "--TempDir"                         = "s3://${var.data_lake_bucket_name}/artifacts/temp/"
    
    # Job-specific parameters
    "--source_database"        = aws_glue_catalog_database.silver.name
    "--orders_table"          = "fact_orders"
    "--products_table"        = "dim_products"
    "--customers_table"       = "dim_customers"
    "--target_database"       = aws_glue_catalog_database.gold.name
    "--target_table"          = "sales_summary"
    "--target_path"           = "s3://${var.data_lake_bucket_name}/gold/sales_summary/"
    "--aggregation_rules"     = jsonencode(var.aggregation_rules.sales_summary)
  }

  execution_property {
    max_concurrent_runs = var.max_concurrent_runs
  }

  tags = merge(var.tags, {
    Layer      = "silver-to-gold"
    DataSource = "sales_summary"
    Type       = "etl-job"
  })
}

resource "aws_glue_job" "silver_to_gold_ml_features" {
  name         = "${var.project_name}-${var.environment}-silver-to-gold-ml-features"
  role_arn     = var.glue_service_role_arn
  description  = "ETL job to create ML features from silver layer data"
  
  glue_version      = var.glue_version
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_number_of_workers_gold
  timeout           = var.glue_job_timeout_gold
  max_retries       = var.glue_job_max_retries

  command {
    script_location = "s3://${var.data_lake_bucket_name}/artifacts/glue_scripts/silver_to_gold_ml_features.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = var.enable_job_bookmarks ? "job-bookmark-enable" : "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"           = "s3://${var.data_lake_bucket_name}/artifacts/spark-logs/"
    "--enable-continuous-cloudwatch-log" = "true"
    "--TempDir"                         = "s3://${var.data_lake_bucket_name}/artifacts/temp/"
    
    # Job-specific parameters
    "--source_database"        = aws_glue_catalog_database.silver.name
    "--customers_table"        = "dim_customers"
    "--orders_table"          = "fact_orders"
    "--products_table"        = "dim_products"
    "--target_database"       = aws_glue_catalog_database.gold.name
    "--target_table"          = "ml_features"
    "--target_path"           = "s3://${var.data_lake_bucket_name}/gold/ml_features/"
    "--feature_engineering"   = jsonencode(var.feature_engineering_config.ml_features)
    "--ml_config"             = jsonencode(var.ml_pipeline_config)
  }

  execution_property {
    max_concurrent_runs = var.max_concurrent_runs
  }

  tags = merge(var.tags, {
    Layer      = "silver-to-gold"
    DataSource = "ml_features"
    Type       = "etl-job"
  })
}

# =============================================================================
# MONITORING AND ALERTING
# =============================================================================

# CloudWatch Log Groups for Glue Jobs
resource "aws_cloudwatch_log_group" "glue_jobs" {
  for_each = toset([
    "bronze-to-silver-customers",
    "bronze-to-silver-orders", 
    "bronze-to-silver-products",
    "silver-to-gold-customer-analytics",
    "silver-to-gold-sales-summary",
    "silver-to-gold-ml-features"
  ])
  
  name              = "/aws-glue/jobs/${var.project_name}-${var.environment}-${each.key}"
  retention_in_days = var.crawler_log_group_retention_days
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-${each.key}-logs"
    Type = "glue-job-logs"
  })
}

# CloudWatch Log Groups for Crawlers
resource "aws_cloudwatch_log_group" "glue_crawlers" {
  for_each = toset([
    "bronze-customers-crawler",
    "bronze-orders-crawler",
    "bronze-products-crawler",
    "silver-dim-customers-crawler",
    "silver-fact-orders-crawler",
    "silver-dim-products-crawler",
    "gold-customer-analytics-crawler",
    "gold-sales-summary-crawler",
    "gold-ml-features-crawler"
  ])
  
  name              = "/aws-glue/crawlers/${var.project_name}-${var.environment}-${each.key}"
  retention_in_days = var.crawler_log_group_retention_days
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-${each.key}-logs"
    Type = "glue-crawler-logs"
  })
}

# CloudWatch Metrics for Glue Jobs
resource "aws_cloudwatch_metric_alarm" "glue_job_failures" {
  for_each = {
    bronze_customers = aws_glue_job.bronze_to_silver_customers.name
    bronze_orders    = aws_glue_job.bronze_to_silver_orders.name
    bronze_products  = aws_glue_job.bronze_to_silver_products.name
    gold_analytics   = aws_glue_job.silver_to_gold_customer_analytics.name
    gold_sales       = aws_glue_job.silver_to_gold_sales_summary.name
    gold_ml          = aws_glue_job.silver_to_gold_ml_features.name
  }
  
  alarm_name          = "${var.project_name}-${var.environment}-glue-job-${each.key}-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "glue.driver.aggregate.numFailedTasks"
  namespace           = "AWS/Glue"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors Glue job ${each.value} failures"
  alarm_actions       = var.enable_sns_alerts ? [aws_sns_topic.glue_alerts[0].arn] : []
  
  dimensions = {
    JobName = each.value
  }
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-glue-job-${each.key}-failures"
    Type = "glue-job-alarm"
  })
}

# CloudWatch Metrics for Glue Job Duration
resource "aws_cloudwatch_metric_alarm" "glue_job_duration" {
  for_each = {
    bronze_customers = aws_glue_job.bronze_to_silver_customers.name
    bronze_orders    = aws_glue_job.bronze_to_silver_orders.name
    bronze_products  = aws_glue_job.bronze_to_silver_products.name
    gold_analytics   = aws_glue_job.silver_to_gold_customer_analytics.name
    gold_sales       = aws_glue_job.silver_to_gold_sales_summary.name
    gold_ml          = aws_glue_job.silver_to_gold_ml_features.name
  }
  
  alarm_name          = "${var.project_name}-${var.environment}-glue-job-${each.key}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "glue.driver.aggregate.elapsedTime"
  namespace           = "AWS/Glue"
  period              = "300"
  statistic           = "Maximum"
  threshold           = var.job_duration_threshold_seconds
  alarm_description   = "This metric monitors Glue job ${each.value} duration"
  alarm_actions       = var.enable_sns_alerts ? [aws_sns_topic.glue_alerts[0].arn] : []
  
  dimensions = {
    JobName = each.value
  }
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-glue-job-${each.key}-duration"
    Type = "glue-job-duration-alarm"
  })
}

# CloudWatch Metrics for Crawler Failures
resource "aws_cloudwatch_metric_alarm" "crawler_failures" {
  for_each = {
    bronze_customers     = aws_glue_crawler.bronze_customers.name
    bronze_orders        = aws_glue_crawler.bronze_orders.name
    bronze_products      = aws_glue_crawler.bronze_products.name
    silver_dim_customers = aws_glue_crawler.silver_dim_customers.name
    silver_fact_orders   = aws_glue_crawler.silver_fact_orders.name
    silver_dim_products  = aws_glue_crawler.silver_dim_products.name
    gold_analytics       = aws_glue_crawler.gold_customer_analytics.name
    gold_sales           = aws_glue_crawler.gold_sales_summary.name
    gold_ml              = aws_glue_crawler.gold_ml_features.name
  }
  
  alarm_name          = "${var.project_name}-${var.environment}-crawler-${each.key}-failures"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "SuccessfulRequestCount"
  namespace           = "AWS/Glue"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors Glue crawler ${each.value} failures"
  alarm_actions       = var.enable_sns_alerts ? [aws_sns_topic.glue_alerts[0].arn] : []
  treat_missing_data  = "breaching"
  
  dimensions = {
    CrawlerName = each.value
  }
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-crawler-${each.key}-failures"
    Type = "glue-crawler-alarm"
  })
}

# SNS Topic for Glue Alerts
resource "aws_sns_topic" "glue_alerts" {
  count = var.enable_sns_alerts ? 1 : 0
  
  name = "${var.project_name}-${var.environment}-glue-alerts"
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-glue-alerts"
    Type = "sns-topic"
  })
}

# SNS Topic Policy
resource "aws_sns_topic_policy" "glue_alerts_policy" {
  count = var.enable_sns_alerts ? 1 : 0
  
  arn = aws_sns_topic.glue_alerts[0].arn
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "cloudwatch.amazonaws.com"
        }
        Action = "sns:Publish"
        Resource = aws_sns_topic.glue_alerts[0].arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# Lambda Function for Enhanced Error Handling
resource "aws_lambda_function" "glue_error_handler" {
  count = var.enable_enhanced_error_handling ? 1 : 0
  
  filename         = data.archive_file.glue_error_handler_zip[0].output_path
  function_name    = "${var.project_name}-${var.environment}-glue-error-handler"
  role            = var.lambda_execution_role_arn
  handler         = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.glue_error_handler_zip[0].output_base64sha256
  runtime         = "python3.9"
  timeout         = 300
  
  environment {
    variables = {
      PROJECT_NAME = var.project_name
      ENVIRONMENT  = var.environment
      SNS_TOPIC_ARN = var.enable_sns_alerts ? aws_sns_topic.glue_alerts[0].arn : ""
      ENABLE_AUTO_RETRY = var.enable_auto_retry ? "true" : "false"
      MAX_RETRY_ATTEMPTS = var.max_retry_attempts
    }
  }
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-glue-error-handler"
    Type = "error-handler"
  })
}

# Create the Lambda deployment package for error handler
data "archive_file" "glue_error_handler_zip" {
  count = var.enable_enhanced_error_handling ? 1 : 0
  
  type        = "zip"
  output_path = "${path.module}/glue_error_handler.zip"
  
  source {
    content = templatefile("${path.module}/templates/glue_error_handler.py", {
      project_name = var.project_name
      environment  = var.environment
    })
    filename = "lambda_function.py"
  }
}

# EventBridge Rule for Glue Job State Changes
resource "aws_cloudwatch_event_rule" "glue_job_state_change" {
  count = var.enable_enhanced_error_handling ? 1 : 0
  
  name        = "${var.project_name}-${var.environment}-glue-job-state-change"
  description = "Capture Glue job state changes for error handling"
  
  event_pattern = jsonencode({
    source      = ["aws.glue"]
    detail-type = ["Glue Job State Change"]
    detail = {
      jobName = [for job in [
        aws_glue_job.bronze_to_silver_customers.name,
        aws_glue_job.bronze_to_silver_orders.name,
        aws_glue_job.bronze_to_silver_products.name,
        aws_glue_job.silver_to_gold_customer_analytics.name,
        aws_glue_job.silver_to_gold_sales_summary.name,
        aws_glue_job.silver_to_gold_ml_features.name
      ] : job]
      state = ["FAILED", "TIMEOUT", "STOPPED"]
    }
  })
  
  tags = var.tags
}

# EventBridge Target for Error Handler
resource "aws_cloudwatch_event_target" "glue_error_handler_target" {
  count = var.enable_enhanced_error_handling ? 1 : 0
  
  rule      = aws_cloudwatch_event_rule.glue_job_state_change[0].name
  target_id = "GlueErrorHandlerTarget"
  arn       = aws_lambda_function.glue_error_handler[0].arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge_glue_error" {
  count = var.enable_enhanced_error_handling ? 1 : 0
  
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.glue_error_handler[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.glue_job_state_change[0].arn
}

# CloudWatch Dashboard for Glue Monitoring
resource "aws_cloudwatch_dashboard" "glue_monitoring" {
  count = var.enable_monitoring_dashboard ? 1 : 0
  
  dashboard_name = "${var.project_name}-${var.environment}-glue-monitoring"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        
        properties = {
          metrics = [
            for job_name in [
              aws_glue_job.bronze_to_silver_customers.name,
              aws_glue_job.bronze_to_silver_orders.name,
              aws_glue_job.bronze_to_silver_products.name,
              aws_glue_job.silver_to_gold_customer_analytics.name,
              aws_glue_job.silver_to_gold_sales_summary.name,
              aws_glue_job.silver_to_gold_ml_features.name
            ] : ["AWS/Glue", "glue.driver.aggregate.numFailedTasks", "JobName", job_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Glue Job Failures"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        
        properties = {
          metrics = [
            for job_name in [
              aws_glue_job.bronze_to_silver_customers.name,
              aws_glue_job.bronze_to_silver_orders.name,
              aws_glue_job.bronze_to_silver_products.name,
              aws_glue_job.silver_to_gold_customer_analytics.name,
              aws_glue_job.silver_to_gold_sales_summary.name,
              aws_glue_job.silver_to_gold_ml_features.name
            ] : ["AWS/Glue", "glue.driver.aggregate.elapsedTime", "JobName", job_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Glue Job Duration"
          period  = 300
        }
      }
    ]
  })
}

# Data Lineage Tracking (if enabled)
resource "aws_glue_data_catalog_encryption_settings" "catalog_encryption" {
  count = var.enable_crawler_security_configuration ? 1 : 0
  
  data_catalog_encryption_settings {
    connection_password_encryption {
      return_connection_password_encrypted = true
    }
    
    encryption_at_rest {
      catalog_encryption_mode = "SSE-KMS"
    }
  }
}
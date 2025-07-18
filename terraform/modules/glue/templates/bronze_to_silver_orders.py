"""
Bronze to Silver ETL Job for Order Data
This PySpark script transforms raw order data from the bronze layer
to cleaned and validated fact table data in the silver layer.
"""

import sys
import json
from datetime import datetime
from typing import Dict, List, Any

from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame

from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

# Get job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'source_database',
    'source_table', 
    'target_database',
    'target_table',
    'target_path',
    'data_quality_rules'
])

job.init(args['JOB_NAME'], args)

# Configuration
SOURCE_DATABASE = args['source_database']
SOURCE_TABLE = args['source_table']
TARGET_DATABASE = args['target_database']
TARGET_TABLE = args['target_table']
TARGET_PATH = args['target_path']
DATA_QUALITY_RULES = json.loads(args['data_quality_rules'])

# Job execution timestamp
EXECUTION_TIMESTAMP = datetime.now()
EXECUTION_DATE = EXECUTION_TIMESTAMP.date()

def log_info(message: str):
    """Log information message with timestamp"""
    print(f"[{datetime.now().isoformat()}] INFO: {message}")

def log_error(message: str):
    """Log error message with timestamp"""
    print(f"[{datetime.now().isoformat()}] ERROR: {message}")

def read_bronze_data() -> DynamicFrame:
    """Read order data from bronze layer"""
    log_info(f"Reading data from {SOURCE_DATABASE}.{SOURCE_TABLE}")
    
    try:
        # Read from Glue Data Catalog
        dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name=SOURCE_TABLE,
            transformation_ctx="read_bronze_orders"
        )
        
        log_info(f"Successfully read {dynamic_frame.count()} records from bronze layer")
        return dynamic_frame
        
    except Exception as e:
        log_error(f"Failed to read bronze data: {str(e)}")
        raise

def clean_order_data(df: DataFrame) -> DataFrame:
    """Clean and standardize order data"""
    log_info("Starting data cleaning process")
    
    try:
        cleaned_df = df
        
        # 1. Data type conversions and null handling
        cleaned_df = cleaned_df.withColumn(
            "order_id", 
            when(col("order_id").isNull(), lit(None)).otherwise(col("order_id").cast(StringType()))
        )
        
        cleaned_df = cleaned_df.withColumn(
            "customer_id",
            when(col("customer_id").isNull(), lit(None)).otherwise(col("customer_id").cast(StringType()))
        )
        
        # 2. Handle monetary values
        cleaned_df = cleaned_df.withColumn(
            "order_amount",
            when(
                col("order_amount").isNull() | (col("order_amount") < 0),
                lit(0.0)
            ).otherwise(col("order_amount").cast(DecimalType(10, 2)))
        )
        
        cleaned_df = cleaned_df.withColumn(
            "tax_amount",
            when(
                col("tax_amount").isNull() | (col("tax_amount") < 0),
                lit(0.0)
            ).otherwise(col("tax_amount").cast(DecimalType(10, 2)))
        )
        
        cleaned_df = cleaned_df.withColumn(
            "shipping_amount",
            when(
                col("shipping_amount").isNull() | (col("shipping_amount") < 0),
                lit(0.0)
            ).otherwise(col("shipping_amount").cast(DecimalType(10, 2)))
        )
        
        # 3. Calculate total order value
        cleaned_df = cleaned_df.withColumn(
            "total_order_value",
            col("order_amount") + col("tax_amount") + col("shipping_amount")
        )
        
        # 4. Standardize order status
        cleaned_df = cleaned_df.withColumn(
            "order_status_standardized",
            when(col("order_status").isNull(), "UNKNOWN")
            .when(upper(col("order_status")).isin(["PENDING", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"]), 
                  upper(col("order_status")))
            .otherwise("OTHER")
        )
        
        # 5. Handle date fields
        cleaned_df = cleaned_df.withColumn(
            "order_date",
            when(col("order_date").isNull(), current_date()).otherwise(col("order_date").cast(DateType()))
        )
        
        cleaned_df = cleaned_df.withColumn(
            "shipped_date",
            when(col("shipped_date").isNotNull(), col("shipped_date").cast(DateType())).otherwise(lit(None))
        )
        
        cleaned_df = cleaned_df.withColumn(
            "delivered_date",
            when(col("delivered_date").isNotNull(), col("delivered_date").cast(DateType())).otherwise(lit(None))
        )
        
        # 6. Calculate business metrics
        cleaned_df = cleaned_df.withColumn(
            "days_to_ship",
            when(
                col("shipped_date").isNotNull() & col("order_date").isNotNull(),
                datediff(col("shipped_date"), col("order_date"))
            ).otherwise(lit(None))
        )
        
        cleaned_df = cleaned_df.withColumn(
            "days_to_deliver",
            when(
                col("delivered_date").isNotNull() & col("order_date").isNotNull(),
                datediff(col("delivered_date"), col("order_date"))
            ).otherwise(lit(None))
        )
        
        # 7. Add order categorization
        cleaned_df = cleaned_df.withColumn(
            "order_size_category",
            when(col("total_order_value") < 50, "SMALL")
            .when(col("total_order_value") < 200, "MEDIUM")
            .when(col("total_order_value") < 500, "LARGE")
            .otherwise("EXTRA_LARGE")
        )
        
        # 8. Add time-based dimensions
        cleaned_df = cleaned_df.withColumn("order_year", year(col("order_date")))
        cleaned_df = cleaned_df.withColumn("order_month", month(col("order_date")))
        cleaned_df = cleaned_df.withColumn("order_quarter", quarter(col("order_date")))
        cleaned_df = cleaned_df.withColumn("order_day_of_week", dayofweek(col("order_date")))
        cleaned_df = cleaned_df.withColumn("order_day_of_year", dayofyear(col("order_date")))
        
        # 9. Add data quality indicators
        cleaned_df = cleaned_df.withColumn(
            "has_customer_id",
            when(col("customer_id").isNotNull(), True).otherwise(False)
        )
        
        cleaned_df = cleaned_df.withColumn(
            "has_valid_amount",
            when(col("order_amount") > 0, True).otherwise(False)
        )
        
        cleaned_df = cleaned_df.withColumn(
            "is_complete_order",
            when(
                col("has_customer_id") & col("has_valid_amount") & 
                col("order_date").isNotNull() & col("order_status_standardized") != "UNKNOWN",
                True
            ).otherwise(False)
        )
        
        # 10. Generate surrogate key
        window_spec = Window.orderBy("order_id", "order_date")
        cleaned_df = cleaned_df.withColumn(
            "order_key",
            row_number().over(window_spec)
        )
        
        # 11. Add audit columns
        cleaned_df = cleaned_df.withColumn("etl_processed_at", lit(EXECUTION_TIMESTAMP))
        cleaned_df = cleaned_df.withColumn("source_system", lit("snowflake"))
        cleaned_df = cleaned_df.withColumn("record_version", lit(1))
        
        log_info(f"Data cleaning completed. Processed {cleaned_df.count()} records")
        return cleaned_df
        
    except Exception as e:
        log_error(f"Data cleaning failed: {str(e)}")
        raise

def validate_data_quality(df: DataFrame) -> Dict[str, Any]:
    """Validate data quality based on defined rules"""
    log_info("Starting data quality validation")
    
    quality_results = {
        "total_records": df.count(),
        "validation_timestamp": EXECUTION_TIMESTAMP.isoformat(),
        "rules_results": [],
        "overall_quality_score": 0.0,
        "business_metrics": {}
    }
    
    try:
        total_records = quality_results["total_records"]
        
        # Standard data quality rules
        for rule in DATA_QUALITY_RULES:
            rule_name = rule["name"]
            expression = rule["expression"]
            threshold = rule["threshold"]
            
            log_info(f"Validating rule: {rule_name}")
            
            # Count records that pass the rule
            valid_records = df.filter(expression).count()
            pass_rate = valid_records / total_records if total_records > 0 else 0
            
            rule_result = {
                "rule_name": rule_name,
                "description": rule["description"],
                "rule_type": rule["rule_type"],
                "expression": expression,
                "threshold": threshold,
                "valid_records": valid_records,
                "total_records": total_records,
                "pass_rate": pass_rate,
                "passed": pass_rate >= threshold,
                "validation_timestamp": EXECUTION_TIMESTAMP.isoformat()
            }
            
            quality_results["rules_results"].append(rule_result)
            
            if not rule_result["passed"]:
                log_error(f"Data quality rule failed: {rule_name} (pass rate: {pass_rate:.2%}, threshold: {threshold:.2%})")
        
        # Business-specific metrics
        business_metrics = {
            "total_order_value": df.agg(sum("total_order_value")).collect()[0][0] or 0,
            "average_order_value": df.agg(avg("total_order_value")).collect()[0][0] or 0,
            "orders_by_status": df.groupBy("order_status_standardized").count().collect(),
            "orders_by_size_category": df.groupBy("order_size_category").count().collect(),
            "complete_orders_percentage": df.filter(col("is_complete_order") == True).count() / total_records if total_records > 0 else 0
        }
        
        quality_results["business_metrics"] = business_metrics
        
        # Calculate overall quality score
        passed_rules = sum(1 for result in quality_results["rules_results"] if result["passed"])
        total_rules = len(quality_results["rules_results"])
        quality_results["overall_quality_score"] = passed_rules / total_rules if total_rules > 0 else 0
        
        log_info(f"Data quality validation completed. Overall score: {quality_results['overall_quality_score']:.2%}")
        return quality_results
        
    except Exception as e:
        log_error(f"Data quality validation failed: {str(e)}")
        raise

def write_silver_data(df: DataFrame):
    """Write cleaned data to silver layer"""
    log_info(f"Writing data to silver layer: {TARGET_PATH}")
    
    try:
        # Select final columns for silver layer
        silver_df = df.select(
            "order_key",
            "order_id",
            "customer_id",
            "order_amount",
            "tax_amount",
            "shipping_amount",
            "total_order_value",
            "order_status_standardized",
            "order_date",
            "shipped_date",
            "delivered_date",
            "days_to_ship",
            "days_to_deliver",
            "order_size_category",
            "order_year",
            "order_month",
            "order_quarter",
            "order_day_of_week",
            "order_day_of_year",
            "has_customer_id",
            "has_valid_amount",
            "is_complete_order",
            "etl_processed_at",
            "source_system",
            "record_version"
        )
        
        # Add partitioning columns
        silver_df = silver_df.withColumn("year", col("order_year"))
        silver_df = silver_df.withColumn("month", col("order_month"))
        
        # Convert back to DynamicFrame for Glue optimizations
        silver_dynamic_frame = DynamicFrame.fromDF(silver_df, glueContext, "silver_orders")
        
        # Write to S3 with partitioning
        glueContext.write_dynamic_frame.from_options(
            frame=silver_dynamic_frame,
            connection_type="s3",
            connection_options={
                "path": TARGET_PATH,
                "partitionKeys": ["year", "month"]
            },
            format="parquet",
            format_options={
                "compression": "snappy",
                "enableUpdateCatalog": True,
                "updateBehavior": "UPDATE_IN_DATABASE"
            },
            transformation_ctx="write_silver_orders"
        )
        
        log_info(f"Successfully wrote {silver_df.count()} records to silver layer")
        
    except Exception as e:
        log_error(f"Failed to write silver data: {str(e)}")
        raise

def write_quality_metrics(quality_results: Dict[str, Any]):
    """Write data quality metrics to monitoring location"""
    log_info("Writing data quality metrics")
    
    try:
        # Convert quality results to DataFrame
        quality_df = spark.createDataFrame([quality_results])
        
        # Write quality metrics
        quality_path = f"s3://{TARGET_PATH.split('/')[2]}/quality-reports/orders/{EXECUTION_DATE}"
        
        quality_df.coalesce(1).write.mode("overwrite").json(quality_path)
        
        log_info("Data quality metrics written successfully")
        
    except Exception as e:
        log_error(f"Failed to write quality metrics: {str(e)}")
        # Don't fail the job for quality metrics writing issues
        pass

def main():
    """Main ETL process"""
    log_info("Starting Bronze to Silver ETL job for orders")
    
    try:
        # Step 1: Read bronze data
        bronze_dynamic_frame = read_bronze_data()
        bronze_df = bronze_dynamic_frame.toDF()
        
        # Step 2: Clean and transform data
        cleaned_df = clean_order_data(bronze_df)
        
        # Step 3: Validate data quality
        quality_results = validate_data_quality(cleaned_df)
        
        # Step 4: Write to silver layer
        write_silver_data(cleaned_df)
        
        # Step 5: Write quality metrics
        write_quality_metrics(quality_results)
        
        log_info("Bronze to Silver ETL job completed successfully")
        
        # Job metrics
        job_metrics = {
            "job_name": args['JOB_NAME'],
            "source_records": bronze_df.count(),
            "target_records": cleaned_df.count(),
            "data_quality_score": quality_results["overall_quality_score"],
            "total_order_value": quality_results["business_metrics"]["total_order_value"],
            "average_order_value": quality_results["business_metrics"]["average_order_value"],
            "execution_time": datetime.now() - EXECUTION_TIMESTAMP,
            "status": "SUCCESS"
        }
        
        log_info(f"Job metrics: {json.dumps(job_metrics, default=str)}")
        
    except Exception as e:
        log_error(f"ETL job failed: {str(e)}")
        raise
    
    finally:
        job.commit()

if __name__ == "__main__":
    main()
"""
Bronze to Silver ETL Job for Product Data
This PySpark script transforms raw product data from the bronze layer
to cleaned and validated dimension data in the silver layer.
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
    """Read product data from bronze layer"""
    log_info(f"Reading data from {SOURCE_DATABASE}.{SOURCE_TABLE}")
    
    try:
        # Read from Glue Data Catalog
        dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name=SOURCE_TABLE,
            transformation_ctx="read_bronze_products"
        )
        
        log_info(f"Successfully read {dynamic_frame.count()} records from bronze layer")
        return dynamic_frame
        
    except Exception as e:
        log_error(f"Failed to read bronze data: {str(e)}")
        raise

def clean_product_data(df: DataFrame) -> DataFrame:
    """Clean and standardize product data"""
    log_info("Starting data cleaning process")
    
    try:
        cleaned_df = df
        
        # 1. Data type conversions and null handling
        cleaned_df = cleaned_df.withColumn(
            "product_id", 
            when(col("product_id").isNull(), lit(None)).otherwise(col("product_id").cast(StringType()))
        )
        
        # 2. Standardize product name and description
        cleaned_df = cleaned_df.withColumn(
            "product_name_standardized",
            when(col("product_name").isNotNull(), 
                 trim(regexp_replace(col("product_name"), "\\s+", " "))
            ).otherwise("Unknown Product")
        )
        
        cleaned_df = cleaned_df.withColumn(
            "product_description_cleaned",
            when(col("product_description").isNotNull(),
                 trim(regexp_replace(col("product_description"), "\\s+", " "))
            ).otherwise(lit(None))
        )
        
        # 3. Handle pricing information
        cleaned_df = cleaned_df.withColumn(
            "price",
            when(
                col("price").isNull() | (col("price") < 0),
                lit(0.0)
            ).otherwise(col("price").cast(DecimalType(10, 2)))
        )
        
        cleaned_df = cleaned_df.withColumn(
            "cost",
            when(
                col("cost").isNull() | (col("cost") < 0),
                lit(0.0)
            ).otherwise(col("cost").cast(DecimalType(10, 2)))
        )
        
        # 4. Calculate profit margin
        cleaned_df = cleaned_df.withColumn(
            "profit_margin",
            when(
                (col("price") > 0) & (col("cost") > 0),
                ((col("price") - col("cost")) / col("price")) * 100
            ).otherwise(lit(0.0))
        )
        
        # 5. Standardize category information
        cleaned_df = cleaned_df.withColumn(
            "category_standardized",
            when(col("category").isNotNull(), 
                 upper(trim(col("category")))
            ).otherwise("UNCATEGORIZED")
        )
        
        cleaned_df = cleaned_df.withColumn(
            "subcategory_standardized",
            when(col("subcategory").isNotNull(), 
                 upper(trim(col("subcategory")))
            ).otherwise(lit(None))
        )
        
        # 6. Handle brand information
        cleaned_df = cleaned_df.withColumn(
            "brand_standardized",
            when(col("brand").isNotNull(), 
                 trim(regexp_replace(col("brand"), "\\s+", " "))
            ).otherwise("Unknown Brand")
        )
        
        # 7. Product status and availability
        cleaned_df = cleaned_df.withColumn(
            "is_active",
            when(col("status").isNotNull() & 
                 upper(col("status")).isin(["ACTIVE", "AVAILABLE", "IN_STOCK"]), 
                 True
            ).otherwise(False)
        )
        
        cleaned_df = cleaned_df.withColumn(
            "inventory_status",
            when(col("inventory_quantity").isNull(), "UNKNOWN")
            .when(col("inventory_quantity") <= 0, "OUT_OF_STOCK")
            .when(col("inventory_quantity") <= 10, "LOW_STOCK")
            .when(col("inventory_quantity") <= 50, "MEDIUM_STOCK")
            .otherwise("HIGH_STOCK")
        )
        
        # 8. Product dimensions and weight
        cleaned_df = cleaned_df.withColumn(
            "weight_kg",
            when(col("weight").isNotNull() & (col("weight") > 0),
                 col("weight").cast(DecimalType(8, 3))
            ).otherwise(lit(None))
        )
        
        cleaned_df = cleaned_df.withColumn(
            "dimensions",
            when(
                col("length").isNotNull() & col("width").isNotNull() & col("height").isNotNull(),
                struct(
                    col("length").cast(DecimalType(8, 2)).alias("length_cm"),
                    col("width").cast(DecimalType(8, 2)).alias("width_cm"),
                    col("height").cast(DecimalType(8, 2)).alias("height_cm")
                )
            ).otherwise(lit(None))
        )
        
        # 9. Price categorization
        cleaned_df = cleaned_df.withColumn(
            "price_category",
            when(col("price") == 0, "FREE")
            .when(col("price") < 25, "BUDGET")
            .when(col("price") < 100, "STANDARD")
            .when(col("price") < 500, "PREMIUM")
            .otherwise("LUXURY")
        )
        
        # 10. Product age calculation
        cleaned_df = cleaned_df.withColumn(
            "days_since_created",
            when(col("created_at").isNotNull(),
                 datediff(current_date(), col("created_at").cast(DateType()))
            ).otherwise(lit(None))
        )
        
        cleaned_df = cleaned_df.withColumn(
            "product_age_category",
            when(col("days_since_created").isNull(), "UNKNOWN")
            .when(col("days_since_created") <= 30, "NEW")
            .when(col("days_since_created") <= 180, "RECENT")
            .when(col("days_since_created") <= 365, "ESTABLISHED")
            .otherwise("MATURE")
        )
        
        # 11. Data quality indicators
        cleaned_df = cleaned_df.withColumn(
            "has_complete_pricing",
            when((col("price") > 0) & (col("cost") > 0), True).otherwise(False)
        )
        
        cleaned_df = cleaned_df.withColumn(
            "has_complete_description",
            when(
                col("product_name_standardized") != "Unknown Product" & 
                col("product_description_cleaned").isNotNull(),
                True
            ).otherwise(False)
        )
        
        cleaned_df = cleaned_df.withColumn(
            "data_completeness_score",
            (
                when(col("product_id").isNotNull(), 1).otherwise(0) +
                when(col("product_name_standardized") != "Unknown Product", 1).otherwise(0) +
                when(col("has_complete_pricing"), 1).otherwise(0) +
                when(col("category_standardized") != "UNCATEGORIZED", 1).otherwise(0) +
                when(col("brand_standardized") != "Unknown Brand", 1).otherwise(0)
            ) / 5.0
        )
        
        # 12. SCD Type 2 columns
        cleaned_df = cleaned_df.withColumn("effective_date", current_date())
        cleaned_df = cleaned_df.withColumn("expiration_date", lit("9999-12-31").cast(DateType()))
        cleaned_df = cleaned_df.withColumn("is_current", lit(True))
        
        # 13. Generate surrogate key
        window_spec = Window.orderBy("product_id")
        cleaned_df = cleaned_df.withColumn(
            "product_key",
            row_number().over(window_spec)
        )
        
        # 14. Add audit columns
        cleaned_df = cleaned_df.withColumn("created_date", col("created_at").cast(DateType()))
        cleaned_df = cleaned_df.withColumn("last_updated_date", col("updated_at").cast(DateType()))
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
            "total_products": total_records,
            "active_products": df.filter(col("is_active") == True).count(),
            "average_price": df.agg(avg("price")).collect()[0][0] or 0,
            "average_profit_margin": df.agg(avg("profit_margin")).collect()[0][0] or 0,
            "products_by_category": df.groupBy("category_standardized").count().collect(),
            "products_by_price_category": df.groupBy("price_category").count().collect(),
            "products_by_inventory_status": df.groupBy("inventory_status").count().collect(),
            "complete_products_percentage": df.filter(col("data_completeness_score") >= 0.8).count() / total_records if total_records > 0 else 0
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
            "product_key",
            "product_id",
            "product_name_standardized",
            "product_description_cleaned",
            "price",
            "cost",
            "profit_margin",
            "category_standardized",
            "subcategory_standardized",
            "brand_standardized",
            "is_active",
            "inventory_status",
            "weight_kg",
            "dimensions",
            "price_category",
            "days_since_created",
            "product_age_category",
            "has_complete_pricing",
            "has_complete_description",
            "data_completeness_score",
            "effective_date",
            "expiration_date",
            "is_current",
            "created_date",
            "last_updated_date",
            "etl_processed_at",
            "source_system",
            "record_version"
        )
        
        # Add partitioning columns
        silver_df = silver_df.withColumn("year", year(col("etl_processed_at")))
        silver_df = silver_df.withColumn("month", month(col("etl_processed_at")))
        
        # Convert back to DynamicFrame for Glue optimizations
        silver_dynamic_frame = DynamicFrame.fromDF(silver_df, glueContext, "silver_products")
        
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
            transformation_ctx="write_silver_products"
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
        quality_path = f"s3://{TARGET_PATH.split('/')[2]}/quality-reports/products/{EXECUTION_DATE}"
        
        quality_df.coalesce(1).write.mode("overwrite").json(quality_path)
        
        log_info("Data quality metrics written successfully")
        
    except Exception as e:
        log_error(f"Failed to write quality metrics: {str(e)}")
        # Don't fail the job for quality metrics writing issues
        pass

def main():
    """Main ETL process"""
    log_info("Starting Bronze to Silver ETL job for products")
    
    try:
        # Step 1: Read bronze data
        bronze_dynamic_frame = read_bronze_data()
        bronze_df = bronze_dynamic_frame.toDF()
        
        # Step 2: Clean and transform data
        cleaned_df = clean_product_data(bronze_df)
        
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
            "active_products": quality_results["business_metrics"]["active_products"],
            "average_price": quality_results["business_metrics"]["average_price"],
            "average_profit_margin": quality_results["business_metrics"]["average_profit_margin"],
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
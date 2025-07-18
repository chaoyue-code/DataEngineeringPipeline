"""
Bronze to Silver ETL Job for Customer Data
This PySpark script transforms raw customer data from the bronze layer
to cleaned and validated data in the silver layer.
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
    """Read customer data from bronze layer"""
    log_info(f"Reading data from {SOURCE_DATABASE}.{SOURCE_TABLE}")
    
    try:
        # Read from Glue Data Catalog
        dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name=SOURCE_TABLE,
            transformation_ctx="read_bronze_customers"
        )
        
        log_info(f"Successfully read {dynamic_frame.count()} records from bronze layer")
        return dynamic_frame
        
    except Exception as e:
        log_error(f"Failed to read bronze data: {str(e)}")
        raise

def clean_customer_data(df: DataFrame) -> DataFrame:
    """Clean and standardize customer data"""
    log_info("Starting data cleaning process")
    
    try:
        # Convert to DataFrame for easier manipulation
        cleaned_df = df
        
        # 1. Handle null values and data type conversions
        cleaned_df = cleaned_df.withColumn(
            "customer_id", 
            when(col("customer_id").isNull(), lit(None)).otherwise(col("customer_id").cast(StringType()))
        )
        
        # 2. Standardize names
        cleaned_df = cleaned_df.withColumn(
            "full_name",
            when(
                col("first_name").isNotNull() & col("last_name").isNotNull(),
                concat(col("first_name"), lit(" "), col("last_name"))
            ).otherwise(
                coalesce(col("first_name"), col("last_name"), lit("Unknown"))
            )
        )
        
        # 3. Normalize email addresses
        cleaned_df = cleaned_df.withColumn(
            "email_normalized",
            when(
                col("email").isNotNull(),
                lower(trim(col("email")))
            ).otherwise(lit(None))
        )
        
        # 4. Normalize phone numbers (remove non-digits, format consistently)
        cleaned_df = cleaned_df.withColumn(
            "phone_normalized",
            when(
                col("phone").isNotNull(),
                regexp_replace(col("phone"), "[^0-9]", "")
            ).otherwise(lit(None))
        )
        
        # 5. Standardize address components
        cleaned_df = cleaned_df.withColumn(
            "address_standardized",
            struct(
                trim(upper(col("address"))).alias("street"),
                trim(upper(col("city"))).alias("city"),
                trim(upper(col("state"))).alias("state"),
                regexp_replace(col("zip_code"), "[^0-9-]", "").alias("zip_code"),
                lit("US").alias("country")  # Assuming US addresses
            )
        )
        
        # 6. Add data quality score based on completeness
        cleaned_df = cleaned_df.withColumn(
            "data_quality_score",
            (
                when(col("customer_id").isNotNull(), 1).otherwise(0) +
                when(col("full_name") != "Unknown", 1).otherwise(0) +
                when(col("email_normalized").isNotNull(), 1).otherwise(0) +
                when(col("phone_normalized").isNotNull(), 1).otherwise(0) +
                when(col("address_standardized.street").isNotNull(), 1).otherwise(0)
            ) / 5.0
        )
        
        # 7. Determine active status
        cleaned_df = cleaned_df.withColumn(
            "is_active",
            when(
                col("updated_at").isNotNull() & 
                (datediff(current_date(), col("updated_at").cast(DateType())) <= 365),
                True
            ).otherwise(False)
        )
        
        # 8. Add SCD Type 2 columns
        cleaned_df = cleaned_df.withColumn("effective_date", current_date())
        cleaned_df = cleaned_df.withColumn("expiration_date", lit("9999-12-31").cast(DateType()))
        cleaned_df = cleaned_df.withColumn("is_current", lit(True))
        
        # 9. Add audit columns
        cleaned_df = cleaned_df.withColumn("created_date", col("created_at").cast(DateType()))
        cleaned_df = cleaned_df.withColumn("last_updated_date", col("updated_at").cast(DateType()))
        cleaned_df = cleaned_df.withColumn("etl_processed_at", lit(EXECUTION_TIMESTAMP))
        
        # 10. Generate surrogate key
        window_spec = Window.orderBy("customer_id")
        cleaned_df = cleaned_df.withColumn(
            "customer_key",
            row_number().over(window_spec)
        )
        
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
        "overall_quality_score": 0.0
    }
    
    try:
        total_records = quality_results["total_records"]
        
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
            "customer_key",
            "customer_id",
            "full_name",
            "email_normalized",
            "phone_normalized",
            "address_standardized",
            "data_quality_score",
            "is_active",
            "created_date",
            "last_updated_date",
            "effective_date",
            "expiration_date",
            "is_current",
            "etl_processed_at"
        )
        
        # Add partitioning columns
        silver_df = silver_df.withColumn("year", year(col("etl_processed_at")))
        silver_df = silver_df.withColumn("month", month(col("etl_processed_at")))
        
        # Convert back to DynamicFrame for Glue optimizations
        silver_dynamic_frame = DynamicFrame.fromDF(silver_df, glueContext, "silver_customers")
        
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
            transformation_ctx="write_silver_customers"
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
        quality_path = f"s3://{TARGET_PATH.split('/')[2]}/quality-reports/customers/{EXECUTION_DATE}"
        
        quality_df.coalesce(1).write.mode("overwrite").json(quality_path)
        
        log_info("Data quality metrics written successfully")
        
    except Exception as e:
        log_error(f"Failed to write quality metrics: {str(e)}")
        # Don't fail the job for quality metrics writing issues
        pass

def main():
    """Main ETL process"""
    log_info("Starting Bronze to Silver ETL job for customers")
    
    try:
        # Step 1: Read bronze data
        bronze_dynamic_frame = read_bronze_data()
        bronze_df = bronze_dynamic_frame.toDF()
        
        # Step 2: Clean and transform data
        cleaned_df = clean_customer_data(bronze_df)
        
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
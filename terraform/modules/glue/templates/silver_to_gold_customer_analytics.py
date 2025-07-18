"""
Silver to Gold ETL Job for Customer Analytics
This PySpark script creates customer analytics and business intelligence
metrics from silver layer data for the gold layer.
"""

import sys
import json
from datetime import datetime, timedelta
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
    'customers_table',
    'orders_table',
    'products_table',
    'target_database',
    'target_table',
    'target_path',
    'aggregation_rules',
    'feature_engineering'
])

job.init(args['JOB_NAME'], args)

# Configuration
SOURCE_DATABASE = args['source_database']
CUSTOMERS_TABLE = args['customers_table']
ORDERS_TABLE = args['orders_table']
PRODUCTS_TABLE = args['products_table']
TARGET_DATABASE = args['target_database']
TARGET_TABLE = args['target_table']
TARGET_PATH = args['target_path']
AGGREGATION_RULES = json.loads(args['aggregation_rules'])
FEATURE_ENGINEERING = json.loads(args['feature_engineering'])

# Job execution timestamp
EXECUTION_TIMESTAMP = datetime.now()
EXECUTION_DATE = EXECUTION_TIMESTAMP.date()

def log_info(message: str):
    """Log information message with timestamp"""
    print(f"[{datetime.now().isoformat()}] INFO: {message}")

def log_error(message: str):
    """Log error message with timestamp"""
    print(f"[{datetime.now().isoformat()}] ERROR: {message}")

def read_silver_data() -> Dict[str, DataFrame]:
    """Read data from silver layer tables"""
    log_info("Reading data from silver layer")
    
    try:
        # Read customers dimension
        customers_df = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name=CUSTOMERS_TABLE,
            transformation_ctx="read_silver_customers"
        ).toDF()
        
        # Read orders fact table
        orders_df = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name=ORDERS_TABLE,
            transformation_ctx="read_silver_orders"
        ).toDF()
        
        # Read products dimension
        products_df = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name=PRODUCTS_TABLE,
            transformation_ctx="read_silver_products"
        ).toDF()
        
        log_info(f"Successfully read silver data - Customers: {customers_df.count()}, Orders: {orders_df.count()}, Products: {products_df.count()}")
        
        return {
            'customers': customers_df,
            'orders': orders_df,
            'products': products_df
        }
        
    except Exception as e:
        log_error(f"Failed to read silver data: {str(e)}")
        raise

def calculate_customer_metrics(customers_df: DataFrame, orders_df: DataFrame) -> DataFrame:
    """Calculate comprehensive customer analytics metrics"""
    log_info("Calculating customer analytics metrics")
    
    try:
        # Filter for complete orders only
        complete_orders = orders_df.filter(col("is_complete_order") == True)
        
        # Calculate basic customer order metrics
        customer_order_metrics = complete_orders.groupBy("customer_id").agg(
            sum("total_order_value").alias("lifetime_value"),
            count("order_id").alias("total_orders"),
            avg("total_order_value").alias("avg_order_value"),
            min("order_date").alias("first_order_date"),
            max("order_date").alias("last_order_date"),
            sum("order_amount").alias("total_order_amount"),
            sum("tax_amount").alias("total_tax_amount"),
            sum("shipping_amount").alias("total_shipping_amount"),
            countDistinct("order_date").alias("unique_order_days"),
            avg("days_to_ship").alias("avg_days_to_ship"),
            avg("days_to_deliver").alias("avg_days_to_deliver")
        )
        
        # Calculate time-based metrics
        current_date_lit = lit(EXECUTION_DATE)
        customer_time_metrics = customer_order_metrics.withColumn(
            "days_since_first_order",
            datediff(current_date_lit, col("first_order_date"))
        ).withColumn(
            "days_since_last_order",
            datediff(current_date_lit, col("last_order_date"))
        ).withColumn(
            "customer_lifespan_days",
            datediff(col("last_order_date"), col("first_order_date")) + 1
        )
        
        # Calculate frequency metrics
        customer_frequency_metrics = customer_time_metrics.withColumn(
            "order_frequency_days",
            when(col("total_orders") > 1, 
                 col("customer_lifespan_days") / (col("total_orders") - 1)
            ).otherwise(lit(None))
        ).withColumn(
            "orders_per_month",
            when(col("customer_lifespan_days") > 0,
                 col("total_orders") * 30.0 / col("customer_lifespan_days")
            ).otherwise(lit(0))
        )
        
        # Calculate order size categories distribution
        order_size_distribution = complete_orders.groupBy("customer_id", "order_size_category").count().groupBy("customer_id").pivot("order_size_category").sum("count").fillna(0)
        
        # Rename columns for order size distribution
        size_columns = ["SMALL", "MEDIUM", "LARGE", "EXTRA_LARGE"]
        for col_name in size_columns:
            if col_name in order_size_distribution.columns:
                order_size_distribution = order_size_distribution.withColumnRenamed(col_name, f"orders_{col_name.lower()}")
        
        # Join customer data with calculated metrics
        customer_analytics = customers_df.join(
            customer_frequency_metrics, 
            customers_df.customer_id == customer_frequency_metrics.customer_id, 
            "left"
        ).join(
            order_size_distribution,
            customers_df.customer_id == order_size_distribution.customer_id,
            "left"
        ).select(
            customers_df["*"],
            customer_frequency_metrics["lifetime_value"],
            customer_frequency_metrics["total_orders"],
            customer_frequency_metrics["avg_order_value"],
            customer_frequency_metrics["first_order_date"],
            customer_frequency_metrics["last_order_date"],
            customer_frequency_metrics["total_order_amount"],
            customer_frequency_metrics["total_tax_amount"],
            customer_frequency_metrics["total_shipping_amount"],
            customer_frequency_metrics["unique_order_days"],
            customer_frequency_metrics["avg_days_to_ship"],
            customer_frequency_metrics["avg_days_to_deliver"],
            customer_frequency_metrics["days_since_first_order"],
            customer_frequency_metrics["days_since_last_order"],
            customer_frequency_metrics["customer_lifespan_days"],
            customer_frequency_metrics["order_frequency_days"],
            customer_frequency_metrics["orders_per_month"],
            coalesce(order_size_distribution["orders_small"], lit(0)).alias("orders_small"),
            coalesce(order_size_distribution["orders_medium"], lit(0)).alias("orders_medium"),
            coalesce(order_size_distribution["orders_large"], lit(0)).alias("orders_large"),
            coalesce(order_size_distribution["orders_extra_large"], lit(0)).alias("orders_extra_large")
        )
        
        # Fill null values for customers with no orders
        customer_analytics = customer_analytics.fillna({
            "lifetime_value": 0.0,
            "total_orders": 0,
            "avg_order_value": 0.0,
            "total_order_amount": 0.0,
            "total_tax_amount": 0.0,
            "total_shipping_amount": 0.0,
            "unique_order_days": 0,
            "avg_days_to_ship": 0.0,
            "avg_days_to_deliver": 0.0,
            "days_since_first_order": 0,
            "days_since_last_order": 9999,
            "customer_lifespan_days": 0,
            "order_frequency_days": 0.0,
            "orders_per_month": 0.0,
            "orders_small": 0,
            "orders_medium": 0,
            "orders_large": 0,
            "orders_extra_large": 0
        })
        
        log_info(f"Customer metrics calculated for {customer_analytics.count()} customers")
        return customer_analytics
        
    except Exception as e:
        log_error(f"Failed to calculate customer metrics: {str(e)}")
        raise

def apply_feature_engineering(df: DataFrame) -> DataFrame:
    """Apply feature engineering for ML and analytics"""
    log_info("Applying feature engineering")
    
    try:
        enhanced_df = df
        
        # Apply configured feature engineering rules
        for feature in FEATURE_ENGINEERING:
            feature_name = feature["feature_name"]
            calculation = feature["calculation"]
            
            log_info(f"Creating feature: {feature_name}")
            
            if feature_name == "customer_segment":
                enhanced_df = enhanced_df.withColumn(
                    "customer_segment",
                    when(col("lifetime_value") > 1000, "HIGH_VALUE")
                    .when(col("lifetime_value") > 500, "MEDIUM_VALUE")
                    .otherwise("LOW_VALUE")
                )
            
            elif feature_name == "churn_risk_score":
                enhanced_df = enhanced_df.withColumn(
                    "churn_risk_score",
                    when(col("days_since_last_order") > 365, 0.9)
                    .when(col("days_since_last_order") > 180, 0.6)
                    .when(col("days_since_last_order") > 90, 0.3)
                    .otherwise(0.1)
                )
        
        # Additional business logic features
        enhanced_df = enhanced_df.withColumn(
            "preferred_order_size",
            when(col("orders_extra_large") > col("orders_large"), "EXTRA_LARGE")
            .when(col("orders_large") > col("orders_medium"), "LARGE")
            .when(col("orders_medium") > col("orders_small"), "MEDIUM")
            .otherwise("SMALL")
        )
        
        enhanced_df = enhanced_df.withColumn(
            "customer_loyalty_score",
            when(col("total_orders") >= 10, 1.0)
            .when(col("total_orders") >= 5, 0.8)
            .when(col("total_orders") >= 2, 0.6)
            .when(col("total_orders") >= 1, 0.4)
            .otherwise(0.0)
        )
        
        enhanced_df = enhanced_df.withColumn(
            "geographic_region",
            when(col("address_standardized.state").isin(["CA", "OR", "WA"]), "WEST")
            .when(col("address_standardized.state").isin(["NY", "NJ", "CT", "MA"]), "NORTHEAST")
            .when(col("address_standardized.state").isin(["TX", "FL", "GA", "NC"]), "SOUTH")
            .otherwise("OTHER")
        )
        
        # RFM Analysis (Recency, Frequency, Monetary)
        enhanced_df = enhanced_df.withColumn(
            "recency_score",
            when(col("days_since_last_order") <= 30, 5)
            .when(col("days_since_last_order") <= 90, 4)
            .when(col("days_since_last_order") <= 180, 3)
            .when(col("days_since_last_order") <= 365, 2)
            .otherwise(1)
        )
        
        enhanced_df = enhanced_df.withColumn(
            "frequency_score",
            when(col("total_orders") >= 20, 5)
            .when(col("total_orders") >= 10, 4)
            .when(col("total_orders") >= 5, 3)
            .when(col("total_orders") >= 2, 2)
            .otherwise(1)
        )
        
        enhanced_df = enhanced_df.withColumn(
            "monetary_score",
            when(col("lifetime_value") >= 2000, 5)
            .when(col("lifetime_value") >= 1000, 4)
            .when(col("lifetime_value") >= 500, 3)
            .when(col("lifetime_value") >= 100, 2)
            .otherwise(1)
        )
        
        enhanced_df = enhanced_df.withColumn(
            "rfm_score",
            concat(col("recency_score"), col("frequency_score"), col("monetary_score"))
        )
        
        # Customer lifecycle stage
        enhanced_df = enhanced_df.withColumn(
            "lifecycle_stage",
            when((col("total_orders") == 0), "PROSPECT")
            .when((col("total_orders") == 1) & (col("days_since_last_order") <= 90), "NEW")
            .when((col("total_orders") >= 2) & (col("days_since_last_order") <= 90), "ACTIVE")
            .when((col("total_orders") >= 2) & (col("days_since_last_order") <= 365), "DORMANT")
            .otherwise("CHURNED")
        )
        
        log_info("Feature engineering completed")
        return enhanced_df
        
    except Exception as e:
        log_error(f"Feature engineering failed: {str(e)}")
        raise

def create_final_analytics_table(df: DataFrame) -> DataFrame:
    """Create the final customer analytics table for gold layer"""
    log_info("Creating final customer analytics table")
    
    try:
        # Select and organize final columns
        final_df = df.select(
            col("customer_key"),
            col("customer_id"),
            col("full_name"),
            col("email_normalized"),
            col("customer_segment"),
            col("lifetime_value"),
            col("total_orders"),
            col("avg_order_value"),
            col("last_order_date"),
            col("days_since_last_order"),
            col("churn_risk_score"),
            col("preferred_order_size"),
            col("geographic_region"),
            col("customer_loyalty_score"),
            col("recency_score"),
            col("frequency_score"),
            col("monetary_score"),
            col("rfm_score"),
            col("lifecycle_stage"),
            col("first_order_date"),
            col("customer_lifespan_days"),
            col("order_frequency_days"),
            col("orders_per_month"),
            col("total_order_amount"),
            col("total_tax_amount"),
            col("total_shipping_amount"),
            col("unique_order_days"),
            col("avg_days_to_ship"),
            col("avg_days_to_deliver"),
            col("orders_small"),
            col("orders_medium"),
            col("orders_large"),
            col("orders_extra_large"),
            col("data_quality_score"),
            col("is_active"),
            lit(EXECUTION_DATE).alias("analysis_date"),
            lit(EXECUTION_TIMESTAMP).alias("etl_processed_at")
        )
        
        log_info(f"Final analytics table created with {final_df.count()} customer records")
        return final_df
        
    except Exception as e:
        log_error(f"Failed to create final analytics table: {str(e)}")
        raise

def write_gold_data(df: DataFrame):
    """Write customer analytics to gold layer"""
    log_info(f"Writing customer analytics to gold layer: {TARGET_PATH}")
    
    try:
        # Add partitioning columns
        partitioned_df = df.withColumn("year", year(col("analysis_date")))
        partitioned_df = partitioned_df.withColumn("month", month(col("analysis_date")))
        
        # Convert to DynamicFrame for Glue optimizations
        gold_dynamic_frame = DynamicFrame.fromDF(partitioned_df, glueContext, "gold_customer_analytics")
        
        # Write to S3 with partitioning and optimization
        glueContext.write_dynamic_frame.from_options(
            frame=gold_dynamic_frame,
            connection_type="s3",
            connection_options={
                "path": TARGET_PATH,
                "partitionKeys": ["year", "month"]
            },
            format="parquet",
            format_options={
                "compression": "snappy",
                "enableUpdateCatalog": True,
                "updateBehavior": "UPDATE_IN_DATABASE",
                "writeParallel": True
            },
            transformation_ctx="write_gold_customer_analytics"
        )
        
        log_info(f"Successfully wrote {df.count()} customer analytics records to gold layer")
        
    except Exception as e:
        log_error(f"Failed to write gold data: {str(e)}")
        raise

def generate_analytics_summary(df: DataFrame) -> Dict[str, Any]:
    """Generate summary statistics for the analytics"""
    log_info("Generating analytics summary")
    
    try:
        summary = {
            "total_customers": df.count(),
            "execution_date": EXECUTION_DATE.isoformat(),
            "customer_segments": df.groupBy("customer_segment").count().collect(),
            "lifecycle_stages": df.groupBy("lifecycle_stage").count().collect(),
            "geographic_regions": df.groupBy("geographic_region").count().collect(),
            "high_value_customers": df.filter(col("customer_segment") == "HIGH_VALUE").count(),
            "at_risk_customers": df.filter(col("churn_risk_score") >= 0.6).count(),
            "active_customers": df.filter(col("lifecycle_stage") == "ACTIVE").count(),
            "average_lifetime_value": df.agg(avg("lifetime_value")).collect()[0][0] or 0,
            "total_lifetime_value": df.agg(sum("lifetime_value")).collect()[0][0] or 0,
            "average_orders_per_customer": df.agg(avg("total_orders")).collect()[0][0] or 0
        }
        
        log_info("Analytics summary generated successfully")
        return summary
        
    except Exception as e:
        log_error(f"Failed to generate analytics summary: {str(e)}")
        return {}

def main():
    """Main ETL process"""
    log_info("Starting Silver to Gold ETL job for customer analytics")
    
    try:
        # Step 1: Read silver layer data
        silver_data = read_silver_data()
        
        # Step 2: Calculate customer metrics
        customer_metrics = calculate_customer_metrics(
            silver_data['customers'], 
            silver_data['orders']
        )
        
        # Step 3: Apply feature engineering
        enhanced_analytics = apply_feature_engineering(customer_metrics)
        
        # Step 4: Create final analytics table
        final_analytics = create_final_analytics_table(enhanced_analytics)
        
        # Step 5: Write to gold layer
        write_gold_data(final_analytics)
        
        # Step 6: Generate summary
        summary = generate_analytics_summary(final_analytics)
        
        log_info("Silver to Gold ETL job completed successfully")
        
        # Job metrics
        job_metrics = {
            "job_name": args['JOB_NAME'],
            "total_customers": summary.get("total_customers", 0),
            "high_value_customers": summary.get("high_value_customers", 0),
            "at_risk_customers": summary.get("at_risk_customers", 0),
            "active_customers": summary.get("active_customers", 0),
            "average_lifetime_value": summary.get("average_lifetime_value", 0),
            "total_lifetime_value": summary.get("total_lifetime_value", 0),
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
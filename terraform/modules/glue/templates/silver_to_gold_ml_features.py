"""
Silver to Gold ETL Job for ML Features
This PySpark script creates machine learning features from silver layer data
optimized for SageMaker and other ML workloads.
"""

import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import math

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
from pyspark.ml.feature import VectorAssembler, StandardScaler, MinMaxScaler
from pyspark.ml.stat import Correlation

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
    'feature_engineering',
    'ml_config'
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
FEATURE_ENGINEERING = json.loads(args['feature_engineering'])
ML_CONFIG = json.loads(args['ml_config'])

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

def create_customer_behavioral_features(customers_df: DataFrame, orders_df: DataFrame) -> DataFrame:
    """Create behavioral features for customer analysis"""
    log_info("Creating customer behavioral features")
    
    try:
        # Filter for complete orders
        complete_orders = orders_df.filter(
            (col("is_complete_order") == True) & 
            (col("order_status_standardized") != "CANCELLED")
        )
        
        # Calculate comprehensive customer metrics
        customer_metrics = complete_orders.groupBy("customer_id").agg(
            # Basic metrics
            sum("total_order_value").alias("lifetime_value"),
            count("order_id").alias("total_orders"),
            avg("total_order_value").alias("avg_order_value"),
            stddev("total_order_value").alias("order_value_std"),
            min("order_date").alias("first_order_date"),
            max("order_date").alias("last_order_date"),
            
            # Advanced metrics
            countDistinct("order_date").alias("unique_order_days"),
            sum("order_amount").alias("total_order_amount"),
            sum("tax_amount").alias("total_tax_amount"),
            sum("shipping_amount").alias("total_shipping_amount"),
            avg("days_to_ship").alias("avg_days_to_ship"),
            avg("days_to_deliver").alias("avg_days_to_deliver"),
            
            # Order size distribution
            sum(when(col("order_size_category") == "SMALL", 1).otherwise(0)).alias("small_orders"),
            sum(when(col("order_size_category") == "MEDIUM", 1).otherwise(0)).alias("medium_orders"),
            sum(when(col("order_size_category") == "LARGE", 1).otherwise(0)).alias("large_orders"),
            sum(when(col("order_size_category") == "EXTRA_LARGE", 1).otherwise(0)).alias("extra_large_orders"),
            
            # Time-based patterns
            sum(when(col("order_day_of_week").isin([1, 7]), 1).otherwise(0)).alias("weekend_orders"),
            sum(when(col("order_day_of_week").isin([2, 3, 4, 5, 6]), 1).otherwise(0)).alias("weekday_orders"),
            
            # Seasonal patterns
            sum(when(col("order_quarter") == 1, 1).otherwise(0)).alias("q1_orders"),
            sum(when(col("order_quarter") == 2, 1).otherwise(0)).alias("q2_orders"),
            sum(when(col("order_quarter") == 3, 1).otherwise(0)).alias("q3_orders"),
            sum(when(col("order_quarter") == 4, 1).otherwise(0)).alias("q4_orders")
        )
        
        # Calculate time-based features
        current_date_lit = lit(EXECUTION_DATE)
        customer_time_features = customer_metrics.withColumn(
            "days_since_first_order",
            datediff(current_date_lit, col("first_order_date"))
        ).withColumn(
            "days_since_last_order",
            datediff(current_date_lit, col("last_order_date"))
        ).withColumn(
            "customer_lifespan_days",
            datediff(col("last_order_date"), col("first_order_date")) + 1
        )
        
        # Calculate advanced behavioral features
        behavioral_features = customer_time_features.withColumn(
            "order_frequency",
            when(col("customer_lifespan_days") > 0,
                 col("total_orders") / (col("customer_lifespan_days") / 30.0)
            ).otherwise(0)
        ).withColumn(
            "purchase_consistency",
            when(col("order_value_std").isNotNull() & (col("avg_order_value") > 0),
                 1.0 / (1.0 + col("order_value_std") / col("avg_order_value"))
            ).otherwise(0)
        ).withColumn(
            "weekend_preference",
            when(col("total_orders") > 0,
                 col("weekend_orders") / col("total_orders")
            ).otherwise(0)
        ).withColumn(
            "seasonal_preference",
            greatest(
                col("q1_orders"), col("q2_orders"), 
                col("q3_orders"), col("q4_orders")
            ) / col("total_orders")
        )
        
        # RFM Features (Recency, Frequency, Monetary)
        rfm_features = behavioral_features.withColumn(
            "recency_score",
            when(col("days_since_last_order") <= 30, 5)
            .when(col("days_since_last_order") <= 90, 4)
            .when(col("days_since_last_order") <= 180, 3)
            .when(col("days_since_last_order") <= 365, 2)
            .otherwise(1)
        ).withColumn(
            "frequency_score",
            when(col("total_orders") >= 20, 5)
            .when(col("total_orders") >= 10, 4)
            .when(col("total_orders") >= 5, 3)
            .when(col("total_orders") >= 2, 2)
            .otherwise(1)
        ).withColumn(
            "monetary_score",
            when(col("lifetime_value") >= 2000, 5)
            .when(col("lifetime_value") >= 1000, 4)
            .when(col("lifetime_value") >= 500, 3)
            .when(col("lifetime_value") >= 100, 2)
            .otherwise(1)
        )
        
        # Apply configured feature engineering
        for feature in FEATURE_ENGINEERING:
            feature_name = feature["feature_name"]
            
            if feature_name == "recency_score":
                rfm_features = rfm_features.withColumn(
                    "recency_score_normalized",
                    1.0 / (1.0 + col("days_since_last_order") / 30.0)
                )
            elif feature_name == "frequency_score":
                rfm_features = rfm_features.withColumn(
                    "frequency_score_log",
                    log(1.0 + col("total_orders"))
                )
            elif feature_name == "monetary_score":
                rfm_features = rfm_features.withColumn(
                    "monetary_score_log",
                    log(1.0 + col("lifetime_value"))
                )
        
        # Join with customer dimension data
        customer_features = customers_df.join(
            rfm_features,
            customers_df.customer_id == rfm_features.customer_id,
            "left"
        ).select(
            customers_df["*"],
            rfm_features["lifetime_value"],
            rfm_features["total_orders"],
            rfm_features["avg_order_value"],
            rfm_features["order_value_std"],
            rfm_features["days_since_first_order"],
            rfm_features["days_since_last_order"],
            rfm_features["customer_lifespan_days"],
            rfm_features["order_frequency"],
            rfm_features["purchase_consistency"],
            rfm_features["weekend_preference"],
            rfm_features["seasonal_preference"],
            rfm_features["recency_score"],
            rfm_features["frequency_score"],
            rfm_features["monetary_score"],
            coalesce(rfm_features["recency_score_normalized"], lit(0)).alias("recency_score_normalized"),
            coalesce(rfm_features["frequency_score_log"], lit(0)).alias("frequency_score_log"),
            coalesce(rfm_features["monetary_score_log"], lit(0)).alias("monetary_score_log"),
            rfm_features["small_orders"],
            rfm_features["medium_orders"],
            rfm_features["large_orders"],
            rfm_features["extra_large_orders"],
            rfm_features["weekend_orders"],
            rfm_features["weekday_orders"],
            rfm_features["q1_orders"],
            rfm_features["q2_orders"],
            rfm_features["q3_orders"],
            rfm_features["q4_orders"]
        )
        
        # Fill null values for customers with no orders
        customer_features = customer_features.fillna({
            "lifetime_value": 0.0,
            "total_orders": 0,
            "avg_order_value": 0.0,
            "order_value_std": 0.0,
            "days_since_first_order": 0,
            "days_since_last_order": 9999,
            "customer_lifespan_days": 0,
            "order_frequency": 0.0,
            "purchase_consistency": 0.0,
            "weekend_preference": 0.0,
            "seasonal_preference": 0.0,
            "recency_score": 1,
            "frequency_score": 1,
            "monetary_score": 1,
            "recency_score_normalized": 0.0,
            "frequency_score_log": 0.0,
            "monetary_score_log": 0.0,
            "small_orders": 0,
            "medium_orders": 0,
            "large_orders": 0,
            "extra_large_orders": 0,
            "weekend_orders": 0,
            "weekday_orders": 0,
            "q1_orders": 0,
            "q2_orders": 0,
            "q3_orders": 0,
            "q4_orders": 0
        })
        
        log_info(f"Customer behavioral features created for {customer_features.count()} customers")
        return customer_features
        
    except Exception as e:
        log_error(f"Failed to create customer behavioral features: {str(e)}")
        raise

def create_ml_target_variables(df: DataFrame) -> DataFrame:
    """Create target variables for ML models"""
    log_info("Creating ML target variables")
    
    try:
        # Churn prediction target
        ml_targets = df.withColumn(
            "churn_risk",
            when(col("days_since_last_order") > 365, 1).otherwise(0)
        )
        
        # Customer value segmentation target
        ml_targets = ml_targets.withColumn(
            "value_segment",
            when(col("lifetime_value") > 1000, 2)  # High value
            .when(col("lifetime_value") > 500, 1)   # Medium value
            .otherwise(0)                           # Low value
        )
        
        # Purchase frequency target
        ml_targets = ml_targets.withColumn(
            "high_frequency_customer",
            when(col("order_frequency") > 2.0, 1).otherwise(0)  # More than 2 orders per month
        )
        
        # Customer lifetime value prediction (continuous target)
        ml_targets = ml_targets.withColumn(
            "predicted_clv_category",
            when(col("lifetime_value") > 2000, 4)
            .when(col("lifetime_value") > 1000, 3)
            .when(col("lifetime_value") > 500, 2)
            .when(col("lifetime_value") > 100, 1)
            .otherwise(0)
        )
        
        log_info("ML target variables created")
        return ml_targets
        
    except Exception as e:
        log_error(f"Failed to create ML target variables: {str(e)}")
        raise

def create_feature_vectors(df: DataFrame) -> DataFrame:
    """Create feature vectors for ML models"""
    log_info("Creating feature vectors for ML")
    
    try:
        # Select numerical features for ML
        numerical_features = [
            "lifetime_value", "total_orders", "avg_order_value",
            "days_since_first_order", "days_since_last_order",
            "customer_lifespan_days", "order_frequency",
            "purchase_consistency", "weekend_preference", "seasonal_preference",
            "recency_score_normalized", "frequency_score_log", "monetary_score_log",
            "small_orders", "medium_orders", "large_orders", "extra_large_orders",
            "weekend_orders", "weekday_orders",
            "q1_orders", "q2_orders", "q3_orders", "q4_orders",
            "data_quality_score"
        ]
        
        # Handle categorical features
        categorical_features = df.withColumn(
            "is_active_numeric",
            when(col("is_active") == True, 1).otherwise(0)
        )
        
        # Add geographic features
        geographic_features = categorical_features.withColumn(
            "state_encoded",
            when(col("address_standardized.state").isNotNull(), 
                 hash(col("address_standardized.state")) % 100
            ).otherwise(0)
        )
        
        # Create feature importance scores
        feature_importance = geographic_features.withColumn(
            "feature_completeness",
            (
                when(col("lifetime_value") > 0, 1).otherwise(0) +
                when(col("total_orders") > 0, 1).otherwise(0) +
                when(col("email_normalized").isNotNull(), 1).otherwise(0) +
                when(col("phone_normalized").isNotNull(), 1).otherwise(0) +
                when(col("address_standardized.state").isNotNull(), 1).otherwise(0)
            ) / 5.0
        )
        
        # Add time-based features for seasonality
        time_features = feature_importance.withColumn(
            "days_since_analysis",
            datediff(lit(EXECUTION_DATE), col("effective_date"))
        ).withColumn(
            "account_age_months",
            col("days_since_first_order") / 30.0
        )
        
        log_info("Feature vectors created")
        return time_features
        
    except Exception as e:
        log_error(f"Failed to create feature vectors: {str(e)}")
        raise

def prepare_ml_dataset(df: DataFrame) -> DataFrame:
    """Prepare the final ML dataset with proper formatting"""
    log_info("Preparing final ML dataset")
    
    try:
        # Select final features for ML
        ml_dataset = df.select(
            # Identifiers
            col("customer_key"),
            col("customer_id"),
            
            # Demographic features
            col("full_name"),
            col("email_normalized"),
            col("data_quality_score"),
            col("is_active"),
            col("state_encoded"),
            
            # Behavioral features
            col("lifetime_value"),
            col("total_orders"),
            col("avg_order_value"),
            col("order_frequency"),
            col("purchase_consistency"),
            col("weekend_preference"),
            col("seasonal_preference"),
            
            # RFM features
            col("recency_score"),
            col("frequency_score"),
            col("monetary_score"),
            col("recency_score_normalized"),
            col("frequency_score_log"),
            col("monetary_score_log"),
            
            # Time-based features
            col("days_since_first_order"),
            col("days_since_last_order"),
            col("customer_lifespan_days"),
            col("account_age_months"),
            
            # Order pattern features
            col("small_orders"),
            col("medium_orders"),
            col("large_orders"),
            col("extra_large_orders"),
            col("weekend_orders"),
            col("weekday_orders"),
            col("q1_orders"),
            col("q2_orders"),
            col("q3_orders"),
            col("q4_orders"),
            
            # Quality and completeness
            col("feature_completeness"),
            
            # Target variables
            col("churn_risk"),
            col("value_segment"),
            col("high_frequency_customer"),
            col("predicted_clv_category"),
            
            # Metadata
            lit(EXECUTION_DATE).alias("feature_date"),
            lit(EXECUTION_TIMESTAMP).alias("etl_processed_at")
        )
        
        # Add feature version for tracking
        ml_dataset = ml_dataset.withColumn("feature_version", lit("1.0"))
        
        # Add data split indicators for ML training
        ml_dataset = ml_dataset.withColumn(
            "data_split",
            when(rand() < ML_CONFIG["data_split_ratio"]["train"], "train")
            .when(rand() < (ML_CONFIG["data_split_ratio"]["train"] + ML_CONFIG["data_split_ratio"]["validation"]), "validation")
            .otherwise("test")
        )
        
        log_info(f"ML dataset prepared with {ml_dataset.count()} records")
        return ml_dataset
        
    except Exception as e:
        log_error(f"Failed to prepare ML dataset: {str(e)}")
        raise

def write_gold_data(df: DataFrame):
    """Write ML features to gold layer"""
    log_info(f"Writing ML features to gold layer: {TARGET_PATH}")
    
    try:
        # Add partitioning columns
        partitioned_df = df.withColumn("year", year(col("feature_date")))
        partitioned_df = partitioned_df.withColumn("month", month(col("feature_date")))
        
        # Convert to DynamicFrame for Glue optimizations
        gold_dynamic_frame = DynamicFrame.fromDF(partitioned_df, glueContext, "gold_ml_features")
        
        # Write to S3 with partitioning and optimization
        glueContext.write_dynamic_frame.from_options(
            frame=gold_dynamic_frame,
            connection_type="s3",
            connection_options={
                "path": TARGET_PATH,
                "partitionKeys": ["year", "month", "data_split"]
            },
            format="parquet",
            format_options={
                "compression": "snappy",
                "enableUpdateCatalog": True,
                "updateBehavior": "UPDATE_IN_DATABASE",
                "writeParallel": True
            },
            transformation_ctx="write_gold_ml_features"
        )
        
        log_info(f"Successfully wrote {df.count()} ML feature records to gold layer")
        
    except Exception as e:
        log_error(f"Failed to write gold data: {str(e)}")
        raise

def generate_feature_statistics(df: DataFrame) -> Dict[str, Any]:
    """Generate statistics about the ML features"""
    log_info("Generating feature statistics")
    
    try:
        stats = {
            "total_records": df.count(),
            "feature_date": EXECUTION_DATE.isoformat(),
            "data_splits": {},
            "target_distributions": {},
            "feature_quality": {}
        }
        
        # Data split distribution
        split_counts = df.groupBy("data_split").count().collect()
        for row in split_counts:
            stats["data_splits"][row["data_split"]] = row["count"]
        
        # Target variable distributions
        churn_dist = df.groupBy("churn_risk").count().collect()
        stats["target_distributions"]["churn_risk"] = {row["churn_risk"]: row["count"] for row in churn_dist}
        
        value_dist = df.groupBy("value_segment").count().collect()
        stats["target_distributions"]["value_segment"] = {row["value_segment"]: row["count"] for row in value_dist}
        
        # Feature quality metrics
        stats["feature_quality"] = {
            "avg_feature_completeness": df.agg(avg("feature_completeness")).collect()[0][0] or 0,
            "avg_data_quality_score": df.agg(avg("data_quality_score")).collect()[0][0] or 0,
            "customers_with_orders": df.filter(col("total_orders") > 0).count(),
            "high_value_customers": df.filter(col("value_segment") == 2).count(),
            "at_risk_customers": df.filter(col("churn_risk") == 1).count()
        }
        
        log_info("Feature statistics generated successfully")
        return stats
        
    except Exception as e:
        log_error(f"Failed to generate feature statistics: {str(e)}")
        return {"error": str(e)}

def main():
    """Main ETL process"""
    log_info("Starting Silver to Gold ETL job for ML features")
    
    try:
        # Step 1: Read silver layer data
        silver_data = read_silver_data()
        
        # Step 2: Create customer behavioral features
        behavioral_features = create_customer_behavioral_features(
            silver_data['customers'], 
            silver_data['orders']
        )
        
        # Step 3: Create ML target variables
        ml_targets = create_ml_target_variables(behavioral_features)
        
        # Step 4: Create feature vectors
        feature_vectors = create_feature_vectors(ml_targets)
        
        # Step 5: Prepare final ML dataset
        ml_dataset = prepare_ml_dataset(feature_vectors)
        
        # Step 6: Write to gold layer
        write_gold_data(ml_dataset)
        
        # Step 7: Generate statistics
        stats = generate_feature_statistics(ml_dataset)
        
        log_info("Silver to Gold ETL job completed successfully")
        
        # Job metrics
        job_metrics = {
            "job_name": args['JOB_NAME'],
            "total_features": stats.get("total_records", 0),
            "train_records": stats.get("data_splits", {}).get("train", 0),
            "validation_records": stats.get("data_splits", {}).get("validation", 0),
            "test_records": stats.get("data_splits", {}).get("test", 0),
            "high_value_customers": stats.get("feature_quality", {}).get("high_value_customers", 0),
            "at_risk_customers": stats.get("feature_quality", {}).get("at_risk_customers", 0),
            "avg_feature_completeness": stats.get("feature_quality", {}).get("avg_feature_completeness", 0),
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
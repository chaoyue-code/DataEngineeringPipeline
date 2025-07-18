"""
Silver to Gold ETL Job for Sales Summary
This PySpark script creates comprehensive sales analytics and summaries
from silver layer data for business intelligence and reporting.
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
    'orders_table',
    'products_table',
    'customers_table',
    'target_database',
    'target_table',
    'target_path',
    'aggregation_rules'
])

job.init(args['JOB_NAME'], args)

# Configuration
SOURCE_DATABASE = args['source_database']
ORDERS_TABLE = args['orders_table']
PRODUCTS_TABLE = args['products_table']
CUSTOMERS_TABLE = args['customers_table']
TARGET_DATABASE = args['target_database']
TARGET_TABLE = args['target_table']
TARGET_PATH = args['target_path']
AGGREGATION_RULES = json.loads(args['aggregation_rules'])

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
        
        # Read customers dimension
        customers_df = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name=CUSTOMERS_TABLE,
            transformation_ctx="read_silver_customers"
        ).toDF()
        
        log_info(f"Successfully read silver data - Orders: {orders_df.count()}, Products: {products_df.count()}, Customers: {customers_df.count()}")
        
        return {
            'orders': orders_df,
            'products': products_df,
            'customers': customers_df
        }
        
    except Exception as e:
        log_error(f"Failed to read silver data: {str(e)}")
        raise

def create_daily_sales_summary(orders_df: DataFrame) -> DataFrame:
    """Create daily sales summary aggregations"""
    log_info("Creating daily sales summary")
    
    try:
        # Filter for complete orders only
        complete_orders = orders_df.filter(
            (col("is_complete_order") == True) & 
            (col("order_status_standardized") != "CANCELLED")
        )
        
        # Daily aggregations
        daily_summary = complete_orders.groupBy("order_date").agg(
            sum("total_order_value").alias("daily_revenue"),
            sum("order_amount").alias("daily_order_amount"),
            sum("tax_amount").alias("daily_tax_amount"),
            sum("shipping_amount").alias("daily_shipping_amount"),
            count("order_id").alias("daily_orders"),
            countDistinct("customer_id").alias("unique_customers"),
            avg("total_order_value").alias("avg_order_value"),
            min("total_order_value").alias("min_order_value"),
            max("total_order_value").alias("max_order_value"),
            stddev("total_order_value").alias("stddev_order_value")
        )
        
        # Add time dimensions
        daily_summary = daily_summary.withColumn("year", year(col("order_date")))
        daily_summary = daily_summary.withColumn("month", month(col("order_date")))
        daily_summary = daily_summary.withColumn("quarter", quarter(col("order_date")))
        daily_summary = daily_summary.withColumn("day_of_week", dayofweek(col("order_date")))
        daily_summary = daily_summary.withColumn("day_of_year", dayofyear(col("order_date")))
        daily_summary = daily_summary.withColumn("week_of_year", weekofyear(col("order_date")))
        
        # Add day name and month name
        daily_summary = daily_summary.withColumn(
            "day_name",
            when(col("day_of_week") == 1, "Sunday")
            .when(col("day_of_week") == 2, "Monday")
            .when(col("day_of_week") == 3, "Tuesday")
            .when(col("day_of_week") == 4, "Wednesday")
            .when(col("day_of_week") == 5, "Thursday")
            .when(col("day_of_week") == 6, "Friday")
            .otherwise("Saturday")
        )
        
        daily_summary = daily_summary.withColumn(
            "month_name",
            when(col("month") == 1, "January")
            .when(col("month") == 2, "February")
            .when(col("month") == 3, "March")
            .when(col("month") == 4, "April")
            .when(col("month") == 5, "May")
            .when(col("month") == 6, "June")
            .when(col("month") == 7, "July")
            .when(col("month") == 8, "August")
            .when(col("month") == 9, "September")
            .when(col("month") == 10, "October")
            .when(col("month") == 11, "November")
            .otherwise("December")
        )
        
        # Add business day indicator
        daily_summary = daily_summary.withColumn(
            "is_business_day",
            when(col("day_of_week").isin([1, 7]), False).otherwise(True)  # Sunday=1, Saturday=7
        )
        
        log_info(f"Daily sales summary created with {daily_summary.count()} records")
        return daily_summary
        
    except Exception as e:
        log_error(f"Failed to create daily sales summary: {str(e)}")
        raise

def create_monthly_sales_summary(orders_df: DataFrame) -> DataFrame:
    """Create monthly sales summary aggregations"""
    log_info("Creating monthly sales summary")
    
    try:
        # Filter for complete orders only
        complete_orders = orders_df.filter(
            (col("is_complete_order") == True) & 
            (col("order_status_standardized") != "CANCELLED")
        )
        
        # Monthly aggregations
        monthly_summary = complete_orders.groupBy("order_year", "order_month").agg(
            sum("total_order_value").alias("monthly_revenue"),
            sum("order_amount").alias("monthly_order_amount"),
            sum("tax_amount").alias("monthly_tax_amount"),
            sum("shipping_amount").alias("monthly_shipping_amount"),
            count("order_id").alias("monthly_orders"),
            countDistinct("customer_id").alias("unique_customers"),
            countDistinct("order_date").alias("active_days"),
            avg("total_order_value").alias("avg_order_value"),
            min("total_order_value").alias("min_order_value"),
            max("total_order_value").alias("max_order_value")
        )
        
        # Add calculated metrics
        monthly_summary = monthly_summary.withColumn(
            "avg_daily_revenue",
            col("monthly_revenue") / col("active_days")
        )
        
        monthly_summary = monthly_summary.withColumn(
            "avg_daily_orders",
            col("monthly_orders") / col("active_days")
        )
        
        # Add month-year string for easier reporting
        monthly_summary = monthly_summary.withColumn(
            "month_year",
            concat(
                lpad(col("order_month"), 2, "0"),
                lit("-"),
                col("order_year")
            )
        )
        
        # Add quarter information
        monthly_summary = monthly_summary.withColumn(
            "quarter",
            when(col("order_month").isin([1, 2, 3]), 1)
            .when(col("order_month").isin([4, 5, 6]), 2)
            .when(col("order_month").isin([7, 8, 9]), 3)
            .otherwise(4)
        )
        
        log_info(f"Monthly sales summary created with {monthly_summary.count()} records")
        return monthly_summary
        
    except Exception as e:
        log_error(f"Failed to create monthly sales summary: {str(e)}")
        raise

def create_product_sales_summary(orders_df: DataFrame, products_df: DataFrame) -> DataFrame:
    """Create product-level sales summary"""
    log_info("Creating product sales summary")
    
    try:
        # Note: This assumes we have order line items or product information in orders
        # For this example, we'll create a simplified version
        
        # Group by order size category as a proxy for product analysis
        product_summary = orders_df.filter(
            (col("is_complete_order") == True) & 
            (col("order_status_standardized") != "CANCELLED")
        ).groupBy("order_size_category").agg(
            sum("total_order_value").alias("category_revenue"),
            count("order_id").alias("category_orders"),
            countDistinct("customer_id").alias("unique_customers"),
            avg("total_order_value").alias("avg_order_value"),
            min("order_date").alias("first_order_date"),
            max("order_date").alias("last_order_date")
        )
        
        # Calculate category performance metrics
        total_revenue = product_summary.agg(sum("category_revenue")).collect()[0][0] or 1
        
        product_summary = product_summary.withColumn(
            "revenue_percentage",
            (col("category_revenue") / lit(total_revenue)) * 100
        )
        
        product_summary = product_summary.withColumn(
            "category_rank",
            row_number().over(Window.orderBy(desc("category_revenue")))
        )
        
        log_info(f"Product sales summary created with {product_summary.count()} categories")
        return product_summary
        
    except Exception as e:
        log_error(f"Failed to create product sales summary: {str(e)}")
        raise

def create_customer_segment_summary(orders_df: DataFrame, customers_df: DataFrame) -> DataFrame:
    """Create customer segment sales summary"""
    log_info("Creating customer segment sales summary")
    
    try:
        # Calculate customer lifetime values first
        customer_values = orders_df.filter(
            (col("is_complete_order") == True) & 
            (col("order_status_standardized") != "CANCELLED")
        ).groupBy("customer_id").agg(
            sum("total_order_value").alias("customer_lifetime_value"),
            count("order_id").alias("customer_total_orders")
        )
        
        # Segment customers based on lifetime value
        customer_segments = customer_values.withColumn(
            "customer_segment",
            when(col("customer_lifetime_value") > 1000, "HIGH_VALUE")
            .when(col("customer_lifetime_value") > 500, "MEDIUM_VALUE")
            .otherwise("LOW_VALUE")
        )
        
        # Aggregate by segment
        segment_summary = customer_segments.groupBy("customer_segment").agg(
            count("customer_id").alias("customers_in_segment"),
            sum("customer_lifetime_value").alias("segment_revenue"),
            avg("customer_lifetime_value").alias("avg_customer_value"),
            sum("customer_total_orders").alias("segment_orders"),
            avg("customer_total_orders").alias("avg_orders_per_customer")
        )
        
        # Calculate segment performance metrics
        total_customers = segment_summary.agg(sum("customers_in_segment")).collect()[0][0] or 1
        total_segment_revenue = segment_summary.agg(sum("segment_revenue")).collect()[0][0] or 1
        
        segment_summary = segment_summary.withColumn(
            "customer_percentage",
            (col("customers_in_segment") / lit(total_customers)) * 100
        )
        
        segment_summary = segment_summary.withColumn(
            "revenue_percentage",
            (col("segment_revenue") / lit(total_segment_revenue)) * 100
        )
        
        log_info(f"Customer segment summary created with {segment_summary.count()} segments")
        return segment_summary
        
    except Exception as e:
        log_error(f"Failed to create customer segment summary: {str(e)}")
        raise

def create_comprehensive_sales_summary(daily_df: DataFrame, monthly_df: DataFrame, 
                                     product_df: DataFrame, segment_df: DataFrame) -> DataFrame:
    """Combine all summaries into a comprehensive sales summary"""
    log_info("Creating comprehensive sales summary")
    
    try:
        # Create a unified summary with different aggregation levels
        # We'll use a union approach with a summary_type column
        
        # Daily summary with summary type
        daily_summary = daily_df.select(
            lit("DAILY").alias("summary_type"),
            col("order_date").alias("summary_date"),
            col("year"),
            col("month"),
            col("quarter"),
            col("daily_revenue").alias("revenue"),
            col("daily_orders").alias("orders"),
            col("unique_customers"),
            col("avg_order_value"),
            col("day_name").alias("period_name"),
            col("is_business_day").alias("is_business_period")
        )
        
        # Monthly summary adapted to match schema
        monthly_summary = monthly_df.select(
            lit("MONTHLY").alias("summary_type"),
            date_format(
                to_date(concat(col("order_year"), lit("-"), 
                              lpad(col("order_month"), 2, "0"), lit("-01"))), 
                "yyyy-MM-dd"
            ).cast(DateType()).alias("summary_date"),
            col("order_year").alias("year"),
            col("order_month").alias("month"),
            col("quarter"),
            col("monthly_revenue").alias("revenue"),
            col("monthly_orders").alias("orders"),
            col("unique_customers"),
            col("avg_order_value"),
            col("month_year").alias("period_name"),
            lit(true).alias("is_business_period")
        )
        
        # Combine daily and monthly summaries
        combined_summary = daily_summary.union(monthly_summary)
        
        # Add additional metrics
        combined_summary = combined_summary.withColumn(
            "revenue_per_customer",
            col("revenue") / col("unique_customers")
        )
        
        combined_summary = combined_summary.withColumn(
            "analysis_date",
            lit(EXECUTION_DATE)
        )
        
        combined_summary = combined_summary.withColumn(
            "etl_processed_at",
            lit(EXECUTION_TIMESTAMP)
        )
        
        log_info(f"Comprehensive sales summary created with {combined_summary.count()} records")
        return combined_summary
        
    except Exception as e:
        log_error(f"Failed to create comprehensive sales summary: {str(e)}")
        raise

def write_gold_data(df: DataFrame):
    """Write sales summary to gold layer"""
    log_info(f"Writing sales summary to gold layer: {TARGET_PATH}")
    
    try:
        # Add partitioning columns
        partitioned_df = df.withColumn("partition_year", year(col("analysis_date")))
        partitioned_df = partitioned_df.withColumn("partition_month", month(col("analysis_date")))
        
        # Convert to DynamicFrame for Glue optimizations
        gold_dynamic_frame = DynamicFrame.fromDF(partitioned_df, glueContext, "gold_sales_summary")
        
        # Write to S3 with partitioning and optimization
        glueContext.write_dynamic_frame.from_options(
            frame=gold_dynamic_frame,
            connection_type="s3",
            connection_options={
                "path": TARGET_PATH,
                "partitionKeys": ["partition_year", "partition_month"]
            },
            format="parquet",
            format_options={
                "compression": "snappy",
                "enableUpdateCatalog": True,
                "updateBehavior": "UPDATE_IN_DATABASE",
                "writeParallel": True
            },
            transformation_ctx="write_gold_sales_summary"
        )
        
        log_info(f"Successfully wrote {df.count()} sales summary records to gold layer")
        
    except Exception as e:
        log_error(f"Failed to write gold data: {str(e)}")
        raise

def generate_sales_insights(daily_df: DataFrame, monthly_df: DataFrame) -> Dict[str, Any]:
    """Generate business insights from sales data"""
    log_info("Generating sales insights")
    
    try:
        insights = {
            "execution_date": EXECUTION_DATE.isoformat(),
            "daily_insights": {},
            "monthly_insights": {},
            "trends": {}
        }
        
        # Daily insights
        if daily_df.count() > 0:
            daily_stats = daily_df.agg(
                sum("daily_revenue").alias("total_revenue"),
                avg("daily_revenue").alias("avg_daily_revenue"),
                max("daily_revenue").alias("max_daily_revenue"),
                min("daily_revenue").alias("min_daily_revenue"),
                sum("daily_orders").alias("total_orders"),
                avg("daily_orders").alias("avg_daily_orders")
            ).collect()[0]
            
            insights["daily_insights"] = {
                "total_revenue": daily_stats["total_revenue"] or 0,
                "avg_daily_revenue": daily_stats["avg_daily_revenue"] or 0,
                "max_daily_revenue": daily_stats["max_daily_revenue"] or 0,
                "min_daily_revenue": daily_stats["min_daily_revenue"] or 0,
                "total_orders": daily_stats["total_orders"] or 0,
                "avg_daily_orders": daily_stats["avg_daily_orders"] or 0
            }
            
            # Best performing day
            best_day = daily_df.orderBy(desc("daily_revenue")).first()
            insights["daily_insights"]["best_day"] = {
                "date": str(best_day["order_date"]),
                "revenue": best_day["daily_revenue"],
                "orders": best_day["daily_orders"]
            }
        
        # Monthly insights
        if monthly_df.count() > 0:
            monthly_stats = monthly_df.agg(
                sum("monthly_revenue").alias("total_revenue"),
                avg("monthly_revenue").alias("avg_monthly_revenue"),
                max("monthly_revenue").alias("max_monthly_revenue"),
                min("monthly_revenue").alias("min_monthly_revenue")
            ).collect()[0]
            
            insights["monthly_insights"] = {
                "total_revenue": monthly_stats["total_revenue"] or 0,
                "avg_monthly_revenue": monthly_stats["avg_monthly_revenue"] or 0,
                "max_monthly_revenue": monthly_stats["max_monthly_revenue"] or 0,
                "min_monthly_revenue": monthly_stats["min_monthly_revenue"] or 0
            }
            
            # Best performing month
            best_month = monthly_df.orderBy(desc("monthly_revenue")).first()
            insights["monthly_insights"]["best_month"] = {
                "year": best_month["order_year"],
                "month": best_month["order_month"],
                "revenue": best_month["monthly_revenue"],
                "orders": best_month["monthly_orders"]
            }
        
        log_info("Sales insights generated successfully")
        return insights
        
    except Exception as e:
        log_error(f"Failed to generate sales insights: {str(e)}")
        return {"error": str(e)}

def main():
    """Main ETL process"""
    log_info("Starting Silver to Gold ETL job for sales summary")
    
    try:
        # Step 1: Read silver layer data
        silver_data = read_silver_data()
        
        # Step 2: Create daily sales summary
        daily_summary = create_daily_sales_summary(silver_data['orders'])
        
        # Step 3: Create monthly sales summary
        monthly_summary = create_monthly_sales_summary(silver_data['orders'])
        
        # Step 4: Create product sales summary
        product_summary = create_product_sales_summary(
            silver_data['orders'], 
            silver_data['products']
        )
        
        # Step 5: Create customer segment summary
        segment_summary = create_customer_segment_summary(
            silver_data['orders'], 
            silver_data['customers']
        )
        
        # Step 6: Create comprehensive summary
        comprehensive_summary = create_comprehensive_sales_summary(
            daily_summary, monthly_summary, product_summary, segment_summary
        )
        
        # Step 7: Write to gold layer
        write_gold_data(comprehensive_summary)
        
        # Step 8: Generate insights
        insights = generate_sales_insights(daily_summary, monthly_summary)
        
        log_info("Silver to Gold ETL job completed successfully")
        
        # Job metrics
        job_metrics = {
            "job_name": args['JOB_NAME'],
            "total_summary_records": comprehensive_summary.count(),
            "daily_records": daily_summary.count(),
            "monthly_records": monthly_summary.count(),
            "total_revenue": insights.get("daily_insights", {}).get("total_revenue", 0),
            "total_orders": insights.get("daily_insights", {}).get("total_orders", 0),
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
"""
Lambda function to trigger appropriate Glue crawlers based on S3 events.
This function analyzes S3 object creation events and triggers the corresponding
crawler based on the data layer and source type.
"""

import json
import os
import boto3
import logging
from typing import Dict, List, Optional
from urllib.parse import unquote_plus

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
glue_client = boto3.client('glue')

# Environment variables
PROJECT_NAME = "${project_name}"
ENVIRONMENT = "${environment}"

# Crawler name mappings from environment variables
CRAWLER_MAPPINGS = {
    'bronze': {
        'customers': os.environ.get('BRONZE_CUSTOMERS_CRAWLER'),
        'orders': os.environ.get('BRONZE_ORDERS_CRAWLER'),
        'products': os.environ.get('BRONZE_PRODUCTS_CRAWLER')
    },
    'silver': {
        'dim_customers': os.environ.get('SILVER_DIM_CUSTOMERS_CRAWLER'),
        'fact_orders': os.environ.get('SILVER_FACT_ORDERS_CRAWLER'),
        'dim_products': os.environ.get('SILVER_DIM_PRODUCTS_CRAWLER')
    },
    'gold': {
        'customer_analytics': os.environ.get('GOLD_CUSTOMER_ANALYTICS_CRAWLER'),
        'sales_summary': os.environ.get('GOLD_SALES_SUMMARY_CRAWLER'),
        'ml_features': os.environ.get('GOLD_ML_FEATURES_CRAWLER')
    }
}


def lambda_handler(event, context):
    """
    Main Lambda handler function.
    
    Args:
        event: EventBridge event containing S3 object creation details
        context: Lambda context object
        
    Returns:
        dict: Response with status and processed objects
    """
    try:
        logger.info(f"Received event: {json.dumps(event, indent=2)}")
        
        # Process the event
        processed_objects = []
        
        # Handle EventBridge S3 events
        if 'detail' in event and 'bucket' in event['detail']:
            processed_objects = process_eventbridge_event(event)
        
        # Handle direct S3 events (for testing or alternative triggers)
        elif 'Records' in event:
            processed_objects = process_s3_records(event['Records'])
        
        else:
            logger.warning("Unrecognized event format")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'message': 'Unrecognized event format',
                    'processed_objects': 0
                })
            }
        
        logger.info(f"Successfully processed {len(processed_objects)} objects")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {len(processed_objects)} objects',
                'processed_objects': processed_objects
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f'Error processing event: {str(e)}',
                'processed_objects': 0
            })
        }


def process_eventbridge_event(event: dict) -> List[dict]:
    """
    Process EventBridge S3 object creation event.
    
    Args:
        event: EventBridge event
        
    Returns:
        List of processed object information
    """
    processed_objects = []
    
    detail = event.get('detail', {})
    bucket_name = detail.get('bucket', {}).get('name')
    object_key = detail.get('object', {}).get('key')
    
    if bucket_name and object_key:
        # Decode URL-encoded object key
        object_key = unquote_plus(object_key)
        
        result = process_s3_object(bucket_name, object_key)
        if result:
            processed_objects.append(result)
    
    return processed_objects


def process_s3_records(records: List[dict]) -> List[dict]:
    """
    Process S3 event records.
    
    Args:
        records: List of S3 event records
        
    Returns:
        List of processed object information
    """
    processed_objects = []
    
    for record in records:
        if record.get('eventSource') == 'aws:s3':
            s3_info = record.get('s3', {})
            bucket_name = s3_info.get('bucket', {}).get('name')
            object_key = s3_info.get('object', {}).get('key')
            
            if bucket_name and object_key:
                # Decode URL-encoded object key
                object_key = unquote_plus(object_key)
                
                result = process_s3_object(bucket_name, object_key)
                if result:
                    processed_objects.append(result)
    
    return processed_objects


def process_s3_object(bucket_name: str, object_key: str) -> Optional[dict]:
    """
    Process a single S3 object and trigger appropriate crawler.
    
    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key
        
    Returns:
        Dictionary with processing results or None if no action taken
    """
    logger.info(f"Processing S3 object: s3://{bucket_name}/{object_key}")
    
    # Parse the object key to determine layer and data source
    path_parts = object_key.split('/')
    
    if len(path_parts) < 2:
        logger.warning(f"Object key does not match expected pattern: {object_key}")
        return None
    
    layer = path_parts[0]  # bronze, silver, or gold
    data_source = path_parts[1]  # customers, orders, products, etc.
    
    # Skip processing for certain file types
    if should_skip_file(object_key):
        logger.info(f"Skipping file: {object_key}")
        return {
            'bucket': bucket_name,
            'key': object_key,
            'action': 'skipped',
            'reason': 'File type excluded from processing'
        }
    
    # Find the appropriate crawler
    crawler_name = get_crawler_name(layer, data_source)
    
    if not crawler_name:
        logger.warning(f"No crawler found for layer '{layer}' and data source '{data_source}'")
        return {
            'bucket': bucket_name,
            'key': object_key,
            'action': 'no_crawler_found',
            'layer': layer,
            'data_source': data_source
        }
    
    # Check if crawler is already running
    if is_crawler_running(crawler_name):
        logger.info(f"Crawler {crawler_name} is already running, skipping trigger")
        return {
            'bucket': bucket_name,
            'key': object_key,
            'action': 'crawler_already_running',
            'crawler_name': crawler_name
        }
    
    # Trigger the crawler
    success = trigger_crawler(crawler_name)
    
    return {
        'bucket': bucket_name,
        'key': object_key,
        'action': 'crawler_triggered' if success else 'crawler_trigger_failed',
        'crawler_name': crawler_name,
        'layer': layer,
        'data_source': data_source
    }


def should_skip_file(object_key: str) -> bool:
    """
    Determine if a file should be skipped based on its name/extension.
    
    Args:
        object_key: S3 object key
        
    Returns:
        True if file should be skipped
    """
    skip_patterns = [
        '_SUCCESS',
        '_started_',
        '_committed_',
        '.DS_Store',
        'Thumbs.db',
        '.tmp',
        '.temp'
    ]
    
    return any(pattern in object_key for pattern in skip_patterns)


def get_crawler_name(layer: str, data_source: str) -> Optional[str]:
    """
    Get the crawler name for a given layer and data source.
    
    Args:
        layer: Data layer (bronze, silver, gold)
        data_source: Data source name
        
    Returns:
        Crawler name or None if not found
    """
    return CRAWLER_MAPPINGS.get(layer, {}).get(data_source)


def is_crawler_running(crawler_name: str) -> bool:
    """
    Check if a crawler is currently running.
    
    Args:
        crawler_name: Name of the crawler
        
    Returns:
        True if crawler is running
    """
    try:
        response = glue_client.get_crawler(Name=crawler_name)
        state = response.get('Crawler', {}).get('State')
        return state == 'RUNNING'
    except Exception as e:
        logger.error(f"Error checking crawler state for {crawler_name}: {str(e)}")
        return False


def trigger_crawler(crawler_name: str) -> bool:
    """
    Trigger a Glue crawler.
    
    Args:
        crawler_name: Name of the crawler to trigger
        
    Returns:
        True if crawler was successfully triggered
    """
    try:
        logger.info(f"Triggering crawler: {crawler_name}")
        
        glue_client.start_crawler(Name=crawler_name)
        
        logger.info(f"Successfully triggered crawler: {crawler_name}")
        return True
        
    except glue_client.exceptions.CrawlerRunningException:
        logger.info(f"Crawler {crawler_name} is already running")
        return True
        
    except Exception as e:
        logger.error(f"Error triggering crawler {crawler_name}: {str(e)}")
        return False


def get_crawler_status(crawler_name: str) -> Optional[dict]:
    """
    Get detailed status information for a crawler.
    
    Args:
        crawler_name: Name of the crawler
        
    Returns:
        Dictionary with crawler status information
    """
    try:
        response = glue_client.get_crawler(Name=crawler_name)
        crawler = response.get('Crawler', {})
        
        return {
            'name': crawler.get('Name'),
            'state': crawler.get('State'),
            'creation_time': crawler.get('CreationTime'),
            'last_updated': crawler.get('LastUpdated'),
            'last_crawl': crawler.get('LastCrawl', {}),
            'version': crawler.get('Version')
        }
        
    except Exception as e:
        logger.error(f"Error getting crawler status for {crawler_name}: {str(e)}")
        return None
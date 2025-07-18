"""
Watermark Manager for Incremental Data Extraction

This module handles watermark tracking using DynamoDB for state management,
implements batch processing with configurable chunk sizes, and provides
data validation and integrity checking functions.
"""

import boto3
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from botocore.exceptions import ClientError
import json

logger = logging.getLogger(__name__)

class WatermarkManager:
    """Manages watermark state for incremental data extraction"""
    
    def __init__(self, table_name: str, region_name: str = None):
        """
        Initialize WatermarkManager
        
        Args:
            table_name: DynamoDB table name for storing watermarks
            region_name: AWS region name (optional)
        """
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(table_name)
        
    def get_watermark(self, source_table: str, watermark_column: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the latest watermark for a specific table and column
        
        Args:
            source_table: Name of the source table
            watermark_column: Column used for watermarking
            
        Returns:
            Dictionary containing watermark information or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'source_table': source_table,
                    'watermark_column': watermark_column
                }
            )
            
            if 'Item' in response:
                item = response['Item']
                logger.info(f"Retrieved watermark for {source_table}.{watermark_column}: {item['watermark_value']}")
                return {
                    'watermark_value': item['watermark_value'],
                    'last_updated': item.get('last_updated'),
                    'extraction_count': item.get('extraction_count', 0),
                    'last_row_count': item.get('last_row_count', 0)
                }
            else:
                logger.info(f"No watermark found for {source_table}.{watermark_column}")
                return None
                
        except ClientError as e:
            logger.error(f"Failed to retrieve watermark: {str(e)}")
            raise
    
    def update_watermark(self, 
                        source_table: str, 
                        watermark_column: str, 
                        watermark_value: Any,
                        row_count: int = 0,
                        metadata: Optional[Dict] = None) -> bool:
        """
        Update watermark value after successful extraction
        
        Args:
            source_table: Name of the source table
            watermark_column: Column used for watermarking
            watermark_value: New watermark value
            row_count: Number of rows extracted
            metadata: Additional metadata to store
            
        Returns:
            True if update was successful
        """
        try:
            current_time = datetime.now(timezone.utc).isoformat()
            
            # Get current extraction count
            current_watermark = self.get_watermark(source_table, watermark_column)
            extraction_count = (current_watermark['extraction_count'] + 1) if current_watermark else 1
            
            item = {
                'source_table': source_table,
                'watermark_column': watermark_column,
                'watermark_value': str(watermark_value),
                'last_updated': current_time,
                'extraction_count': extraction_count,
                'last_row_count': row_count
            }
            
            # Add metadata if provided
            if metadata:
                item['metadata'] = metadata
            
            self.table.put_item(Item=item)
            
            logger.info(f"Updated watermark for {source_table}.{watermark_column}: {watermark_value} (rows: {row_count})")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to update watermark: {str(e)}")
            raise
    
    def get_all_watermarks(self) -> List[Dict[str, Any]]:
        """
        Retrieve all watermarks from the table
        
        Returns:
            List of all watermark records
        """
        try:
            response = self.table.scan()
            items = response.get('Items', [])
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                items.extend(response.get('Items', []))
            
            logger.info(f"Retrieved {len(items)} watermark records")
            return items
            
        except ClientError as e:
            logger.error(f"Failed to retrieve all watermarks: {str(e)}")
            raise
    
    def delete_watermark(self, source_table: str, watermark_column: str) -> bool:
        """
        Delete a specific watermark record
        
        Args:
            source_table: Name of the source table
            watermark_column: Column used for watermarking
            
        Returns:
            True if deletion was successful
        """
        try:
            self.table.delete_item(
                Key={
                    'source_table': source_table,
                    'watermark_column': watermark_column
                }
            )
            
            logger.info(f"Deleted watermark for {source_table}.{watermark_column}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete watermark: {str(e)}")
            raise


class BatchProcessor:
    """Handles batch processing with configurable chunk sizes"""
    
    def __init__(self, batch_size: int = 10000, max_batches: int = 100):
        """
        Initialize BatchProcessor
        
        Args:
            batch_size: Number of rows per batch
            max_batches: Maximum number of batches to process
        """
        self.batch_size = batch_size
        self.max_batches = max_batches
        
    def create_batched_query(self, base_query: str, watermark_column: str, 
                           watermark_value: Optional[str] = None) -> str:
        """
        Create a batched query with LIMIT and OFFSET for pagination
        
        Args:
            base_query: Base SQL query
            watermark_column: Column used for watermarking
            watermark_value: Starting watermark value
            
        Returns:
            Modified query with batching logic
        """
        # Add watermark condition if provided
        if watermark_value:
            if 'WHERE' in base_query.upper():
                query = f"{base_query} AND {watermark_column} > '{watermark_value}'"
            else:
                query = f"{base_query} WHERE {watermark_column} > '{watermark_value}'"
        else:
            query = base_query
        
        # Add ordering and limit
        if 'ORDER BY' not in query.upper():
            query = f"{query} ORDER BY {watermark_column}"
        
        query = f"{query} LIMIT {self.batch_size}"
        
        return query
    
    def process_in_batches(self, query_executor, base_query: str, 
                          watermark_column: str, watermark_value: Optional[str] = None) -> List[Dict]:
        """
        Process data in batches to handle large datasets
        
        Args:
            query_executor: Function to execute queries
            base_query: Base SQL query
            watermark_column: Column used for watermarking
            watermark_value: Starting watermark value
            
        Returns:
            List of all extracted data
        """
        all_data = []
        current_watermark = watermark_value
        batch_count = 0
        
        while batch_count < self.max_batches:
            # Create batched query
            batched_query = self.create_batched_query(base_query, watermark_column, current_watermark)
            
            logger.info(f"Executing batch {batch_count + 1} with query: {batched_query}")
            
            # Execute query
            batch_data = query_executor(batched_query)
            
            if not batch_data:
                logger.info("No more data to process")
                break
            
            all_data.extend(batch_data)
            batch_count += 1
            
            # Update watermark for next batch
            if watermark_column in batch_data[-1]:
                current_watermark = str(batch_data[-1][watermark_column])
            
            logger.info(f"Processed batch {batch_count}, rows: {len(batch_data)}, total rows: {len(all_data)}")
            
            # If we got fewer rows than batch_size, we've reached the end
            if len(batch_data) < self.batch_size:
                logger.info("Reached end of data (partial batch)")
                break
        
        if batch_count >= self.max_batches:
            logger.warning(f"Reached maximum batch limit ({self.max_batches})")
        
        return all_data


class DataValidator:
    """Provides data validation and integrity checking functions"""
    
    def __init__(self):
        self.validation_results = {}
    
    def validate_schema(self, data: List[Dict], expected_schema: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate data schema against expected structure
        
        Args:
            data: List of data records
            expected_schema: Dictionary mapping column names to expected types
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if not data:
            errors.append("No data to validate")
            return False, errors
        
        # Check if all expected columns are present
        first_row = data[0]
        missing_columns = set(expected_schema.keys()) - set(first_row.keys())
        if missing_columns:
            errors.append(f"Missing columns: {missing_columns}")
        
        # Check data types (basic validation)
        for column, expected_type in expected_schema.items():
            if column in first_row:
                sample_value = first_row[column]
                if sample_value is not None:
                    if expected_type == 'string' and not isinstance(sample_value, str):
                        errors.append(f"Column {column} expected string, got {type(sample_value)}")
                    elif expected_type == 'integer' and not isinstance(sample_value, int):
                        errors.append(f"Column {column} expected integer, got {type(sample_value)}")
                    elif expected_type == 'float' and not isinstance(sample_value, (int, float)):
                        errors.append(f"Column {column} expected float, got {type(sample_value)}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_data_quality(self, data: List[Dict], quality_rules: Dict) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate data quality based on defined rules
        
        Args:
            data: List of data records
            quality_rules: Dictionary containing quality validation rules
            
        Returns:
            Tuple of (is_valid, validation_report)
        """
        report = {
            'total_rows': len(data),
            'validation_timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': {},
            'errors': [],
            'warnings': []
        }
        
        if not data:
            report['errors'].append("No data to validate")
            return False, report
        
        # Check minimum row count
        min_rows = quality_rules.get('min_rows', 0)
        if len(data) < min_rows:
            report['errors'].append(f"Row count {len(data)} below minimum {min_rows}")
        
        # Check for null values in critical columns
        non_null_columns = quality_rules.get('non_null_columns', [])
        for column in non_null_columns:
            null_count = sum(1 for row in data if row.get(column) is None)
            null_percentage = (null_count / len(data)) * 100
            
            report['checks'][f'{column}_null_count'] = null_count
            report['checks'][f'{column}_null_percentage'] = null_percentage
            
            if null_count > 0:
                max_null_percentage = quality_rules.get('max_null_percentage', 0)
                if null_percentage > max_null_percentage:
                    report['errors'].append(f"Column {column} has {null_percentage:.2f}% null values (max allowed: {max_null_percentage}%)")
                else:
                    report['warnings'].append(f"Column {column} has {null_count} null values")
        
        # Check for duplicate records
        if quality_rules.get('check_duplicates', False):
            unique_key_columns = quality_rules.get('unique_key_columns', [])
            if unique_key_columns:
                seen_keys = set()
                duplicate_count = 0
                
                for row in data:
                    key = tuple(row.get(col) for col in unique_key_columns)
                    if key in seen_keys:
                        duplicate_count += 1
                    else:
                        seen_keys.add(key)
                
                report['checks']['duplicate_count'] = duplicate_count
                if duplicate_count > 0:
                    report['warnings'].append(f"Found {duplicate_count} duplicate records")
        
        # Check value ranges
        range_checks = quality_rules.get('range_checks', {})
        for column, range_config in range_checks.items():
            min_val = range_config.get('min')
            max_val = range_config.get('max')
            
            out_of_range_count = 0
            for row in data:
                value = row.get(column)
                if value is not None:
                    try:
                        numeric_value = float(value)
                        if min_val is not None and numeric_value < min_val:
                            out_of_range_count += 1
                        elif max_val is not None and numeric_value > max_val:
                            out_of_range_count += 1
                    except (ValueError, TypeError):
                        continue
            
            report['checks'][f'{column}_out_of_range_count'] = out_of_range_count
            if out_of_range_count > 0:
                report['warnings'].append(f"Column {column} has {out_of_range_count} values out of range")
        
        is_valid = len(report['errors']) == 0
        return is_valid, report
    
    def validate_referential_integrity(self, data: List[Dict], reference_data: Dict[str, List], 
                                     foreign_keys: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate referential integrity between datasets
        
        Args:
            data: Main dataset to validate
            reference_data: Dictionary of reference datasets
            foreign_keys: Mapping of foreign key columns to reference tables
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        for fk_column, ref_table in foreign_keys.items():
            if ref_table not in reference_data:
                errors.append(f"Reference table {ref_table} not found")
                continue
            
            # Create set of valid reference values
            ref_values = set()
            for ref_row in reference_data[ref_table]:
                # Assume first column is the primary key
                if ref_row:
                    pk_value = list(ref_row.values())[0]
                    ref_values.add(pk_value)
            
            # Check foreign key values
            invalid_count = 0
            for row in data:
                fk_value = row.get(fk_column)
                if fk_value is not None and fk_value not in ref_values:
                    invalid_count += 1
            
            if invalid_count > 0:
                errors.append(f"Column {fk_column} has {invalid_count} invalid references to {ref_table}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
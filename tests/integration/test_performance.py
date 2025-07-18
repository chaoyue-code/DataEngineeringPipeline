"""
Performance Testing for Pipeline Components

This module contains performance tests for the data pipeline components using
realistic data volumes to evaluate throughput, latency, and resource utilization.
"""

import os
import json
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import time
import io
import pyarrow as pa
import pyarrow.parquet as pq
import boto3
import gc
import psutil
import logging

# Path manipulation to import Lambda functions
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../lambda/snowflake_extractor')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../lambda/data_quality_monitor')))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestPipelinePerformance:
    """Performance tests for pipeline components with realistic data volumes."""
    
    @pytest.fixture
    def large_synthetic_dataset(self, size=100000):
        """Generate a large synthetic dataset for performance testing."""
        logger.info(f"Generating large synthetic dataset with {size} records")
        
        # Create customer IDs
        customer_ids = [f"CUST{i:08d}" for i in range(1, size + 1)]
        
        # Create names
        first_names = ["John", "Jane", "Michael", "Emily", "David", "Sarah", "Robert", "Lisa", 
                      "William", "Elizabeth", "James", "Jennifer", "Richard", "Patricia", "Thomas", "Linda"]
        last_names = ["Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller", "Wilson",
                     "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin"]
        
        # Generate random data
        np.random.seed(42)  # For reproducibility
        
        data = {
            'customer_id': customer_ids,
            'first_name': np.random.choice(first_names, size),
            'last_name': np.random.choice(last_names, size),
            'email': [f"{fn.lower()}.{ln.lower()}{i}@example.com" for i, (fn, ln) in 
                     enumerate(zip(np.random.choice(first_names, size), 
                                  np.random.choice(last_names, size)))],
            'phone': [f"+1-555-{np.random.randint(100, 999)}-{np.random.randint(1000, 9999)}" 
                     for _ in range(size)],
            'address': [f"{np.random.randint(100, 9999)} {np.random.choice(['Main', 'Oak', 'Pine', 'Maple', 'Cedar'])} {np.random.choice(['St', 'Ave', 'Blvd', 'Rd', 'Ln'])}" 
                       for _ in range(size)],
            'city': np.random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", 
                                     "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose"], size),
            'state': np.random.choice(["NY", "CA", "IL", "TX", "AZ", "PA", "FL", "OH", "GA", "NC"], size),
            'zip_code': [f"{np.random.randint(10000, 99999)}" for _ in range(size)],
            'created_at': [
                (datetime.now(timezone.utc) - timedelta(days=np.random.randint(1, 365))).isoformat()
                for _ in range(size)
            ],
            'updated_at': [
                (datetime.now(timezone.utc) - timedelta(days=np.random.randint(0, 30))).isoformat()
                for _ in range(size)
            ],
            'account_balance': np.round(np.random.uniform(0, 10000, size), 2),
            'credit_score': np.random.randint(300, 850, size),
            'is_active': np.random.choice([True, False], size, p=[0.9, 0.1]),
            'last_login': [
                (datetime.now(timezone.utc) - timedelta(days=np.random.randint(0, 60))).isoformat()
                for _ in range(size)
            ],
            'registration_date': [
                (datetime.now(timezone.utc) - timedelta(days=np.random.randint(30, 1000))).isoformat()
                for _ in range(size)
            ]
        }
        
        # Introduce some nulls (about 5% of data)
        for col in ['phone', 'address', 'last_login']:
            null_indices = np.random.choice(size, size=int(size * 0.05), replace=False)
            for idx in null_indices:
                data[col][idx] = None
        
        # Introduce some duplicates (about 1% of data)
        duplicate_indices = np.random.choice(size, size=int(size * 0.01), replace=False)
        for idx in duplicate_indices:
            # Pick a random index to duplicate
            dup_idx = np.random.randint(0, size)
            for col in data:
                if col != 'customer_id':  # Keep customer_id unique
                    data[col][idx] = data[col][dup_idx]
        
        df = pd.DataFrame(data)
        logger.info(f"Generated dataset with shape: {df.shape}")
        return df
    
    @pytest.mark.performance
    def test_snowflake_extractor_performance(self, mock_aws_services, mock_snowflake_connection, 
                                           test_environment, mock_context):
        """Test Snowflake extractor performance with large datasets."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import SnowflakeExtractor
        
        # Setup mocks
        mock_conn, mock_cursor = mock_snowflake_connection
        mock_secrets = mock_aws_services['secrets']
        mock_s3 = mock_aws_services['s3']
        mock_table = mock_aws_services['table']
        
        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'username': 'test_user',
                'password': 'test_password',
                'account': 'test_account',
                'warehouse': 'test_warehouse',
                'database': 'test_db',
                'schema': 'test_schema'
            })
        }
        
        # Mock DynamoDB watermark response
        mock_table.get_item.return_value = {
            'Item': {
                'watermark_value': '2023-01-01T00:00:00Z'
            }
        }
        
        # Create extractor instance
        extractor = SnowflakeExtractor()
        
        # Test with different dataset sizes
        sizes = [10000, 50000, 100000]
        results = []
        
        for size in sizes:
            # Generate large dataset
            large_dataset = self.large_synthetic_dataset(size)
            records = large_dataset.to_dict('records')
            
            # Mock cursor to return large dataset
            mock_cursor.fetchall.return_value = records
            
            # Mock S3 put_object
            mock_s3.put_object.return_value = {}
            
            # Measure memory before
            gc.collect()
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Measure execution time
            start_time = time.time()
            
            # Execute extraction
            extraction_config = {
                'queries': [
                    {
                        'name': 'customers',
                        'sql': 'SELECT * FROM customers WHERE updated_at > ?',
                        'watermark_column': 'updated_at',
                        'partition_by': 'date',
                        'enable_batching': True
                    }
                ],
                'output_format': 'parquet'
            }
            
            extraction_result = extractor.extract_data(extraction_config)
            
            # Calculate metrics
            execution_time = time.time() - start_time
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = memory_after - memory_before
            
            # Log results
            logger.info(f"Dataset size: {size} records")
            logger.info(f"Execution time: {execution_time:.2f} seconds")
            logger.info(f"Memory used: {memory_used:.2f} MB")
            logger.info(f"Throughput: {size / execution_time:.2f} records/second")
            
            results.append({
                'size': size,
                'execution_time': execution_time,
                'memory_used': memory_used,
                'throughput': size / execution_time
            })
        
        # Assertions
        for i in range(len(results) - 1):
            # Verify that throughput doesn't degrade significantly with larger datasets
            # Allow for some degradation but not more than 50%
            throughput_ratio = results[i+1]['throughput'] / results[i]['throughput']
            assert throughput_ratio > 0.5, f"Throughput degraded significantly: {throughput_ratio:.2f}"
        
        return results
    
    @pytest.mark.performance
    def test_data_quality_monitor_performance(self, mock_aws_services, test_environment, mock_context):
        """Test data quality monitor performance with large datasets."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import DataQualityMonitor
        
        # Setup mocks
        mock_s3 = mock_aws_services['s3']
        mock_glue = mock_aws_services['glue']
        mock_table = mock_aws_services['table']
        
        # Mock Glue table schema
        mock_glue.get_table.return_value = {
            'Table': {
                'StorageDescriptor': {
                    'Columns': [
                        {'Name': 'customer_id', 'Type': 'string'},
                        {'Name': 'first_name', 'Type': 'string'},
                        {'Name': 'last_name', 'Type': 'string'},
                        {'Name': 'email', 'Type': 'string'},
                        {'Name': 'phone', 'Type': 'string'},
                        {'Name': 'address', 'Type': 'string'},
                        {'Name': 'city', 'Type': 'string'},
                        {'Name': 'state', 'Type': 'string'},
                        {'Name': 'zip_code', 'Type': 'string'},
                        {'Name': 'created_at', 'Type': 'timestamp'},
                        {'Name': 'updated_at', 'Type': 'timestamp'},
                        {'Name': 'account_balance', 'Type': 'double'},
                        {'Name': 'credit_score', 'Type': 'int'},
                        {'Name': 'is_active', 'Type': 'boolean'},
                        {'Name': 'last_login', 'Type': 'timestamp'},
                        {'Name': 'registration_date', 'Type': 'timestamp'}
                    ]
                }
            }
        }
        
        # Create monitor instance
        monitor = DataQualityMonitor()
        
        # Test with different dataset sizes
        sizes = [10000, 50000, 100000]
        results = []
        
        for size in sizes:
            # Generate large dataset
            large_dataset = self.large_synthetic_dataset(size)
            
            # Measure memory before
            gc.collect()
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Measure execution time
            start_time = time.time()
            
            # Mock pandas read_parquet to return our large dataset
            with patch('pandas.read_parquet', return_value=large_dataset):
                # Run quality checks
                data_config = {
                    'bucket': 'test-data-lake-bucket',
                    'key': f'bronze/customers/year=2024/month=07/day=18/customers_{size}_records.parquet',
                    'table_name': 'customers',
                    'data_source': 'snowflake',
                    'quality_rules': {
                        'check_schema': True,
                        'check_nulls': True,
                        'check_duplicates': True,
                        'check_outliers': True,
                        'timestamp_column': 'updated_at',
                        'key_columns': ['customer_id'],
                        'numeric_columns': ['account_balance', 'credit_score'],
                        'range_rules': {
                            'account_balance': {
                                'min': 0,
                                'max': 10000
                            },
                            'credit_score': {
                                'min': 300,
                                'max': 850
                            }
                        }
                    }
                }
                
                quality_result = monitor.run_quality_checks(data_config)
            
            # Calculate metrics
            execution_time = time.time() - start_time
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = memory_after - memory_before
            
            # Log results
            logger.info(f"Dataset size: {size} records")
            logger.info(f"Execution time: {execution_time:.2f} seconds")
            logger.info(f"Memory used: {memory_used:.2f} MB")
            logger.info(f"Throughput: {size / execution_time:.2f} records/second")
            
            results.append({
                'size': size,
                'execution_time': execution_time,
                'memory_used': memory_used,
                'throughput': size / execution_time,
                'quality_score': quality_result['overall_quality_score']
            })
        
        # Assertions
        for i in range(len(results) - 1):
            # Verify that throughput doesn't degrade significantly with larger datasets
            # Allow for some degradation but not more than 50%
            throughput_ratio = results[i+1]['throughput'] / results[i]['throughput']
            assert throughput_ratio > 0.5, f"Throughput degraded significantly: {throughput_ratio:.2f}"
        
        return results
    
    @pytest.mark.performance
    def test_batch_processing_performance(self, mock_aws_services, mock_snowflake_connection, 
                                         test_environment, mock_context):
        """Test batch processing performance with different batch sizes."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import SnowflakeExtractor
            from watermark_manager import BatchProcessor
        
        # Setup mocks
        mock_conn, mock_cursor = mock_snowflake_connection
        mock_secrets = mock_aws_services['secrets']
        
        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'username': 'test_user',
                'password': 'test_password',
                'account': 'test_account',
                'warehouse': 'test_warehouse',
                'database': 'test_db',
                'schema': 'test_schema'
            })
        }
        
        # Generate large dataset (100K records)
        large_dataset = self.large_synthetic_dataset(100000)
        
        # Test with different batch sizes
        batch_sizes = [1000, 5000, 10000, 25000]
        results = []
        
        for batch_size in batch_sizes:
            # Create batch processor with specific batch size
            batch_processor = BatchProcessor(batch_size=batch_size, max_batches=10)
            
            # Split dataset into batches for mock responses
            total_records = len(large_dataset)
            num_batches = (total_records + batch_size - 1) // batch_size  # Ceiling division
            
            # Prepare mock responses for each batch
            batch_responses = []
            for i in range(num_batches):
                start_idx = i * batch_size
                end_idx = min((i + 1) * batch_size, total_records)
                batch_data = large_dataset.iloc[start_idx:end_idx].to_dict('records')
                batch_responses.append(batch_data)
            
            # Configure mock cursor to return batches
            mock_cursor.fetchall.side_effect = batch_responses
            
            # Measure execution time
            start_time = time.time()
            
            # Execute batch processing
            def execute_query(query, params=None):
                # This simulates the query execution with the mock cursor
                return mock_cursor.fetchall()
            
            # Process in batches
            all_data = []
            for i in range(num_batches):
                batch = execute_query("SELECT * FROM customers LIMIT ? OFFSET ?", [batch_size, i * batch_size])
                all_data.extend(batch)
            
            execution_time = time.time() - start_time
            
            # Log results
            logger.info(f"Batch size: {batch_size}")
            logger.info(f"Number of batches: {num_batches}")
            logger.info(f"Total records: {len(all_data)}")
            logger.info(f"Execution time: {execution_time:.2f} seconds")
            logger.info(f"Throughput: {len(all_data) / execution_time:.2f} records/second")
            
            results.append({
                'batch_size': batch_size,
                'num_batches': num_batches,
                'total_records': len(all_data),
                'execution_time': execution_time,
                'throughput': len(all_data) / execution_time
            })
        
        # Find optimal batch size (highest throughput)
        optimal_batch = max(results, key=lambda x: x['throughput'])
        logger.info(f"Optimal batch size: {optimal_batch['batch_size']} with throughput: {optimal_batch['throughput']:.2f} records/second")
        
        return results
    
    @pytest.mark.performance
    def test_parquet_vs_json_performance(self, mock_aws_services, test_environment, mock_context):
        """Compare performance between Parquet and JSON formats."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import SnowflakeExtractor
        
        # Setup mocks
        mock_s3 = mock_aws_services['s3']
        
        # Create extractor instance
        extractor = SnowflakeExtractor()
        
        # Generate dataset (50K records)
        dataset = self.large_synthetic_dataset(50000)
        records = dataset.to_dict('records')
        
        # Test Parquet format
        start_time = time.time()
        extractor._upload_to_s3(records, 's3_key_parquet.parquet', 'parquet')
        parquet_time = time.time() - start_time
        
        # Test JSON format
        start_time = time.time()
        extractor._upload_to_s3(records, 's3_key_json.json', 'json')
        json_time = time.time() - start_time
        
        # Log results
        logger.info(f"Parquet upload time: {parquet_time:.2f} seconds")
        logger.info(f"JSON upload time: {json_time:.2f} seconds")
        logger.info(f"Performance ratio (JSON/Parquet): {json_time/parquet_time:.2f}x")
        
        # Assertions
        # Parquet should be faster than JSON for large datasets
        assert parquet_time < json_time, "Parquet should be faster than JSON for large datasets"
        
        return {
            'parquet_time': parquet_time,
            'json_time': json_time,
            'ratio': json_time / parquet_time
        }
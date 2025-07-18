"""
Data Quality Validation Integration Tests

This module contains integration tests specifically focused on data quality validation
across different pipeline components.
"""

import os
import json
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import io
import pyarrow as pa
import pyarrow.parquet as pq

# Import Lambda functions
# We need to mock AWS services before importing the Lambda functions
import boto3

# Path manipulation to import Lambda functions
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../lambda/data_quality_monitor')))

class TestDataQualityValidation:
    """Test data quality validation across pipeline components."""
    
    @pytest.mark.integration
    def test_schema_validation(self, mock_aws_services, test_environment, 
                              synthetic_customer_data, mock_context):
        """Test schema validation functionality."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import DataQualityMonitor
        
        # Setup mocks
        mock_glue = mock_aws_services['glue']
        
        # Create a DataQualityMonitor instance
        monitor = DataQualityMonitor()
        
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
                        {'Name': 'updated_at', 'Type': 'timestamp'}
                    ]
                }
            }
        }
        
        # Get schema from Glue
        expected_schema = monitor.get_glue_table_schema('customers')
        
        # Test with correct schema
        df = synthetic_customer_data
        result = monitor.validate_schema_compliance(df, expected_schema)
        
        # Assertions for correct schema
        assert result['passed'] is True
        assert result['score'] >= 95.0
        
        # Test with missing column
        df_missing = df.drop(columns=['email'])
        result_missing = monitor.validate_schema_compliance(df_missing, expected_schema)
        
        # Assertions for missing column
        assert result_missing['passed'] is False
        assert 'email' in result_missing['details']['missing_columns']
        
        # Test with extra column
        df_extra = df.copy()
        df_extra['extra_column'] = 'test'
        result_extra = monitor.validate_schema_compliance(df_extra, expected_schema)
        
        # Assertions for extra column
        assert 'extra_column' in result_extra['details']['extra_columns']
        
        # Test with type mismatch
        df_type_mismatch = df.copy()
        df_type_mismatch['created_at'] = df_type_mismatch['created_at'].astype(str)
        result_type_mismatch = monitor.validate_schema_compliance(df_type_mismatch, expected_schema)
        
        # Check if type mismatch was detected
        type_mismatches = [m['column'] for m in result_type_mismatch['details']['type_mismatches']]
        assert 'created_at' in type_mismatches
    
    @pytest.mark.integration
    def test_null_value_detection(self, mock_aws_services, test_environment, mock_context):
        """Test null value detection functionality."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import DataQualityMonitor
        
        # Create a DataQualityMonitor instance
        monitor = DataQualityMonitor()
        
        # Create test data with controlled null values
        data = {
            'col1': [1, 2, None, 4, 5, 6, 7, 8, 9, 10],  # 10% nulls
            'col2': [1, 2, 3, None, None, 6, 7, None, 9, 10],  # 30% nulls
            'col3': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # 0% nulls
        }
        df = pd.DataFrame(data)
        
        # Test with default threshold (10%)
        result = monitor.check_null_values(df)
        
        # Assertions
        assert result['passed'] is False  # col2 exceeds threshold
        assert result['details']['columns_with_nulls']['col1']['passed'] is True
        assert result['details']['columns_with_nulls']['col2']['passed'] is False
        assert result['details']['columns_with_nulls']['col3']['passed'] is True
        
        # Test with custom column rules
        column_rules = {
            'col2': {'null_threshold': 40}  # Allow up to 40% nulls for col2
        }
        
        result_custom = monitor.check_null_values(df, column_rules)
        
        # Assertions for custom rules
        assert result_custom['passed'] is True  # col2 now passes with higher threshold
        assert result_custom['details']['columns_with_nulls']['col2']['passed'] is True
    
    @pytest.mark.integration
    def test_duplicate_detection(self, mock_aws_services, test_environment, mock_context):
        """Test duplicate record detection functionality."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import DataQualityMonitor
        
        # Create a DataQualityMonitor instance
        monitor = DataQualityMonitor()
        
        # Create test data with controlled duplicates
        data = {
            'id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'name': ['A', 'B', 'C', 'D', 'A', 'B', 'G', 'H', 'I', 'J'],
            'value': [100, 200, 300, 400, 100, 200, 700, 800, 900, 1000]
        }
        df = pd.DataFrame(data)
        
        # Test duplicate detection on all columns
        result_all = monitor.check_duplicate_records(df)
        
        # Assertions - no exact duplicates
        assert result_all['passed'] is True
        assert result_all['details']['duplicate_rows'] == 0
        
        # Test duplicate detection on specific columns
        result_key = monitor.check_duplicate_records(df, key_columns=['name', 'value'])
        
        # Assertions - duplicates in name+value
        assert result_key['passed'] is False
        assert result_key['details']['duplicate_rows'] == 4  # rows 0,4 and 1,5 are duplicates
        
        # Create data with more duplicates to test threshold
        data_high_dups = {
            'id': [1, 2, 3, 1, 2, 3, 7, 8, 9, 10],
            'value': [100, 200, 300, 100, 200, 300, 700, 800, 900, 1000]
        }
        df_high_dups = pd.DataFrame(data_high_dups)
        
        # Test with high duplicate percentage
        result_high = monitor.check_duplicate_records(df_high_dups, key_columns=['id', 'value'])
        
        # Assertions - high duplicates
        assert result_high['passed'] is False
        assert result_high['details']['duplicate_percentage'] == 60.0  # 6 out of 10 rows are duplicates
    
    @pytest.mark.integration
    def test_data_range_validation(self, mock_aws_services, test_environment, mock_context):
        """Test data range validation functionality."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import DataQualityMonitor
        
        # Create a DataQualityMonitor instance
        monitor = DataQualityMonitor()
        
        # Create test data with controlled values
        data = {
            'age': [25, 30, 15, 40, 55, 60, 70, 18, 22, 35],
            'score': [85, 90, 95, 100, 75, 80, 65, 70, 60, 110],
            'category': ['A', 'B', 'A', 'C', 'B', 'A', 'D', 'C', 'B', 'A']
        }
        df = pd.DataFrame(data)
        
        # Define range rules
        range_rules = {
            'age': {
                'min': 18,
                'max': 65
            },
            'score': {
                'min': 0,
                'max': 100
            },
            'category': {
                'allowed_values': ['A', 'B', 'C']
            }
        }
        
        # Test range validation
        result = monitor.check_data_ranges(df, range_rules)
        
        # Assertions
        assert result['passed'] is False
        
        # Check age violations (one value below min: 15)
        age_violations = result['details']['column_checks']['age']['violations']
        assert age_violations == 1
        
        # Check score violations (one value above max: 110)
        score_violations = result['details']['column_checks']['score']['violations']
        assert score_violations == 1
        
        # Check category violations (one value not in allowed list: 'D')
        category_violations = result['details']['column_checks']['category']['violations']
        assert category_violations == 1
        
        # Total violations
        assert result['details']['total_violations'] == 3
    
    @pytest.mark.integration
    def test_data_freshness(self, mock_aws_services, test_environment, mock_context):
        """Test data freshness validation functionality."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import DataQualityMonitor
        
        # Create a DataQualityMonitor instance
        monitor = DataQualityMonitor()
        
        # Create test data with controlled timestamps
        now = datetime.now(timezone.utc)
        
        data = {
            'id': range(1, 11),
            'recent_timestamp': [now - timedelta(hours=i) for i in range(10)],
            'old_timestamp': [now - timedelta(hours=i*10) for i in range(10)]
        }
        df = pd.DataFrame(data)
        
        # Test freshness with recent timestamps (all within 24 hours)
        result_recent = monitor.check_data_freshness(df, 'recent_timestamp')
        
        # Assertions for recent data
        assert result_recent['passed'] is True
        assert result_recent['details']['hours_since_latest'] < 1.0
        
        # Test freshness with old timestamps (some beyond 24 hours)
        result_old = monitor.check_data_freshness(df, 'old_timestamp')
        
        # Assertions for old data
        assert result_old['details']['hours_since_latest'] < 1.0  # Most recent is still fresh
        assert result_old['passed'] is True
        
        # Test with very old data
        very_old_data = {
            'id': range(1, 11),
            'timestamp': [now - timedelta(days=i+2) for i in range(10)]  # All older than 2 days
        }
        df_old = pd.DataFrame(very_old_data)
        
        result_very_old = monitor.check_data_freshness(df_old, 'timestamp')
        
        # Assertions for very old data
        assert result_very_old['passed'] is False
        assert result_very_old['details']['hours_since_latest'] > 24.0
    
    @pytest.mark.integration
    def test_statistical_outlier_detection(self, mock_aws_services, test_environment, mock_context):
        """Test statistical outlier detection functionality."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import DataQualityMonitor
        
        # Create a DataQualityMonitor instance
        monitor = DataQualityMonitor()
        
        # Create test data with controlled outliers
        np.random.seed(42)
        normal_values = np.random.normal(100, 15, 98)
        outliers = np.array([10, 200])  # Clear outliers
        
        data = {
            'id': range(1, 101),
            'normal_values': np.concatenate([normal_values, outliers])
        }
        df = pd.DataFrame(data)
        
        # Test outlier detection
        result = monitor.detect_statistical_outliers(df, ['normal_values'])
        
        # Assertions
        assert result['passed'] is False  # Outliers detected
        assert result['details']['column_outliers']['normal_values']['outlier_count'] >= 2
        
        # Test with data having no outliers
        clean_data = {
            'id': range(1, 101),
            'values': np.random.normal(100, 5, 100)  # Tight distribution
        }
        df_clean = pd.DataFrame(clean_data)
        
        result_clean = monitor.detect_statistical_outliers(df_clean, ['values'])
        
        # Check if outlier percentage is within threshold
        outlier_pct = result_clean['details']['column_outliers']['values']['outlier_percentage']
        assert outlier_pct <= monitor.default_thresholds['outlier_percentage_threshold']
    
    @pytest.mark.integration
    def test_end_to_end_quality_validation(self, mock_aws_services, test_environment, 
                                          synthetic_customer_data, data_quality_event, 
                                          mock_context):
        """Test end-to-end data quality validation process."""
        # Import the Lambda function after mocking dependencies
        with patch.dict('sys.modules', {'boto3': boto3}):
            from lambda_function import lambda_handler as data_quality_handler
        
        # Setup mocks
        mock_s3 = mock_aws_services['s3']
        mock_glue = mock_aws_services['glue']
        mock_table = mock_aws_services['table']
        mock_sns = mock_aws_services['sns']
        
        # Mock pandas read_parquet to return our synthetic data
        with patch('pandas.read_parquet', return_value=synthetic_customer_data):
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
                            {'Name': 'updated_at', 'Type': 'timestamp'}
                        ]
                    }
                }
            }
            
            # Execute the Lambda function
            response = data_quality_handler(data_quality_event, mock_context)
            
            # Assertions
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            # Verify all quality checks were performed
            check_names = [check['check_name'] for check in body['quality_checks']]
            assert 'schema_compliance' in check_names
            assert 'null_values' in check_names
            assert 'duplicate_records' in check_names
            
            # Verify quality results were saved
            mock_table.put_item.assert_called()
            
            # If data was quarantined, verify S3 put_object was called
            if not body['passed'] and body.get('quarantine_location'):
                mock_s3.put_object.assert_called()
            
            return body
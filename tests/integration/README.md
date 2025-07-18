# Integration Tests for Snowflake-AWS Pipeline

This directory contains integration tests for the Snowflake-AWS data pipeline. These tests validate the end-to-end functionality of the pipeline components, data quality validation, and performance characteristics.

## Test Categories

The integration tests are organized into three main categories:

1. **End-to-End Pipeline Tests** (`test_e2e_pipeline.py`): Tests the complete pipeline flow from Snowflake extraction to data quality validation and transformation.

2. **Data Quality Validation Tests** (`test_data_quality.py`): Tests the data quality validation functionality across different pipeline components.

3. **Performance Tests** (`test_performance.py`): Tests the pipeline components with realistic data volumes to evaluate throughput, latency, and resource utilization.

## Prerequisites

Before running the tests, ensure you have the following:

- Python 3.8+ installed
- Required Python packages installed:
  ```
  pytest
  pytest-cov
  pandas
  numpy
  pyarrow
  boto3
  moto
  psutil
  ```

## Running the Tests

### Running All Integration Tests

```bash
cd DataEngineeringPipeline
python -m pytest tests/integration -v
```

### Running Specific Test Categories

```bash
# Run end-to-end pipeline tests
python -m pytest tests/integration/test_e2e_pipeline.py -v

# Run data quality validation tests
python -m pytest tests/integration/test_data_quality.py -v

# Run performance tests
python -m pytest tests/integration/test_performance.py -v
```

### Running Tests with Coverage

```bash
python -m pytest tests/integration --cov=lambda --cov-report=term-missing -v
```

## Test Markers

The tests use the following markers:

- `integration`: Marks tests that validate integration between components
- `performance`: Marks tests that evaluate performance characteristics

To run tests with a specific marker:

```bash
python -m pytest tests/integration -m performance -v
```

## Test Environment

The tests use mock AWS services to simulate the AWS environment. The test environment is configured in `conftest.py` with fixtures for:

- Mock AWS services (S3, DynamoDB, Lambda, Glue, SNS, etc.)
- Mock Snowflake connection
- Test environment variables
- Synthetic data generation

## Synthetic Data

The tests use synthetic data generators to create realistic test data:

- `synthetic_customer_data`: Generates customer data with configurable size
- `synthetic_order_data`: Generates order data related to customers
- `large_synthetic_dataset`: Generates large datasets for performance testing

## Test Configuration

Test configuration is managed through fixtures in `conftest.py`. You can modify the test environment by updating the fixtures.

## Adding New Tests

To add new integration tests:

1. Create a new test file in the `tests/integration` directory
2. Import the necessary fixtures from `conftest.py`
3. Use the appropriate test markers (`integration`, `performance`)
4. Follow the existing test patterns for consistency

## Continuous Integration

These tests are designed to run in a CI/CD pipeline. The tests use mock AWS services, so they don't require actual AWS resources.

## Troubleshooting

If you encounter issues running the tests:

1. Ensure all dependencies are installed
2. Check that the Lambda functions are properly imported
3. Verify that the mock AWS services are properly configured
4. Check the test logs for detailed error messages
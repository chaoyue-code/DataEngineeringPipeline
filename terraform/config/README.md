# Configuration Management System

This document describes the configuration management system for the Snowflake AWS Pipeline project. The system provides a centralized way to manage environment-specific configurations with parameter validation and default value management.

## Overview

The configuration management system consists of:

1. **Environment-specific configuration files**: JSON files stored in environment-specific directories
2. **Parameter validation**: Schema-based validation for configuration parameters
3. **Default value management**: Default values for configuration parameters
4. **Configuration documentation**: Documentation for configuration parameters
5. **Configuration loading utilities**: Utilities for loading configuration in Lambda functions

## Directory Structure

```
terraform/
├── config/
│   ├── dev/
│   │   └── snowflake_extraction.json
│   ├── staging/
│   │   └── snowflake_extraction.json
│   ├── prod/
│   │   └── snowflake_extraction.json
│   └── README.md (this file)
├── modules/
│   └── config_manager/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── scripts/
│           └── validate_config.sh
└── main.tf
```

## Configuration Files

Configuration files are stored in environment-specific directories (`dev`, `staging`, `prod`) and are named according to their purpose (e.g., `snowflake_extraction.json`).

### Snowflake Extraction Configuration

The `snowflake_extraction.json` file contains configuration for the Snowflake extraction Lambda function:

```json
{
  "batch_size": 10000,
  "max_batches": 100,
  "max_retries": 3,
  "output_format": "parquet",
  "validation_rules": {
    "min_rows": 1,
    "required_columns": ["created_at", "updated_at"],
    "non_null_columns": ["created_at"]
  },
  "queries": [
    {
      "name": "customers",
      "sql": "SELECT customer_id, first_name, last_name, email, phone, address, city, state, zip_code, created_at, updated_at FROM customers WHERE updated_at > ? ORDER BY updated_at",
      "watermark_column": "updated_at",
      "partition_by": "date"
    }
  ]
}
```

#### Parameters

| Parameter | Type | Description | Default | Validation |
|-----------|------|-------------|---------|------------|
| `batch_size` | Integer | Number of records to extract in each batch | 10000 | 1-100000 |
| `max_batches` | Integer | Maximum number of batches to process in a single execution | 100 | 1-1000 |
| `max_retries` | Integer | Maximum number of retry attempts for failed operations | 3 | 0-10 |
| `output_format` | String | Output file format for extracted data | "parquet" | "parquet" or "json" |
| `validation_rules` | Object | Rules for validating extracted data | See below | - |
| `queries` | Array | List of SQL queries to execute | [] | At least one query |

##### Validation Rules

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `min_rows` | Integer | Minimum number of rows expected in extraction | 1 |
| `required_columns` | Array | List of columns that must be present in extracted data | ["created_at", "updated_at"] |
| `non_null_columns` | Array | List of columns that should not contain null values | ["created_at"] |

##### Query Configuration

| Parameter | Type | Description | Default | Required |
|-----------|------|-------------|---------|----------|
| `name` | String | Unique name for the query/table | - | Yes |
| `sql` | String | SQL query to execute | - | Yes |
| `watermark_column` | String | Column used for incremental extraction | - | No |
| `partition_by` | String | Partitioning strategy for S3 storage | "date" | No |
| `enable_batching` | Boolean | Enable batch processing for this query | true | No |

## Parameter Validation

Configuration parameters are validated using JSON Schema. The schema for each configuration file is stored in the corresponding Lambda function directory (e.g., `lambda/snowflake_extractor/config_schema_v2.json`).

## Default Value Management

Default values for configuration parameters are defined in the `config_manager` module and can be overridden by environment-specific configuration files.

## Configuration Storage

Configuration is stored in AWS SSM Parameter Store with the following naming convention:

```
/{project_name}/{environment}/config/{config_name}
```

For example:

```
/snowflake-aws-pipeline/dev/config/snowflake_extraction
```

Sensitive configuration values are stored in AWS SSM Parameter Store as SecureString parameters with the following naming convention:

```
/{project_name}/{environment}/secure-config/{config_name}
```

## Configuration Loading

Configuration is loaded in Lambda functions using the `ConfigLoader` utility class:

```python
from utils.config_loader import ConfigLoader

# Initialize configuration loader
config_loader = ConfigLoader(project_name, environment)

# Load configuration with schema validation
config = config_loader.load_config_with_defaults(
    "snowflake_extraction",
    default_config,
    config_schema
)
```

## Adding New Configuration

To add a new configuration file:

1. Create a new JSON file in the environment-specific directories
2. Define a JSON Schema for validation
3. Update the `config_manager` module to include the new configuration
4. Update the Lambda function to load the new configuration

## Environment-Specific Configuration

The configuration management system supports environment-specific configuration for the following environments:

- `dev`: Development environment
- `staging`: Staging environment
- `prod`: Production environment

Each environment can have different configuration values for the same parameters.

## Secure Configuration

Sensitive configuration values (e.g., passwords, API keys) are stored in AWS SSM Parameter Store as SecureString parameters and are encrypted using a KMS key.

## Configuration Deployment

Configuration is deployed using Terraform as part of the infrastructure deployment process. The `config_manager` module is responsible for creating the SSM parameters and validating the configuration.

## Configuration Validation

Configuration is validated during deployment using the `validate_config.sh` script. The script validates the configuration against the defined constraints and fails the deployment if the validation fails.

## Best Practices

1. **Use environment-specific configuration**: Define different configuration values for different environments
2. **Define default values**: Always define default values for configuration parameters
3. **Validate configuration**: Always validate configuration parameters against a schema
4. **Document configuration**: Always document configuration parameters
5. **Use secure storage**: Store sensitive configuration values in AWS SSM Parameter Store as SecureString parameters
6. **Use version control**: Store configuration files in version control
7. **Use parameter validation**: Validate configuration parameters during deployment
8. **Use configuration loading utilities**: Use the `ConfigLoader` utility class to load configuration in Lambda functions
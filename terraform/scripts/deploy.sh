#!/bin/bash

set -e

ENV=$1

if [ -z "$ENV" ]; then
  echo "Usage: ./deploy.sh <environment>"
  exit 1
fi

# Validate environment
if [[ "$ENV" != "dev" && "$ENV" != "staging" && "$ENV" != "prod" ]]; then
  echo "Error: Environment must be one of: dev, staging, prod"
  exit 1
fi

echo "Deploying to $ENV environment..."

# Validate configuration files
echo "Validating configuration files..."

# Check if jq is installed
if ! command -v jq &> /dev/null; then
  echo "Error: jq is required for configuration validation"
  echo "Install with: brew install jq"
  exit 1
fi

# Validate Snowflake extraction configuration
SNOWFLAKE_CONFIG_FILE="../config/$ENV/snowflake_extraction.json"
if [ -f "$SNOWFLAKE_CONFIG_FILE" ]; then
  echo "Validating $SNOWFLAKE_CONFIG_FILE..."
  
  # Basic JSON validation
  if ! jq . "$SNOWFLAKE_CONFIG_FILE" > /dev/null; then
    echo "Error: Invalid JSON in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  # Check required fields
  if ! jq -e '.batch_size' "$SNOWFLAKE_CONFIG_FILE" > /dev/null; then
    echo "Error: batch_size is required in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  if ! jq -e '.max_batches' "$SNOWFLAKE_CONFIG_FILE" > /dev/null; then
    echo "Error: max_batches is required in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  if ! jq -e '.max_retries' "$SNOWFLAKE_CONFIG_FILE" > /dev/null; then
    echo "Error: max_retries is required in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  if ! jq -e '.output_format' "$SNOWFLAKE_CONFIG_FILE" > /dev/null; then
    echo "Error: output_format is required in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  if ! jq -e '.queries' "$SNOWFLAKE_CONFIG_FILE" > /dev/null; then
    echo "Error: queries is required in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  # Validate batch_size
  BATCH_SIZE=$(jq -r '.batch_size' "$SNOWFLAKE_CONFIG_FILE")
  if [ "$BATCH_SIZE" -lt 1 ] || [ "$BATCH_SIZE" -gt 100000 ]; then
    echo "Error: batch_size must be between 1 and 100000 in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  # Validate max_batches
  MAX_BATCHES=$(jq -r '.max_batches' "$SNOWFLAKE_CONFIG_FILE")
  if [ "$MAX_BATCHES" -lt 1 ] || [ "$MAX_BATCHES" -gt 1000 ]; then
    echo "Error: max_batches must be between 1 and 1000 in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  # Validate max_retries
  MAX_RETRIES=$(jq -r '.max_retries' "$SNOWFLAKE_CONFIG_FILE")
  if [ "$MAX_RETRIES" -lt 0 ] || [ "$MAX_RETRIES" -gt 10 ]; then
    echo "Error: max_retries must be between 0 and 10 in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  # Validate output_format
  OUTPUT_FORMAT=$(jq -r '.output_format' "$SNOWFLAKE_CONFIG_FILE")
  if [ "$OUTPUT_FORMAT" != "parquet" ] && [ "$OUTPUT_FORMAT" != "json" ]; then
    echo "Error: output_format must be either 'parquet' or 'json' in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  # Validate queries
  QUERIES_COUNT=$(jq '.queries | length' "$SNOWFLAKE_CONFIG_FILE")
  if [ "$QUERIES_COUNT" -lt 1 ]; then
    echo "Error: At least one query is required in $SNOWFLAKE_CONFIG_FILE"
    exit 1
  fi
  
  # Validate each query
  for i in $(seq 0 $(($QUERIES_COUNT - 1))); do
    QUERY=$(jq -r ".queries[$i]" "$SNOWFLAKE_CONFIG_FILE")
    
    # Check required fields
    if ! echo "$QUERY" | jq -e '.name' > /dev/null; then
      echo "Error: name is required for query $i in $SNOWFLAKE_CONFIG_FILE"
      exit 1
    fi
    
    if ! echo "$QUERY" | jq -e '.sql' > /dev/null; then
      echo "Error: sql is required for query $i in $SNOWFLAKE_CONFIG_FILE"
      exit 1
    fi
  done
  
  echo "Configuration validation passed for $SNOWFLAKE_CONFIG_FILE"
else
  echo "Warning: $SNOWFLAKE_CONFIG_FILE not found, using default configuration"
fi

echo "All configuration files validated successfully"

# Initialize Terraform
echo "Initializing Terraform..."
terraform init -backend-config=backend-$ENV.hcl

# Plan Terraform changes
echo "Planning Terraform changes..."
terraform plan -var-file=terraform.tfvars.$ENV

# Apply Terraform changes
echo "Applying Terraform changes..."
terraform apply -auto-approve -var-file=terraform.tfvars.$ENV

echo "Deployment to $ENV environment completed successfully"
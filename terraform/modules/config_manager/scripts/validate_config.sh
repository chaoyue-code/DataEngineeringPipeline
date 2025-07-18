#!/bin/bash

# Configuration validation script
# This script validates the configuration JSON against schema requirements

set -e

CONFIG_JSON=$1

if [ -z "$CONFIG_JSON" ]; then
  echo "Error: No configuration JSON provided"
  exit 1
fi

# Function to validate configuration
validate_config() {
  local config="$1"
  
  # Extract sections for validation
  local snowflake_extraction=$(echo "$config" | jq -r '.snowflake_extraction // {}')
  local glue_jobs=$(echo "$config" | jq -r '.glue_jobs // {}')
  local lambda_functions=$(echo "$config" | jq -r '.lambda_functions // {}')
  local sagemaker=$(echo "$config" | jq -r '.sagemaker // {}')
  local monitoring=$(echo "$config" | jq -r '.monitoring // {}')
  
  # Validate Snowflake extraction configuration
  validate_snowflake_extraction "$snowflake_extraction"
  
  # Validate Glue jobs configuration
  validate_glue_jobs "$glue_jobs"
  
  # Validate Lambda functions configuration
  validate_lambda_functions "$lambda_functions"
  
  # Validate SageMaker configuration
  validate_sagemaker "$sagemaker"
  
  # Validate monitoring configuration
  validate_monitoring "$monitoring"
  
  echo "Configuration validation passed"
}

validate_snowflake_extraction() {
  local config="$1"
  
  # Check batch_size
  local batch_size=$(echo "$config" | jq -r '.batch_size')
  if [ "$batch_size" -lt 1 ] || [ "$batch_size" -gt 100000 ]; then
    echo "Error: batch_size must be between 1 and 100000"
    exit 1
  fi
  
  # Check max_batches
  local max_batches=$(echo "$config" | jq -r '.max_batches')
  if [ "$max_batches" -lt 1 ] || [ "$max_batches" -gt 1000 ]; then
    echo "Error: max_batches must be between 1 and 1000"
    exit 1
  fi
  
  # Check max_retries
  local max_retries=$(echo "$config" | jq -r '.max_retries')
  if [ "$max_retries" -lt 0 ] || [ "$max_retries" -gt 10 ]; then
    echo "Error: max_retries must be between 0 and 10"
    exit 1
  fi
  
  # Check output_format
  local output_format=$(echo "$config" | jq -r '.output_format')
  if [ "$output_format" != "parquet" ] && [ "$output_format" != "json" ]; then
    echo "Error: output_format must be either 'parquet' or 'json'"
    exit 1
  fi
}

validate_glue_jobs() {
  local config="$1"
  
  # Check bronze_to_silver configuration
  local bronze_to_silver=$(echo "$config" | jq -r '.bronze_to_silver // {}')
  
  local timeout_minutes=$(echo "$bronze_to_silver" | jq -r '.timeout_minutes')
  if [ "$timeout_minutes" -lt 1 ] || [ "$timeout_minutes" -gt 720 ]; then
    echo "Error: bronze_to_silver.timeout_minutes must be between 1 and 720"
    exit 1
  fi
  
  local max_retries=$(echo "$bronze_to_silver" | jq -r '.max_retries')
  if [ "$max_retries" -lt 0 ] || [ "$max_retries" -gt 10 ]; then
    echo "Error: bronze_to_silver.max_retries must be between 0 and 10"
    exit 1
  fi
  
  # Check silver_to_gold configuration
  local silver_to_gold=$(echo "$config" | jq -r '.silver_to_gold // {}')
  
  local timeout_minutes=$(echo "$silver_to_gold" | jq -r '.timeout_minutes')
  if [ "$timeout_minutes" -lt 1 ] || [ "$timeout_minutes" -gt 720 ]; then
    echo "Error: silver_to_gold.timeout_minutes must be between 1 and 720"
    exit 1
  fi
  
  local max_retries=$(echo "$silver_to_gold" | jq -r '.max_retries')
  if [ "$max_retries" -lt 0 ] || [ "$max_retries" -gt 10 ]; then
    echo "Error: silver_to_gold.max_retries must be between 0 and 10"
    exit 1
  fi
}

validate_lambda_functions() {
  local config="$1"
  
  # Validate each Lambda function configuration
  for func in $(echo "$config" | jq -r 'keys[]'); do
    local func_config=$(echo "$config" | jq -r ".[\"$func\"]")
    
    local memory_size=$(echo "$func_config" | jq -r '.memory_size')
    if [ "$memory_size" -lt 128 ] || [ "$memory_size" -gt 10240 ]; then
      echo "Error: $func.memory_size must be between 128 and 10240"
      exit 1
    fi
    
    local timeout=$(echo "$func_config" | jq -r '.timeout')
    if [ "$timeout" -lt 1 ] || [ "$timeout" -gt 900 ]; then
      echo "Error: $func.timeout must be between 1 and 900"
      exit 1
    fi
  done
}

validate_sagemaker() {
  local config="$1"
  
  # Validate instance types (simplified check)
  local training_instance_type=$(echo "$config" | jq -r '.training_instance_type')
  if [[ ! "$training_instance_type" =~ ^ml\. ]]; then
    echo "Error: training_instance_type must start with 'ml.'"
    exit 1
  fi
  
  local inference_instance_type=$(echo "$config" | jq -r '.inference_instance_type')
  if [[ ! "$inference_instance_type" =~ ^ml\. ]]; then
    echo "Error: inference_instance_type must start with 'ml.'"
    exit 1
  fi
  
  # Validate auto-scaling configuration
  local endpoint_auto_scaling=$(echo "$config" | jq -r '.endpoint_auto_scaling // {}')
  
  local min_capacity=$(echo "$endpoint_auto_scaling" | jq -r '.min_capacity')
  if [ "$min_capacity" -lt 1 ]; then
    echo "Error: endpoint_auto_scaling.min_capacity must be at least 1"
    exit 1
  fi
  
  local max_capacity=$(echo "$endpoint_auto_scaling" | jq -r '.max_capacity')
  if [ "$max_capacity" -lt "$min_capacity" ]; then
    echo "Error: endpoint_auto_scaling.max_capacity must be greater than or equal to min_capacity"
    exit 1
  fi
}

validate_monitoring() {
  local config="$1"
  
  # Validate alarm_evaluation_periods
  local alarm_evaluation_periods=$(echo "$config" | jq -r '.alarm_evaluation_periods')
  if [ "$alarm_evaluation_periods" -lt 1 ] || [ "$alarm_evaluation_periods" -gt 10 ]; then
    echo "Error: alarm_evaluation_periods must be between 1 and 10"
    exit 1
  fi
  
  # Validate lambda_error_threshold
  local lambda_error_threshold=$(echo "$config" | jq -r '.lambda_error_threshold')
  if [ "$lambda_error_threshold" -lt 1 ]; then
    echo "Error: lambda_error_threshold must be at least 1"
    exit 1
  fi
  
  # Validate data_quality_threshold
  local data_quality_threshold=$(echo "$config" | jq -r '.data_quality_threshold')
  if (( $(echo "$data_quality_threshold < 0.0 || $data_quality_threshold > 1.0" | bc -l) )); then
    echo "Error: data_quality_threshold must be between 0.0 and 1.0"
    exit 1
  fi
}

# Run validation
validate_config "$CONFIG_JSON"
#!/bin/bash

# Configuration Management Utility Script
# This script helps manage configuration files across environments

set -e

# Default values
ACTION=""
CONFIG_TYPE=""
SOURCE_ENV=""
TARGET_ENV=""
CONFIG_FILE=""

# Display usage information
usage() {
  echo "Configuration Management Utility"
  echo ""
  echo "Usage: $0 [options]"
  echo ""
  echo "Options:"
  echo "  -a, --action ACTION      Action to perform (copy, validate, show)"
  echo "  -t, --type CONFIG_TYPE   Configuration type (snowflake_extraction, etc.)"
  echo "  -s, --source ENV         Source environment (dev, staging, prod)"
  echo "  -d, --target ENV         Target environment (dev, staging, prod)"
  echo "  -f, --file FILE          Path to configuration file (for import action)"
  echo "  -h, --help               Display this help message"
  echo ""
  echo "Examples:"
  echo "  $0 --action copy --type snowflake_extraction --source dev --target staging"
  echo "  $0 --action validate --type snowflake_extraction --source dev"
  echo "  $0 --action show --type snowflake_extraction --source dev"
  echo ""
  exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -a|--action)
      ACTION="$2"
      shift
      shift
      ;;
    -t|--type)
      CONFIG_TYPE="$2"
      shift
      shift
      ;;
    -s|--source)
      SOURCE_ENV="$2"
      shift
      shift
      ;;
    -d|--target)
      TARGET_ENV="$2"
      shift
      shift
      ;;
    -f|--file)
      CONFIG_FILE="$2"
      shift
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown option: $1"
      usage
      ;;
  esac
done

# Validate environment
validate_env() {
  local env=$1
  if [[ "$env" != "dev" && "$env" != "staging" && "$env" != "prod" ]]; then
    echo "Error: Environment must be one of: dev, staging, prod"
    exit 1
  fi
}

# Validate configuration type
validate_config_type() {
  local config_type=$1
  if [[ -z "$config_type" ]]; then
    echo "Error: Configuration type is required"
    exit 1
  fi
}

# Validate configuration file
validate_config_file() {
  local config_file=$1
  local config_type=$2
  
  echo "Validating configuration file: $config_file"
  
  # Check if file exists
  if [[ ! -f "$config_file" ]]; then
    echo "Error: Configuration file not found: $config_file"
    exit 1
  fi
  
  # Check if jq is installed
  if ! command -v jq &> /dev/null; then
    echo "Error: jq is required for configuration validation"
    echo "Install with: brew install jq"
    exit 1
  fi
  
  # Basic JSON validation
  if ! jq . "$config_file" > /dev/null; then
    echo "Error: Invalid JSON in $config_file"
    exit 1
  fi
  
  # Specific validation based on config type
  if [[ "$config_type" == "snowflake_extraction" ]]; then
    # Check required fields
    if ! jq -e '.batch_size' "$config_file" > /dev/null; then
      echo "Error: batch_size is required in $config_file"
      exit 1
    fi
    
    if ! jq -e '.max_batches' "$config_file" > /dev/null; then
      echo "Error: max_batches is required in $config_file"
      exit 1
    fi
    
    if ! jq -e '.max_retries' "$config_file" > /dev/null; then
      echo "Error: max_retries is required in $config_file"
      exit 1
    fi
    
    if ! jq -e '.output_format' "$config_file" > /dev/null; then
      echo "Error: output_format is required in $config_file"
      exit 1
    fi
    
    if ! jq -e '.queries' "$config_file" > /dev/null; then
      echo "Error: queries is required in $config_file"
      exit 1
    fi
    
    # Validate batch_size
    BATCH_SIZE=$(jq -r '.batch_size' "$config_file")
    if [ "$BATCH_SIZE" -lt 1 ] || [ "$BATCH_SIZE" -gt 100000 ]; then
      echo "Error: batch_size must be between 1 and 100000 in $config_file"
      exit 1
    fi
    
    # Validate max_batches
    MAX_BATCHES=$(jq -r '.max_batches' "$config_file")
    if [ "$MAX_BATCHES" -lt 1 ] || [ "$MAX_BATCHES" -gt 1000 ]; then
      echo "Error: max_batches must be between 1 and 1000 in $config_file"
      exit 1
    fi
    
    # Validate max_retries
    MAX_RETRIES=$(jq -r '.max_retries' "$config_file")
    if [ "$MAX_RETRIES" -lt 0 ] || [ "$MAX_RETRIES" -gt 10 ]; then
      echo "Error: max_retries must be between 0 and 10 in $config_file"
      exit 1
    fi
    
    # Validate output_format
    OUTPUT_FORMAT=$(jq -r '.output_format' "$config_file")
    if [ "$OUTPUT_FORMAT" != "parquet" ] && [ "$OUTPUT_FORMAT" != "json" ]; then
      echo "Error: output_format must be either 'parquet' or 'json' in $config_file"
      exit 1
    fi
    
    # Validate queries
    QUERIES_COUNT=$(jq '.queries | length' "$config_file")
    if [ "$QUERIES_COUNT" -lt 1 ]; then
      echo "Error: At least one query is required in $config_file"
      exit 1
    fi
    
    # Validate each query
    for i in $(seq 0 $(($QUERIES_COUNT - 1))); do
      QUERY=$(jq -r ".queries[$i]" "$config_file")
      
      # Check required fields
      if ! echo "$QUERY" | jq -e '.name' > /dev/null; then
        echo "Error: name is required for query $i in $config_file"
        exit 1
      fi
      
      if ! echo "$QUERY" | jq -e '.sql' > /dev/null; then
        echo "Error: sql is required for query $i in $config_file"
        exit 1
      fi
    done
  fi
  
  echo "Configuration validation passed for $config_file"
}

# Copy configuration from source to target environment
copy_config() {
  local source_env=$1
  local target_env=$2
  local config_type=$3
  
  validate_env "$source_env"
  validate_env "$target_env"
  validate_config_type "$config_type"
  
  local source_file="../config/$source_env/$config_type.json"
  local target_file="../config/$target_env/$config_type.json"
  
  if [[ ! -f "$source_file" ]]; then
    echo "Error: Source configuration file not found: $source_file"
    exit 1
  fi
  
  # Create target directory if it doesn't exist
  mkdir -p "../config/$target_env"
  
  # Copy configuration file
  cp "$source_file" "$target_file"
  
  echo "Configuration copied from $source_file to $target_file"
}

# Show configuration
show_config() {
  local env=$1
  local config_type=$2
  
  validate_env "$env"
  validate_config_type "$config_type"
  
  local config_file="../config/$env/$config_type.json"
  
  if [[ ! -f "$config_file" ]]; then
    echo "Error: Configuration file not found: $config_file"
    exit 1
  fi
  
  # Check if jq is installed
  if ! command -v jq &> /dev/null; then
    echo "Error: jq is required for showing configuration"
    echo "Install with: brew install jq"
    exit 1
  fi
  
  # Show configuration
  echo "Configuration for $config_type in $env environment:"
  echo ""
  jq . "$config_file"
}

# Import configuration from file
import_config() {
  local env=$1
  local config_type=$2
  local config_file=$3
  
  validate_env "$env"
  validate_config_type "$config_type"
  
  if [[ -z "$config_file" ]]; then
    echo "Error: Configuration file is required for import action"
    exit 1
  fi
  
  if [[ ! -f "$config_file" ]]; then
    echo "Error: Configuration file not found: $config_file"
    exit 1
  fi
  
  # Validate configuration file
  validate_config_file "$config_file" "$config_type"
  
  # Create target directory if it doesn't exist
  mkdir -p "../config/$env"
  
  # Copy configuration file
  cp "$config_file" "../config/$env/$config_type.json"
  
  echo "Configuration imported from $config_file to ../config/$env/$config_type.json"
}

# Main logic
if [[ -z "$ACTION" ]]; then
  echo "Error: Action is required"
  usage
fi

case "$ACTION" in
  copy)
    if [[ -z "$SOURCE_ENV" || -z "$TARGET_ENV" || -z "$CONFIG_TYPE" ]]; then
      echo "Error: Source environment, target environment, and configuration type are required for copy action"
      usage
    fi
    copy_config "$SOURCE_ENV" "$TARGET_ENV" "$CONFIG_TYPE"
    ;;
  validate)
    if [[ -z "$SOURCE_ENV" || -z "$CONFIG_TYPE" ]]; then
      echo "Error: Source environment and configuration type are required for validate action"
      usage
    fi
    validate_config_file "../config/$SOURCE_ENV/$CONFIG_TYPE.json" "$CONFIG_TYPE"
    ;;
  show)
    if [[ -z "$SOURCE_ENV" || -z "$CONFIG_TYPE" ]]; then
      echo "Error: Source environment and configuration type are required for show action"
      usage
    fi
    show_config "$SOURCE_ENV" "$CONFIG_TYPE"
    ;;
  import)
    if [[ -z "$TARGET_ENV" || -z "$CONFIG_TYPE" || -z "$CONFIG_FILE" ]]; then
      echo "Error: Target environment, configuration type, and configuration file are required for import action"
      usage
    fi
    import_config "$TARGET_ENV" "$CONFIG_TYPE" "$CONFIG_FILE"
    ;;
  *)
    echo "Error: Unknown action: $ACTION"
    usage
    ;;
esac

exit 0
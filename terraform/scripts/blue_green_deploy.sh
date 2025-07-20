#!/bin/bash
# Blue-Green Deployment Script for Zero-Downtime Updates
# This script implements a blue-green deployment strategy for AWS resources

set -e

# Parse command line arguments
ENV=$1
COMPONENT=$2

if [ -z "$ENV" ] || [ -z "$COMPONENT" ]; then
  echo "Usage: ./blue_green_deploy.sh <environment> <component>"
  echo "  environment: dev, staging, prod"
  echo "  component: lambda, api, sagemaker"
  exit 1
fi

# Validate environment
if [[ "$ENV" != "dev" && "$ENV" != "staging" && "$ENV" != "prod" ]]; then
  echo "Error: Environment must be one of: dev, staging, prod"
  exit 1
fi

# Validate component
if [[ "$COMPONENT" != "lambda" && "$COMPONENT" != "api" && "$COMPONENT" != "sagemaker" ]]; then
  echo "Error: Component must be one of: lambda, api, sagemaker"
  exit 1
fi

echo "Starting blue-green deployment for $COMPONENT in $ENV environment..."

# Set AWS region based on environment
case "$ENV" in
  "dev")
    AWS_REGION="us-east-1"
    ;;
  "staging")
    AWS_REGION="us-east-1"
    ;;
  "prod")
    AWS_REGION="us-east-1"
    ;;
esac

# Export AWS region for AWS CLI
export AWS_DEFAULT_REGION=$AWS_REGION

# Function to check deployment health
check_health() {
  local component=$1
  local version=$2
  local max_retries=10
  local retry_count=0
  local health_check_passed=false

  echo "Checking health of $component version $version..."

  while [ $retry_count -lt $max_retries ]; do
    case "$component" in
      "lambda")
        # For Lambda, invoke the function with a test event and check the response
        RESPONSE=$(aws lambda invoke --function-name "$component-$ENV-$version" \
          --payload '{"action": "health_check"}' /tmp/lambda-output.json 2>&1)
        
        if echo "$RESPONSE" | grep -q "StatusCode: 200"; then
          health_check_passed=true
          break
        fi
        ;;
      "api")
        # For API Gateway, call the health check endpoint
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
          "https://$component-$ENV-$version.execute-api.$AWS_REGION.amazonaws.com/health")
        
        if [ "$RESPONSE" == "200" ]; then
          health_check_passed=true
          break
        fi
        ;;
      "sagemaker")
        # For SageMaker, check the endpoint status
        RESPONSE=$(aws sagemaker describe-endpoint \
          --endpoint-name "$component-$ENV-$version" \
          --query "EndpointStatus" --output text)
        
        if [ "$RESPONSE" == "InService" ]; then
          health_check_passed=true
          break
        fi
        ;;
    esac

    echo "Health check attempt $((retry_count+1))/$max_retries failed, retrying in 10 seconds..."
    sleep 10
    retry_count=$((retry_count+1))
  done

  if [ "$health_check_passed" = true ]; then
    echo "Health check passed for $component version $version"
    return 0
  else
    echo "Health check failed for $component version $version after $max_retries attempts"
    return 1
  fi
}

# Function to get current active version (blue or green)
get_current_version() {
  local component=$1
  
  case "$component" in
    "lambda")
      # For Lambda, check the alias pointing to the current version
      CURRENT_VERSION=$(aws lambda get-alias \
        --function-name "$component-$ENV" \
        --name current \
        --query "FunctionVersion" --output text)
      ;;
    "api")
      # For API Gateway, check the current stage
      CURRENT_VERSION=$(aws apigateway get-stage \
        --rest-api-id $(aws apigateway get-rest-apis --query "items[?name=='$component-$ENV'].id" --output text) \
        --stage-name current \
        --query "variables.version" --output text)
      ;;
    "sagemaker")
      # For SageMaker, check the endpoint configuration
      CURRENT_VERSION=$(aws sagemaker describe-endpoint \
        --endpoint-name "$component-$ENV" \
        --query "EndpointConfigName" --output text | grep -o -E 'blue|green')
      ;;
  esac
  
  echo $CURRENT_VERSION
}

# Function to deploy new version
deploy_new_version() {
  local component=$1
  local current_version=$2
  local new_version
  
  # Determine new version
  if [ "$current_version" == "blue" ]; then
    new_version="green"
  else
    new_version="blue"
  fi
  
  echo "Deploying new $new_version version for $component..."
  
  case "$component" in
    "lambda")
      # For Lambda, deploy new version and update the alias
      aws lambda update-function-code \
        --function-name "$component-$ENV-$new_version" \
        --s3-bucket "deployment-artifacts-$ENV" \
        --s3-key "$component/latest.zip"
      
      # Wait for the function to be updated
      aws lambda wait function-updated \
        --function-name "$component-$ENV-$new_version"
      ;;
    "api")
      # For API Gateway, deploy new version to the stage
      aws apigateway create-deployment \
        --rest-api-id $(aws apigateway get-rest-apis --query "items[?name=='$component-$ENV'].id" --output text) \
        --stage-name $new_version \
        --variables version=$new_version
      ;;
    "sagemaker")
      # For SageMaker, create new endpoint configuration and update endpoint
      aws sagemaker create-endpoint-config \
        --endpoint-config-name "$component-$ENV-$new_version-config" \
        --production-variants "VariantName=default,ModelName=$component-$ENV-latest,InitialInstanceCount=1,InstanceType=ml.m5.large"
      
      aws sagemaker update-endpoint \
        --endpoint-name "$component-$ENV" \
        --endpoint-config-name "$component-$ENV-$new_version-config"
      
      # Wait for the endpoint to be updated
      aws sagemaker wait endpoint-in-service \
        --endpoint-name "$component-$ENV"
      ;;
  esac
  
  echo "$new_version version deployed for $component"
  return 0
}

# Function to switch traffic to new version
switch_traffic() {
  local component=$1
  local new_version=$2
  local traffic_percentage=$3
  
  echo "Switching $traffic_percentage% traffic to $new_version version for $component..."
  
  case "$component" in
    "lambda")
      # For Lambda, update the routing configuration
      aws lambda update-alias \
        --function-name "$component-$ENV" \
        --name current \
        --function-version $new_version \
        --routing-config "AdditionalVersionWeights={$new_version=$traffic_percentage}"
      ;;
    "api")
      # For API Gateway, update the canary settings
      aws apigateway update-stage \
        --rest-api-id $(aws apigateway get-rest-apis --query "items[?name=='$component-$ENV'].id" --output text) \
        --stage-name current \
        --patch-operations "op=replace,path=/canarySettings/percentTraffic,value=$traffic_percentage"
      ;;
    "sagemaker")
      # For SageMaker, update the production variants
      aws sagemaker update-endpoint \
        --endpoint-name "$component-$ENV" \
        --endpoint-config-name "$component-$ENV-$new_version-config"
      ;;
  esac
  
  echo "Traffic switched to $new_version version for $component"
  return 0
}

# Function to finalize deployment
finalize_deployment() {
  local component=$1
  local new_version=$2
  
  echo "Finalizing deployment for $component..."
  
  case "$component" in
    "lambda")
      # For Lambda, update the alias to point to the new version
      aws lambda update-alias \
        --function-name "$component-$ENV" \
        --name current \
        --function-version $new_version \
        --routing-config "AdditionalVersionWeights={}"
      ;;
    "api")
      # For API Gateway, promote the canary
      aws apigateway update-stage \
        --rest-api-id $(aws apigateway get-rest-apis --query "items[?name=='$component-$ENV'].id" --output text) \
        --stage-name current \
        --patch-operations "op=replace,path=/canarySettings/percentTraffic,value=0"
      
      aws apigateway update-stage \
        --rest-api-id $(aws apigateway get-rest-apis --query "items[?name=='$component-$ENV'].id" --output text) \
        --stage-name current \
        --variables version=$new_version
      ;;
    "sagemaker")
      # For SageMaker, delete the old endpoint configuration
      local current_version
      if [ "$new_version" == "blue" ]; then
        current_version="green"
      else
        current_version="blue"
      fi
      
      aws sagemaker delete-endpoint-config \
        --endpoint-config-name "$component-$ENV-$current_version-config"
      ;;
  esac
  
  echo "Deployment finalized for $component"
  return 0
}

# Function to rollback deployment
rollback_deployment() {
  local component=$1
  local current_version=$2
  
  echo "Rolling back deployment for $component to $current_version version..."
  
  case "$component" in
    "lambda")
      # For Lambda, update the alias to point back to the current version
      aws lambda update-alias \
        --function-name "$component-$ENV" \
        --name current \
        --function-version $current_version \
        --routing-config "AdditionalVersionWeights={}"
      ;;
    "api")
      # For API Gateway, revert to the current stage
      aws apigateway update-stage \
        --rest-api-id $(aws apigateway get-rest-apis --query "items[?name=='$component-$ENV'].id" --output text) \
        --stage-name current \
        --patch-operations "op=replace,path=/canarySettings/percentTraffic,value=0"
      
      aws apigateway update-stage \
        --rest-api-id $(aws apigateway get-rest-apis --query "items[?name=='$component-$ENV'].id" --output text) \
        --stage-name current \
        --variables version=$current_version
      ;;
    "sagemaker")
      # For SageMaker, revert to the current endpoint configuration
      aws sagemaker update-endpoint \
        --endpoint-name "$component-$ENV" \
        --endpoint-config-name "$component-$ENV-$current_version-config"
      
      # Wait for the endpoint to be updated
      aws sagemaker wait endpoint-in-service \
        --endpoint-name "$component-$ENV"
      ;;
  esac
  
  echo "Rollback completed for $component"
  return 0
}

# Main deployment flow
echo "Starting blue-green deployment for $COMPONENT in $ENV environment..."

# Get current version
CURRENT_VERSION=$(get_current_version $COMPONENT)
echo "Current version is $CURRENT_VERSION"

# Determine new version
if [ "$CURRENT_VERSION" == "blue" ]; then
  NEW_VERSION="green"
else
  NEW_VERSION="blue"
fi
echo "New version will be $NEW_VERSION"

# Deploy new version
deploy_new_version $COMPONENT $CURRENT_VERSION
if [ $? -ne 0 ]; then
  echo "Failed to deploy new version, aborting deployment"
  exit 1
fi

# Check health of new version
check_health $COMPONENT $NEW_VERSION
if [ $? -ne 0 ]; then
  echo "Health check failed for new version, rolling back"
  rollback_deployment $COMPONENT $CURRENT_VERSION
  exit 1
fi

# Gradually shift traffic to new version
for PERCENTAGE in 10 25 50 75 100; do
  echo "Shifting $PERCENTAGE% of traffic to $NEW_VERSION version..."
  switch_traffic $COMPONENT $NEW_VERSION $PERCENTAGE
  
  # Wait for a short period to observe any issues
  sleep 30
  
  # Check health again
  check_health $COMPONENT $NEW_VERSION
  if [ $? -ne 0 ]; then
    echo "Health check failed after shifting $PERCENTAGE% traffic, rolling back"
    rollback_deployment $COMPONENT $CURRENT_VERSION
    exit 1
  fi
done

# Finalize deployment
finalize_deployment $COMPONENT $NEW_VERSION

echo "Blue-green deployment completed successfully for $COMPONENT in $ENV environment"
exit 0
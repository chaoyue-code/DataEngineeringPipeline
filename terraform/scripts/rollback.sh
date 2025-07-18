#!/bin/bash

set -e

ENV=$1

if [ -z "$ENV" ]; then
  echo "Usage: ./rollback.sh <environment>"
  exit 1
fi

# Validate environment
if [[ "$ENV" != "dev" && "$ENV" != "staging" && "$ENV" != "prod" ]]; then
  echo "Error: Environment must be one of: dev, staging, prod"
  exit 1
fi

echo "Rolling back $ENV environment..."

# Initialize Terraform
echo "Initializing Terraform..."
terraform init -backend-config=backend-$ENV.hcl

# Plan Terraform destroy
echo "Planning Terraform destroy..."
terraform plan -destroy -var-file=terraform.tfvars.$ENV

# Confirm rollback
read -p "Are you sure you want to roll back the $ENV environment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Rollback cancelled"
  exit 0
fi

# Apply Terraform destroy
echo "Applying Terraform destroy..."
terraform destroy -auto-approve -var-file=terraform.tfvars.$ENV

echo "Rollback of $ENV environment completed successfully"
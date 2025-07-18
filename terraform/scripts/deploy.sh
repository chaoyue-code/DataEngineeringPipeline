#!/bin/bash

set -e

ENV=$1

if [ -z "$ENV" ]; then
  echo "Usage: ./deploy.sh <environment>"
  exit 1
fi

terraform init -backend-config=backend-$ENV.hcl
terraform plan -var-file=terraform.tfvars.$ENV
terraform apply -auto-approve -var-file=terraform.tfvars.$ENV
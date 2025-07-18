#!/bin/bash

set -e

ENV=$1

if [ -z "$ENV" ]; then
  echo "Usage: ./rollback.sh <environment>"
  exit 1
fi

terraform init -backend-config=backend-$ENV.hcl
terraform destroy -auto-approve -var-file=terraform.tfvars.$ENV
# Backend configuration for development environment
bucket         = "snowflake-pipeline-terraform-state-dev"
key            = "dev/terraform.tfstate"
region         = "ap-southeast-2"
encrypt        = true
dynamodb_table = "terraform-state-lock-dev"
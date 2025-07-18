# Snowflake AWS Pipeline - Terraform Infrastructure

This directory contains the Terraform infrastructure code for the Snowflake AWS Pipeline project.

## Project Structure

```
terraform/
├── main.tf                    # Main Terraform configuration
├── variables.tf               # Global variable definitions
├── outputs.tf                 # Global output definitions
├── versions.tf                # Terraform and provider version constraints
├── backend.tf                 # Backend configuration template
├── backend-dev.hcl            # Development environment backend config
├── terraform.tfvars.example   # Example variables file
├── .tflint.hcl                # TFLint configuration
├── README.md                  # This file
├── scripts/                   # Utility scripts
│   ├── validate_terraform.sh  # Terraform validation script
│   ├── validate_env_config.py # Environment config validation
│   ├── deploy.sh              # Deployment script
│   └── rollback.sh            # Rollback script
├── tests/                     # Terraform tests
│   ├── go.mod                 # Go module file for Terratest
│   ├── storage_test.go        # Tests for storage module
│   ├── networking_test.go     # Tests for networking module
│   └── README.md              # Testing documentation
└── modules/                   # Terraform modules
    ├── networking/            # VPC, subnets, security groups
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── storage/               # S3 data lake and related storage
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── compute/               # Lambda functions, Glue jobs
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── ml/                    # SageMaker and ML infrastructure
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

## Modules Overview

### Networking Module
- Creates VPC with public, private, and database subnets
- Sets up NAT gateways for private subnet internet access
- Configures VPC endpoints for AWS services
- Manages security groups and network ACLs

### Storage Module
- Creates S3 data lake with medallion architecture (bronze/silver/gold)
- Implements lifecycle policies for cost optimization
- Sets up bucket encryption and access logging
- Configures event notifications for pipeline triggers

### Compute Module
- Manages Lambda execution roles and security groups
- Creates Glue catalog database and crawlers
- Sets up CloudWatch log groups for monitoring
- Configures IAM policies for service access

### ML Module
- Creates SageMaker domain and execution roles
- Sets up Feature Store for online/offline feature serving
- Manages KMS encryption for ML workloads
- Creates S3 bucket for ML artifacts

## Usage

### Prerequisites
1. AWS CLI configured with appropriate credentials
2. Terraform >= 1.0 installed
3. S3 bucket for Terraform state storage
4. DynamoDB table for state locking (optional but recommended)

### Deployment Steps

1. **Copy and customize variables file:**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your specific values
   ```

2. **Initialize Terraform:**
   ```bash
   terraform init -backend-config=backend-dev.hcl
   ```

3. **Plan the deployment:**
   ```bash
   terraform plan
   ```

4. **Apply the configuration:**
   ```bash
   terraform apply
   ```

### Environment-Specific Deployments

For different environments, create separate backend configuration files:
- `backend-dev.hcl` - Development environment
- `backend-staging.hcl` - Staging environment  
- `backend-prod.hcl` - Production environment

Initialize with the appropriate backend config:
```bash
terraform init -backend-config=backend-<environment>.hcl
```

## Configuration

### Required Variables
- `project_name` - Name of the project
- `environment` - Environment name (dev/staging/prod)
- `aws_region` - AWS region for deployment

### Optional Variables
See `variables.tf` for a complete list of configurable options including:
- VPC and subnet CIDR blocks
- Lambda function configurations
- Glue job settings
- SageMaker instance types
- Storage lifecycle policies

## Outputs

The Terraform configuration provides outputs for:
- VPC and subnet IDs
- S3 bucket names and ARNs
- IAM role ARNs
- SageMaker domain details
- Security group IDs

These outputs can be used by other Terraform configurations or application code.

## Security Considerations

- All S3 buckets have public access blocked by default
- Encryption is enabled for all storage resources
- IAM roles follow least privilege principle
- VPC endpoints are used for private AWS service access
- Security groups restrict network access appropriately

## Cost Optimization

- S3 lifecycle policies automatically transition data to cheaper storage classes
- NAT gateways can be disabled in development environments
- SageMaker instances use cost-effective instance types by default
- CloudWatch log retention is set to 14 days to control costs

## Validation and Testing

### Terraform Validation

The project includes a validation script that checks Terraform configurations for best practices and common issues:

```bash
./scripts/validate_terraform.sh
```

This script performs the following checks:
- Terraform formatting validation
- Terraform configuration validation
- TFLint checks for AWS best practices
- Detection of potential hardcoded secrets
- Verification of required files
- Validation of variable declarations

### Environment Configuration Validation

To validate environment-specific configurations:

```bash
./scripts/validate_env_config.py --env dev
./scripts/validate_env_config.py --env staging
./scripts/validate_env_config.py --env prod
```

This script ensures that:
- All required variables are defined for the environment
- Environment-specific values are appropriate (e.g., stricter security in production)
- Configuration values are consistent and valid

### Infrastructure Testing

The project uses [Terratest](https://terratest.gruntwork.io/) for infrastructure testing. To run the tests:

```bash
cd tests
go test -v ./...
```

Tests validate:
- Module configurations can be successfully applied
- Resources are created with correct properties
- Outputs match expected values
- Security configurations are properly applied

See the [tests/README.md](tests/README.md) file for more details on testing.

### CI/CD Integration

The validation and testing scripts are designed to be integrated into CI/CD pipelines:

1. Run `validate_terraform.sh` during the validation stage
2. Run `validate_env_config.py` for the target environment
3. Run Terratest tests for critical modules
4. Use `terraform plan` output for review
5. Apply changes only after approval
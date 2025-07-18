# Deployment Guide

This guide provides detailed instructions for deploying the Snowflake AWS Pipeline.

## Prerequisites

Before deploying the pipeline, ensure you have:

1. **AWS Account** with appropriate permissions
2. **Snowflake Account** with read access to source data
3. **Development Environment** with:
   - AWS CLI configured
   - Terraform >= 1.0
   - jq (for configuration validation)
   - Python 3.8+ (for utility scripts)

## Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/DataEngineeringPipeline.git
cd DataEngineeringPipeline
```

### 2. Configure AWS Credentials

```bash
aws configure
```

Ensure your AWS credentials have permissions to create:
- IAM roles and policies
- S3 buckets
- Lambda functions
- Glue jobs and crawlers
- SageMaker resources
- CloudWatch resources
- VPC and networking components

### 3. Configure Terraform Backend

Create an S3 bucket for Terraform state:

```bash
aws s3 mb s3://your-terraform-state-bucket
```

Create a DynamoDB table for state locking:

```bash
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

Update the backend configuration files (`backend-dev.hcl`, `backend-staging.hcl`, `backend-prod.hcl`) with your bucket and table names.

## Configuration

### 1. Environment-Specific Variables

Create environment-specific variable files:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars.dev
cp terraform/terraform.tfvars.example terraform/terraform.tfvars.staging
cp terraform/terraform.tfvars.example terraform/terraform.tfvars.prod
```

Edit each file with environment-specific values.

### 2. Snowflake Configuration

Create environment-specific Snowflake configuration files:

```bash
mkdir -p terraform/config/dev terraform/config/staging terraform/config/prod
cp lambda/snowflake_extractor/example_config.json terraform/config/dev/snowflake_extraction.json
```

Edit the configuration files with appropriate Snowflake connection details and queries.

### 3. Secrets Management

Create AWS Secrets Manager secrets for Snowflake credentials:

```bash
aws secretsmanager create-secret \
  --name snowflake/credentials/dev \
  --secret-string '{"user":"your-user","password":"your-password","account":"your-account","warehouse":"your-warehouse","role":"your-role"}'
```

Repeat for staging and production environments.

## Deployment Process

### 1. Development Environment

```bash
cd terraform
./scripts/deploy.sh dev
```

The script will:
1. Validate configuration files
2. Initialize Terraform with the dev backend
3. Plan the deployment
4. Apply the Terraform configuration

### 2. Staging Environment

After testing in development:

```bash
./scripts/deploy.sh staging
```

### 3. Production Environment

After validation in staging:

```bash
./scripts/deploy.sh prod
```

## Verification

After deployment, verify:

1. **S3 Buckets**: Check that all buckets are created with correct policies
2. **Lambda Functions**: Verify functions are deployed and configured
3. **Glue Resources**: Check that databases, tables, and crawlers are created
4. **IAM Roles**: Verify all roles have appropriate permissions
5. **CloudWatch**: Check that log groups and dashboards are created

Run a test extraction:

```bash
aws lambda invoke \
  --function-name snowflake-extractor-dev \
  --payload '{"test": true}' \
  response.json
```

## Rollback Procedure

If issues are encountered, roll back the deployment:

```bash
cd terraform
./scripts/rollback.sh dev
```

The script will:
1. Initialize Terraform with the appropriate backend
2. Plan the destroy operation
3. Confirm before proceeding
4. Destroy all resources created by Terraform

## Blue-Green Deployment

For zero-downtime updates to production:

1. Create a parallel "green" environment:
```bash
./scripts/deploy.sh prod-green
```

2. Test the green environment
3. Switch traffic from blue to green
4. Decommission the old blue environment

## Monitoring Deployment

Monitor the deployment process:

1. **CloudWatch Logs**: Check Lambda and Glue logs for errors
2. **CloudTrail**: Monitor API calls for resource creation
3. **CloudWatch Metrics**: Watch for resource utilization spikes

## Post-Deployment Tasks

After successful deployment:

1. **Configure Monitoring Alerts**: Set up CloudWatch alarms for critical metrics
2. **Schedule Crawlers**: Configure Glue crawler schedules
3. **Set Up Event Rules**: Configure EventBridge rules for pipeline orchestration
4. **Test End-to-End Flow**: Run a complete pipeline test
5. **Document Deployed Resources**: Update documentation with actual resource names and ARNs
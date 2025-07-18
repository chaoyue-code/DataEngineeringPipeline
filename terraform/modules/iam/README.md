# IAM Module for Snowflake AWS Pipeline

This module creates comprehensive IAM roles and policies for all services in the Snowflake AWS data pipeline, implementing least privilege access principles and proper cross-service access patterns.

## Overview

The IAM module provides service-specific IAM roles and policies for:

- **Lambda Functions**: Snowflake extractor, pipeline orchestrator, data quality monitor, notification handler
- **AWS Glue**: Service role for ETL jobs and crawler role for schema discovery
- **SageMaker**: Execution role for ML workloads and Feature Store role
- **EventBridge**: Role for event-driven orchestration
- **Step Functions**: Role for complex workflow orchestration
- **CloudWatch**: Role for monitoring and alerting
- **Cross-service Access**: S3 Lambda trigger role for event-driven processing

## Architecture

### Security Design Principles

1. **Least Privilege Access**: Each role has only the minimum permissions required for its specific function
2. **Service Isolation**: Separate roles for different services to limit blast radius
3. **Resource-Specific Permissions**: Policies are scoped to specific resources using ARN patterns
4. **Cross-Service Boundaries**: Proper trust relationships and resource-based policies
5. **Encryption Support**: KMS key management for enhanced security

### Role Structure

```
IAM Module
├── Lambda Roles
│   ├── Snowflake Extractor Role
│   ├── Pipeline Orchestrator Role
│   ├── Data Quality Monitor Role
│   └── Notification Handler Role
├── Glue Roles
│   ├── Service Role (ETL Jobs)
│   └── Crawler Role (Schema Discovery)
├── SageMaker Roles
│   ├── Execution Role (Training/Inference)
│   └── Feature Store Role
├── Orchestration Roles
│   ├── EventBridge Role
│   └── Step Functions Role
├── Monitoring Roles
│   └── CloudWatch Role
└── Cross-Service Roles
    └── S3 Lambda Trigger Role
```

## Usage

### Basic Usage

```hcl
module "iam" {
  source = "./modules/iam"

  project_name = "snowflake-aws-pipeline"
  environment  = "dev"

  # S3 Bucket ARNs for IAM policies
  data_lake_bucket_arn = "arn:aws:s3:::my-data-lake-bucket"
  sagemaker_bucket_arn = "arn:aws:s3:::my-sagemaker-bucket"

  # Security Configuration
  enable_kms_encryption = true
  enable_vpc_access     = true

  tags = {
    Project     = "snowflake-aws-pipeline"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
```

### Advanced Configuration

```hcl
module "iam" {
  source = "./modules/iam"

  project_name = "snowflake-aws-pipeline"
  environment  = "prod"

  # S3 Bucket ARNs
  data_lake_bucket_arn = module.storage.data_lake_bucket_arn
  sagemaker_bucket_arn = module.ml.sagemaker_artifacts_bucket_arn

  # Security Configuration
  enable_kms_encryption = true
  enable_vpc_access     = true

  # Cross-account access (if needed)
  enable_cross_account_access = true
  trusted_account_ids         = ["244653595735", "987654321098"]

  # Compliance settings
  enforce_mfa         = true
  session_duration    = 3600
  external_id         = "unique-external-id"

  # Custom policies (if needed)
  custom_lambda_policies = {
    additional_s3_access = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = ["s3:GetObject"]
          Resource = ["arn:aws:s3:::additional-bucket/*"]
        }
      ]
    })
  }

  tags = local.common_tags
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project | `string` | n/a | yes |
| environment | Environment name (dev, staging, prod) | `string` | n/a | yes |
| data_lake_bucket_arn | ARN of the data lake S3 bucket | `string` | n/a | yes |
| sagemaker_bucket_arn | ARN of the SageMaker artifacts S3 bucket | `string` | n/a | yes |
| enable_kms_encryption | Enable KMS encryption for IAM resources | `bool` | `true` | no |
| enable_vpc_access | Enable VPC access for Lambda functions | `bool` | `true` | no |
| enable_cross_account_access | Enable cross-account access patterns | `bool` | `false` | no |
| trusted_account_ids | List of trusted AWS account IDs | `list(string)` | `[]` | no |
| enforce_mfa | Enforce MFA for sensitive operations | `bool` | `false` | no |
| session_duration | Maximum session duration for assumed roles (seconds) | `number` | `3600` | no |
| tags | Common tags to apply to all resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| lambda_roles | Map of all Lambda role ARNs |
| glue_roles | Map of all Glue role ARNs |
| sagemaker_roles | Map of all SageMaker role ARNs |
| orchestration_roles | Map of all orchestration role ARNs |
| iam_summary | Summary of all IAM resources created |

### Lambda Roles Output Structure

```hcl
lambda_roles = {
  snowflake_extractor   = "arn:aws:iam::244653595735:role/project-env-snowflake-extractor-role"
  pipeline_orchestrator = "arn:aws:iam::244653595735:role/project-env-pipeline-orchestrator-role"
  data_quality_monitor  = "arn:aws:iam::244653595735:role/project-env-data-quality-monitor-role"
  notification_handler  = "arn:aws:iam::244653595735:role/project-env-notification-handler-role"
}
```

## IAM Policies and Permissions

### Lambda Function Permissions

#### Snowflake Extractor Lambda
- **S3**: Read/write access to bronze layer
- **Secrets Manager**: Access to Snowflake credentials
- **DynamoDB**: Watermark tracking
- **EventBridge**: Pipeline event publishing
- **CloudWatch**: Metrics and logging

#### Pipeline Orchestrator Lambda
- **Glue**: Start/stop jobs and crawlers
- **Step Functions**: Workflow execution
- **Lambda**: Function invocation
- **EventBridge**: Event publishing
- **DynamoDB**: State management

#### Data Quality Monitor Lambda
- **S3**: Read data, write quality reports
- **Glue**: Catalog access for schema validation
- **SNS**: Alert publishing
- **DynamoDB**: Quality metrics storage

#### Notification Handler Lambda
- **SNS**: Message publishing
- **SES**: Email sending
- **CloudWatch**: Metrics access
- **DynamoDB**: Notification tracking

### Glue Service Permissions

#### Service Role (ETL Jobs)
- **S3**: Full access to data lake buckets
- **Glue Catalog**: Database and table management
- **CloudWatch**: Logging and metrics
- **DynamoDB**: Job bookmarks

#### Crawler Role (Schema Discovery)
- **S3**: Read access to data lake buckets
- **Glue Catalog**: Schema discovery and updates
- **CloudWatch**: Logging

### SageMaker Permissions

#### Execution Role
- **S3**: Access to data lake and model artifacts
- **ECR**: Container image access
- **CloudWatch**: Logging and metrics
- **SageMaker**: Model management

#### Feature Store Role
- **S3**: Feature store data access
- **Glue Catalog**: Feature metadata management
- **SageMaker**: Feature store operations

## Security Features

### Encryption
- Optional KMS key creation for enhanced encryption
- Support for customer-managed keys
- Automatic key rotation policies

### Network Security
- VPC endpoint support for private connectivity
- Security group integration
- Network ACL compatibility

### Access Control
- Resource-based policies with specific ARN patterns
- Condition-based access controls
- Time-based session limits
- MFA enforcement options

### Compliance
- CloudTrail integration for audit logging
- AWS Config rule compatibility
- Cross-account access controls
- External ID support for enhanced security

## Best Practices

### Role Design
1. **Single Responsibility**: Each role serves a specific function
2. **Minimal Permissions**: Only necessary permissions are granted
3. **Resource Scoping**: Permissions are limited to specific resources
4. **Regular Review**: Roles should be reviewed and updated regularly

### Policy Management
1. **Version Control**: All policies are managed through Terraform
2. **Testing**: Policies should be tested in development environments
3. **Documentation**: All permissions are documented and justified
4. **Monitoring**: Access patterns should be monitored and audited

### Security Hardening
1. **Encryption**: Enable KMS encryption for sensitive operations
2. **Network Isolation**: Use VPC endpoints for private connectivity
3. **Access Logging**: Enable comprehensive access logging
4. **Regular Rotation**: Rotate credentials and keys regularly

## Troubleshooting

### Common Issues

#### Permission Denied Errors
```bash
# Check role trust relationships
aws iam get-role --role-name project-env-lambda-role

# Verify policy attachments
aws iam list-attached-role-policies --role-name project-env-lambda-role
```

#### Cross-Service Access Issues
```bash
# Verify resource-based policies
aws s3api get-bucket-policy --bucket data-lake-bucket

# Check EventBridge permissions
aws events describe-rule --name pipeline-rule
```

#### KMS Access Issues
```bash
# Check KMS key policy
aws kms describe-key --key-id alias/project-env-iam

# Verify key usage permissions
aws kms list-grants --key-id alias/project-env-iam
```

### Debugging Steps

1. **Verify Role Existence**: Ensure all roles are created successfully
2. **Check Policy Attachments**: Verify policies are attached to correct roles
3. **Test Permissions**: Use AWS CLI to test specific permissions
4. **Review CloudTrail**: Check access logs for permission denials
5. **Validate Resource ARNs**: Ensure ARN patterns match actual resources

## Integration with Other Modules

### Compute Module Integration
```hcl
module "compute" {
  source = "./modules/compute"
  
  # Pass IAM roles from IAM module
  lambda_roles = module.iam.lambda_roles
  glue_roles   = module.iam.glue_roles
  
  # Other configuration...
}
```

### ML Module Integration
```hcl
module "ml" {
  source = "./modules/ml"
  
  # Pass IAM roles from IAM module
  sagemaker_roles = module.iam.sagemaker_roles
  
  # Other configuration...
}
```

## Maintenance

### Regular Tasks
1. **Policy Review**: Quarterly review of all policies
2. **Access Audit**: Monthly audit of role usage
3. **Permission Cleanup**: Remove unused permissions
4. **Documentation Updates**: Keep documentation current

### Monitoring
- Set up CloudWatch alarms for unusual access patterns
- Monitor IAM policy usage through AWS Access Analyzer
- Regular security assessments using AWS Security Hub
- Automated compliance checking with AWS Config

## Contributing

When modifying this module:

1. **Test Changes**: Always test in development environment first
2. **Document Updates**: Update this README for any changes
3. **Security Review**: Have security team review permission changes
4. **Validation**: Run `terraform validate` and `terraform plan`
5. **Gradual Rollout**: Deploy changes gradually across environments

## License

This module is part of the Snowflake AWS Pipeline project and follows the same licensing terms.
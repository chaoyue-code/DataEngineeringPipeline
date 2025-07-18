# Troubleshooting Guide

This guide provides solutions for common issues encountered with the Snowflake AWS Pipeline.

## Table of Contents

1. [Data Extraction Issues](#data-extraction-issues)
2. [ETL Processing Issues](#etl-processing-issues)
3. [Infrastructure Deployment Issues](#infrastructure-deployment-issues)
4. [Performance Issues](#performance-issues)
5. [Security and Access Issues](#security-and-access-issues)
6. [Monitoring and Alerting Issues](#monitoring-and-alerting-issues)
7. [ML Pipeline Issues](#ml-pipeline-issues)

## Data Extraction Issues

### Snowflake Connection Failures

**Symptoms**:
- Lambda function fails with connection errors
- CloudWatch logs show "Could not connect to Snowflake"

**Possible Causes**:
1. Invalid credentials in Secrets Manager
2. Network connectivity issues
3. Snowflake account maintenance or downtime

**Resolution Steps**:
1. Verify Snowflake credentials in AWS Secrets Manager
   ```bash
   aws secretsmanager get-secret-value --secret-id snowflake/credentials/dev
   ```
2. Check Lambda VPC configuration and ensure proper network access
3. Test Snowflake connectivity from a similar network environment
4. Check Snowflake status page for any reported incidents

### Watermark Management Issues

**Symptoms**:
- Duplicate data extraction
- Missing data between extractions
- "Watermark not found" errors in logs

**Possible Causes**:
1. DynamoDB table missing or inaccessible
2. Watermark column not present in query results
3. Watermark format mismatch

**Resolution Steps**:
1. Verify DynamoDB table exists and is accessible
   ```bash
   aws dynamodb describe-table --table-name snowflake-watermarks
   ```
2. Check query configuration for proper watermark column specification
3. Verify watermark column exists in Snowflake table
4. Reset watermark for specific query if necessary
   ```bash
   aws dynamodb put-item \
     --table-name snowflake-watermarks \
     --item '{"query_name":{"S":"customers"},"watermark_value":{"S":"2023-01-01T00:00:00Z"}}'
   ```

### Data Validation Failures

**Symptoms**:
- Extraction completes but data is quarantined
- CloudWatch logs show validation errors

**Possible Causes**:
1. Schema changes in Snowflake source
2. Data quality issues in source data
3. Overly strict validation rules

**Resolution Steps**:
1. Compare current Snowflake schema with expected schema
2. Check validation rules in configuration
3. Examine quarantined data for patterns
4. Update validation rules if necessary

## ETL Processing Issues

### Glue Job Failures

**Symptoms**:
- Glue job shows "FAILED" status
- Error messages in Glue job logs

**Possible Causes**:
1. Insufficient resources (memory/DPUs)
2. Input data schema mismatch
3. Script errors or exceptions
4. S3 permission issues

**Resolution Steps**:
1. Check Glue job logs for specific error messages
   ```bash
   aws logs get-log-events \
     --log-group-name /aws-glue/jobs/error \
     --log-stream-name <job-run-id>
   ```
2. Increase DPUs if resource constraints are indicated
3. Verify input data schema using Glue Data Catalog
4. Test Glue script locally with sample data
5. Check IAM role permissions for Glue job

### Data Quality Check Failures

**Symptoms**:
- Data quality monitor Lambda reports failures
- Data does not progress to next stage

**Possible Causes**:
1. Source data quality issues
2. Transformation logic errors
3. Overly strict quality thresholds

**Resolution Steps**:
1. Examine data quality metrics in CloudWatch
2. Check specific quality check failures in logs
3. Analyze sample of failing data
4. Adjust quality thresholds if appropriate
5. Fix transformation logic if needed

### Glue Crawler Issues

**Symptoms**:
- Crawler fails or completes with warnings
- Schema not updated in Data Catalog
- Missing tables or columns

**Possible Causes**:
1. S3 permission issues
2. File format incompatibilities
3. Empty directories or zero-byte files

**Resolution Steps**:
1. Check crawler logs for specific errors
2. Verify S3 bucket permissions
3. Examine sample files for format issues
4. Check for empty directories or zero-byte files
5. Run crawler manually with increased log level

## Infrastructure Deployment Issues

### Terraform Apply Failures

**Symptoms**:
- `terraform apply` fails with error messages
- Resources partially created

**Possible Causes**:
1. Insufficient IAM permissions
2. Resource quota limits
3. Resource naming conflicts
4. Invalid configuration values

**Resolution Steps**:
1. Check Terraform logs for specific error messages
2. Verify IAM permissions for the deployment user
3. Check AWS service quotas in the target region
4. Ensure resource names are unique and valid
5. Validate configuration files using `terraform validate`

### Resource Dependency Issues

**Symptoms**:
- Resources created in wrong order
- Missing dependencies
- Timeout waiting for resource creation

**Possible Causes**:
1. Missing `depends_on` in Terraform
2. Race conditions in resource creation
3. Service-side delays

**Resolution Steps**:
1. Add explicit `depends_on` to resources
2. Increase timeouts in resource configurations
3. Apply resources in smaller batches
4. Check for circular dependencies

### State Management Issues

**Symptoms**:
- "State lock could not be acquired" errors
- State file conflicts
- Resources not tracked in state

**Possible Causes**:
1. Concurrent Terraform operations
2. Stale state locks
3. Corrupted state file

**Resolution Steps**:
1. Check for running Terraform operations
2. Force-unlock the state if necessary
   ```bash
   terraform force-unlock <LOCK_ID>
   ```
3. Check S3 bucket for state file integrity
4. Import existing resources into state if needed
   ```bash
   terraform import <RESOURCE_ADDRESS> <RESOURCE_ID>
   ```

## Performance Issues

### Slow Data Extraction

**Symptoms**:
- Extraction takes longer than expected
- Lambda timeouts during extraction

**Possible Causes**:
1. Inefficient SQL queries
2. Batch size too large
3. Snowflake performance issues
4. Network latency

**Resolution Steps**:
1. Optimize SQL queries with proper indexing
2. Reduce batch size in configuration
3. Monitor Snowflake query performance
4. Consider increasing Lambda timeout and memory
5. Use Lambda provisioned concurrency for cold start issues

### ETL Job Performance

**Symptoms**:
- Glue jobs take longer than expected
- High resource utilization

**Possible Causes**:
1. Insufficient DPUs
2. Inefficient transformations
3. Suboptimal partitioning
4. Data skew

**Resolution Steps**:
1. Increase Glue job DPUs
2. Optimize PySpark transformations
3. Improve partitioning strategy
4. Enable job metrics for detailed analysis
5. Use Glue job bookmarks to avoid reprocessing

### SageMaker Performance

**Symptoms**:
- Slow model training or inference
- Resource utilization spikes

**Possible Causes**:
1. Insufficient instance size
2. Inefficient model code
3. Data preprocessing bottlenecks

**Resolution Steps**:
1. Increase instance size or count
2. Profile model code for optimization
3. Optimize data preprocessing steps
4. Use SageMaker Debugger for detailed insights
5. Consider distributed training for large models

## Security and Access Issues

### IAM Permission Errors

**Symptoms**:
- "Access Denied" errors in logs
- Services unable to access resources

**Possible Causes**:
1. Missing IAM permissions
2. Incorrect resource policies
3. Resource-based policy conflicts

**Resolution Steps**:
1. Check CloudTrail for specific access denied events
2. Review IAM role policies for missing permissions
3. Check resource policies (S3 bucket policies, KMS key policies)
4. Use IAM Access Analyzer to identify issues
5. Apply least privilege principle when adding permissions

### Encryption Issues

**Symptoms**:
- "KMS access denied" errors
- Encryption/decryption failures

**Possible Causes**:
1. KMS key policy issues
2. Cross-account access problems
3. Key rotation or deletion

**Resolution Steps**:
1. Check KMS key policies
2. Verify service roles have kms:Decrypt permissions
3. Check for key rotation or deletion events
4. Use AWS Config to track key policy changes

### VPC Access Issues

**Symptoms**:
- Services unable to access external resources
- Timeouts when accessing AWS services

**Possible Causes**:
1. Missing VPC endpoints
2. Security group restrictions
3. NACL rules blocking traffic
4. Subnet routing issues

**Resolution Steps**:
1. Verify VPC endpoint configurations
2. Check security group inbound/outbound rules
3. Review NACL rules for blocked ports
4. Ensure proper subnet routing to NAT gateways or internet gateways
5. Test connectivity using VPC Reachability Analyzer

## Monitoring and Alerting Issues

### Missing Metrics

**Symptoms**:
- CloudWatch dashboards show no data
- Alerts not triggering as expected

**Possible Causes**:
1. Custom metrics not being published
2. Incorrect metric namespace or dimensions
3. Insufficient permissions

**Resolution Steps**:
1. Check Lambda/Glue logs for metric publication errors
2. Verify metric namespace and dimensions
3. Ensure IAM roles have cloudwatch:PutMetricData permission
4. Test metric publication manually

### Alert Notification Failures

**Symptoms**:
- Alerts trigger but notifications not received
- SNS delivery failures

**Possible Causes**:
1. SNS subscription issues
2. Email filtering or blocking
3. Endpoint unreachable

**Resolution Steps**:
1. Verify SNS topic subscriptions
2. Check email spam folders
3. Confirm endpoint availability
4. Check SNS delivery status in CloudWatch

### Log Aggregation Issues

**Symptoms**:
- Missing logs in CloudWatch
- Incomplete log data

**Possible Causes**:
1. Log retention settings too short
2. Log group throttling
3. Permission issues

**Resolution Steps**:
1. Check log group retention settings
2. Verify IAM permissions for logging
3. Check for throttling events in CloudWatch
4. Increase log group retention if needed#
# ML Pipeline Issues

### Feature Store Integration Failures

**Symptoms**:
- Feature ingestion Lambda fails
- Feature groups not created or updated
- "ValidationException" errors in CloudWatch logs

**Possible Causes**:
1. Schema mismatch between data and feature group definition
2. Missing required feature columns
3. Data type conversion issues
4. IAM permission issues for SageMaker Feature Store

**Resolution Steps**:
1. Compare data schema with feature group schema
   ```bash
   aws sagemaker describe-feature-group --feature-group-name <feature-group-name>
   ```
2. Check for missing required features in the source data
3. Verify data types match feature definitions
4. Ensure Lambda has proper IAM permissions for Feature Store operations
5. Check CloudWatch logs for specific error messages

### Model Training Failures

**Symptoms**:
- SageMaker training jobs fail
- "AlgorithmError" in training job status
- Unexpected model performance

**Possible Causes**:
1. Insufficient training data
2. Data quality issues
3. Hyperparameter configuration issues
4. Resource constraints (memory/disk)
5. Algorithm-specific errors

**Resolution Steps**:
1. Check training job logs for specific error messages
   ```bash
   aws sagemaker describe-training-job --training-job-name <job-name>
   aws logs get-log-events --log-group-name /aws/sagemaker/TrainingJobs --log-stream-name <job-name>/algo-1-<timestamp>
   ```
2. Validate training data quality and quantity
3. Review hyperparameter configurations
4. Increase instance size or storage if resource constraints are indicated
5. Test algorithm with smaller dataset locally if possible

### Model Deployment Issues

**Symptoms**:
- Endpoint creation fails
- Inference requests return errors
- Slow inference performance

**Possible Causes**:
1. Model artifact issues
2. Incompatible instance type
3. Missing dependencies in inference code
4. Serialization/deserialization errors
5. Endpoint configuration issues

**Resolution Steps**:
1. Verify model artifacts are correctly created and accessible
2. Check endpoint logs for specific error messages
   ```bash
   aws logs get-log-events --log-group-name /aws/sagemaker/Endpoints/<endpoint-name> --log-stream-name <variant-name>/algo-<instance-id>
   ```
3. Test inference code locally with the model artifacts
4. Ensure inference code handles serialization/deserialization correctly
5. Check instance type compatibility with model size and requirements
6. Consider using multi-model endpoints for smaller models

### A/B Testing Configuration Issues

**Symptoms**:
- Traffic not split according to configuration
- Variant performance metrics missing
- Endpoint update failures

**Possible Causes**:
1. Incorrect production variant configuration
2. Monitoring configuration issues
3. IAM permission issues for CloudWatch metrics
4. Endpoint update conflicts

**Resolution Steps**:
1. Verify production variant configuration
   ```bash
   aws sagemaker describe-endpoint-config --endpoint-config-name <config-name>
   ```
2. Check that all variants have proper model artifacts and instance types
3. Ensure CloudWatch metrics are being published for each variant
4. Use blue/green deployment for major endpoint configuration changes
5. Check IAM roles have proper permissions for metric publication
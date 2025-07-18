# CloudWatch Monitoring Module

This Terraform module creates comprehensive monitoring and alerting infrastructure for the Snowflake-AWS data pipeline. It provides dashboards, metrics, alarms, and log aggregation to ensure pipeline health and performance visibility.

## Features

### 📊 CloudWatch Dashboards
- **Pipeline Overview**: High-level metrics for Lambda functions, Glue jobs, S3 storage, and SageMaker endpoints
- **Data Quality**: Monitoring data quality scores, validation failures, and processing metrics
- **Cost & Performance**: Resource utilization, execution times, and cost estimates

### 🚨 Advanced Alerting & Notification System
- **Multi-tier SNS Topics**: Critical, Warning, Info, and Escalation alerts
- **Multiple Notification Channels**: Email, SMS, Slack, PagerDuty integration
- **Critical Pipeline Metrics**: Lambda failures, Glue job failures, data quality degradation
- **Performance Monitoring**: Duration thresholds, latency monitoring, cost tracking
- **Composite Alarms**: Complex monitoring scenarios with multiple conditions
- **Escalation Procedures**: Automated escalation for persistent issues
- **Auto-Recovery**: Automated recovery actions for common failure patterns

### 📈 Custom Metrics
- Data quality scores by pipeline stage
- Records processed per stage
- Validation failure counts by rule type
- Cost estimates by service
- Pipeline latency and throughput
- Memory utilization tracking

### 🔍 Log Aggregation & Analysis
- Centralized log groups for different pipeline components
- CloudWatch Insights queries for error analysis and performance trends
- Structured log streams for organized logging
- Custom metric filters for automated metric extraction

### 🔬 Advanced Monitoring
- **X-Ray Tracing**: Distributed tracing for pipeline components
- **Performance Monitoring**: Latency, memory usage, and throughput tracking
- **Cost Monitoring**: Daily cost thresholds and storage growth alerts
- **Automated Responses**: EventBridge-driven incident response

## Usage

### Basic Usage
```hcl
module "monitoring" {
  source = "./modules/monitoring"

  project_name = "my-pipeline"
  environment  = "prod"
  aws_region   = "us-east-1"

  # Lambda Function Names
  snowflake_extractor_function_name   = "snowflake-extractor"
  pipeline_orchestrator_function_name = "pipeline-orchestrator"
  data_quality_monitor_function_name  = "data-quality-monitor"

  # Glue Job Names
  bronze_to_silver_job_name = "bronze-to-silver-etl"
  silver_to_gold_job_name   = "silver-to-gold-etl"

  # S3 Resources
  data_lake_bucket_name = "my-data-lake-bucket"

  # SageMaker Resources (optional)
  sagemaker_endpoint_name = "ml-inference-endpoint"

  tags = {
    Environment = "prod"
    Team        = "data-engineering"
  }
}
```

### Advanced Usage with Full Alerting System
```hcl
module "monitoring" {
  source = "./modules/monitoring"

  project_name = "my-pipeline"
  environment  = "prod"
  aws_region   = "us-east-1"

  # Resource Names
  snowflake_extractor_function_name   = "snowflake-extractor"
  pipeline_orchestrator_function_name = "pipeline-orchestrator"
  data_quality_monitor_function_name  = "data-quality-monitor"
  bronze_to_silver_job_name = "bronze-to-silver-etl"
  silver_to_gold_job_name   = "silver-to-gold-etl"
  data_lake_bucket_name = "my-data-lake-bucket"
  sagemaker_endpoint_name = "ml-inference-endpoint"

  # ============================================================================
  # ALERTING CONFIGURATION
  # ============================================================================

  # Critical Alert Recipients (pipeline failures, data corruption)
  critical_alert_emails = [
    "oncall-engineer@company.com",
    "data-team-lead@company.com"
  ]
  critical_alert_phone_numbers = [
    "+1234567890"  # On-call engineer
  ]

  # Warning Alert Recipients (performance issues, cost thresholds)
  warning_alert_emails = [
    "data-team@company.com",
    "devops-team@company.com"
  ]

  # Info Notification Recipients (successful completions, reports)
  info_notification_emails = [
    "data-team@company.com"
  ]

  # Escalation Alert Recipients (persistent issues)
  escalation_alert_emails = [
    "engineering-manager@company.com"
  ]
  escalation_alert_phone_numbers = [
    "+1111111111"  # Engineering manager
  ]

  # Third-party Integrations
  slack_webhook_url = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
  pagerduty_endpoint = "https://events.pagerduty.com/integration/YOUR_KEY/enqueue"

  # ============================================================================
  # ALERTING THRESHOLDS
  # ============================================================================

  lambda_error_threshold        = 3
  lambda_duration_threshold_ms  = 60000  # 1 minute
  data_quality_threshold        = 0.85   # 85%
  s3_storage_threshold_bytes    = 2147483648000  # 2TB
  pipeline_latency_threshold_ms = 600000 # 10 minutes
  sagemaker_error_threshold     = 5
  daily_cost_threshold          = 200    # $200/day

  # ============================================================================
  # ESCALATION & AUTO-RECOVERY
  # ============================================================================

  escalation_threshold_minutes = 45  # Escalate after 45 minutes
  enable_auto_recovery        = true
  max_recovery_attempts       = 5    # Max 5 attempts per day

  # ============================================================================
  # MONITORING CONFIGURATION
  # ============================================================================

  log_retention_days         = 30
  enable_cost_monitoring     = true
  enable_xray_tracing       = true
  enable_detailed_monitoring = true

  tags = {
    Environment = "prod"
    Team        = "data-engineering"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| project_name | Name of the project for resource naming | `string` | n/a | yes |
| aws_region | AWS region for resources | `string` | n/a | yes |
| environment | Environment name (dev, staging, prod) | `string` | n/a | yes |
| snowflake_extractor_function_name | Name of the Snowflake extractor Lambda function | `string` | n/a | yes |
| pipeline_orchestrator_function_name | Name of the pipeline orchestrator Lambda function | `string` | n/a | yes |
| data_quality_monitor_function_name | Name of the data quality monitor Lambda function | `string` | n/a | yes |
| bronze_to_silver_job_name | Name of the bronze to silver Glue ETL job | `string` | n/a | yes |
| silver_to_gold_job_name | Name of the silver to gold Glue ETL job | `string` | n/a | yes |
| data_lake_bucket_name | Name of the S3 data lake bucket | `string` | n/a | yes |
| sagemaker_endpoint_name | Name of the SageMaker inference endpoint | `string` | `""` | no |
| critical_sns_topic_arn | ARN of SNS topic for critical alerts | `string` | `""` | no |
| warning_sns_topic_arn | ARN of SNS topic for warning alerts | `string` | `""` | no |
| info_sns_topic_arn | ARN of SNS topic for info notifications | `string` | `""` | no |
| log_retention_days | Number of days to retain CloudWatch logs | `number` | `30` | no |
| enable_cost_monitoring | Enable cost monitoring and alerting | `bool` | `true` | no |
| enable_xray_tracing | Enable AWS X-Ray tracing | `bool` | `true` | no |
| enable_detailed_monitoring | Enable detailed monitoring for all resources | `bool` | `true` | no |
| lambda_error_threshold | Threshold for Lambda error alarms | `number` | `5` | no |
| data_quality_threshold | Minimum acceptable data quality score | `number` | `0.8` | no |
| daily_cost_threshold | Daily cost threshold for alerts (USD) | `number` | `100` | no |
| lambda_duration_threshold_ms | Lambda duration threshold in milliseconds | `number` | `30000` | no |

## Outputs

| Name | Description |
|------|-------------|
| monitoring_dashboard_urls | URLs for all CloudWatch dashboards |
| monitoring_summary | Complete summary of all monitoring resources created |
| sns_topic_arns | ARNs of SNS topics for alerting |
| log_groups | Information about created log groups |
| alarms | Information about created CloudWatch alarms |
| xray_sampling_rule_arn | ARN of X-Ray sampling rule (if enabled) |

## Dashboard Details

### Pipeline Overview Dashboard
- **Lambda Metrics**: Duration, errors, invocations for all Lambda functions
- **Glue Metrics**: Task completion, failures, data throughput
- **S3 Metrics**: Storage size, object count
- **SageMaker Metrics**: Endpoint invocations, latency
- **Data Quality**: Quality scores by pipeline stage

### Data Quality Dashboard
- **Processing Metrics**: Records processed by stage
- **Validation Metrics**: Failure counts by validation rule
- **Error Logs**: Recent data quality errors with filtering

### Cost & Performance Dashboard
- **Execution Times**: Lambda and Glue job durations
- **Cost Estimates**: Daily costs by service
- **Resource Utilization**: Memory, CPU, and throughput metrics

## Custom Metrics

The module creates several custom CloudWatch metrics:

### Data Quality Metrics (`Pipeline/DataQuality`)
- `pipeline_data_quality_score`: Quality score by pipeline stage
- `pipeline_data_validation_failures`: Validation failures by rule type

### Processing Metrics (`Pipeline/Processing`)
- `pipeline_records_processed`: Records processed by stage
- `pipeline_stage_latency`: Processing latency by stage
- `pipeline_throughput`: Records per second by stage

### Performance Metrics (`Pipeline/Performance`)
- `pipeline_memory_utilization`: Memory usage by component
- `pipeline_stage_latency`: Processing time by stage

### Cost Metrics (`Pipeline/Cost`)
- `pipeline_cost_estimate`: Estimated costs by service

## Log Format Requirements

To leverage custom metrics, your application logs should follow these formats:

### Data Quality Score
```
2024-01-15T10:30:00Z request-123 bronze 0.95
```

### Records Processed
```
2024-01-15T10:30:00Z request-123 silver RECORDS_PROCESSED 1000
```

### Validation Failures
```
2024-01-15T10:30:00Z request-123 VALIDATION_FAILURE null_check 5
```

### Cost Estimates
```
2024-01-15T10:30:00Z request-123 COST_ESTIMATE lambda 12.50
```

### Performance Metrics
```
2024-01-15T10:30:00Z request-123 PIPELINE_LATENCY bronze 1500
2024-01-15T10:30:00Z request-123 MEMORY_USAGE extractor 512
2024-01-15T10:30:00Z request-123 THROUGHPUT silver 150
```

## Advanced Alerting System

The module implements a comprehensive 4-tier alerting system with escalation procedures and auto-recovery mechanisms.

### 🚨 Alert Tiers

#### Critical Alerts
- **Pipeline failures**: Lambda function failures, Glue job failures
- **Data corruption**: Data quality score below critical threshold
- **System outages**: SageMaker endpoint failures, composite health failures
- **Recipients**: On-call engineers, team leads
- **Channels**: Email, SMS, Slack, PagerDuty
- **Response Time**: Immediate

#### Warning Alerts  
- **Performance degradation**: High latency, duration thresholds exceeded
- **Resource issues**: Cost thresholds, storage growth
- **Quality issues**: Data quality degradation (non-critical)
- **Recipients**: Development teams, DevOps teams
- **Channels**: Email, Slack
- **Response Time**: Within business hours

#### Info Notifications
- **Successful operations**: Pipeline completions, recovery success
- **Scheduled reports**: Daily summaries, cost reports
- **Status updates**: Auto-recovery attempts, maintenance notifications
- **Recipients**: Stakeholders, business users
- **Channels**: Email
- **Response Time**: Informational only

#### Escalation Alerts
- **Persistent issues**: Alarms in ALARM state > threshold time
- **Auto-recovery failures**: Maximum recovery attempts reached
- **System-wide problems**: Multiple critical alarms triggered
- **Recipients**: Engineering managers, executives
- **Channels**: Email, SMS, PagerDuty
- **Response Time**: Immediate escalation

### 🔄 Escalation Procedures

#### Automatic Escalation
- **Trigger**: Critical alarms remain in ALARM state for > `escalation_threshold_minutes`
- **Process**: 
  1. Escalation Lambda monitors alarm duration
  2. Sends escalation notification to management
  3. Creates incident ticket (if integrated)
  4. Continues monitoring until resolved

#### Escalation Lambda Features
- Tracks alarm state duration using CloudWatch API
- Configurable escalation thresholds per alarm type
- Rich escalation messages with context and recommended actions
- Integration with external ticketing systems
- Audit trail of all escalation actions

### 🛠️ Auto-Recovery System

#### Recovery Actions
- **Lambda Failures**: Restart function by updating configuration
- **Glue Job Failures**: Start new job run with recovery parameters
- **Data Quality Issues**: Trigger validation rerun
- **Pipeline Health**: Comprehensive restart of failed components

#### Recovery Logic
- **Attempt Tracking**: Uses DynamoDB to track daily recovery attempts
- **Attempt Limits**: Configurable maximum attempts per day per alarm
- **Recovery Notifications**: Status updates on each recovery attempt
- **Failure Handling**: Escalates to manual intervention when max attempts reached

#### Auto-Recovery Lambda Features
- Intelligent failure pattern recognition
- Configurable recovery strategies per alarm type
- Recovery attempt rate limiting
- Comprehensive logging and audit trail
- Integration with monitoring dashboards

### 📊 Alerting Metrics

#### Critical Pipeline Metrics Monitored
- **Lambda Function Failure Rate**: Errors per time period
- **Lambda Function Duration**: Execution time thresholds
- **Glue Job Failures**: Failed task counts
- **Data Quality Degradation**: Quality score below threshold
- **S3 Storage Growth**: Critical storage thresholds
- **Pipeline Latency**: End-to-end processing time
- **SageMaker Endpoint Errors**: Inference failure rates
- **Daily Cost Thresholds**: Budget overrun alerts

#### Composite Alarms
- **Pipeline Health**: Combines multiple critical metrics
- **Performance Degradation**: Latency and duration metrics
- **Cost Optimization**: Storage and compute cost metrics

### 🔗 Third-Party Integrations

#### Slack Integration
- Real-time notifications to Slack channels
- Rich message formatting with action buttons
- Channel routing based on alert severity
- Thread management for related alerts

#### PagerDuty Integration
- Automatic incident creation for critical alerts
- Escalation policy integration
- Incident resolution tracking
- On-call schedule integration

#### Custom Webhooks
- Generic webhook support for any system
- Configurable payload formatting
- Retry logic with exponential backoff
- Authentication support (API keys, tokens)

### 📋 Alert Message Templates

#### Critical Alert Example
```
🚨 CRITICAL PIPELINE ALERT 🚨

Project: my-snowflake-pipeline
Alarm: lambda-failure-rate
State: ALARM
Timestamp: 2024-01-15T10:30:00Z

Description: Lambda function failure rate is too high
Reason: Threshold of 3 errors exceeded with 5 errors in 5 minutes

Recommended Actions:
1. Check Lambda function logs for error details
2. Verify Snowflake connectivity
3. Check AWS service health status
4. Review recent deployments

Dashboard: https://console.aws.amazon.com/cloudwatch/...
```

#### Escalation Alert Example
```
🚨 PIPELINE ESCALATION ALERT 🚨

Project: my-snowflake-pipeline
Alarm: pipeline-health
Duration: 45 minutes in ALARM state

This alarm has exceeded the escalation threshold and requires immediate attention.
Auto-recovery has been attempted 3 times without success.

Escalation Actions Required:
1. Assign incident owner
2. Initiate emergency response procedures
3. Consider manual intervention
4. Update stakeholders on status
```

### ⚙️ Configuration Examples

#### Basic Alerting Setup
```hcl
# Minimal alerting configuration
critical_alert_emails = ["oncall@company.com"]
warning_alert_emails  = ["team@company.com"]
```

#### Advanced Alerting Setup
```hcl
# Comprehensive alerting configuration
critical_alert_emails = [
  "oncall-engineer@company.com",
  "data-team-lead@company.com"
]

critical_alert_phone_numbers = [
  "+1234567890"  # On-call engineer
]

escalation_alert_emails = [
  "engineering-manager@company.com",
  "cto@company.com"
]

escalation_alert_phone_numbers = [
  "+1111111111"  # Engineering manager
]

# Third-party integrations
slack_webhook_url = "https://hooks.slack.com/services/..."
pagerduty_endpoint = "https://events.pagerduty.com/integration/..."

# Escalation timing
escalation_threshold_minutes = 30

# Auto-recovery settings
enable_auto_recovery = true
max_recovery_attempts = 3
```

## X-Ray Tracing

When enabled, X-Ray tracing provides:
- End-to-end request tracing
- Service map visualization
- Performance bottleneck identification
- Error root cause analysis

Configure your Lambda functions and other services to use X-Ray tracing for full visibility.

## Cost Monitoring

The module includes comprehensive cost monitoring:
- Daily cost threshold alerts
- Storage growth monitoring
- Resource utilization tracking
- Cost optimization recommendations

## Best Practices

1. **Log Formatting**: Use structured logging with consistent formats
2. **Metric Naming**: Follow CloudWatch naming conventions
3. **Alert Tuning**: Adjust thresholds based on your pipeline characteristics
4. **Dashboard Customization**: Modify dashboard widgets for your specific needs
5. **Cost Optimization**: Monitor and optimize based on cost alerts

## Troubleshooting

### Common Issues

1. **Missing Metrics**: Ensure log formats match the expected patterns
2. **Alarm False Positives**: Adjust thresholds based on baseline performance
3. **Dashboard Errors**: Verify all referenced resources exist
4. **SNS Delivery**: Check SNS topic subscriptions and permissions

### Debugging

Use CloudWatch Insights queries to troubleshoot:
- Error analysis query for recent errors
- Performance analysis for bottlenecks
- Data quality trends for quality issues

## Security Considerations

- SNS topics use encryption at rest
- CloudWatch logs support KMS encryption
- IAM roles follow least privilege principle
- VPC endpoints used for private connectivity

## Maintenance

- Regularly review and update alarm thresholds
- Archive old logs based on retention policies
- Monitor CloudWatch costs and optimize queries
- Update dashboard widgets as pipeline evolves
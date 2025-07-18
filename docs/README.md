# Snowflake AWS Pipeline Documentation

This directory contains comprehensive documentation for the Snowflake AWS Pipeline project.

## Documentation Structure

- **[Architecture](./architecture/README.md)**: System architecture diagrams and component descriptions
- **[Data Flow](./data_flow/README.md)**: Data flow diagrams and process descriptions
- **[Deployment](./deployment/README.md)**: Deployment guides and procedures
- **[Troubleshooting](./troubleshooting/README.md)**: Common issues and resolution steps
- **[Scripts](./scripts/README.md)**: Documentation generation and utility scripts

## Project Overview

The Snowflake AWS Pipeline is a comprehensive data pipeline that extracts data from Snowflake as the upstream source and processes it through AWS services including Glue, S3, Lambda, and SageMaker. The entire infrastructure is managed using Terraform for Infrastructure as Code (IaC) practices.

### Key Features

- **Automated Data Extraction**: Extract data from Snowflake using configurable SQL queries
- **Medallion Architecture**: Process data through bronze, silver, and gold layers
- **Event-Driven Processing**: Use AWS EventBridge and S3 events for pipeline orchestration
- **Machine Learning Integration**: Seamless integration with SageMaker for ML workloads
- **Infrastructure as Code**: All infrastructure managed through Terraform
- **Comprehensive Monitoring**: CloudWatch dashboards, metrics, and alerts

### Technology Stack

- **Data Source**: Snowflake
- **Storage**: Amazon S3
- **Compute**: AWS Lambda, AWS Glue
- **Machine Learning**: Amazon SageMaker
- **Orchestration**: AWS EventBridge, Step Functions
- **Monitoring**: CloudWatch, SNS
- **Infrastructure**: Terraform

## Getting Started

For new users, we recommend starting with the following documentation:

1. [Architecture Overview](./architecture/README.md)
2. [Deployment Guide](./deployment/README.md)
3. [Data Flow Overview](./data_flow/README.md)

## Contributing to Documentation

To contribute to this documentation:

1. Create a new branch from `main`
2. Make your changes
3. Submit a pull request

For automated documentation generation, see the [Scripts](./scripts/README.md) section.
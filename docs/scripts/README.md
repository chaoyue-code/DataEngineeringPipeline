# Documentation Scripts

This directory contains scripts for generating and maintaining documentation for the Snowflake AWS Pipeline project.

## Available Scripts

### `generate_docs.py`

This script automatically generates documentation from code and configuration files.

#### Features

- Extracts Lambda function documentation from docstrings
- Generates Terraform module documentation
- Documents configuration schemas and examples
- Creates resource relationship diagrams
- Produces Markdown documentation for all components

#### Usage

```bash
# Generate all documentation
python generate_docs.py --all

# Generate specific documentation
python generate_docs.py --lambda --terraform --config --diagram

# Generate only Lambda documentation
python generate_docs.py --lambda

# Generate only Terraform documentation
python generate_docs.py --terraform

# Generate only configuration schema documentation
python generate_docs.py --config

# Generate only resource diagram
python generate_docs.py --diagram
```

#### Requirements

- Python 3.8+
- PyYAML
- Markdown
- Graphviz (optional, for diagram generation)

Install requirements:

```bash
pip install pyyaml markdown
```

For diagram generation, install Graphviz:

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
apt-get install graphviz

# CentOS/RHEL
yum install graphviz
```

#### Output

The script generates documentation in the following directories:

- `docs/generated/lambda/` - Lambda function documentation
- `docs/generated/terraform/` - Terraform module documentation
- `docs/generated/config/` - Configuration schema documentation
- `docs/generated/diagrams/` - Resource relationship diagrams

## Adding New Documentation

To add new documentation scripts:

1. Create a new Python script in this directory
2. Add a description to this README
3. Ensure the script follows the project's coding standards
4. Add appropriate error handling and logging

## Best Practices

When writing documentation scripts:

1. Use docstrings for all functions and classes
2. Include usage examples in script headers
3. Provide clear error messages
4. Make scripts idempotent (can be run multiple times without side effects)
5. Support both automatic and manual documentation generation
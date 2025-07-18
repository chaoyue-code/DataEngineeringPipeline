# Generated Documentation

This directory contains automatically generated documentation for the Snowflake AWS Pipeline project.

## Directory Structure

- **[lambda/](./lambda/)**: Documentation for Lambda functions
- **[terraform/](./terraform/)**: Documentation for Terraform modules and resources
- **[config/](./config/)**: Documentation for configuration schemas
- **[diagrams/](./diagrams/)**: Resource relationship diagrams

## Generation Process

Documentation in this directory is automatically generated using the script at `../scripts/generate_docs.py`. This ensures that documentation stays in sync with the codebase.

### How to Generate Documentation

To regenerate all documentation:

```bash
cd ../scripts
python generate_docs.py --all
```

To generate specific documentation:

```bash
# Generate only Lambda documentation
python generate_docs.py --lambda-docs

# Generate only Terraform documentation
python generate_docs.py --terraform

# Generate only configuration schema documentation
python generate_docs.py --config

# Generate only resource diagrams
python generate_docs.py --diagram
```

## Documentation Updates

The documentation in this directory is automatically updated as part of the CI/CD pipeline. Manual updates to these files will be overwritten during the next documentation generation run.

For persistent documentation changes, update the source code comments or the documentation generation script.
# Terraform Testing

This directory contains tests for the Terraform modules using [Terratest](https://terratest.gruntwork.io/).

## Prerequisites

- Go 1.20 or later
- Terraform 1.0 or later
- AWS credentials configured

## Running Tests

To run all tests:

```bash
cd terraform/tests
go test -v ./...
```

To run a specific test:

```bash
cd terraform/tests
go test -v -run TestNetworkingModule
```

## Test Structure

The tests are organized by module:

- `storage_test.go`: Tests for the S3 storage module
- `networking_test.go`: Tests for the VPC networking module

## Test Methodology

Each test follows this general pattern:

1. Create a unique test name to avoid resource naming conflicts
2. Set up Terraform options with test-specific variables
3. Run `terraform init` and `terraform plan` to validate the configuration
4. Optionally run `terraform apply` to create real resources (commented out by default)
5. Validate outputs and resource properties
6. Run `terraform destroy` to clean up resources

## Adding New Tests

To add a new test for a module:

1. Create a new file named `<module_name>_test.go`
2. Import the required packages
3. Create a test function that follows the pattern above
4. Add any module-specific validations

## CI/CD Integration

These tests can be integrated into a CI/CD pipeline by:

1. Setting up Go and Terraform in the CI environment
2. Running `go test -v ./...` as part of the pipeline
3. Using AWS credentials provided by the CI system

## Best Practices

- Always use `defer terraform.Destroy()` to ensure resources are cleaned up
- Use random IDs to prevent naming conflicts
- Keep tests focused on a single module or functionality
- Use assertions to validate expected outcomes
package test

import (
	"fmt"
	"testing"

	"github.com/gruntwork-io/terratest/modules/random"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

// TestStorageModule tests the storage module
func TestStorageModule(t *testing.T) {
	t.Parallel()

	// Generate a random project name to prevent a naming conflict
	projectName := fmt.Sprintf("terratest-%s", random.UniqueId())
	environment := "test"

	// Construct the terraform options with default retryable errors
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Set the path to the Terraform code that will be tested
		TerraformDir: "../modules/storage",

		// Variables to pass to our Terraform code using -var options
		Vars: map[string]interface{}{
			"project_name":         projectName,
			"environment":          environment,
			"data_lake_bucket_name": fmt.Sprintf("test-bucket-%s", random.UniqueId()),
			"enable_versioning":    true,
			"enable_encryption":    true,
			"bronze_lifecycle_days": 30,
			"silver_lifecycle_days": 60,
			"gold_lifecycle_days":   90,
			"tags": map[string]string{
				"Terraform": "true",
				"Environment": "test",
			},
		},

		// Environment variables to set when running Terraform
		EnvVars: map[string]string{
			"AWS_DEFAULT_REGION": "ap-southeast-2",
		},
	})

	// At the end of the test, run `terraform destroy` to clean up any resources that were created
	defer terraform.Destroy(t, terraformOptions)

	// Run `terraform init` and `terraform plan` and fail the test if there are any errors
	terraform.InitAndPlan(t, terraformOptions)

	// Uncomment to actually apply the changes
	// Run `terraform apply` and fail the test if there are any errors
	// terraform.Apply(t, terraformOptions)

	// Run `terraform output` to get the values of output variables
	// bucketName := terraform.Output(t, terraformOptions, "data_lake_bucket_name")
	// bucketArn := terraform.Output(t, terraformOptions, "data_lake_bucket_arn")

	// Verify that the bucket name is correct
	// assert.Contains(t, bucketName, projectName)
	// assert.Contains(t, bucketArn, "arn:aws:s3")
}
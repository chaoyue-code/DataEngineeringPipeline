package test

import (
	"fmt"
	"testing"

	"github.com/gruntwork-io/terratest/modules/random"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

// TestNetworkingModule tests the networking module
func TestNetworkingModule(t *testing.T) {
	t.Parallel()

	// Generate a random project name to prevent a naming conflict
	projectName := fmt.Sprintf("terratest-%s", random.UniqueId())
	environment := "test"

	// Construct the terraform options with default retryable errors
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Set the path to the Terraform code that will be tested
		TerraformDir: "../modules/networking",

		// Variables to pass to our Terraform code using -var options
		Vars: map[string]interface{}{
			"project_name":        projectName,
			"environment":         environment,
			"vpc_cidr":            "10.0.0.0/16",
			"availability_zones":  []string{"ap-southeast-2a", "ap-southeast-2b"},
			"public_subnet_cidrs": []string{"10.0.1.0/24", "10.0.2.0/24"},
			"private_subnet_cidrs": []string{"10.0.10.0/24", "10.0.20.0/24"},
			"database_subnet_cidrs": []string{"10.0.30.0/24", "10.0.40.0/24"},
			"enable_nat_gateway":  true,
			"enable_vpn_gateway":  false,
			"enable_vpc_flow_logs": true,
			"flow_log_retention_days": 7,
			"enable_network_acls": true,
			"enable_vpc_endpoints": true,
			"vpc_endpoint_policy_restrictive": true,
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
	// vpcId := terraform.Output(t, terraformOptions, "vpc_id")
	// publicSubnetIds := terraform.OutputList(t, terraformOptions, "public_subnet_ids")
	// privateSubnetIds := terraform.OutputList(t, terraformOptions, "private_subnet_ids")
	// databaseSubnetIds := terraform.OutputList(t, terraformOptions, "database_subnet_ids")

	// Verify that the outputs are correct
	// assert.NotEmpty(t, vpcId)
	// assert.Equal(t, 2, len(publicSubnetIds))
	// assert.Equal(t, 2, len(privateSubnetIds))
	// assert.Equal(t, 2, len(databaseSubnetIds))
}
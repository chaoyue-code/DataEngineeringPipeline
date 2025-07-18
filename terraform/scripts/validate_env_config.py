#!/usr/bin/env python3
"""
Environment-specific configuration validation script for Terraform.

This script validates that environment-specific Terraform variable files
contain all required variables and that the values are appropriate for
the specified environment.
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Any, Set


def parse_terraform_vars(file_path: str) -> Dict[str, Any]:
    """Parse a Terraform .tfvars file into a dictionary."""
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist")
        sys.exit(1)

    with open(file_path, 'r') as f:
        content = f.read()

    # Simple parsing of key-value pairs
    vars_dict = {}
    
    # Handle simple key-value pairs
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Try to match key = value pattern
        match = re.match(r'^([a-zA-Z0-9_]+)\s*=\s*(.+)$', line)
        if match:
            key, value = match.groups()
            
            # Try to parse the value
            try:
                # Handle string values
                if value.startswith('"') and value.endswith('"'):
                    vars_dict[key] = value[1:-1]
                # Handle boolean values
                elif value.lower() == 'true':
                    vars_dict[key] = True
                elif value.lower() == 'false':
                    vars_dict[key] = False
                # Handle null values
                elif value.lower() == 'null':
                    vars_dict[key] = None
                # Handle numeric values
                elif value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                    vars_dict[key] = int(value)
                elif re.match(r'^-?\d+\.\d+$', value):
                    vars_dict[key] = float(value)
                # Handle lists and maps (simplified)
                elif value.startswith('[') or value.startswith('{'):
                    # This is a very simplified approach - for complex structures
                    # you might want to use a proper parser
                    vars_dict[key] = value
                else:
                    vars_dict[key] = value
            except Exception as e:
                print(f"Warning: Could not parse value for {key}: {e}")
                vars_dict[key] = value
    
    return vars_dict


def get_required_variables(variables_file: str) -> Set[str]:
    """Extract required variables from variables.tf file."""
    if not os.path.exists(variables_file):
        print(f"Error: Variables file {variables_file} does not exist")
        sys.exit(1)
        
    with open(variables_file, 'r') as f:
        content = f.read()
    
    # Find all variable declarations
    variable_blocks = re.findall(r'variable\s+"([^"]+)"\s+{([^}]+)}', content, re.DOTALL)
    
    required_vars = set()
    for var_name, var_block in variable_blocks:
        # Check if the variable has a default value
        has_default = re.search(r'default\s*=', var_block)
        if not has_default:
            required_vars.add(var_name)
    
    return required_vars


def validate_environment_config(env: str, vars_dict: Dict[str, Any]) -> List[str]:
    """Validate environment-specific configuration values."""
    errors = []
    
    # Ensure environment is set correctly
    if 'environment' in vars_dict and vars_dict['environment'] != env:
        errors.append(f"Environment variable is set to '{vars_dict['environment']}' but should be '{env}'")
    
    # Environment-specific validations
    if env == 'prod':
        # Production environment validations
        if 'enable_vpc_flow_logs' in vars_dict and not vars_dict['enable_vpc_flow_logs']:
            errors.append("VPC flow logs should be enabled in production")
        
        if 'enable_s3_encryption' in vars_dict and not vars_dict['enable_s3_encryption']:
            errors.append("S3 encryption should be enabled in production")
        
        if 'enable_key_rotation' in vars_dict and not vars_dict['enable_key_rotation']:
            errors.append("KMS key rotation should be enabled in production")
        
        if 'enable_detailed_monitoring' in vars_dict and not vars_dict['enable_detailed_monitoring']:
            errors.append("Detailed monitoring should be enabled in production")
        
        if 'lambda_memory_size' in vars_dict and vars_dict['lambda_memory_size'] < 512:
            errors.append(f"Lambda memory size ({vars_dict['lambda_memory_size']}) is too low for production")
        
    elif env == 'staging':
        # Staging environment validations
        if 'enable_vpc_flow_logs' in vars_dict and not vars_dict['enable_vpc_flow_logs']:
            errors.append("VPC flow logs should be enabled in staging")
        
        if 'enable_s3_encryption' in vars_dict and not vars_dict['enable_s3_encryption']:
            errors.append("S3 encryption should be enabled in staging")
    
    # Common validations for all environments
    if 'project_name' in vars_dict and not vars_dict['project_name']:
        errors.append("Project name cannot be empty")
    
    if 'aws_region' in vars_dict and not vars_dict['aws_region']:
        errors.append("AWS region cannot be empty")
    
    return errors


def main():
    parser = argparse.ArgumentParser(description='Validate Terraform environment configuration')
    parser.add_argument('--env', required=True, choices=['dev', 'staging', 'prod'],
                        help='Environment to validate (dev, staging, prod)')
    args = parser.parse_args()
    
    # Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    variables_file = os.path.join(base_dir, 'variables.tf')
    env_vars_file = os.path.join(base_dir, f'terraform.tfvars.{args.env}')
    
    # Get required variables
    required_vars = get_required_variables(variables_file)
    
    # Parse environment variables file
    env_vars = parse_terraform_vars(env_vars_file)
    
    # Check for missing required variables
    missing_vars = required_vars - set(env_vars.keys())
    if missing_vars:
        print(f"Error: Missing required variables in {env_vars_file}:")
        for var in missing_vars:
            print(f"  - {var}")
        sys.exit(1)
    
    # Validate environment-specific configuration
    validation_errors = validate_environment_config(args.env, env_vars)
    if validation_errors:
        print(f"Error: Invalid configuration for {args.env} environment:")
        for error in validation_errors:
            print(f"  - {error}")
        sys.exit(1)
    
    print(f"✅ Configuration for {args.env} environment is valid")
    sys.exit(0)


if __name__ == "__main__":
    main()
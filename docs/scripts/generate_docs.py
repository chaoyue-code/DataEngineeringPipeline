#!/usr/bin/env python3
"""
Documentation Generator for Snowflake AWS Pipeline

This script automatically generates documentation from code and configuration files.
It extracts:
- Lambda function documentation from docstrings
- Terraform module documentation
- Configuration schemas and examples
- Resource relationships and dependencies
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
import subprocess
import yaml
import markdown
from typing import Dict, List, Any, Optional

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCS_OUTPUT_DIR = PROJECT_ROOT / "docs"
LAMBDA_DIR = PROJECT_ROOT / "lambda"
TERRAFORM_DIR = PROJECT_ROOT / "terraform"
SAGEMAKER_DIR = PROJECT_ROOT / "sagemaker"


def extract_lambda_docs() -> Dict[str, Any]:
    """
    Extract documentation from Lambda function docstrings and comments.
    
    Returns:
        Dict containing Lambda function documentation
    """
    lambda_docs = {}
    
    # Iterate through all Lambda directories
    for lambda_path in LAMBDA_DIR.iterdir():
        if not lambda_path.is_dir():
            continue
            
        lambda_name = lambda_path.name
        lambda_docs[lambda_name] = {
            "name": lambda_name,
            "description": "",
            "parameters": [],
            "environment_variables": [],
            "returns": "",
            "dependencies": [],
            "example_events": []
        }
        
        # Check for main Lambda function file
        lambda_file = lambda_path / "lambda_function.py"
        if lambda_file.exists():
            with open(lambda_file, "r") as f:
                content = f.read()
                
                # Extract docstring
                docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                if docstring_match:
                    lambda_docs[lambda_name]["description"] = docstring_match.group(1).strip()
                
                # Extract environment variables
                env_vars = re.findall(r'os\.environ\.get\([\'"](\w+)[\'"]', content)
                for env_var in env_vars:
                    lambda_docs[lambda_name]["environment_variables"].append(env_var)
                
                # Extract dependencies from requirements.txt
                req_file = lambda_path / "requirements.txt"
                if req_file.exists():
                    with open(req_file, "r") as req:
                        dependencies = [line.strip() for line in req if line.strip() and not line.startswith("#")]
                        lambda_docs[lambda_name]["dependencies"] = dependencies
                
                # Look for example events
                example_file = lambda_path / "examples" / "events.json"
                if example_file.exists():
                    try:
                        with open(example_file, "r") as ex:
                            lambda_docs[lambda_name]["example_events"] = json.load(ex)
                    except json.JSONDecodeError:
                        print(f"Warning: Invalid JSON in {example_file}")
    
    return lambda_docs


def extract_terraform_docs() -> Dict[str, Any]:
    """
    Extract documentation from Terraform files.
    
    Returns:
        Dict containing Terraform module documentation
    """
    terraform_docs = {
        "modules": {},
        "variables": {},
        "outputs": {}
    }
    
    # Extract main variables
    variables_file = TERRAFORM_DIR / "variables.tf"
    if variables_file.exists():
        terraform_docs["variables"] = parse_terraform_variables(variables_file)
    
    # Extract main outputs
    outputs_file = TERRAFORM_DIR / "outputs.tf"
    if outputs_file.exists():
        terraform_docs["outputs"] = parse_terraform_outputs(outputs_file)
    
    # Extract module documentation
    modules_dir = TERRAFORM_DIR / "modules"
    if modules_dir.exists():
        for module_path in modules_dir.iterdir():
            if not module_path.is_dir():
                continue
                
            module_name = module_path.name
            terraform_docs["modules"][module_name] = {
                "name": module_name,
                "description": "",
                "variables": {},
                "outputs": {},
                "resources": []
            }
            
            # Extract module description from README
            readme_file = module_path / "README.md"
            if readme_file.exists():
                with open(readme_file, "r") as f:
                    content = f.read()
                    terraform_docs["modules"][module_name]["description"] = content
            
            # Extract module variables
            module_vars_file = module_path / "variables.tf"
            if module_vars_file.exists():
                terraform_docs["modules"][module_name]["variables"] = parse_terraform_variables(module_vars_file)
            
            # Extract module outputs
            module_outputs_file = module_path / "outputs.tf"
            if module_outputs_file.exists():
                terraform_docs["modules"][module_name]["outputs"] = parse_terraform_outputs(module_outputs_file)
            
            # Extract resources
            main_file = module_path / "main.tf"
            if main_file.exists():
                with open(main_file, "r") as f:
                    content = f.read()
                    # Simple regex to find resource blocks
                    resources = re.findall(r'resource\s+"(\w+)"\s+"(\w+)"\s+{', content)
                    terraform_docs["modules"][module_name]["resources"] = [
                        {"type": res[0], "name": res[1]} for res in resources
                    ]
    
    return terraform_docs


def parse_terraform_variables(file_path: Path) -> Dict[str, Any]:
    """
    Parse Terraform variables from a variables.tf file.
    
    Args:
        file_path: Path to the variables.tf file
        
    Returns:
        Dict of variable definitions
    """
    variables = {}
    
    with open(file_path, "r") as f:
        content = f.read()
        
        # Find all variable blocks
        var_blocks = re.findall(r'variable\s+"(\w+)"\s+{(.*?)}', content, re.DOTALL)
        
        for var_name, var_content in var_blocks:
            variables[var_name] = {
                "name": var_name,
                "type": None,
                "default": None,
                "description": None
            }
            
            # Extract type
            type_match = re.search(r'type\s+=\s+(\w+)', var_content)
            if type_match:
                variables[var_name]["type"] = type_match.group(1)
            
            # Extract default value
            default_match = re.search(r'default\s+=\s+(.*?)(\s+#|\s*$)', var_content, re.DOTALL)
            if default_match:
                variables[var_name]["default"] = default_match.group(1).strip()
            
            # Extract description
            desc_match = re.search(r'description\s+=\s+"(.*?)"', var_content)
            if desc_match:
                variables[var_name]["description"] = desc_match.group(1)
    
    return variables


def parse_terraform_outputs(file_path: Path) -> Dict[str, Any]:
    """
    Parse Terraform outputs from an outputs.tf file.
    
    Args:
        file_path: Path to the outputs.tf file
        
    Returns:
        Dict of output definitions
    """
    outputs = {}
    
    with open(file_path, "r") as f:
        content = f.read()
        
        # Find all output blocks
        output_blocks = re.findall(r'output\s+"(\w+)"\s+{(.*?)}', content, re.DOTALL)
        
        for output_name, output_content in output_blocks:
            outputs[output_name] = {
                "name": output_name,
                "description": None,
                "value": None
            }
            
            # Extract description
            desc_match = re.search(r'description\s+=\s+"(.*?)"', output_content)
            if desc_match:
                outputs[output_name]["description"] = desc_match.group(1)
            
            # Extract value
            value_match = re.search(r'value\s+=\s+(.*?)(\s+#|\s*$)', output_content, re.DOTALL)
            if value_match:
                outputs[output_name]["value"] = value_match.group(1).strip()
    
    return outputs


def extract_config_schemas() -> Dict[str, Any]:
    """
    Extract configuration schemas from the project.
    
    Returns:
        Dict containing configuration schemas
    """
    schemas = {}
    
    # Extract Snowflake extractor schema
    schema_file = LAMBDA_DIR / "snowflake_extractor" / "config_schema.json"
    if schema_file.exists():
        try:
            with open(schema_file, "r") as f:
                schemas["snowflake_extractor"] = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {schema_file}")
    
    # Extract example configs
    example_config = LAMBDA_DIR / "snowflake_extractor" / "example_config.json"
    if example_config.exists():
        try:
            with open(example_config, "r") as f:
                if "snowflake_extractor" not in schemas:
                    schemas["snowflake_extractor"] = {}
                schemas["snowflake_extractor"]["example"] = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {example_config}")
    
    return schemas


def generate_markdown_docs(lambda_docs: Dict[str, Any], terraform_docs: Dict[str, Any], 
                          config_schemas: Dict[str, Any]) -> None:
    """
    Generate Markdown documentation files from extracted data.
    
    Args:
        lambda_docs: Lambda function documentation
        terraform_docs: Terraform module documentation
        config_schemas: Configuration schemas
    """
    # Create output directories
    (DOCS_OUTPUT_DIR / "generated").mkdir(exist_ok=True)
    (DOCS_OUTPUT_DIR / "generated" / "lambda").mkdir(exist_ok=True)
    (DOCS_OUTPUT_DIR / "generated" / "terraform").mkdir(exist_ok=True)
    (DOCS_OUTPUT_DIR / "generated" / "config").mkdir(exist_ok=True)
    
    # Generate Lambda documentation
    with open(DOCS_OUTPUT_DIR / "generated" / "lambda" / "index.md", "w") as f:
        f.write("# Lambda Functions\n\n")
        f.write("This document provides documentation for all Lambda functions in the project.\n\n")
        
        for lambda_name, lambda_info in lambda_docs.items():
            f.write(f"## {lambda_name}\n\n")
            f.write(f"{lambda_info['description']}\n\n")
            
            if lambda_info["environment_variables"]:
                f.write("### Environment Variables\n\n")
                for env_var in lambda_info["environment_variables"]:
                    f.write(f"- `{env_var}`\n")
                f.write("\n")
            
            if lambda_info["dependencies"]:
                f.write("### Dependencies\n\n")
                for dep in lambda_info["dependencies"]:
                    f.write(f"- {dep}\n")
                f.write("\n")
            
            if lambda_info["example_events"]:
                f.write("### Example Events\n\n")
                f.write("```json\n")
                f.write(json.dumps(lambda_info["example_events"], indent=2))
                f.write("\n```\n\n")
            
            # Generate individual Lambda documentation
            with open(DOCS_OUTPUT_DIR / "generated" / "lambda" / f"{lambda_name}.md", "w") as lf:
                lf.write(f"# {lambda_name}\n\n")
                lf.write(f"{lambda_info['description']}\n\n")
                
                if lambda_info["environment_variables"]:
                    lf.write("## Environment Variables\n\n")
                    for env_var in lambda_info["environment_variables"]:
                        lf.write(f"- `{env_var}`\n")
                    lf.write("\n")
                
                if lambda_info["dependencies"]:
                    lf.write("## Dependencies\n\n")
                    for dep in lambda_info["dependencies"]:
                        lf.write(f"- {dep}\n")
                    lf.write("\n")
                
                if lambda_info["example_events"]:
                    lf.write("## Example Events\n\n")
                    lf.write("```json\n")
                    lf.write(json.dumps(lambda_info["example_events"], indent=2))
                    lf.write("\n```\n\n")
    
    # Generate Terraform documentation
    with open(DOCS_OUTPUT_DIR / "generated" / "terraform" / "index.md", "w") as f:
        f.write("# Terraform Infrastructure\n\n")
        f.write("This document provides documentation for the Terraform infrastructure.\n\n")
        
        f.write("## Variables\n\n")
        for var_name, var_info in terraform_docs["variables"].items():
            f.write(f"### {var_name}\n\n")
            if var_info["description"]:
                f.write(f"{var_info['description']}\n\n")
            f.write(f"- **Type**: {var_info['type'] or 'Not specified'}\n")
            if var_info["default"]:
                f.write(f"- **Default**: `{var_info['default']}`\n")
            f.write("\n")
        
        f.write("## Outputs\n\n")
        for output_name, output_info in terraform_docs["outputs"].items():
            f.write(f"### {output_name}\n\n")
            if output_info["description"]:
                f.write(f"{output_info['description']}\n\n")
            if output_info["value"]:
                f.write(f"- **Value**: `{output_info['value']}`\n")
            f.write("\n")
        
        f.write("## Modules\n\n")
        for module_name, module_info in terraform_docs["modules"].items():
            f.write(f"### {module_name}\n\n")
            
            # Generate individual module documentation
            with open(DOCS_OUTPUT_DIR / "generated" / "terraform" / f"{module_name}.md", "w") as mf:
                mf.write(f"# {module_name} Module\n\n")
                if module_info["description"]:
                    mf.write(f"{module_info['description']}\n\n")
                
                mf.write("## Variables\n\n")
                for var_name, var_info in module_info["variables"].items():
                    mf.write(f"### {var_name}\n\n")
                    if var_info["description"]:
                        mf.write(f"{var_info['description']}\n\n")
                    mf.write(f"- **Type**: {var_info['type'] or 'Not specified'}\n")
                    if var_info["default"]:
                        mf.write(f"- **Default**: `{var_info['default']}`\n")
                    mf.write("\n")
                
                mf.write("## Outputs\n\n")
                for output_name, output_info in module_info["outputs"].items():
                    mf.write(f"### {output_name}\n\n")
                    if output_info["description"]:
                        mf.write(f"{output_info['description']}\n\n")
                    if output_info["value"]:
                        mf.write(f"- **Value**: `{output_info['value']}`\n")
                    mf.write("\n")
                
                mf.write("## Resources\n\n")
                for resource in module_info["resources"]:
                    mf.write(f"- {resource['type']}.{resource['name']}\n")
                mf.write("\n")
    
    # Generate configuration schema documentation
    with open(DOCS_OUTPUT_DIR / "generated" / "config" / "index.md", "w") as f:
        f.write("# Configuration Schemas\n\n")
        f.write("This document provides documentation for configuration schemas used in the project.\n\n")
        
        for schema_name, schema_info in config_schemas.items():
            f.write(f"## {schema_name}\n\n")
            
            if "example" in schema_info:
                f.write("### Example Configuration\n\n")
                f.write("```json\n")
                f.write(json.dumps(schema_info["example"], indent=2))
                f.write("\n```\n\n")
            
            # Generate individual schema documentation
            with open(DOCS_OUTPUT_DIR / "generated" / "config" / f"{schema_name}.md", "w") as sf:
                sf.write(f"# {schema_name} Configuration Schema\n\n")
                
                if "example" in schema_info:
                    sf.write("## Example Configuration\n\n")
                    sf.write("```json\n")
                    sf.write(json.dumps(schema_info["example"], indent=2))
                    sf.write("\n```\n\n")
                
                if "properties" in schema_info:
                    sf.write("## Properties\n\n")
                    for prop_name, prop_info in schema_info["properties"].items():
                        sf.write(f"### {prop_name}\n\n")
                        if "description" in prop_info:
                            sf.write(f"{prop_info['description']}\n\n")
                        if "type" in prop_info:
                            sf.write(f"- **Type**: {prop_info['type']}\n")
                        if "default" in prop_info:
                            sf.write(f"- **Default**: `{prop_info['default']}`\n")
                        sf.write("\n")


def generate_resource_diagram() -> None:
    """
    Generate a resource relationship diagram using Terraform graph.
    """
    try:
        # Create output directory
        (DOCS_OUTPUT_DIR / "generated" / "diagrams").mkdir(exist_ok=True)
        
        # Run terraform graph
        result = subprocess.run(
            ["terraform", "graph"],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Save DOT file
            dot_file = DOCS_OUTPUT_DIR / "generated" / "diagrams" / "terraform_graph.dot"
            with open(dot_file, "w") as f:
                f.write(result.stdout)
            
            # Try to convert to SVG if graphviz is installed
            try:
                svg_file = DOCS_OUTPUT_DIR / "generated" / "diagrams" / "terraform_graph.svg"
                subprocess.run(
                    ["dot", "-Tsvg", "-o", str(svg_file), str(dot_file)],
                    check=True
                )
                print(f"Generated resource diagram at {svg_file}")
            except (subprocess.SubprocessError, FileNotFoundError):
                print("Graphviz not installed. DOT file generated but not converted to SVG.")
        else:
            print(f"Error generating Terraform graph: {result.stderr}")
    except Exception as e:
        print(f"Error generating resource diagram: {e}")


def main():
    parser = argparse.ArgumentParser(description="Generate documentation for Snowflake AWS Pipeline")
    parser.add_argument("--lambda-docs", dest="lambda_docs", action="store_true", help="Generate Lambda documentation")
    parser.add_argument("--terraform", action="store_true", help="Generate Terraform documentation")
    parser.add_argument("--config", action="store_true", help="Generate configuration schema documentation")
    parser.add_argument("--diagram", action="store_true", help="Generate resource diagram")
    parser.add_argument("--all", action="store_true", help="Generate all documentation")
    
    args = parser.parse_args()
    
    # If no specific options, generate all
    if not (args.lambda_docs or args.terraform or args.config or args.diagram):
        args.all = True
    
    if args.all or args.lambda_docs:
        print("Extracting Lambda documentation...")
        lambda_docs = extract_lambda_docs()
    else:
        lambda_docs = {}
    
    if args.all or args.terraform:
        print("Extracting Terraform documentation...")
        terraform_docs = extract_terraform_docs()
    else:
        terraform_docs = {"modules": {}, "variables": {}, "outputs": {}}
    
    if args.all or args.config:
        print("Extracting configuration schemas...")
        config_schemas = extract_config_schemas()
    else:
        config_schemas = {}
    
    print("Generating Markdown documentation...")
    generate_markdown_docs(lambda_docs, terraform_docs, config_schemas)
    
    if args.all or args.diagram:
        print("Generating resource diagram...")
        generate_resource_diagram()
    
    print(f"Documentation generated in {DOCS_OUTPUT_DIR}/generated/")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error generating documentation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
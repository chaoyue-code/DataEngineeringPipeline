#!/bin/bash
# Terraform Validation Script
# This script validates Terraform configurations and enforces best practices

set -e

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Define the root directory of the Terraform project
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo -e "${YELLOW}Starting Terraform validation for project...${NC}"

# Step 1: Check Terraform formatting
echo -e "\n${YELLOW}Checking Terraform formatting...${NC}"
terraform fmt -check -recursive
if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ Terraform formatting is correct${NC}"
else
  echo -e "${RED}✗ Terraform formatting issues found. Run 'terraform fmt -recursive' to fix.${NC}"
  exit 1
fi

# Step 2: Validate Terraform configuration
echo -e "\n${YELLOW}Validating Terraform configuration...${NC}"
terraform validate
if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ Terraform configuration is valid${NC}"
else
  echo -e "${RED}✗ Terraform configuration validation failed${NC}"
  exit 1
fi

# Step 3: Run tflint if installed
if command -v tflint &> /dev/null; then
  echo -e "\n${YELLOW}Running tflint...${NC}"
  tflint --recursive
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ tflint passed${NC}"
  else
    echo -e "${RED}✗ tflint found issues${NC}"
    exit 1
  fi
else
  echo -e "\n${YELLOW}tflint not installed, skipping linting${NC}"
  echo -e "Install with: brew install tflint (macOS) or https://github.com/terraform-linters/tflint#installation"
fi

# Step 4: Check for hardcoded secrets
echo -e "\n${YELLOW}Checking for hardcoded secrets...${NC}"
grep -r --include="*.tf" --include="*.tfvars" "password\|secret\|key\|token" --exclude="variables.tf" .
if [ $? -eq 0 ]; then
  echo -e "${RED}✗ Potential hardcoded secrets found. Please review the above files.${NC}"
  echo -e "${YELLOW}Note: This is a simple check and may include false positives.${NC}"
else
  echo -e "${GREEN}✓ No obvious hardcoded secrets found${NC}"
fi

# Step 5: Check for required files
echo -e "\n${YELLOW}Checking for required files...${NC}"
REQUIRED_FILES=("main.tf" "variables.tf" "outputs.tf" "versions.tf")
MISSING_FILES=0

for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo -e "${RED}✗ Required file $file is missing${NC}"
    MISSING_FILES=1
  fi
done

if [ $MISSING_FILES -eq 0 ]; then
  echo -e "${GREEN}✓ All required files are present${NC}"
else
  echo -e "${RED}✗ Some required files are missing${NC}"
  exit 1
fi

# Step 6: Check for proper variable declarations
echo -e "\n${YELLOW}Checking variable declarations...${NC}"
VARS_WITHOUT_DESCRIPTION=$(grep -l "variable" --include="*.tf" -r . | xargs grep -L "description" 2>/dev/null || true)

if [ -n "$VARS_WITHOUT_DESCRIPTION" ]; then
  echo -e "${RED}✗ Variables without descriptions found in:${NC}"
  echo "$VARS_WITHOUT_DESCRIPTION"
  exit 1
else
  echo -e "${GREEN}✓ All variables have descriptions${NC}"
fi

echo -e "\n${GREEN}All validation checks passed!${NC}"
exit 0
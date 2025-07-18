#!/usr/bin/env python3
"""
Access Review Lambda Function

This function performs automated access reviews for the Snowflake AWS Pipeline.
It analyzes IAM roles, policies, and access patterns to identify potential
security issues and compliance violations.
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Initialize AWS clients
iam_client = boto3.client('iam')
access_analyzer_client = boto3.client('accessanalyzer')
sns_client = boto3.client('sns')

# Environment variables
PROJECT_NAME = os.environ.get('PROJECT_NAME', '${project_name}')
ENVIRONMENT = os.environ.get('ENVIRONMENT', '${environment}')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def handler(event, context):
    """
    Main Lambda handler for access review automation.
    
    Args:
        event: Lambda event data
        context: Lambda context object
        
    Returns:
        dict: Response with status and findings
    """
    try:
        print(f"Starting access review for {PROJECT_NAME}-{ENVIRONMENT}")
        
        # Perform access review checks
        findings = []
        
        # 1. Review IAM roles and policies
        iam_findings = review_iam_roles()
        findings.extend(iam_findings)
        
        # 2. Check Access Analyzer findings
        analyzer_findings = check_access_analyzer()
        findings.extend(analyzer_findings)
        
        # 3. Review unused permissions
        unused_permissions = find_unused_permissions()
        findings.extend(unused_permissions)
        
        # 4. Check for overprivileged roles
        overprivileged_roles = check_overprivileged_roles()
        findings.extend(overprivileged_roles)
        
        # Generate report
        report = generate_access_review_report(findings)
        
        # Send notification if there are findings
        if findings:
            send_notification(report)
        
        print(f"Access review completed. Found {len(findings)} issues.")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Access review completed successfully',
                'findings_count': len(findings),
                'findings': findings[:10]  # Return first 10 findings
            })
        }
        
    except Exception as e:
        print(f"Error during access review: {str(e)}")
        
        # Send error notification
        error_message = f"Access review failed for {PROJECT_NAME}-{ENVIRONMENT}: {str(e)}"
        send_notification(error_message, severity='ERROR')
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def review_iam_roles() -> List[Dict[str, Any]]:
    """
    Review IAM roles for security issues.
    
    Returns:
        List of findings related to IAM roles
    """
    findings = []
    
    try:
        # Get all roles for the project
        paginator = iam_client.get_paginator('list_roles')
        
        for page in paginator.paginate():
            for role in page['Roles']:
                role_name = role['RoleName']
                
                # Only check roles for our project
                if not role_name.startswith(f"{PROJECT_NAME}-{ENVIRONMENT}"):
                    continue
                
                # Check role age
                role_age = datetime.now(role['CreateDate'].tzinfo) - role['CreateDate']
                if role_age.days > 90:
                    findings.append({
                        'type': 'OLD_ROLE',
                        'severity': 'LOW',
                        'resource': role_name,
                        'description': f"Role {role_name} is {role_age.days} days old and should be reviewed",
                        'recommendation': 'Review if this role is still needed'
                    })
                
                # Check for wildcard permissions
                wildcard_findings = check_wildcard_permissions(role_name)
                findings.extend(wildcard_findings)
                
                # Check for unused roles
                if is_role_unused(role_name):
                    findings.append({
                        'type': 'UNUSED_ROLE',
                        'severity': 'MEDIUM',
                        'resource': role_name,
                        'description': f"Role {role_name} appears to be unused",
                        'recommendation': 'Consider removing this role if it is no longer needed'
                    })
                    
    except Exception as e:
        print(f"Error reviewing IAM roles: {str(e)}")
        findings.append({
            'type': 'REVIEW_ERROR',
            'severity': 'HIGH',
            'resource': 'IAM_ROLES',
            'description': f"Failed to review IAM roles: {str(e)}",
            'recommendation': 'Manual review required'
        })
    
    return findings

def check_wildcard_permissions(role_name: str) -> List[Dict[str, Any]]:
    """
    Check for wildcard permissions in role policies.
    
    Args:
        role_name: Name of the IAM role to check
        
    Returns:
        List of findings related to wildcard permissions
    """
    findings = []
    
    try:
        # Get attached policies
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
        
        for policy in attached_policies['AttachedPolicies']:
            policy_arn = policy['PolicyArn']
            
            # Skip AWS managed policies (they're generally safe)
            if policy_arn.startswith('arn:aws:iam::aws:policy/'):
                continue
            
            # Get policy document
            policy_version = iam_client.get_policy(PolicyArn=policy_arn)
            policy_document = iam_client.get_policy_version(
                PolicyArn=policy_arn,
                VersionId=policy_version['Policy']['DefaultVersionId']
            )
            
            # Check for wildcard actions or resources
            for statement in policy_document['PolicyVersion']['Document'].get('Statement', []):
                actions = statement.get('Action', [])
                resources = statement.get('Resource', [])
                
                if isinstance(actions, str):
                    actions = [actions]
                if isinstance(resources, str):
                    resources = [resources]
                
                # Check for wildcard actions
                for action in actions:
                    if '*' in action and action != 'sts:AssumeRole':
                        findings.append({
                            'type': 'WILDCARD_ACTION',
                            'severity': 'HIGH',
                            'resource': f"{role_name}/{policy['PolicyName']}",
                            'description': f"Policy contains wildcard action: {action}",
                            'recommendation': 'Replace wildcard actions with specific permissions'
                        })
                
                # Check for wildcard resources
                for resource in resources:
                    if resource == '*':
                        findings.append({
                            'type': 'WILDCARD_RESOURCE',
                            'severity': 'MEDIUM',
                            'resource': f"{role_name}/{policy['PolicyName']}",
                            'description': f"Policy allows access to all resources (*)",
                            'recommendation': 'Restrict resource access to specific ARNs'
                        })
                        
    except Exception as e:
        print(f"Error checking wildcard permissions for {role_name}: {str(e)}")
    
    return findings

def is_role_unused(role_name: str) -> bool:
    """
    Check if a role appears to be unused based on last activity.
    
    Args:
        role_name: Name of the IAM role to check
        
    Returns:
        True if role appears unused, False otherwise
    """
    try:
        # Get role details
        role_details = iam_client.get_role(RoleName=role_name)
        
        # Check last used information
        role_last_used = role_details['Role'].get('RoleLastUsed')
        if not role_last_used:
            return True  # Never used
        
        last_used_date = role_last_used.get('LastUsedDate')
        if not last_used_date:
            return True  # No usage date
        
        # Consider unused if not used in last 30 days
        days_since_use = (datetime.now(last_used_date.tzinfo) - last_used_date).days
        return days_since_use > 30
        
    except Exception as e:
        print(f"Error checking if role {role_name} is unused: {str(e)}")
        return False

def check_access_analyzer() -> List[Dict[str, Any]]:
    """
    Check AWS Access Analyzer for external access findings.
    
    Returns:
        List of Access Analyzer findings
    """
    findings = []
    
    try:
        # List all analyzers
        analyzers = access_analyzer_client.list_analyzers()
        
        for analyzer in analyzers['analyzers']:
            if analyzer['name'].startswith(f"{PROJECT_NAME}-{ENVIRONMENT}"):
                # Get findings for this analyzer
                analyzer_findings = access_analyzer_client.list_findings(
                    analyzerArn=analyzer['arn'],
                    filter={
                        'status': {
                            'eq': ['ACTIVE']
                        }
                    }
                )
                
                for finding in analyzer_findings['findings']:
                    findings.append({
                        'type': 'ACCESS_ANALYZER',
                        'severity': 'HIGH',
                        'resource': finding['resource'],
                        'description': f"External access detected: {finding['condition']}",
                        'recommendation': 'Review and restrict external access if not intended'
                    })
                    
    except Exception as e:
        print(f"Error checking Access Analyzer: {str(e)}")
    
    return findings

def find_unused_permissions() -> List[Dict[str, Any]]:
    """
    Identify potentially unused permissions.
    
    Returns:
        List of findings for unused permissions
    """
    findings = []
    
    # This is a simplified implementation
    # In a real scenario, you would analyze CloudTrail logs to determine actual usage
    
    try:
        # Get service last accessed data for roles
        paginator = iam_client.get_paginator('list_roles')
        
        for page in paginator.paginate():
            for role in page['Roles']:
                role_name = role['RoleName']
                
                if not role_name.startswith(f"{PROJECT_NAME}-{ENVIRONMENT}"):
                    continue
                
                # Generate service last accessed report
                try:
                    response = iam_client.generate_service_last_accessed_details(
                        Arn=role['Arn']
                    )
                    job_id = response['JobId']
                    
                    # Note: In a real implementation, you would need to poll for job completion
                    # and then get the results. This is simplified for demonstration.
                    
                except Exception as e:
                    print(f"Could not generate service access report for {role_name}: {str(e)}")
                    
    except Exception as e:
        print(f"Error finding unused permissions: {str(e)}")
    
    return findings

def check_overprivileged_roles() -> List[Dict[str, Any]]:
    """
    Check for roles that might be overprivileged.
    
    Returns:
        List of findings for overprivileged roles
    """
    findings = []
    
    try:
        # Define expected permissions for each role type
        role_permission_expectations = {
            'snowflake-extractor': ['s3:PutObject', 'secretsmanager:GetSecretValue'],
            'pipeline-orchestrator': ['glue:StartJobRun', 'lambda:InvokeFunction'],
            'data-quality-monitor': ['s3:GetObject', 'glue:GetTable'],
            'notification-handler': ['sns:Publish', 'ses:SendEmail']
        }
        
        paginator = iam_client.get_paginator('list_roles')
        
        for page in paginator.paginate():
            for role in page['Roles']:
                role_name = role['RoleName']
                
                if not role_name.startswith(f"{PROJECT_NAME}-{ENVIRONMENT}"):
                    continue
                
                # Determine role type
                role_type = None
                for expected_type in role_permission_expectations.keys():
                    if expected_type in role_name:
                        role_type = expected_type
                        break
                
                if not role_type:
                    continue
                
                # Check if role has more permissions than expected
                # This is a simplified check - in practice, you'd do more detailed analysis
                attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
                
                if len(attached_policies['AttachedPolicies']) > 3:
                    findings.append({
                        'type': 'OVERPRIVILEGED_ROLE',
                        'severity': 'MEDIUM',
                        'resource': role_name,
                        'description': f"Role has {len(attached_policies['AttachedPolicies'])} attached policies, which may be excessive",
                        'recommendation': 'Review and consolidate permissions if possible'
                    })
                    
    except Exception as e:
        print(f"Error checking overprivileged roles: {str(e)}")
    
    return findings

def generate_access_review_report(findings: List[Dict[str, Any]]) -> str:
    """
    Generate a formatted access review report.
    
    Args:
        findings: List of security findings
        
    Returns:
        Formatted report string
    """
    report = f"""
ACCESS REVIEW REPORT
Project: {PROJECT_NAME}
Environment: {ENVIRONMENT}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

SUMMARY:
- Total Findings: {len(findings)}
- High Severity: {len([f for f in findings if f['severity'] == 'HIGH'])}
- Medium Severity: {len([f for f in findings if f['severity'] == 'MEDIUM'])}
- Low Severity: {len([f for f in findings if f['severity'] == 'LOW'])}

DETAILED FINDINGS:
"""
    
    for i, finding in enumerate(findings, 1):
        report += f"""
{i}. {finding['type']} - {finding['severity']}
   Resource: {finding['resource']}
   Description: {finding['description']}
   Recommendation: {finding['recommendation']}
"""
    
    report += f"""

NEXT STEPS:
1. Review all HIGH severity findings immediately
2. Plan remediation for MEDIUM severity findings
3. Consider LOW severity findings for future improvements
4. Update access controls based on recommendations

This report was generated automatically by the Access Review Lambda function.
For questions or concerns, please contact the security team.
"""
    
    return report

def send_notification(message: str, severity: str = 'INFO'):
    """
    Send notification via SNS.
    
    Args:
        message: Message to send
        severity: Severity level (INFO, WARNING, ERROR)
    """
    if not SNS_TOPIC_ARN:
        print("SNS_TOPIC_ARN not configured, skipping notification")
        return
    
    try:
        subject = f"[{severity}] Access Review - {PROJECT_NAME}-{ENVIRONMENT}"
        
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
        
        print(f"Notification sent successfully: {subject}")
        
    except Exception as e:
        print(f"Failed to send notification: {str(e)}")

if __name__ == "__main__":
    # For local testing
    test_event = {}
    test_context = type('Context', (), {
        'function_name': 'test',
        'function_version': '1',
        'invoked_function_arn': 'test',
        'memory_limit_in_mb': 128,
        'remaining_time_in_millis': lambda: 30000
    })()
    
    result = handler(test_event, test_context)
    print(json.dumps(result, indent=2))
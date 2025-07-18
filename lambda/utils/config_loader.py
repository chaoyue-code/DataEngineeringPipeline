"""
Configuration Loader Utility

This module provides utilities for loading and validating configuration from AWS SSM Parameter Store
and environment variables with default fallbacks.
"""

import os
import json
import logging
import boto3
from typing import Dict, Any, Optional, Union, List
from botocore.exceptions import ClientError
import jsonschema

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class ConfigLoader:
    """
    Utility class for loading and validating configuration from multiple sources
    with parameter validation and default value management.
    """
    
    def __init__(self, project_name: str, environment: str):
        """
        Initialize the ConfigLoader with project and environment context.
        
        Args:
            project_name: Name of the project
            environment: Environment name (dev, staging, prod)
        """
        self.project_name = project_name
        self.environment = environment
        self.ssm_client = boto3.client('ssm')
        self.secrets_client = boto3.client('secretsmanager')
        
        # Cache for loaded parameters
        self._parameter_cache = {}
        self._secret_cache = {}
    
    def get_parameter(self, param_name: str, default: Any = None) -> Any:
        """
        Get a parameter from SSM Parameter Store with caching.
        
        Args:
            param_name: Name of the parameter (without project/environment prefix)
            default: Default value if parameter doesn't exist
            
        Returns:
            Parameter value (parsed from JSON if applicable)
        """
        # Check cache first
        if param_name in self._parameter_cache:
            return self._parameter_cache[param_name]
        
        # Construct full parameter name
        full_param_name = f"/{self.project_name}/{self.environment}/{param_name}"
        
        try:
            response = self.ssm_client.get_parameter(
                Name=full_param_name,
                WithDecryption=True
            )
            
            value = response['Parameter']['Value']
            
            # Try to parse as JSON if it looks like JSON
            if value.strip().startswith('{') or value.strip().startswith('['):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    # Not valid JSON, return as string
                    pass
            
            # Cache the result
            self._parameter_cache[param_name] = value
            return value
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                logger.warning(f"Parameter {full_param_name} not found, using default value")
                return default
            else:
                logger.error(f"Error retrieving parameter {full_param_name}: {str(e)}")
                raise
    
    def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Get a secret from AWS Secrets Manager with caching.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret value as dictionary
        """
        # Check cache first
        if secret_name in self._secret_cache:
            return self._secret_cache[secret_name]
        
        try:
            response = self.secrets_client.get_secret_value(
                SecretId=secret_name
            )
            
            secret_value = json.loads(response['SecretString'])
            
            # Cache the result
            self._secret_cache[secret_name] = secret_value
            return secret_value
            
        except ClientError as e:
            logger.error(f"Error retrieving secret {secret_name}: {str(e)}")
            raise
    
    def get_config(self, config_name: str, schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Get configuration from SSM Parameter Store and validate against schema.
        
        Args:
            config_name: Name of the configuration parameter
            schema: JSON Schema for validation (optional)
            
        Returns:
            Configuration as dictionary
        """
        config = self.get_parameter(f"config/{config_name}", {})
        
        # Validate against schema if provided
        if schema and config:
            try:
                jsonschema.validate(instance=config, schema=schema)
            except jsonschema.exceptions.ValidationError as e:
                logger.error(f"Configuration validation failed for {config_name}: {str(e)}")
                raise ValueError(f"Configuration validation failed: {str(e)}")
        
        return config
    
    def get_env_var(self, name: str, default: Any = None) -> str:
        """
        Get environment variable with default fallback.
        
        Args:
            name: Name of the environment variable
            default: Default value if environment variable is not set
            
        Returns:
            Environment variable value or default
        """
        return os.environ.get(name, default)
    
    def load_config_with_defaults(self, 
                                 config_name: str, 
                                 defaults: Dict[str, Any],
                                 schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Load configuration with default values and schema validation.
        
        Args:
            config_name: Name of the configuration parameter
            defaults: Default configuration values
            schema: JSON Schema for validation (optional)
            
        Returns:
            Merged configuration
        """
        # Get configuration from parameter store
        config = self.get_parameter(f"config/{config_name}", {})
        
        # Merge with defaults
        merged_config = self._deep_merge(defaults, config)
        
        # Validate against schema if provided
        if schema:
            try:
                jsonschema.validate(instance=merged_config, schema=schema)
            except jsonschema.exceptions.ValidationError as e:
                logger.error(f"Configuration validation failed for {config_name}: {str(e)}")
                raise ValueError(f"Configuration validation failed: {str(e)}")
        
        return merged_config
    
    def _deep_merge(self, default_dict: Dict, override_dict: Dict) -> Dict:
        """
        Deep merge two dictionaries, with override_dict taking precedence.
        
        Args:
            default_dict: Default dictionary
            override_dict: Dictionary with override values
            
        Returns:
            Merged dictionary
        """
        result = default_dict.copy()
        
        for key, value in override_dict.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
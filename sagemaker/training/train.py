#!/usr/bin/env python3
"""
SageMaker Training Script for Automated Model Training Pipeline
Supports multiple ML algorithms with hyperparameter tuning
"""

import argparse
import json
import logging
import os
import pickle
import sys
from pathlib import Path

import boto3
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelTrainer:
    """Automated model training with hyperparameter tuning support"""
    
    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.feature_columns = None
        self.target_column = None
        
    def load_data(self, input_path):
        """Load training data from S3 or local path"""
        logger.info(f"Loading data from {input_path}")
        
        if input_path.startswith('s3://'):
            # Load from S3
            s3 = boto3.client('s3')
            bucket, key = input_path.replace('s3://', '').split('/', 1)
            
            # Download file locally
            local_path = '/tmp/training_data.parquet'
            s3.download_file(bucket, key, local_path)
            data = pd.read_parquet(local_path)
        else:
            # Load from local path
            if input_path.endswith('.parquet'):
                data = pd.read_parquet(input_path)
            elif input_path.endswith('.csv'):
                data = pd.read_csv(input_path)
            else:
                raise ValueError(f"Unsupported file format: {input_path}")
        
        logger.info(f"Loaded data with shape: {data.shape}")
        return data
    
    def preprocess_data(self, data, target_column, feature_columns=None):
        """Preprocess data for training"""
        logger.info("Preprocessing data...")
        
        self.target_column = target_column
        
        # Handle missing values
        data = data.dropna()
        
        # Separate features and target
        if feature_columns:
            self.feature_columns = feature_columns
            X = data[feature_columns]
        else:
            # Use all columns except target
            self.feature_columns = [col for col in data.columns if col != target_column]
            X = data[self.feature_columns]
        
        y = data[target_column]
        
        # Encode categorical features
        categorical_columns = X.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
        
        # Encode target if categorical
        if y.dtype == 'object':
            y = self.label_encoder.fit_transform(y)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        logger.info(f"Preprocessed features shape: {X_scaled.shape}")
        logger.info(f"Target distribution: {np.bincount(y)}")
        
        return X_scaled, y
    
    def create_model(self, hyperparameters):
        """Create model based on type and hyperparameters"""
        logger.info(f"Creating {self.model_type} model with hyperparameters: {hyperparameters}")
        
        if self.model_type == 'random_forest':
            self.model = RandomForestClassifier(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', None),
                min_samples_split=hyperparameters.get('min_samples_split', 2),
                min_samples_leaf=hyperparameters.get('min_samples_leaf', 1),
                random_state=42
            )
        elif self.model_type == 'gradient_boosting':
            self.model = GradientBoostingClassifier(
                n_estimators=hyperparameters.get('n_estimators', 100),
                learning_rate=hyperparameters.get('learning_rate', 0.1),
                max_depth=hyperparameters.get('max_depth', 3),
                random_state=42
            )
        elif self.model_type == 'logistic_regression':
            self.model = LogisticRegression(
                C=hyperparameters.get('C', 1.0),
                max_iter=hyperparameters.get('max_iter', 1000),
                random_state=42
            )
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")
    
    def train(self, X, y):
        """Train the model"""
        logger.info("Training model...")
        
        # Split data for validation
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train model
        self.model.fit(X_train, y_train)
        
        # Validate model
        y_pred = self.model.predict(X_val)
        y_pred_proba = self.model.predict_proba(X_val)[:, 1] if hasattr(self.model, 'predict_proba') else None
        
        # Calculate metrics
        metrics = self.calculate_metrics(y_val, y_pred, y_pred_proba)
        
        logger.info("Training completed successfully")
        logger.info(f"Validation metrics: {metrics}")
        
        return metrics
    
    def calculate_metrics(self, y_true, y_pred, y_pred_proba=None):
        """Calculate model performance metrics"""
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, average='weighted'),
            'recall': recall_score(y_true, y_pred, average='weighted'),
            'f1_score': f1_score(y_true, y_pred, average='weighted')
        }
        
        if y_pred_proba is not None and len(np.unique(y_true)) == 2:
            metrics['roc_auc'] = roc_auc_score(y_true, y_pred_proba)
        
        return metrics
    
    def save_model(self, model_path):
        """Save trained model and preprocessing components"""
        logger.info(f"Saving model to {model_path}")
        
        # Create model directory
        os.makedirs(model_path, exist_ok=True)
        
        # Save model
        model_file = os.path.join(model_path, 'model.pkl')
        joblib.dump(self.model, model_file)
        
        # Save preprocessing components
        scaler_file = os.path.join(model_path, 'scaler.pkl')
        joblib.dump(self.scaler, scaler_file)
        
        if hasattr(self.label_encoder, 'classes_'):
            encoder_file = os.path.join(model_path, 'label_encoder.pkl')
            joblib.dump(self.label_encoder, encoder_file)
        
        # Save metadata
        metadata = {
            'model_type': self.model_type,
            'feature_columns': self.feature_columns,
            'target_column': self.target_column,
            'model_params': self.model.get_params() if self.model else None
        }
        
        metadata_file = os.path.join(model_path, 'metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info("Model saved successfully")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='SageMaker Training Script')
    
    # SageMaker specific arguments
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN', '/opt/ml/input/data/train'))
    parser.add_argument('--output-data-dir', type=str, default=os.environ.get('SM_OUTPUT_DATA_DIR', '/opt/ml/output'))
    
    # Model hyperparameters
    parser.add_argument('--model-type', type=str, default='random_forest',
                       choices=['random_forest', 'gradient_boosting', 'logistic_regression'])
    parser.add_argument('--target-column', type=str, required=True)
    parser.add_argument('--feature-columns', type=str, default=None,
                       help='Comma-separated list of feature columns')
    
    # Hyperparameters for different models
    parser.add_argument('--n-estimators', type=int, default=100)
    parser.add_argument('--max-depth', type=int, default=None)
    parser.add_argument('--min-samples-split', type=int, default=2)
    parser.add_argument('--min-samples-leaf', type=int, default=1)
    parser.add_argument('--learning-rate', type=float, default=0.1)
    parser.add_argument('--C', type=float, default=1.0)
    parser.add_argument('--max-iter', type=int, default=1000)
    
    return parser.parse_args()

def main():
    """Main training function"""
    args = parse_args()
    
    logger.info("Starting SageMaker training job")
    logger.info(f"Arguments: {vars(args)}")
    
    try:
        # Initialize trainer
        trainer = ModelTrainer(model_type=args.model_type)
        
        # Load data
        train_file = os.path.join(args.train, 'train.parquet')
        if not os.path.exists(train_file):
            train_file = os.path.join(args.train, 'train.csv')
        
        data = trainer.load_data(train_file)
        
        # Parse feature columns
        feature_columns = None
        if args.feature_columns:
            feature_columns = [col.strip() for col in args.feature_columns.split(',')]
        
        # Preprocess data
        X, y = trainer.preprocess_data(data, args.target_column, feature_columns)
        
        # Create model with hyperparameters
        hyperparameters = {
            'n_estimators': args.n_estimators,
            'max_depth': args.max_depth,
            'min_samples_split': args.min_samples_split,
            'min_samples_leaf': args.min_samples_leaf,
            'learning_rate': args.learning_rate,
            'C': args.C,
            'max_iter': args.max_iter
        }
        
        trainer.create_model(hyperparameters)
        
        # Train model
        metrics = trainer.train(X, y)
        
        # Save model
        trainer.save_model(args.model_dir)
        
        # Save metrics
        metrics_file = os.path.join(args.output_data_dir, 'metrics.json')
        os.makedirs(args.output_data_dir, exist_ok=True)
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info("Training job completed successfully")
        
    except Exception as e:
        logger.error(f"Training job failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
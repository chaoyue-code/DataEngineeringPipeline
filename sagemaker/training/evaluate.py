#!/usr/bin/env python3
"""
Model Evaluation and Validation Script for SageMaker Pipeline
Provides comprehensive model evaluation metrics and validation
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import boto3
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, precision_recall_curve,
    classification_report, confusion_matrix,
    mean_squared_error, mean_absolute_error, r2_score
)
from sklearn.model_selection import cross_val_score

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelEvaluator:
    """Comprehensive model evaluation and validation"""
    
    def __init__(self, model_path):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.metadata = None
        self.load_model()
    
    def load_model(self):
        """Load trained model and preprocessing components"""
        logger.info(f"Loading model from {self.model_path}")
        
        # Load model
        model_file = os.path.join(self.model_path, 'model.pkl')
        if os.path.exists(model_file):
            self.model = joblib.load(model_file)
        else:
            raise FileNotFoundError(f"Model file not found: {model_file}")
        
        # Load scaler
        scaler_file = os.path.join(self.model_path, 'scaler.pkl')
        if os.path.exists(scaler_file):
            self.scaler = joblib.load(scaler_file)
        
        # Load label encoder
        encoder_file = os.path.join(self.model_path, 'label_encoder.pkl')
        if os.path.exists(encoder_file):
            self.label_encoder = joblib.load(encoder_file)
        
        # Load metadata
        metadata_file = os.path.join(self.model_path, 'metadata.json')
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                self.metadata = json.load(f)
        
        logger.info("Model loaded successfully")
    
    def load_test_data(self, test_path):
        """Load test data for evaluation"""
        logger.info(f"Loading test data from {test_path}")
        
        if test_path.startswith('s3://'):
            # Load from S3
            s3 = boto3.client('s3')
            bucket, key = test_path.replace('s3://', '').split('/', 1)
            
            # Download file locally
            local_path = '/tmp/test_data.parquet'
            s3.download_file(bucket, key, local_path)
            data = pd.read_parquet(local_path)
        else:
            # Load from local path
            if test_path.endswith('.parquet'):
                data = pd.read_parquet(test_path)
            elif test_path.endswith('.csv'):
                data = pd.read_csv(test_path)
            else:
                raise ValueError(f"Unsupported file format: {test_path}")
        
        logger.info(f"Loaded test data with shape: {data.shape}")
        return data
    
    def preprocess_test_data(self, data):
        """Preprocess test data using saved preprocessing components"""
        logger.info("Preprocessing test data...")
        
        if not self.metadata:
            raise ValueError("Model metadata not available")
        
        target_column = self.metadata['target_column']
        feature_columns = self.metadata['feature_columns']
        
        # Handle missing values
        data = data.dropna()
        
        # Separate features and target
        X = data[feature_columns]
        y = data[target_column] if target_column in data.columns else None
        
        # Encode categorical features (using same encoding as training)
        categorical_columns = X.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            # Simple label encoding (in production, should use saved encoders)
            unique_values = X[col].unique()
            value_map = {val: idx for idx, val in enumerate(unique_values)}
            X[col] = X[col].map(value_map).fillna(-1)
        
        # Scale features
        if self.scaler:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X.values
        
        # Encode target if available
        if y is not None and self.label_encoder and hasattr(self.label_encoder, 'classes_'):
            try:
                y = self.label_encoder.transform(y)
            except ValueError:
                logger.warning("Some target values not seen during training")
                # Handle unseen labels
                y = pd.Series(y).map(
                    {label: idx for idx, label in enumerate(self.label_encoder.classes_)}
                ).fillna(-1).values
        
        return X_scaled, y
    
    def evaluate_classification(self, X_test, y_test):
        """Evaluate classification model"""
        logger.info("Evaluating classification model...")
        
        # Make predictions
        y_pred = self.model.predict(X_test)
        y_pred_proba = None
        
        if hasattr(self.model, 'predict_proba'):
            y_pred_proba = self.model.predict_proba(X_test)
        
        # Calculate metrics
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision_macro': precision_score(y_test, y_pred, average='macro'),
            'precision_weighted': precision_score(y_test, y_pred, average='weighted'),
            'recall_macro': recall_score(y_test, y_pred, average='macro'),
            'recall_weighted': recall_score(y_test, y_pred, average='weighted'),
            'f1_macro': f1_score(y_test, y_pred, average='macro'),
            'f1_weighted': f1_score(y_test, y_pred, average='weighted')
        }
        
        # ROC AUC for binary classification
        if len(np.unique(y_test)) == 2 and y_pred_proba is not None:
            metrics['roc_auc'] = roc_auc_score(y_test, y_pred_proba[:, 1])
        
        # Classification report
        class_report = classification_report(y_test, y_pred, output_dict=True)
        
        # Confusion matrix
        conf_matrix = confusion_matrix(y_test, y_pred)
        
        return {
            'metrics': metrics,
            'classification_report': class_report,
            'confusion_matrix': conf_matrix.tolist(),
            'predictions': y_pred.tolist(),
            'prediction_probabilities': y_pred_proba.tolist() if y_pred_proba is not None else None
        }
    
    def evaluate_regression(self, X_test, y_test):
        """Evaluate regression model"""
        logger.info("Evaluating regression model...")
        
        # Make predictions
        y_pred = self.model.predict(X_test)
        
        # Calculate metrics
        metrics = {
            'mse': mean_squared_error(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'mae': mean_absolute_error(y_test, y_pred),
            'r2': r2_score(y_test, y_pred)
        }
        
        return {
            'metrics': metrics,
            'predictions': y_pred.tolist()
        }
    
    def cross_validate(self, X, y, cv=5):
        """Perform cross-validation"""
        logger.info(f"Performing {cv}-fold cross-validation...")
        
        # Determine scoring metric based on model type
        if hasattr(self.model, 'predict_proba'):
            scoring = 'accuracy'
        else:
            scoring = 'r2'
        
        cv_scores = cross_val_score(self.model, X, y, cv=cv, scoring=scoring)
        
        cv_results = {
            'cv_scores': cv_scores.tolist(),
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'scoring_metric': scoring
        }
        
        logger.info(f"Cross-validation {scoring}: {cv_results['cv_mean']:.4f} (+/- {cv_results['cv_std'] * 2:.4f})")
        
        return cv_results
    
    def generate_plots(self, evaluation_results, output_dir):
        """Generate evaluation plots"""
        logger.info("Generating evaluation plots...")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Confusion matrix plot for classification
        if 'confusion_matrix' in evaluation_results:
            plt.figure(figsize=(8, 6))
            conf_matrix = np.array(evaluation_results['confusion_matrix'])
            sns.heatmap(conf_matrix, annot=True, fmt='d', cmap='Blues')
            plt.title('Confusion Matrix')
            plt.ylabel('True Label')
            plt.xlabel('Predicted Label')
            plt.savefig(os.path.join(output_dir, 'confusion_matrix.png'))
            plt.close()
        
        # ROC curve for binary classification
        if evaluation_results.get('prediction_probabilities') and len(np.unique(evaluation_results.get('predictions', []))) == 2:
            # Note: This would require actual y_test values, simplified for demo
            plt.figure(figsize=(8, 6))
            plt.plot([0, 1], [0, 1], 'k--', label='Random')
            plt.xlabel('False Positive Rate')
            plt.ylabel('True Positive Rate')
            plt.title('ROC Curve')
            plt.legend()
            plt.savefig(os.path.join(output_dir, 'roc_curve.png'))
            plt.close()
        
        logger.info(f"Plots saved to {output_dir}")
    
    def feature_importance(self):
        """Get feature importance if available"""
        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
            feature_names = self.metadata.get('feature_columns', [])
            
            if len(feature_names) == len(importance):
                feature_importance = dict(zip(feature_names, importance.tolist()))
                return sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        
        return None
    
    def model_summary(self):
        """Generate model summary"""
        summary = {
            'model_type': self.metadata.get('model_type') if self.metadata else 'unknown',
            'model_parameters': self.metadata.get('model_params') if self.metadata else {},
            'feature_count': len(self.metadata.get('feature_columns', [])) if self.metadata else 0,
            'feature_columns': self.metadata.get('feature_columns') if self.metadata else [],
            'target_column': self.metadata.get('target_column') if self.metadata else 'unknown'
        }
        
        # Add feature importance if available
        feature_importance = self.feature_importance()
        if feature_importance:
            summary['feature_importance'] = feature_importance
        
        return summary

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Model Evaluation Script')
    
    parser.add_argument('--model-path', type=str, required=True,
                       help='Path to trained model directory')
    parser.add_argument('--test-data', type=str, required=True,
                       help='Path to test data file')
    parser.add_argument('--output-dir', type=str, default='/opt/ml/output',
                       help='Output directory for evaluation results')
    parser.add_argument('--cross-validate', action='store_true',
                       help='Perform cross-validation')
    parser.add_argument('--cv-folds', type=int, default=5,
                       help='Number of cross-validation folds')
    parser.add_argument('--generate-plots', action='store_true',
                       help='Generate evaluation plots')
    
    return parser.parse_args()

def main():
    """Main evaluation function"""
    args = parse_args()
    
    logger.info("Starting model evaluation")
    logger.info(f"Arguments: {vars(args)}")
    
    try:
        # Initialize evaluator
        evaluator = ModelEvaluator(args.model_path)
        
        # Load test data
        test_data = evaluator.load_test_data(args.test_data)
        
        # Preprocess test data
        X_test, y_test = evaluator.preprocess_test_data(test_data)
        
        if y_test is None:
            logger.error("No target column found in test data")
            sys.exit(1)
        
        # Determine if classification or regression
        is_classification = hasattr(evaluator.model, 'predict_proba') or len(np.unique(y_test)) < 20
        
        # Evaluate model
        if is_classification:
            evaluation_results = evaluator.evaluate_classification(X_test, y_test)
        else:
            evaluation_results = evaluator.evaluate_regression(X_test, y_test)
        
        # Cross-validation
        if args.cross_validate:
            cv_results = evaluator.cross_validate(X_test, y_test, cv=args.cv_folds)
            evaluation_results['cross_validation'] = cv_results
        
        # Model summary
        model_summary = evaluator.model_summary()
        evaluation_results['model_summary'] = model_summary
        
        # Add evaluation metadata
        evaluation_results['evaluation_metadata'] = {
            'evaluation_timestamp': datetime.now().isoformat(),
            'test_data_shape': test_data.shape,
            'model_type': 'classification' if is_classification else 'regression'
        }
        
        # Save results
        os.makedirs(args.output_dir, exist_ok=True)
        results_file = os.path.join(args.output_dir, 'evaluation_results.json')
        with open(results_file, 'w') as f:
            json.dump(evaluation_results, f, indent=2)
        
        # Generate plots
        if args.generate_plots:
            plots_dir = os.path.join(args.output_dir, 'plots')
            evaluator.generate_plots(evaluation_results, plots_dir)
        
        logger.info("Model evaluation completed successfully")
        logger.info(f"Results saved to {results_file}")
        
        # Print key metrics
        if 'metrics' in evaluation_results:
            logger.info("Key Metrics:")
            for metric, value in evaluation_results['metrics'].items():
                logger.info(f"  {metric}: {value:.4f}")
        
    except Exception as e:
        logger.error(f"Model evaluation failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
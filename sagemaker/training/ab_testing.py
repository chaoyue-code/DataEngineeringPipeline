#!/usr/bin/env python3
"""
A/B Testing Framework for Model Comparison
Supports statistical testing and performance comparison between models
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Any

import boto3
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ABTestFramework:
    """A/B Testing framework for model comparison"""
    
    def __init__(self):
        self.models = {}
        self.test_results = {}
        self.statistical_tests = {}
    
    def add_model(self, model_name: str, model_path: str, evaluation_results_path: str):
        """Add a model to the A/B test"""
        logger.info(f"Adding model {model_name} to A/B test")
        
        # Load evaluation results
        with open(evaluation_results_path, 'r') as f:
            evaluation_results = json.load(f)
        
        self.models[model_name] = {
            'model_path': model_path,
            'evaluation_results': evaluation_results
        }
        
        logger.info(f"Model {model_name} added successfully")
    
    def compare_metrics(self, metric_name: str) -> Dict[str, Any]:
        """Compare a specific metric across all models"""
        logger.info(f"Comparing metric: {metric_name}")
        
        metric_values = {}
        for model_name, model_data in self.models.items():
            metrics = model_data['evaluation_results'].get('metrics', {})
            if metric_name in metrics:
                metric_values[model_name] = metrics[metric_name]
            else:
                logger.warning(f"Metric {metric_name} not found for model {model_name}")
        
        if len(metric_values) < 2:
            logger.error(f"Need at least 2 models with {metric_name} metric for comparison")
            return {}
        
        # Find best and worst performing models
        best_model = max(metric_values.items(), key=lambda x: x[1])
        worst_model = min(metric_values.items(), key=lambda x: x[1])
        
        # Calculate relative improvements
        improvements = {}
        for model_name, value in metric_values.items():
            if model_name != best_model[0]:
                improvement = ((best_model[1] - value) / value) * 100
                improvements[model_name] = improvement
        
        comparison_results = {
            'metric_name': metric_name,
            'metric_values': metric_values,
            'best_model': {'name': best_model[0], 'value': best_model[1]},
            'worst_model': {'name': worst_model[0], 'value': worst_model[1]},
            'improvements': improvements,
            'ranking': sorted(metric_values.items(), key=lambda x: x[1], reverse=True)
        }
        
        return comparison_results
    
    def statistical_significance_test(self, model_a: str, model_b: str, 
                                    metric_name: str = 'accuracy',
                                    alpha: float = 0.05) -> Dict[str, Any]:
        """Perform statistical significance test between two models"""
        logger.info(f"Performing statistical test between {model_a} and {model_b}")
        
        if model_a not in self.models or model_b not in self.models:
            raise ValueError(f"Models {model_a} or {model_b} not found")
        
        # Get cross-validation results if available
        cv_a = self.models[model_a]['evaluation_results'].get('cross_validation', {}).get('cv_scores', [])
        cv_b = self.models[model_b]['evaluation_results'].get('cross_validation', {}).get('cv_scores', [])
        
        if not cv_a or not cv_b:
            logger.warning("Cross-validation results not available, using point estimates")
            metric_a = self.models[model_a]['evaluation_results']['metrics'].get(metric_name)
            metric_b = self.models[model_b]['evaluation_results']['metrics'].get(metric_name)
            
            if metric_a is None or metric_b is None:
                raise ValueError(f"Metric {metric_name} not found for one or both models")
            
            # Simple comparison without statistical test
            return {
                'model_a': model_a,
                'model_b': model_b,
                'metric_name': metric_name,
                'value_a': metric_a,
                'value_b': metric_b,
                'difference': metric_a - metric_b,
                'better_model': model_a if metric_a > metric_b else model_b,
                'statistical_test': 'point_comparison',
                'p_value': None,
                'significant': abs(metric_a - metric_b) > 0.01  # Simple threshold
            }
        
        # Perform paired t-test
        t_stat, p_value = stats.ttest_rel(cv_a, cv_b)
        
        # Effect size (Cohen's d)
        pooled_std = np.sqrt((np.var(cv_a) + np.var(cv_b)) / 2)
        cohens_d = (np.mean(cv_a) - np.mean(cv_b)) / pooled_std if pooled_std > 0 else 0
        
        # Interpret effect size
        if abs(cohens_d) < 0.2:
            effect_size = 'small'
        elif abs(cohens_d) < 0.5:
            effect_size = 'medium'
        else:
            effect_size = 'large'
        
        results = {
            'model_a': model_a,
            'model_b': model_b,
            'metric_name': metric_name,
            'mean_a': np.mean(cv_a),
            'mean_b': np.mean(cv_b),
            'std_a': np.std(cv_a),
            'std_b': np.std(cv_b),
            'difference': np.mean(cv_a) - np.mean(cv_b),
            'better_model': model_a if np.mean(cv_a) > np.mean(cv_b) else model_b,
            'statistical_test': 'paired_t_test',
            't_statistic': t_stat,
            'p_value': p_value,
            'significant': p_value < alpha,
            'alpha': alpha,
            'cohens_d': cohens_d,
            'effect_size': effect_size
        }
        
        return results
    
    def bootstrap_comparison(self, model_a: str, model_b: str, 
                           metric_name: str = 'accuracy',
                           n_bootstrap: int = 1000,
                           confidence_level: float = 0.95) -> Dict[str, Any]:
        """Bootstrap comparison between two models"""
        logger.info(f"Performing bootstrap comparison between {model_a} and {model_b}")
        
        # Get cross-validation results
        cv_a = self.models[model_a]['evaluation_results'].get('cross_validation', {}).get('cv_scores', [])
        cv_b = self.models[model_b]['evaluation_results'].get('cross_validation', {}).get('cv_scores', [])
        
        if not cv_a or not cv_b:
            logger.warning("Cross-validation results not available for bootstrap")
            return {}
        
        # Bootstrap sampling
        differences = []
        for _ in range(n_bootstrap):
            sample_a = np.random.choice(cv_a, size=len(cv_a), replace=True)
            sample_b = np.random.choice(cv_b, size=len(cv_b), replace=True)
            diff = np.mean(sample_a) - np.mean(sample_b)
            differences.append(diff)
        
        differences = np.array(differences)
        
        # Calculate confidence interval
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100
        
        ci_lower = np.percentile(differences, lower_percentile)
        ci_upper = np.percentile(differences, upper_percentile)
        
        # Check if zero is in confidence interval
        significant = not (ci_lower <= 0 <= ci_upper)
        
        results = {
            'model_a': model_a,
            'model_b': model_b,
            'metric_name': metric_name,
            'mean_difference': np.mean(differences),
            'std_difference': np.std(differences),
            'confidence_level': confidence_level,
            'confidence_interval': [ci_lower, ci_upper],
            'significant': significant,
            'better_model': model_a if np.mean(differences) > 0 else model_b,
            'n_bootstrap': n_bootstrap
        }
        
        return results
    
    def comprehensive_comparison(self, metrics: List[str] = None) -> Dict[str, Any]:
        """Perform comprehensive comparison across all models and metrics"""
        logger.info("Performing comprehensive model comparison")
        
        if metrics is None:
            metrics = ['accuracy', 'precision_weighted', 'recall_weighted', 'f1_weighted']
        
        comparison_results = {
            'models': list(self.models.keys()),
            'metrics_compared': metrics,
            'metric_comparisons': {},
            'overall_ranking': {},
            'statistical_tests': {},
            'recommendations': []
        }
        
        # Compare each metric
        for metric in metrics:
            metric_comparison = self.compare_metrics(metric)
            if metric_comparison:
                comparison_results['metric_comparisons'][metric] = metric_comparison
        
        # Calculate overall ranking (average rank across metrics)
        model_ranks = {model: [] for model in self.models.keys()}
        
        for metric, comparison in comparison_results['metric_comparisons'].items():
            ranking = comparison['ranking']
            for rank, (model, value) in enumerate(ranking):
                model_ranks[model].append(rank + 1)  # 1-based ranking
        
        # Calculate average rank
        overall_ranking = {}
        for model, ranks in model_ranks.items():
            if ranks:
                overall_ranking[model] = np.mean(ranks)
        
        comparison_results['overall_ranking'] = sorted(
            overall_ranking.items(), key=lambda x: x[1]
        )
        
        # Perform pairwise statistical tests
        model_names = list(self.models.keys())
        for i, model_a in enumerate(model_names):
            for model_b in model_names[i+1:]:
                test_key = f"{model_a}_vs_{model_b}"
                try:
                    stat_test = self.statistical_significance_test(model_a, model_b)
                    comparison_results['statistical_tests'][test_key] = stat_test
                except Exception as e:
                    logger.warning(f"Statistical test failed for {test_key}: {str(e)}")
        
        # Generate recommendations
        if comparison_results['overall_ranking']:
            best_model = comparison_results['overall_ranking'][0][0]
            comparison_results['recommendations'].append(
                f"Best overall model: {best_model}"
            )
            
            # Check for significant differences
            significant_improvements = []
            for test_key, test_result in comparison_results['statistical_tests'].items():
                if test_result.get('significant', False):
                    better_model = test_result['better_model']
                    worse_model = test_result['model_a'] if better_model == test_result['model_b'] else test_result['model_b']
                    significant_improvements.append(f"{better_model} significantly outperforms {worse_model}")
            
            if significant_improvements:
                comparison_results['recommendations'].extend(significant_improvements)
            else:
                comparison_results['recommendations'].append(
                    "No statistically significant differences found between models"
                )
        
        return comparison_results
    
    def generate_report(self, output_path: str):
        """Generate comprehensive A/B testing report"""
        logger.info(f"Generating A/B testing report to {output_path}")
        
        # Perform comprehensive comparison
        comparison_results = self.comprehensive_comparison()
        
        # Add metadata
        report = {
            'ab_test_metadata': {
                'timestamp': datetime.now().isoformat(),
                'models_tested': list(self.models.keys()),
                'total_models': len(self.models)
            },
            'comparison_results': comparison_results,
            'model_summaries': {}
        }
        
        # Add model summaries
        for model_name, model_data in self.models.items():
            summary = model_data['evaluation_results'].get('model_summary', {})
            metrics = model_data['evaluation_results'].get('metrics', {})
            report['model_summaries'][model_name] = {
                'model_type': summary.get('model_type', 'unknown'),
                'feature_count': summary.get('feature_count', 0),
                'key_metrics': metrics
            }
        
        # Save report
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"A/B testing report saved to {output_path}")
        
        return report

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='A/B Testing Framework')
    
    parser.add_argument('--models', type=str, required=True,
                       help='JSON file containing model configurations')
    parser.add_argument('--output-dir', type=str, default='/opt/ml/output',
                       help='Output directory for A/B test results')
    parser.add_argument('--metrics', type=str, nargs='+',
                       default=['accuracy', 'precision_weighted', 'recall_weighted', 'f1_weighted'],
                       help='Metrics to compare')
    parser.add_argument('--alpha', type=float, default=0.05,
                       help='Significance level for statistical tests')
    
    return parser.parse_args()

def main():
    """Main A/B testing function"""
    args = parse_args()
    
    logger.info("Starting A/B testing framework")
    logger.info(f"Arguments: {vars(args)}")
    
    try:
        # Load model configurations
        with open(args.models, 'r') as f:
            model_configs = json.load(f)
        
        # Initialize A/B testing framework
        ab_test = ABTestFramework()
        
        # Add models to the test
        for model_name, config in model_configs.items():
            ab_test.add_model(
                model_name=model_name,
                model_path=config['model_path'],
                evaluation_results_path=config['evaluation_results_path']
            )
        
        # Generate comprehensive report
        report_path = os.path.join(args.output_dir, 'ab_test_report.json')
        report = ab_test.generate_report(report_path)
        
        # Print summary
        logger.info("A/B Testing Summary:")
        logger.info(f"Models tested: {len(ab_test.models)}")
        
        if report['comparison_results']['overall_ranking']:
            best_model = report['comparison_results']['overall_ranking'][0]
            logger.info(f"Best overall model: {best_model[0]} (avg rank: {best_model[1]:.2f})")
        
        for recommendation in report['comparison_results']['recommendations']:
            logger.info(f"Recommendation: {recommendation}")
        
        logger.info("A/B testing completed successfully")
        
    except Exception as e:
        logger.error(f"A/B testing failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
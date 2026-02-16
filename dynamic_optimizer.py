#!/usr/bin/env python3
"""
Dynamic Optimizer for DaVinci Resolve OpenClaw
Self-learning system that improves workflow performance over time

Features:
- Performance pattern recognition and optimization
- Adaptive workflow tuning based on success metrics
- Learning from quality scores and processing times
- Automatic parameter optimization for different content types
- Predictive optimization suggestions
"""

import json
import os
import time
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
import statistics
import numpy as np
from dataclasses import dataclass, asdict
from collections import defaultdict, deque

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProcessingMetrics:
    """Data class for workflow processing metrics"""
    project_name: str
    content_type: str  # interview, presentation, vlog, etc.
    video_count: int
    total_duration: float
    processing_time: float
    quality_score: float
    success_rate: float
    optimization_settings: Dict[str, Any]
    timestamp: datetime
    
    def efficiency_score(self) -> float:
        """Calculate efficiency score (quality vs time)"""
        if self.processing_time == 0:
            return 0.0
        return (self.quality_score * self.success_rate) / (self.processing_time / 60)  # Per minute

@dataclass
class OptimizationSuggestion:
    """Optimization suggestion with confidence score"""
    parameter: str
    current_value: Any
    suggested_value: Any
    confidence: float
    reasoning: str
    expected_improvement: float


class DynamicOptimizer:
    def __init__(self, learning_rate: float = 0.1):
        """Initialize dynamic optimization system"""
        self.learning_rate = learning_rate
        self.metrics_history = deque(maxlen=1000)  # Keep last 1000 processing runs
        self.optimization_patterns = defaultdict(list)
        self.content_profiles = {}
        self.performance_baselines = {}
        
        # Load existing learning data
        self.data_dir = Path("optimization_data")
        self.data_dir.mkdir(exist_ok=True)
        self._load_learning_data()
        
        # Optimization parameters and their ranges
        self.parameter_ranges = {
            'max_workers': (1, 8),
            'render_quality': (0.5, 1.0),
            'transcription_model': ['whisper-1'],
            'social_clip_count': (3, 8),
            'broll_ratio': (0.2, 0.8),
            'processing_timeout': (300, 1800),
            'parallel_transcription': [True, False],
            'quality_preset': ['fast', 'balanced', 'quality'],
            'scene_detection_sensitivity': (0.3, 0.9)
        }
        
        # Current optimal settings (learned over time)
        self.optimal_settings = {
            'max_workers': 4,
            'render_quality': 0.85,
            'transcription_model': 'whisper-1',
            'social_clip_count': 5,
            'broll_ratio': 0.5,
            'processing_timeout': 900,
            'parallel_transcription': True,
            'quality_preset': 'balanced',
            'scene_detection_sensitivity': 0.6
        }
    
    def _load_learning_data(self):
        """Load previously learned optimization data"""
        try:
            # Load metrics history
            metrics_file = self.data_dir / "metrics_history.pkl"
            if metrics_file.exists():
                with open(metrics_file, 'rb') as f:
                    saved_metrics = pickle.load(f)
                    self.metrics_history.extend(saved_metrics)
                logger.info(f"Loaded {len(self.metrics_history)} historical metrics")
            
            # Load optimization patterns
            patterns_file = self.data_dir / "optimization_patterns.json"
            if patterns_file.exists():
                with open(patterns_file, 'r') as f:
                    self.optimization_patterns = json.load(f)
            
            # Load content profiles
            profiles_file = self.data_dir / "content_profiles.json"
            if profiles_file.exists():
                with open(profiles_file, 'r') as f:
                    self.content_profiles = json.load(f)
            
            # Load optimal settings
            settings_file = self.data_dir / "optimal_settings.json"
            if settings_file.exists():
                with open(settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    self.optimal_settings.update(loaded_settings)
                
        except Exception as e:
            logger.error(f"Error loading learning data: {e}")
    
    def _save_learning_data(self):
        """Save learned optimization data"""
        try:
            # Save metrics history
            metrics_file = self.data_dir / "metrics_history.pkl"
            with open(metrics_file, 'wb') as f:
                pickle.dump(list(self.metrics_history), f)
            
            # Save optimization patterns
            patterns_file = self.data_dir / "optimization_patterns.json"
            with open(patterns_file, 'w') as f:
                json.dump(dict(self.optimization_patterns), f, indent=2, default=str)
            
            # Save content profiles
            profiles_file = self.data_dir / "content_profiles.json"
            with open(profiles_file, 'w') as f:
                json.dump(self.content_profiles, f, indent=2, default=str)
            
            # Save optimal settings
            settings_file = self.data_dir / "optimal_settings.json"
            with open(settings_file, 'w') as f:
                json.dump(self.optimal_settings, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving learning data: {e}")
    
    def record_processing_metrics(self, 
                                project_name: str,
                                content_type: str,
                                video_count: int,
                                total_duration: float,
                                processing_time: float,
                                quality_score: float,
                                success_rate: float,
                                settings: Dict[str, Any]) -> ProcessingMetrics:
        """Record metrics from a processing run for learning"""
        
        metrics = ProcessingMetrics(
            project_name=project_name,
            content_type=content_type,
            video_count=video_count,
            total_duration=total_duration,
            processing_time=processing_time,
            quality_score=quality_score,
            success_rate=success_rate,
            optimization_settings=settings.copy(),
            timestamp=datetime.now()
        )
        
        # Add to history
        self.metrics_history.append(metrics)
        
        # Update content profile
        self._update_content_profile(content_type, metrics)
        
        # Learn optimization patterns
        self._learn_optimization_patterns(metrics)
        
        # Update optimal settings if this run was better
        self._update_optimal_settings(metrics)
        
        # Save learning data
        self._save_learning_data()
        
        logger.info(f"📊 Recorded metrics: {project_name} - Quality: {quality_score:.2f}, "
                   f"Efficiency: {metrics.efficiency_score():.2f}")
        
        return metrics
    
    def _update_content_profile(self, content_type: str, metrics: ProcessingMetrics):
        """Update learned profile for a content type"""
        if content_type not in self.content_profiles:
            self.content_profiles[content_type] = {
                'total_runs': 0,
                'avg_quality': 0.0,
                'avg_efficiency': 0.0,
                'best_settings': {},
                'typical_duration': 0.0,
                'typical_video_count': 0,
                'last_updated': datetime.now().isoformat()
            }
        
        profile = self.content_profiles[content_type]
        
        # Update running averages
        total_runs = profile['total_runs']
        profile['avg_quality'] = (profile['avg_quality'] * total_runs + metrics.quality_score) / (total_runs + 1)
        profile['avg_efficiency'] = (profile['avg_efficiency'] * total_runs + metrics.efficiency_score()) / (total_runs + 1)
        profile['total_runs'] += 1
        profile['last_updated'] = datetime.now().isoformat()
        
        # Update typical values
        profile['typical_duration'] = (profile['typical_duration'] * total_runs + metrics.total_duration) / (total_runs + 1)
        profile['typical_video_count'] = int((profile['typical_video_count'] * total_runs + metrics.video_count) / (total_runs + 1))
        
        # Update best settings if this run was better
        if metrics.efficiency_score() > profile['avg_efficiency']:
            profile['best_settings'] = metrics.optimization_settings.copy()
    
    def _learn_optimization_patterns(self, metrics: ProcessingMetrics):
        """Learn which optimization settings work best"""
        efficiency = metrics.efficiency_score()
        
        # Record pattern for each setting
        for setting, value in metrics.optimization_settings.items():
            pattern_key = f"{setting}_{value}"
            self.optimization_patterns[pattern_key].append({
                'efficiency': efficiency,
                'quality': metrics.quality_score,
                'processing_time': metrics.processing_time,
                'timestamp': metrics.timestamp.isoformat()
            })
            
            # Keep only recent patterns (last 50 observations per pattern)
            if len(self.optimization_patterns[pattern_key]) > 50:
                self.optimization_patterns[pattern_key] = self.optimization_patterns[pattern_key][-50:]
    
    def _update_optimal_settings(self, metrics: ProcessingMetrics):
        """Update optimal settings based on successful runs"""
        efficiency = metrics.efficiency_score()
        
        # Only learn from high-performing runs
        if efficiency > self._get_baseline_efficiency() * 1.1:  # 10% better than baseline
            # Gradually adjust optimal settings using learning rate
            for setting, value in metrics.optimization_settings.items():
                if setting in self.optimal_settings:
                    current = self.optimal_settings[setting]
                    
                    # For numeric values, use weighted average
                    if isinstance(value, (int, float)) and isinstance(current, (int, float)):
                        new_value = current * (1 - self.learning_rate) + value * self.learning_rate
                        self.optimal_settings[setting] = new_value
                    
                    # For categorical values, switch if consistently better
                    elif value != current:
                        # Count recent successes with this value
                        recent_runs = [m for m in list(self.metrics_history)[-20:] 
                                     if m.optimization_settings.get(setting) == value]
                        if len(recent_runs) >= 3:  # Need at least 3 good runs
                            avg_efficiency = statistics.mean([r.efficiency_score() for r in recent_runs])
                            if avg_efficiency > self._get_baseline_efficiency() * 1.15:  # 15% better
                                self.optimal_settings[setting] = value
                                logger.info(f"🎯 Updated optimal {setting}: {current} → {value}")
    
    def _get_baseline_efficiency(self) -> float:
        """Get baseline efficiency score for comparison"""
        if len(self.metrics_history) < 5:
            return 1.0  # Default baseline
        
        recent_runs = list(self.metrics_history)[-20:]  # Last 20 runs
        efficiencies = [m.efficiency_score() for m in recent_runs]
        return statistics.median(efficiencies)
    
    def get_optimized_settings(self, content_type: str = "general", 
                             video_count: int = 5,
                             estimated_duration: float = 300) -> Dict[str, Any]:
        """Get optimized settings for a specific content type and project"""
        
        # Start with current optimal settings
        settings = self.optimal_settings.copy()
        
        # Adjust based on content type profile
        if content_type in self.content_profiles:
            profile = self.content_profiles[content_type]
            if profile['best_settings']:
                # Blend profile-specific settings with general optimal settings
                for key, value in profile['best_settings'].items():
                    if key in settings:
                        settings[key] = value
        
        # Adjust based on project characteristics
        settings = self._adjust_for_project_characteristics(settings, video_count, estimated_duration)
        
        logger.info(f"🎯 Generated optimized settings for {content_type}: {video_count} videos, {estimated_duration:.0f}s")
        
        return settings
    
    def _adjust_for_project_characteristics(self, settings: Dict[str, Any], 
                                          video_count: int, 
                                          estimated_duration: float) -> Dict[str, Any]:
        """Adjust settings based on project size and characteristics"""
        
        # Adjust worker count based on project size
        if video_count > 20:
            settings['max_workers'] = min(6, settings.get('max_workers', 4) + 1)
        elif video_count < 5:
            settings['max_workers'] = max(2, settings.get('max_workers', 4) - 1)
        
        # Adjust timeout based on estimated duration
        if estimated_duration > 1200:  # Over 20 minutes of content
            settings['processing_timeout'] = max(1200, settings.get('processing_timeout', 900))
        elif estimated_duration < 300:  # Under 5 minutes
            settings['processing_timeout'] = 600
        
        # Adjust quality preset based on content length
        if estimated_duration > 1800:  # Over 30 minutes - prioritize speed
            settings['quality_preset'] = 'fast'
        elif estimated_duration < 180:  # Under 3 minutes - prioritize quality
            settings['quality_preset'] = 'quality'
        
        return settings
    
    def generate_optimization_suggestions(self) -> List[OptimizationSuggestion]:
        """Generate suggestions for improving current optimal settings"""
        suggestions = []
        
        if len(self.metrics_history) < 10:
            return suggestions  # Need more data
        
        # Analyze recent performance trends
        recent_runs = list(self.metrics_history)[-20:]
        
        for parameter, param_range in self.parameter_ranges.items():
            if parameter not in self.optimal_settings:
                continue
                
            current_value = self.optimal_settings[parameter]
            suggestion = self._analyze_parameter_optimization(parameter, current_value, recent_runs)
            
            if suggestion:
                suggestions.append(suggestion)
        
        # Sort by expected improvement
        suggestions.sort(key=lambda s: s.expected_improvement, reverse=True)
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def _analyze_parameter_optimization(self, parameter: str, current_value: Any, 
                                      recent_runs: List[ProcessingMetrics]) -> Optional[OptimizationSuggestion]:
        """Analyze if a parameter could be optimized"""
        
        # Get performance data for different values of this parameter
        performance_by_value = defaultdict(list)
        
        for run in recent_runs:
            value = run.optimization_settings.get(parameter)
            if value is not None:
                performance_by_value[value].append(run.efficiency_score())
        
        if len(performance_by_value) < 2:
            return None  # Need data from multiple values
        
        # Calculate average performance for each value
        avg_performance = {}
        for value, performances in performance_by_value.items():
            if len(performances) >= 2:  # Need at least 2 data points
                avg_performance[value] = statistics.mean(performances)
        
        if len(avg_performance) < 2:
            return None
        
        # Find best performing value
        best_value = max(avg_performance.keys(), key=lambda v: avg_performance[v])
        current_performance = avg_performance.get(current_value, 0)
        best_performance = avg_performance[best_value]
        
        # Only suggest if improvement is significant
        if best_value != current_value and best_performance > current_performance * 1.05:  # 5% improvement
            confidence = min(0.9, len(performance_by_value[best_value]) / 10)  # More data = higher confidence
            expected_improvement = (best_performance - current_performance) / current_performance
            
            reasoning = f"Analysis of {len(performance_by_value[best_value])} runs shows " \
                       f"{expected_improvement:.1%} better efficiency with {parameter}={best_value}"
            
            return OptimizationSuggestion(
                parameter=parameter,
                current_value=current_value,
                suggested_value=best_value,
                confidence=confidence,
                reasoning=reasoning,
                expected_improvement=expected_improvement
            )
        
        return None
    
    def apply_suggestion(self, suggestion: OptimizationSuggestion):
        """Apply an optimization suggestion to the optimal settings"""
        if suggestion.confidence > 0.6:  # Only apply high-confidence suggestions
            old_value = self.optimal_settings.get(suggestion.parameter)
            self.optimal_settings[suggestion.parameter] = suggestion.suggested_value
            self._save_learning_data()
            
            logger.info(f"✅ Applied optimization: {suggestion.parameter} "
                       f"{old_value} → {suggestion.suggested_value} "
                       f"(Expected improvement: {suggestion.expected_improvement:.1%})")
            return True
        else:
            logger.info(f"⚠️ Suggestion confidence too low ({suggestion.confidence:.2f}), not applying")
            return False
    
    def get_performance_analytics(self) -> Dict[str, Any]:
        """Get comprehensive performance analytics"""
        if not self.metrics_history:
            return {'error': 'No performance data available'}
        
        runs = list(self.metrics_history)
        recent_runs = runs[-20:]  # Last 20 runs
        
        # Overall statistics
        all_quality = [r.quality_score for r in runs]
        all_efficiency = [r.efficiency_score() for r in runs]
        recent_quality = [r.quality_score for r in recent_runs]
        recent_efficiency = [r.efficiency_score() for r in recent_runs]
        
        # Trend analysis
        quality_trend = 'stable'
        efficiency_trend = 'stable'
        
        if len(runs) >= 10:
            early_quality = statistics.mean([r.quality_score for r in runs[:10]])
            late_quality = statistics.mean([r.quality_score for r in runs[-10:]])
            
            if late_quality > early_quality * 1.05:
                quality_trend = 'improving'
            elif late_quality < early_quality * 0.95:
                quality_trend = 'declining'
            
            early_efficiency = statistics.mean([r.efficiency_score() for r in runs[:10]])
            late_efficiency = statistics.mean([r.efficiency_score() for r in runs[-10:]])
            
            if late_efficiency > early_efficiency * 1.05:
                efficiency_trend = 'improving'
            elif late_efficiency < early_efficiency * 0.95:
                efficiency_trend = 'declining'
        
        analytics = {
            'total_runs': len(runs),
            'date_range': {
                'first_run': runs[0].timestamp.isoformat(),
                'last_run': runs[-1].timestamp.isoformat()
            },
            'quality_metrics': {
                'overall_average': statistics.mean(all_quality),
                'recent_average': statistics.mean(recent_quality),
                'best_score': max(all_quality),
                'trend': quality_trend
            },
            'efficiency_metrics': {
                'overall_average': statistics.mean(all_efficiency),
                'recent_average': statistics.mean(recent_efficiency),
                'best_score': max(all_efficiency),
                'trend': efficiency_trend
            },
            'content_type_breakdown': {},
            'optimization_impact': self._calculate_optimization_impact(),
            'current_optimal_settings': self.optimal_settings.copy()
        }
        
        # Content type breakdown
        content_types = set(r.content_type for r in runs)
        for content_type in content_types:
            type_runs = [r for r in runs if r.content_type == content_type]
            analytics['content_type_breakdown'][content_type] = {
                'runs': len(type_runs),
                'avg_quality': statistics.mean([r.quality_score for r in type_runs]),
                'avg_efficiency': statistics.mean([r.efficiency_score() for r in type_runs])
            }
        
        return analytics
    
    def _calculate_optimization_impact(self) -> Dict[str, float]:
        """Calculate the impact of optimization over time"""
        if len(self.metrics_history) < 20:
            return {'insufficient_data': True}
        
        runs = list(self.metrics_history)
        
        # Compare first quarter vs last quarter
        quarter_size = len(runs) // 4
        early_runs = runs[:quarter_size]
        recent_runs = runs[-quarter_size:]
        
        early_quality = statistics.mean([r.quality_score for r in early_runs])
        recent_quality = statistics.mean([r.quality_score for r in recent_runs])
        
        early_efficiency = statistics.mean([r.efficiency_score() for r in early_runs])
        recent_efficiency = statistics.mean([r.efficiency_score() for r in recent_runs])
        
        return {
            'quality_improvement': (recent_quality - early_quality) / early_quality,
            'efficiency_improvement': (recent_efficiency - early_efficiency) / early_efficiency,
            'runs_analyzed': len(runs),
            'learning_period_days': (runs[-1].timestamp - runs[0].timestamp).days
        }
    
    def generate_optimization_report(self) -> str:
        """Generate human-readable optimization report"""
        analytics = self.get_performance_analytics()
        suggestions = self.generate_optimization_suggestions()
        
        report = f"""
🤖 DYNAMIC OPTIMIZATION REPORT
{'='*50}

📊 PERFORMANCE OVERVIEW:
• Total Processing Runs: {analytics['total_runs']}
• Average Quality Score: {analytics['quality_metrics']['overall_average']:.3f}
• Average Efficiency: {analytics['efficiency_metrics']['overall_average']:.2f}
• Quality Trend: {analytics['quality_metrics']['trend'].title()}
• Efficiency Trend: {analytics['efficiency_metrics']['trend'].title()}

🎯 OPTIMIZATION IMPACT:
"""
        
        if 'insufficient_data' not in analytics['optimization_impact']:
            impact = analytics['optimization_impact']
            report += f"""• Quality Improvement: {impact['quality_improvement']:.1%}
• Efficiency Improvement: {impact['efficiency_improvement']:.1%}
• Learning Period: {impact['learning_period_days']} days
"""
        else:
            report += "• Insufficient data for impact analysis (need 20+ runs)\n"
        
        report += f"""
⚙️ CURRENT OPTIMAL SETTINGS:
"""
        for key, value in self.optimal_settings.items():
            report += f"• {key}: {value}\n"
        
        if suggestions:
            report += f"""
💡 OPTIMIZATION SUGGESTIONS:
"""
            for i, suggestion in enumerate(suggestions, 1):
                report += f"""{i}. {suggestion.parameter}: {suggestion.current_value} → {suggestion.suggested_value}
   Confidence: {suggestion.confidence:.1%}, Expected improvement: {suggestion.expected_improvement:.1%}
   {suggestion.reasoning}

"""
        else:
            report += "\n✅ No optimization suggestions - current settings appear optimal!\n"
        
        report += f"""
📈 CONTENT TYPE PERFORMANCE:
"""
        for content_type, stats in analytics['content_type_breakdown'].items():
            report += f"• {content_type.title()}: {stats['runs']} runs, "
            report += f"Quality: {stats['avg_quality']:.3f}, Efficiency: {stats['avg_efficiency']:.2f}\n"
        
        report += f"""
{'='*50}
🤖 Dynamic Learning System Active
"""
        
        return report


def main():
    """Demo usage of dynamic optimizer"""
    optimizer = DynamicOptimizer()
    
    # Simulate recording some metrics (in real usage, this comes from actual pipeline runs)
    optimizer.record_processing_metrics(
        project_name="nycap-portalcam",
        content_type="interview",
        video_count=26,
        total_duration=1720,  # ~28 minutes
        processing_time=195,   # Current optimized time
        quality_score=0.87,
        success_rate=1.0,
        settings={
            'max_workers': 4,
            'render_quality': 0.85,
            'social_clip_count': 5,
            'parallel_transcription': True,
            'quality_preset': 'balanced'
        }
    )
    
    # Get optimized settings for a new project
    optimized_settings = optimizer.get_optimized_settings(
        content_type="interview",
        video_count=15,
        estimated_duration=900
    )
    
    print("🎯 Optimized Settings for New Project:")
    for key, value in optimized_settings.items():
        print(f"  {key}: {value}")
    
    # Generate optimization report
    report = optimizer.generate_optimization_report()
    print(report)
    
    # Get optimization suggestions
    suggestions = optimizer.get_optimization_suggestions()
    if suggestions:
        print(f"\n💡 Top Optimization Suggestions:")
        for suggestion in suggestions[:3]:
            print(f"• {suggestion.parameter}: {suggestion.current_value} → {suggestion.suggested_value}")
            print(f"  Expected improvement: {suggestion.expected_improvement:.1%}")


if __name__ == "__main__":
    main()
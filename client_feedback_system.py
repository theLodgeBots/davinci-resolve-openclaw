#!/usr/bin/env python3
"""
Client Feedback Integration System for DaVinci Resolve OpenClaw
Advanced preference learning and adaptation system

Features:
- Client preference tracking and learning
- Automated workflow adaptation based on feedback
- Quality preference profiling per client
- Feedback-driven optimization suggestions
- Historical preference analysis and trending
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
import statistics
from dataclasses import dataclass, asdict
from collections import defaultdict
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ClientPreference:
    """Individual client preference record"""
    client_id: str
    project_name: str
    preference_type: str  # style, pacing, music, color_grade, etc.
    rating: int  # 1-5 scale
    feedback_text: str
    timestamp: datetime
    content_type: str  # interview, presentation, vlog, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClientPreference':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class ClientProfile:
    """Aggregate client preferences and tendencies"""
    client_id: str
    total_projects: int
    avg_satisfaction: float
    style_preferences: Dict[str, float]  # style -> preference score
    pacing_preferences: Dict[str, float]  # fast/medium/slow -> preference score
    color_preferences: Dict[str, float]  # warm/cool/neutral -> preference score
    music_preferences: Dict[str, float]  # energetic/calm/no_music -> preference score
    preferred_lengths: Dict[str, float]  # short/medium/long -> preference score
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['last_updated'] = self.last_updated.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClientProfile':
        """Create from dictionary"""
        data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        return cls(**data)

class ClientFeedbackSystem:
    def __init__(self):
        """Initialize client feedback system"""
        self.openai_client = OpenAI()
        self.feedback_dir = Path("client_feedback")
        self.feedback_dir.mkdir(exist_ok=True)
        
        self.feedback_file = self.feedback_dir / "feedback_history.json"
        self.profiles_file = self.feedback_dir / "client_profiles.json"
        
        # Load existing data
        self.feedback_history = self._load_feedback_history()
        self.client_profiles = self._load_client_profiles()
        
        # Preference categories and their possible values
        self.preference_categories = {
            'style': ['cinematic', 'documentary', 'corporate', 'creative', 'minimalist'],
            'pacing': ['fast', 'medium', 'slow', 'dynamic'],
            'color_grade': ['warm', 'cool', 'neutral', 'vibrant', 'muted'],
            'music': ['energetic', 'calm', 'dramatic', 'no_music'],
            'length': ['short', 'medium', 'long'],
            'b_roll_usage': ['heavy', 'moderate', 'minimal'],
            'transitions': ['smooth', 'dynamic', 'minimal'],
            'text_overlay': ['frequent', 'moderate', 'minimal']
        }
        
        logger.info("Client Feedback System initialized")
    
    def _load_feedback_history(self) -> List[ClientPreference]:
        """Load feedback history from file"""
        if not self.feedback_file.exists():
            return []
        
        try:
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            return [ClientPreference.from_dict(item) for item in data]
        except Exception as e:
            logger.error(f"Error loading feedback history: {e}")
            return []
    
    def _load_client_profiles(self) -> Dict[str, ClientProfile]:
        """Load client profiles from file"""
        if not self.profiles_file.exists():
            return {}
        
        try:
            with open(self.profiles_file, 'r') as f:
                data = json.load(f)
            return {client_id: ClientProfile.from_dict(profile_data) 
                   for client_id, profile_data in data.items()}
        except Exception as e:
            logger.error(f"Error loading client profiles: {e}")
            return {}
    
    def _save_feedback_history(self):
        """Save feedback history to file"""
        try:
            data = [feedback.to_dict() for feedback in self.feedback_history]
            with open(self.feedback_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving feedback history: {e}")
    
    def _save_client_profiles(self):
        """Save client profiles to file"""
        try:
            data = {client_id: profile.to_dict() 
                   for client_id, profile in self.client_profiles.items()}
            with open(self.profiles_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving client profiles: {e}")
    
    def collect_feedback(self, client_id: str, project_name: str, 
                        feedback_data: Dict[str, Any]) -> bool:
        """
        Collect and process client feedback
        
        feedback_data format:
        {
            'overall_rating': 4,
            'overall_feedback': 'Great work, but...',
            'style_rating': 5,
            'style_feedback': 'Perfect cinematic feel',
            'pacing_rating': 3,
            'pacing_feedback': 'A bit too fast',
            'color_rating': 4,
            'color_feedback': 'Love the warm tones',
            'music_rating': 5,
            'music_feedback': 'Perfect background music choice',
            'length_rating': 4,
            'length_feedback': 'Good length overall',
            'content_type': 'interview'
        }
        """
        try:
            timestamp = datetime.now()
            
            # Process each feedback category
            for category in ['overall', 'style', 'pacing', 'color', 'music', 'length']:
                rating_key = f'{category}_rating'
                feedback_key = f'{category}_feedback'
                
                if rating_key in feedback_data and feedback_key in feedback_data:
                    preference = ClientPreference(
                        client_id=client_id,
                        project_name=project_name,
                        preference_type=category,
                        rating=feedback_data[rating_key],
                        feedback_text=feedback_data[feedback_key],
                        timestamp=timestamp,
                        content_type=feedback_data.get('content_type', 'unknown')
                    )
                    self.feedback_history.append(preference)
            
            # Update client profile
            self._update_client_profile(client_id, feedback_data)
            
            # Save data
            self._save_feedback_history()
            self._save_client_profiles()
            
            logger.info(f"Collected feedback for client {client_id}, project {project_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error collecting feedback: {e}")
            return False
    
    def _update_client_profile(self, client_id: str, feedback_data: Dict[str, Any]):
        """Update client profile based on new feedback"""
        if client_id not in self.client_profiles:
            # Create new profile
            self.client_profiles[client_id] = ClientProfile(
                client_id=client_id,
                total_projects=0,
                avg_satisfaction=0.0,
                style_preferences={},
                pacing_preferences={},
                color_preferences={},
                music_preferences={},
                preferred_lengths={},
                last_updated=datetime.now()
            )
        
        profile = self.client_profiles[client_id]
        profile.total_projects += 1
        profile.last_updated = datetime.now()
        
        # Update satisfaction average
        if 'overall_rating' in feedback_data:
            current_total = profile.avg_satisfaction * (profile.total_projects - 1)
            profile.avg_satisfaction = (current_total + feedback_data['overall_rating']) / profile.total_projects
        
        # Update category preferences based on ratings and AI analysis of feedback text
        self._analyze_preference_signals(profile, feedback_data)
    
    def _analyze_preference_signals(self, profile: ClientProfile, feedback_data: Dict[str, Any]):
        """Use AI to analyze feedback text and extract preference signals"""
        try:
            # Prepare feedback text for analysis
            feedback_text = ""
            for key, value in feedback_data.items():
                if key.endswith('_feedback') and value:
                    category = key.replace('_feedback', '')
                    rating = feedback_data.get(f'{category}_rating', 0)
                    feedback_text += f"{category} (rated {rating}/5): {value}\n"
            
            if not feedback_text.strip():
                return
            
            # AI analysis prompt
            prompt = f"""
            Analyze this client feedback and extract specific preferences. Return JSON with preference scores (0.0-1.0):
            
            Feedback:
            {feedback_text}
            
            Extract preferences for these categories:
            - style: cinematic, documentary, corporate, creative, minimalist
            - pacing: fast, medium, slow, dynamic  
            - color_grade: warm, cool, neutral, vibrant, muted
            - music: energetic, calm, dramatic, no_music
            - length: short, medium, long
            - b_roll_usage: heavy, moderate, minimal
            - transitions: smooth, dynamic, minimal
            - text_overlay: frequent, moderate, minimal
            
            Return only JSON with format:
            {{
                "style": {{"cinematic": 0.8, "corporate": 0.2}},
                "pacing": {{"medium": 0.9}},
                ...
            }}
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3
            )
            
            preferences = json.loads(response.choices[0].message.content)
            
            # Update profile preferences
            for category, values in preferences.items():
                if category == 'style':
                    self._update_preference_dict(profile.style_preferences, values)
                elif category == 'pacing':
                    self._update_preference_dict(profile.pacing_preferences, values)
                elif category == 'color_grade':
                    self._update_preference_dict(profile.color_preferences, values)
                elif category == 'music':
                    self._update_preference_dict(profile.music_preferences, values)
                elif category == 'length':
                    self._update_preference_dict(profile.preferred_lengths, values)
            
        except Exception as e:
            logger.warning(f"Could not analyze preference signals: {e}")
    
    def _update_preference_dict(self, preference_dict: Dict[str, float], 
                               new_values: Dict[str, float], learning_rate: float = 0.3):
        """Update preference dictionary with new values using exponential smoothing"""
        for key, new_score in new_values.items():
            if key in preference_dict:
                # Exponential smoothing: new = alpha * new + (1-alpha) * old
                preference_dict[key] = learning_rate * new_score + (1 - learning_rate) * preference_dict[key]
            else:
                preference_dict[key] = new_score * learning_rate  # Conservative start
    
    def get_client_preferences(self, client_id: str) -> Optional[ClientProfile]:
        """Get client preference profile"""
        return self.client_profiles.get(client_id)
    
    def generate_optimization_suggestions(self, client_id: str, 
                                        content_type: str = 'interview') -> Dict[str, Any]:
        """Generate workflow optimization suggestions based on client preferences"""
        if client_id not in self.client_profiles:
            return {"status": "no_profile", "suggestions": []}
        
        profile = self.client_profiles[client_id]
        suggestions = {
            "status": "success",
            "client_satisfaction": profile.avg_satisfaction,
            "optimization_suggestions": [],
            "workflow_adjustments": {}
        }
        
        try:
            # Style suggestions
            if profile.style_preferences:
                top_style = max(profile.style_preferences, key=profile.style_preferences.get)
                suggestions["workflow_adjustments"]["preferred_style"] = top_style
                suggestions["optimization_suggestions"].append(
                    f"Client prefers {top_style} style (score: {profile.style_preferences[top_style]:.2f})"
                )
            
            # Pacing suggestions
            if profile.pacing_preferences:
                top_pacing = max(profile.pacing_preferences, key=profile.pacing_preferences.get)
                suggestions["workflow_adjustments"]["preferred_pacing"] = top_pacing
                suggestions["optimization_suggestions"].append(
                    f"Client prefers {top_pacing} pacing (score: {profile.pacing_preferences[top_pacing]:.2f})"
                )
            
            # Color grading suggestions
            if profile.color_preferences:
                top_color = max(profile.color_preferences, key=profile.color_preferences.get)
                suggestions["workflow_adjustments"]["color_grade"] = top_color
                suggestions["optimization_suggestions"].append(
                    f"Client prefers {top_color} color grading (score: {profile.color_preferences[top_color]:.2f})"
                )
            
            # Music suggestions
            if profile.music_preferences:
                top_music = max(profile.music_preferences, key=profile.music_preferences.get)
                suggestions["workflow_adjustments"]["music_style"] = top_music
                suggestions["optimization_suggestions"].append(
                    f"Client prefers {top_music} music style (score: {profile.music_preferences[top_music]:.2f})"
                )
            
            # Length suggestions
            if profile.preferred_lengths:
                top_length = max(profile.preferred_lengths, key=profile.preferred_lengths.get)
                suggestions["workflow_adjustments"]["preferred_length"] = top_length
                suggestions["optimization_suggestions"].append(
                    f"Client prefers {top_length} video lengths (score: {profile.preferred_lengths[top_length]:.2f})"
                )
            
        except Exception as e:
            logger.error(f"Error generating suggestions for {client_id}: {e}")
            suggestions["status"] = "error"
            suggestions["error"] = str(e)
        
        return suggestions
    
    def get_feedback_analytics(self, client_id: Optional[str] = None, 
                             days_back: int = 30) -> Dict[str, Any]:
        """Get analytics on feedback trends"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Filter feedback by date and optionally by client
        relevant_feedback = [
            f for f in self.feedback_history 
            if f.timestamp > cutoff_date and (client_id is None or f.client_id == client_id)
        ]
        
        if not relevant_feedback:
            return {"status": "no_data", "message": "No feedback data in specified timeframe"}
        
        analytics = {
            "status": "success",
            "total_feedback_items": len(relevant_feedback),
            "unique_clients": len(set(f.client_id for f in relevant_feedback)),
            "unique_projects": len(set(f.project_name for f in relevant_feedback)),
            "rating_distribution": defaultdict(int),
            "category_averages": defaultdict(list),
            "trending_preferences": {},
            "client_satisfaction_trend": []
        }
        
        # Calculate rating distribution and category averages
        for feedback in relevant_feedback:
            analytics["rating_distribution"][feedback.rating] += 1
            analytics["category_averages"][feedback.preference_type].append(feedback.rating)
        
        # Convert to averages
        for category, ratings in analytics["category_averages"].items():
            analytics["category_averages"][category] = statistics.mean(ratings)
        
        # Client satisfaction trends (if specific client)
        if client_id:
            client_feedback = [f for f in relevant_feedback if f.preference_type == 'overall']
            client_feedback.sort(key=lambda x: x.timestamp)
            analytics["client_satisfaction_trend"] = [
                {"date": f.timestamp.isoformat()[:10], "rating": f.rating} 
                for f in client_feedback
            ]
        
        return analytics
    
    def export_client_report(self, client_id: str, output_file: Optional[str] = None) -> bool:
        """Export comprehensive client preference report"""
        if client_id not in self.client_profiles:
            logger.error(f"No profile found for client {client_id}")
            return False
        
        profile = self.client_profiles[client_id]
        analytics = self.get_feedback_analytics(client_id=client_id, days_back=90)
        suggestions = self.generate_optimization_suggestions(client_id)
        
        report = {
            "client_id": client_id,
            "report_generated": datetime.now().isoformat(),
            "profile_summary": {
                "total_projects": profile.total_projects,
                "average_satisfaction": profile.avg_satisfaction,
                "last_updated": profile.last_updated.isoformat()
            },
            "preferences": {
                "style": dict(profile.style_preferences),
                "pacing": dict(profile.pacing_preferences),
                "color": dict(profile.color_preferences),
                "music": dict(profile.music_preferences),
                "length": dict(profile.preferred_lengths)
            },
            "analytics": analytics,
            "optimization_suggestions": suggestions
        }
        
        if output_file is None:
            output_file = f"client_report_{client_id}_{datetime.now().strftime('%Y%m%d')}.json"
        
        try:
            with open(self.feedback_dir / output_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Client report exported to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Error exporting client report: {e}")
            return False

def demo_feedback_collection():
    """Demo function showing how to collect client feedback"""
    system = ClientFeedbackSystem()
    
    # Example feedback collection
    demo_feedback = {
        'overall_rating': 4,
        'overall_feedback': 'Great work overall, but could use some improvements in pacing',
        'style_rating': 5,
        'style_feedback': 'Perfect cinematic style, exactly what we wanted',
        'pacing_rating': 3,
        'pacing_feedback': 'A bit too fast, would prefer slower transitions',
        'color_rating': 4,
        'color_feedback': 'Love the warm color grading, very professional',
        'music_rating': 5,
        'music_feedback': 'Background music choice was perfect, not distracting',
        'length_rating': 4,
        'length_feedback': 'Good length for social media',
        'content_type': 'interview'
    }
    
    # Collect feedback
    success = system.collect_feedback(
        client_id="demo_client_001",
        project_name="demo_project",
        feedback_data=demo_feedback
    )
    
    if success:
        print("✅ Feedback collected successfully")
        
        # Generate suggestions
        suggestions = system.generate_optimization_suggestions("demo_client_001")
        print(f"💡 Optimization suggestions: {suggestions}")
        
        # Get analytics
        analytics = system.get_feedback_analytics(client_id="demo_client_001")
        print(f"📊 Analytics: {analytics}")
        
        # Export report
        system.export_client_report("demo_client_001")
        print("📄 Client report exported")
    else:
        print("❌ Error collecting feedback")

if __name__ == "__main__":
    demo_feedback_collection()
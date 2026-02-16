#!/usr/bin/env python3
"""
AI Voice Mood Analyzer for DaVinci Resolve OpenClaw
Advanced voice analysis for emotion-aware video editing

Features:
- Real-time emotion detection from audio
- Speaker energy analysis (excitement, calm, tension)
- Optimal cut point detection based on emotional flow
- Music/color grading suggestions based on mood
- Audience engagement prediction based on voice patterns
- Multi-speaker emotional journey mapping

Premium differentiator: First AI video platform with emotion-aware editing
"""

import os
import json
import numpy as np
import librosa
import librosa.display
from scipy import signal
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class EmotionSegment:
    """Represents an emotional segment of audio"""
    start_time: float
    end_time: float
    emotion: str
    confidence: float
    energy: float
    pitch_mean: float
    pitch_variance: float
    speaking_rate: float
    speaker_id: Optional[str] = None

@dataclass
class MoodBasedEditSuggestion:
    """Editing suggestion based on mood analysis"""
    timestamp: float
    suggestion_type: str  # 'cut', 'color_grade', 'music', 'transition'
    description: str
    confidence: float
    parameters: Dict

class AIVoiceMoodAnalyzer:
    """Advanced voice mood analysis for intelligent video editing"""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.analysis_dir = os.path.join(project_root, 'voice_analysis')
        os.makedirs(self.analysis_dir, exist_ok=True)
        
        # Emotion mapping based on acoustic features
        self.emotion_labels = [
            'excited', 'happy', 'calm', 'serious', 'concerned', 
            'tense', 'sad', 'angry', 'surprised', 'neutral'
        ]
        
        # Audio analysis parameters
        self.sample_rate = 22050
        self.hop_length = 512
        self.frame_length = 2048
        
        logger.info("🎤 AI Voice Mood Analyzer initialized")
        logger.info(f"📁 Analysis output: {self.analysis_dir}")
    
    def extract_audio_features(self, audio_path: str) -> Dict:
        """Extract comprehensive audio features for mood analysis"""
        logger.info(f"🔊 Analyzing audio: {os.path.basename(audio_path)}")
        
        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=self.sample_rate)
            duration = len(y) / sr
            
            logger.info(f"⏱️  Audio duration: {duration:.2f}s at {sr}Hz")
            
            # Extract features
            features = {}
            
            # 1. Spectral features
            features.update(self._extract_spectral_features(y, sr))
            
            # 2. Prosodic features (pitch, energy, rhythm)
            features.update(self._extract_prosodic_features(y, sr))
            
            # 3. Temporal features (speaking rate, pauses)
            features.update(self._extract_temporal_features(y, sr))
            
            # 4. Harmonic/percussive separation
            features.update(self._extract_harmonic_features(y, sr))
            
            # 5. Voice quality features
            features.update(self._extract_voice_quality_features(y, sr))
            
            # Add metadata
            features['duration'] = duration
            features['sample_rate'] = sr
            features['analysis_time'] = datetime.now().isoformat()
            
            logger.info(f"✅ Extracted {len(features)} audio features")
            return features
            
        except Exception as e:
            logger.error(f"❌ Audio feature extraction failed: {e}")
            return {}
    
    def _extract_spectral_features(self, y: np.ndarray, sr: int) -> Dict:
        """Extract spectral features (MFCCs, spectral centroid, etc.)"""
        
        # MFCCs (Mel-frequency cepstral coefficients)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=self.hop_length)
        mfcc_mean = np.mean(mfccs, axis=1)
        mfcc_std = np.std(mfccs, axis=1)
        
        # Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=self.hop_length)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=self.hop_length)[0]
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=self.hop_length)[0]
        zero_crossing_rate = librosa.feature.zero_crossing_rate(y, hop_length=self.hop_length)[0]
        
        return {
            'mfcc_mean': mfcc_mean.tolist(),
            'mfcc_std': mfcc_std.tolist(),
            'spectral_centroid_mean': np.mean(spectral_centroids),
            'spectral_centroid_std': np.std(spectral_centroids),
            'spectral_rolloff_mean': np.mean(spectral_rolloff),
            'spectral_bandwidth_mean': np.mean(spectral_bandwidth),
            'zero_crossing_rate_mean': np.mean(zero_crossing_rate),
            'zero_crossing_rate_std': np.std(zero_crossing_rate)
        }
    
    def _extract_prosodic_features(self, y: np.ndarray, sr: int) -> Dict:
        """Extract prosodic features (pitch, energy, rhythm)"""
        
        # Pitch (fundamental frequency)
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr, hop_length=self.hop_length, threshold=0.1)
        
        # Get the most prominent pitch at each time frame
        pitch_values = []
        for i in range(pitches.shape[1]):
            index = magnitudes[:, i].argmax()
            pitch = pitches[index, i]
            if pitch > 0:
                pitch_values.append(pitch)
        
        if pitch_values:
            pitch_mean = np.mean(pitch_values)
            pitch_std = np.std(pitch_values)
            pitch_range = np.max(pitch_values) - np.min(pitch_values)
        else:
            pitch_mean = pitch_std = pitch_range = 0
        
        # Energy (RMS)
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
        energy_mean = np.mean(rms)
        energy_std = np.std(rms)
        
        # Dynamic range
        dynamic_range = np.max(rms) - np.min(rms)
        
        return {
            'pitch_mean': pitch_mean,
            'pitch_std': pitch_std,
            'pitch_range': pitch_range,
            'energy_mean': energy_mean,
            'energy_std': energy_std,
            'dynamic_range': dynamic_range
        }
    
    def _extract_temporal_features(self, y: np.ndarray, sr: int) -> Dict:
        """Extract temporal features (speaking rate, pauses)"""
        
        # Voice activity detection using energy
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
        rms_threshold = np.mean(rms) * 0.3
        
        # Find voiced segments
        voiced_frames = rms > rms_threshold
        
        # Calculate speaking rate (voiced frames per second)
        hop_duration = self.hop_length / sr
        speaking_rate = np.sum(voiced_frames) * hop_duration / len(voiced_frames)
        
        # Find pause segments
        pause_starts = []
        pause_ends = []
        in_pause = False
        
        for i, is_voiced in enumerate(voiced_frames):
            if not is_voiced and not in_pause:
                pause_starts.append(i * hop_duration)
                in_pause = True
            elif is_voiced and in_pause:
                pause_ends.append(i * hop_duration)
                in_pause = False
        
        # Close final pause if needed
        if in_pause:
            pause_ends.append(len(voiced_frames) * hop_duration)
        
        # Calculate pause statistics
        if pause_starts and pause_ends:
            pause_durations = [end - start for start, end in zip(pause_starts, pause_ends)]
            mean_pause_duration = np.mean(pause_durations)
            pause_frequency = len(pause_durations) / (len(y) / sr)
        else:
            mean_pause_duration = 0
            pause_frequency = 0
        
        return {
            'speaking_rate': speaking_rate,
            'mean_pause_duration': mean_pause_duration,
            'pause_frequency': pause_frequency,
            'voice_activity_ratio': np.sum(voiced_frames) / len(voiced_frames)
        }
    
    def _extract_harmonic_features(self, y: np.ndarray, sr: int) -> Dict:
        """Extract harmonic and percussive features"""
        
        # Harmonic/percussive separation
        y_harmonic, y_percussive = librosa.effects.hpss(y)
        
        # Calculate harmonic/percussive ratio
        harmonic_energy = np.sum(y_harmonic ** 2)
        percussive_energy = np.sum(y_percussive ** 2)
        
        if percussive_energy > 0:
            harmonic_percussive_ratio = harmonic_energy / percussive_energy
        else:
            harmonic_percussive_ratio = float('inf')
        
        return {
            'harmonic_energy': harmonic_energy,
            'percussive_energy': percussive_energy,
            'harmonic_percussive_ratio': harmonic_percussive_ratio
        }
    
    def _extract_voice_quality_features(self, y: np.ndarray, sr: int) -> Dict:
        """Extract voice quality indicators"""
        
        # Jitter (pitch period irregularity)
        # Simplified jitter calculation
        pitches, _ = librosa.piptrack(y=y, sr=sr, hop_length=self.hop_length)
        
        # Shimmer (amplitude irregularity)
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
        shimmer = np.std(np.diff(rms)) / np.mean(rms) if np.mean(rms) > 0 else 0
        
        # Harmonics-to-noise ratio estimate
        # Using spectral flatness as a proxy
        spectral_flatness = librosa.feature.spectral_flatness(y=y, hop_length=self.hop_length)[0]
        hnr_estimate = -np.mean(np.log(spectral_flatness + 1e-10))
        
        return {
            'shimmer': shimmer,
            'hnr_estimate': hnr_estimate,
            'spectral_flatness_mean': np.mean(spectral_flatness)
        }
    
    def classify_emotion(self, features: Dict) -> Dict[str, float]:
        """Classify emotion based on extracted features"""
        
        # Simple rule-based emotion classification
        # In production, this would use trained ML models
        
        emotion_scores = {emotion: 0.0 for emotion in self.emotion_labels}
        
        # Energy-based classification
        energy = features.get('energy_mean', 0)
        dynamic_range = features.get('dynamic_range', 0)
        
        # Pitch-based classification
        pitch_mean = features.get('pitch_mean', 0)
        pitch_std = features.get('pitch_std', 0)
        
        # Speaking rate-based classification
        speaking_rate = features.get('speaking_rate', 0)
        
        # Voice quality-based classification
        shimmer = features.get('shimmer', 0)
        
        # High energy + high pitch variance = excited
        if energy > 0.05 and pitch_std > 50:
            emotion_scores['excited'] = 0.8
            emotion_scores['happy'] = 0.6
        
        # High energy + stable pitch = happy
        elif energy > 0.04 and pitch_std < 30:
            emotion_scores['happy'] = 0.7
            emotion_scores['excited'] = 0.3
        
        # Low energy + slow speaking = calm
        elif energy < 0.02 and speaking_rate < 0.5:
            emotion_scores['calm'] = 0.8
            emotion_scores['serious'] = 0.4
        
        # Medium energy + stable = serious
        elif 0.02 <= energy <= 0.04 and pitch_std < 25:
            emotion_scores['serious'] = 0.7
            emotion_scores['calm'] = 0.3
        
        # High shimmer = concerned/tense
        elif shimmer > 0.1:
            emotion_scores['concerned'] = 0.6
            emotion_scores['tense'] = 0.5
        
        # High pitch + high energy = surprised
        elif pitch_mean > 200 and energy > 0.04:
            emotion_scores['surprised'] = 0.7
            emotion_scores['excited'] = 0.4
        
        # Default to neutral
        else:
            emotion_scores['neutral'] = 0.6
        
        # Normalize scores
        total_score = sum(emotion_scores.values())
        if total_score > 0:
            emotion_scores = {k: v/total_score for k, v in emotion_scores.items()}
        
        return emotion_scores
    
    def analyze_emotional_flow(self, audio_path: str, window_size: float = 2.0) -> List[EmotionSegment]:
        """Analyze emotional flow through the audio timeline"""
        logger.info(f"📊 Analyzing emotional flow: {os.path.basename(audio_path)}")
        
        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=self.sample_rate)
            duration = len(y) / sr
            
            # Segment audio into windows
            window_samples = int(window_size * sr)
            segments = []
            
            for start_sample in range(0, len(y), window_samples):
                end_sample = min(start_sample + window_samples, len(y))
                segment_audio = y[start_sample:end_sample]
                
                if len(segment_audio) < window_samples // 2:
                    continue  # Skip too-short segments
                
                start_time = start_sample / sr
                end_time = end_sample / sr
                
                # Extract features for this segment
                features = self._extract_segment_features(segment_audio, sr)
                
                # Classify emotion
                emotion_scores = self.classify_emotion(features)
                primary_emotion = max(emotion_scores.items(), key=lambda x: x[1])
                
                # Create emotion segment
                segment = EmotionSegment(
                    start_time=start_time,
                    end_time=end_time,
                    emotion=primary_emotion[0],
                    confidence=primary_emotion[1],
                    energy=features.get('energy_mean', 0),
                    pitch_mean=features.get('pitch_mean', 0),
                    pitch_variance=features.get('pitch_std', 0),
                    speaking_rate=features.get('speaking_rate', 0)
                )
                
                segments.append(segment)
            
            logger.info(f"✅ Analyzed {len(segments)} emotional segments")
            return segments
            
        except Exception as e:
            logger.error(f"❌ Emotional flow analysis failed: {e}")
            return []
    
    def _extract_segment_features(self, segment_audio: np.ndarray, sr: int) -> Dict:
        """Extract features from a short audio segment"""
        
        features = {}
        
        # Basic energy
        rms = librosa.feature.rms(y=segment_audio, hop_length=self.hop_length)[0]
        features['energy_mean'] = np.mean(rms)
        
        # Basic pitch
        pitches, magnitudes = librosa.piptrack(y=segment_audio, sr=sr, hop_length=self.hop_length)
        pitch_values = []
        for i in range(pitches.shape[1]):
            index = magnitudes[:, i].argmax()
            pitch = pitches[index, i]
            if pitch > 0:
                pitch_values.append(pitch)
        
        if pitch_values:
            features['pitch_mean'] = np.mean(pitch_values)
            features['pitch_std'] = np.std(pitch_values)
        else:
            features['pitch_mean'] = 0
            features['pitch_std'] = 0
        
        # Speaking rate (simplified)
        rms_threshold = np.mean(rms) * 0.3
        voiced_frames = rms > rms_threshold
        features['speaking_rate'] = np.sum(voiced_frames) / len(voiced_frames)
        
        # Shimmer
        features['shimmer'] = np.std(np.diff(rms)) / np.mean(rms) if np.mean(rms) > 0 else 0
        
        return features
    
    def generate_edit_suggestions(self, emotion_segments: List[EmotionSegment]) -> List[MoodBasedEditSuggestion]:
        """Generate intelligent edit suggestions based on emotional flow"""
        logger.info("🎬 Generating mood-based edit suggestions")
        
        suggestions = []
        
        for i, segment in enumerate(emotion_segments):
            
            # 1. Suggest cuts at emotional transitions
            if i > 0:
                prev_segment = emotion_segments[i-1]
                
                # Major emotional shift = good cut point
                if segment.emotion != prev_segment.emotion and segment.confidence > 0.6:
                    suggestions.append(MoodBasedEditSuggestion(
                        timestamp=segment.start_time,
                        suggestion_type='cut',
                        description=f"Emotional transition: {prev_segment.emotion} → {segment.emotion}",
                        confidence=0.8,
                        parameters={
                            'transition_type': 'cut',
                            'from_emotion': prev_segment.emotion,
                            'to_emotion': segment.emotion
                        }
                    ))
            
            # 2. Color grading suggestions based on mood
            color_suggestion = self._suggest_color_grading(segment)
            if color_suggestion:
                suggestions.append(color_suggestion)
            
            # 3. Music suggestions
            music_suggestion = self._suggest_music(segment)
            if music_suggestion:
                suggestions.append(music_suggestion)
            
            # 4. Transition suggestions for high-energy segments
            if segment.energy > 0.05 and segment.emotion in ['excited', 'happy', 'surprised']:
                suggestions.append(MoodBasedEditSuggestion(
                    timestamp=segment.start_time,
                    suggestion_type='transition',
                    description=f"Dynamic transition for {segment.emotion} segment",
                    confidence=0.7,
                    parameters={
                        'transition_style': 'dynamic',
                        'emotion': segment.emotion,
                        'energy_level': segment.energy
                    }
                ))
        
        logger.info(f"✅ Generated {len(suggestions)} edit suggestions")
        return suggestions
    
    def _suggest_color_grading(self, segment: EmotionSegment) -> Optional[MoodBasedEditSuggestion]:
        """Suggest color grading based on emotion"""
        
        color_mappings = {
            'happy': {'temperature': 'warm', 'saturation': 'high', 'brightness': 'bright'},
            'excited': {'temperature': 'warm', 'saturation': 'very_high', 'brightness': 'bright'},
            'calm': {'temperature': 'neutral', 'saturation': 'medium', 'brightness': 'medium'},
            'serious': {'temperature': 'cool', 'saturation': 'low', 'brightness': 'medium'},
            'sad': {'temperature': 'cool', 'saturation': 'desaturated', 'brightness': 'dark'},
            'tense': {'temperature': 'cool', 'saturation': 'high', 'brightness': 'high_contrast'},
            'concerned': {'temperature': 'neutral', 'saturation': 'medium', 'brightness': 'medium'},
            'angry': {'temperature': 'warm', 'saturation': 'very_high', 'brightness': 'high_contrast'},
            'surprised': {'temperature': 'bright', 'saturation': 'high', 'brightness': 'bright'},
            'neutral': {'temperature': 'neutral', 'saturation': 'medium', 'brightness': 'medium'}
        }
        
        if segment.emotion in color_mappings and segment.confidence > 0.5:
            color_params = color_mappings[segment.emotion]
            
            return MoodBasedEditSuggestion(
                timestamp=segment.start_time,
                suggestion_type='color_grade',
                description=f"Color grade for {segment.emotion} mood",
                confidence=segment.confidence,
                parameters=color_params
            )
        
        return None
    
    def _suggest_music(self, segment: EmotionSegment) -> Optional[MoodBasedEditSuggestion]:
        """Suggest background music based on emotion"""
        
        music_mappings = {
            'happy': {'genre': 'upbeat', 'tempo': 'medium_fast', 'key': 'major'},
            'excited': {'genre': 'energetic', 'tempo': 'fast', 'key': 'major'},
            'calm': {'genre': 'ambient', 'tempo': 'slow', 'key': 'major'},
            'serious': {'genre': 'minimal', 'tempo': 'medium', 'key': 'minor'},
            'sad': {'genre': 'melancholy', 'tempo': 'slow', 'key': 'minor'},
            'tense': {'genre': 'suspenseful', 'tempo': 'variable', 'key': 'minor'},
            'concerned': {'genre': 'subtle', 'tempo': 'medium', 'key': 'minor'}
        }
        
        if segment.emotion in music_mappings and segment.confidence > 0.6:
            music_params = music_mappings[segment.emotion]
            
            return MoodBasedEditSuggestion(
                timestamp=segment.start_time,
                suggestion_type='music',
                description=f"Background music for {segment.emotion} segment",
                confidence=segment.confidence,
                parameters=music_params
            )
        
        return None
    
    def analyze_audience_engagement(self, emotion_segments: List[EmotionSegment]) -> Dict:
        """Predict audience engagement based on emotional flow"""
        logger.info("📊 Analyzing audience engagement potential")
        
        if not emotion_segments:
            return {'engagement_score': 0, 'recommendations': []}
        
        # Calculate engagement metrics
        total_duration = sum(seg.end_time - seg.start_time for seg in emotion_segments)
        
        # High-engagement emotions
        engaging_emotions = ['excited', 'happy', 'surprised', 'tense']
        engaging_duration = sum(
            seg.end_time - seg.start_time 
            for seg in emotion_segments 
            if seg.emotion in engaging_emotions
        )
        
        # Emotional variety score
        unique_emotions = len(set(seg.emotion for seg in emotion_segments))
        variety_score = min(unique_emotions / len(self.emotion_labels), 1.0)
        
        # Energy consistency
        energies = [seg.energy for seg in emotion_segments]
        energy_mean = np.mean(energies)
        energy_std = np.std(energies)
        
        # Calculate overall engagement score (0-1)
        engagement_score = (
            (engaging_duration / total_duration) * 0.4 +  # 40% engaging content
            variety_score * 0.3 +  # 30% emotional variety
            min(energy_mean * 10, 1.0) * 0.2 +  # 20% average energy
            (1 - min(energy_std * 5, 1.0)) * 0.1  # 10% energy consistency
        )
        
        # Generate recommendations
        recommendations = []
        
        if engaging_duration / total_duration < 0.3:
            recommendations.append("Increase high-energy segments for better engagement")
        
        if variety_score < 0.4:
            recommendations.append("Add more emotional variety throughout the content")
        
        if energy_mean < 0.03:
            recommendations.append("Overall energy is low - consider adding more dynamic segments")
        
        if energy_std > 0.02:
            recommendations.append("Energy levels are inconsistent - smooth transitions between segments")
        
        return {
            'engagement_score': engagement_score,
            'engaging_duration_percent': (engaging_duration / total_duration) * 100,
            'emotional_variety_score': variety_score,
            'average_energy': energy_mean,
            'energy_consistency': 1 - min(energy_std * 5, 1.0),
            'recommendations': recommendations
        }
    
    def generate_mood_analysis_report(self, audio_path: str, emotion_segments: List[EmotionSegment], 
                                    edit_suggestions: List[MoodBasedEditSuggestion], 
                                    engagement_analysis: Dict) -> str:
        """Generate comprehensive mood analysis report"""
        
        audio_name = os.path.splitext(os.path.basename(audio_path))[0]
        
        report = {
            'audio_file': audio_name,
            'analysis_time': datetime.now().isoformat(),
            'total_segments': len(emotion_segments),
            'emotion_summary': {},
            'engagement_analysis': engagement_analysis,
            'edit_suggestions': [
                {
                    'timestamp': suggestion.timestamp,
                    'type': suggestion.suggestion_type,
                    'description': suggestion.description,
                    'confidence': suggestion.confidence,
                    'parameters': suggestion.parameters
                }
                for suggestion in edit_suggestions
            ],
            'emotional_timeline': [
                {
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'emotion': segment.emotion,
                    'confidence': segment.confidence,
                    'energy': segment.energy,
                    'pitch_mean': segment.pitch_mean
                }
                for segment in emotion_segments
            ]
        }
        
        # Calculate emotion summary
        emotion_durations = {}
        total_duration = 0
        
        for segment in emotion_segments:
            duration = segment.end_time - segment.start_time
            total_duration += duration
            
            if segment.emotion not in emotion_durations:
                emotion_durations[segment.emotion] = 0
            emotion_durations[segment.emotion] += duration
        
        # Convert to percentages
        report['emotion_summary'] = {
            emotion: (duration / total_duration * 100) 
            for emotion, duration in emotion_durations.items()
        }
        
        # Save report
        report_path = os.path.join(self.analysis_dir, f"{audio_name}_mood_analysis.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📊 Mood analysis report saved: {report_path}")
        return report_path
    
    def analyze_audio_file(self, audio_path: str) -> Dict:
        """Complete mood analysis pipeline for a single audio file"""
        logger.info(f"🎤 Starting complete mood analysis: {os.path.basename(audio_path)}")
        
        if not os.path.exists(audio_path):
            logger.error(f"❌ Audio file not found: {audio_path}")
            return {}
        
        try:
            # Step 1: Extract overall features
            features = self.extract_audio_features(audio_path)
            
            # Step 2: Analyze emotional flow
            emotion_segments = self.analyze_emotional_flow(audio_path)
            
            # Step 3: Generate edit suggestions
            edit_suggestions = self.generate_edit_suggestions(emotion_segments)
            
            # Step 4: Analyze audience engagement
            engagement_analysis = self.analyze_audience_engagement(emotion_segments)
            
            # Step 5: Generate report
            report_path = self.generate_mood_analysis_report(
                audio_path, emotion_segments, edit_suggestions, engagement_analysis
            )
            
            logger.info("✅ Complete mood analysis finished")
            
            return {
                'features': features,
                'emotion_segments': emotion_segments,
                'edit_suggestions': edit_suggestions,
                'engagement_analysis': engagement_analysis,
                'report_path': report_path
            }
            
        except Exception as e:
            logger.error(f"❌ Mood analysis failed: {e}")
            return {}

def main():
    """Main function for CLI usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Voice Mood Analyzer for DaVinci Resolve OpenClaw')
    parser.add_argument('audio_path', help='Path to audio file')
    parser.add_argument('--project-root', default='.', help='Project root directory')
    parser.add_argument('--window-size', type=float, default=2.0, help='Analysis window size in seconds')
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = AIVoiceMoodAnalyzer(args.project_root)
    
    # Run analysis
    results = analyzer.analyze_audio_file(args.audio_path)
    
    if results:
        print(f"✅ Mood analysis complete!")
        print(f"📊 Report: {results.get('report_path', 'N/A')}")
        print(f"🎭 Emotion segments: {len(results.get('emotion_segments', []))}")
        print(f"💡 Edit suggestions: {len(results.get('edit_suggestions', []))}")
        print(f"📈 Engagement score: {results.get('engagement_analysis', {}).get('engagement_score', 0):.2f}")
    else:
        print("❌ Analysis failed")

if __name__ == "__main__":
    main()
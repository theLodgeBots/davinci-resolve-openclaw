#!/usr/bin/env python3
"""
AI Quality Scoring System for DaVinci Resolve OpenClaw
Automated content quality assessment and improvement recommendations

Features:
- Technical quality analysis (resolution, bitrate, audio levels)
- Content quality scoring (engagement, flow, pacing)
- AI-powered visual and audio analysis
- Automated recommendations for improvement
- Quality comparison across different edits
- Integration with batch processing pipeline
"""

import json
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import numpy as np
import cv2
from PIL import Image
import librosa
import scipy.stats
import openai

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QualityCategory(Enum):
    """Quality assessment categories"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    CRITICAL = "critical"

class QualityMetric(Enum):
    """Individual quality metrics"""
    TECHNICAL_OVERALL = "technical_overall"
    VISUAL_CLARITY = "visual_clarity"
    AUDIO_QUALITY = "audio_quality"
    EDIT_FLOW = "edit_flow"
    CONTENT_ENGAGEMENT = "content_engagement"
    PRODUCTION_VALUE = "production_value"
    BRAND_CONSISTENCY = "brand_consistency"

@dataclass
class QualityScore:
    """Individual quality metric score"""
    metric: QualityMetric
    score: float  # 0.0 to 100.0
    category: QualityCategory
    confidence: float  # 0.0 to 1.0
    details: Dict[str, Any]
    recommendations: List[str]

@dataclass
class VideoQualityAssessment:
    """Complete quality assessment for a video"""
    video_path: str
    overall_score: float
    overall_category: QualityCategory
    scores: Dict[QualityMetric, QualityScore]
    technical_analysis: Dict[str, Any]
    content_analysis: Dict[str, Any]
    recommendations: List[str]
    strengths: List[str]
    weaknesses: List[str]
    processed_at: datetime
    processing_time: float

class TechnicalAnalyzer:
    """Technical quality analysis (resolution, bitrate, encoding, etc.)"""
    
    def __init__(self):
        self.acceptable_resolutions = [(1920, 1080), (3840, 2160), (1280, 720)]
        self.min_bitrate = 1000000  # 1 Mbps
        self.optimal_bitrate = 5000000  # 5 Mbps
        
    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """Analyze technical video quality"""
        try:
            # Get video information using ffprobe
            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"ffprobe failed: {result.stderr}")
            
            info = json.loads(result.stdout)
            
            # Extract video stream info
            video_stream = None
            audio_stream = None
            
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                elif stream.get('codec_type') == 'audio':
                    audio_stream = stream
            
            analysis = {}
            
            # Video analysis
            if video_stream:
                width = int(video_stream.get('width', 0))
                height = int(video_stream.get('height', 0))
                bitrate = int(video_stream.get('bit_rate', 0))
                fps = eval(video_stream.get('r_frame_rate', '30/1'))  # Convert fraction to float
                codec = video_stream.get('codec_name', 'unknown')
                
                analysis['video'] = {
                    'resolution': (width, height),
                    'bitrate': bitrate,
                    'fps': fps,
                    'codec': codec,
                    'duration': float(video_stream.get('duration', 0)),
                }
                
                # Score video quality
                resolution_score = self._score_resolution(width, height)
                bitrate_score = self._score_bitrate(bitrate)
                codec_score = self._score_codec(codec)
                
                analysis['video']['quality_scores'] = {
                    'resolution': resolution_score,
                    'bitrate': bitrate_score,
                    'codec': codec_score,
                    'overall': (resolution_score + bitrate_score + codec_score) / 3
                }
            
            # Audio analysis
            if audio_stream:
                audio_bitrate = int(audio_stream.get('bit_rate', 0))
                sample_rate = int(audio_stream.get('sample_rate', 0))
                channels = int(audio_stream.get('channels', 0))
                audio_codec = audio_stream.get('codec_name', 'unknown')
                
                analysis['audio'] = {
                    'bitrate': audio_bitrate,
                    'sample_rate': sample_rate,
                    'channels': channels,
                    'codec': audio_codec,
                }
                
                # Score audio quality
                audio_bitrate_score = self._score_audio_bitrate(audio_bitrate)
                sample_rate_score = self._score_sample_rate(sample_rate)
                channel_score = self._score_channels(channels)
                
                analysis['audio']['quality_scores'] = {
                    'bitrate': audio_bitrate_score,
                    'sample_rate': sample_rate_score,
                    'channels': channel_score,
                    'overall': (audio_bitrate_score + sample_rate_score + channel_score) / 3
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Technical analysis failed: {e}")
            return {'error': str(e)}
    
    def _score_resolution(self, width: int, height: int) -> float:
        """Score video resolution quality"""
        resolution = (width, height)
        
        if resolution == (3840, 2160):  # 4K
            return 100.0
        elif resolution == (1920, 1080):  # 1080p
            return 90.0
        elif resolution == (1280, 720):  # 720p
            return 75.0
        elif width >= 1280:  # Decent quality
            return 60.0
        else:  # Low resolution
            return 30.0
    
    def _score_bitrate(self, bitrate: int) -> float:
        """Score video bitrate quality"""
        if bitrate >= self.optimal_bitrate:
            return 100.0
        elif bitrate >= self.min_bitrate:
            # Scale between min and optimal
            ratio = (bitrate - self.min_bitrate) / (self.optimal_bitrate - self.min_bitrate)
            return 60.0 + (ratio * 40.0)
        else:
            # Below minimum acceptable
            return max(0.0, (bitrate / self.min_bitrate) * 60.0)
    
    def _score_codec(self, codec: str) -> float:
        """Score video codec quality"""
        codec_scores = {
            'h264': 85.0,
            'hevc': 95.0,
            'h265': 95.0,
            'vp9': 90.0,
            'av1': 100.0,
            'prores': 100.0,
            'dnxhd': 95.0,
        }
        return codec_scores.get(codec.lower(), 50.0)
    
    def _score_audio_bitrate(self, bitrate: int) -> float:
        """Score audio bitrate quality"""
        if bitrate >= 320000:  # 320 kbps
            return 100.0
        elif bitrate >= 192000:  # 192 kbps
            return 85.0
        elif bitrate >= 128000:  # 128 kbps
            return 70.0
        elif bitrate >= 96000:  # 96 kbps
            return 50.0
        else:
            return 30.0
    
    def _score_sample_rate(self, sample_rate: int) -> float:
        """Score audio sample rate quality"""
        if sample_rate >= 48000:
            return 100.0
        elif sample_rate >= 44100:
            return 95.0
        elif sample_rate >= 22050:
            return 60.0
        else:
            return 30.0
    
    def _score_channels(self, channels: int) -> float:
        """Score audio channel configuration"""
        if channels >= 6:  # Surround
            return 100.0
        elif channels == 2:  # Stereo
            return 90.0
        elif channels == 1:  # Mono
            return 60.0
        else:
            return 30.0

class ContentAnalyzer:
    """Content quality analysis using AI"""
    
    def __init__(self):
        # Initialize OpenAI
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
    def analyze_content(self, video_path: str, transcript_path: str = None) -> Dict[str, Any]:
        """Analyze content quality using AI"""
        try:
            analysis = {}
            
            # Extract key frames for visual analysis
            frames = self._extract_key_frames(video_path, max_frames=5)
            
            if frames:
                visual_analysis = self._analyze_visual_content(frames)
                analysis['visual'] = visual_analysis
            
            # Analyze transcript if available
            if transcript_path and Path(transcript_path).exists():
                with open(transcript_path, 'r') as f:
                    transcript_data = json.load(f)
                
                content_analysis = self._analyze_transcript_content(transcript_data)
                analysis['content'] = content_analysis
            
            # Analyze edit flow and pacing
            pacing_analysis = self._analyze_pacing(video_path)
            analysis['pacing'] = pacing_analysis
            
            return analysis
            
        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            return {'error': str(e)}
    
    def _extract_key_frames(self, video_path: str, max_frames: int = 5) -> List[np.ndarray]:
        """Extract key frames from video for analysis"""
        try:
            cap = cv2.VideoCapture(video_path)
            frames = []
            
            if not cap.isOpened():
                return frames
            
            # Get video properties
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps > 0 else 0
            
            # Extract frames at regular intervals
            if frame_count > 0:
                step = max(1, frame_count // max_frames)
                for i in range(0, frame_count, step):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, frame = cap.read()
                    if ret:
                        frames.append(frame)
                    if len(frames) >= max_frames:
                        break
            
            cap.release()
            return frames
            
        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return []
    
    def _analyze_visual_content(self, frames: List[np.ndarray]) -> Dict[str, Any]:
        """Analyze visual content quality"""
        try:
            analysis = {
                'clarity_scores': [],
                'exposure_scores': [],
                'composition_scores': [],
                'color_balance_scores': []
            }
            
            for frame in frames:
                # Convert to different color spaces for analysis
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                
                # Clarity (using Laplacian variance)
                clarity = cv2.Laplacian(gray, cv2.CV_64F).var()
                clarity_score = min(100.0, clarity / 100.0 * 100)  # Normalize
                analysis['clarity_scores'].append(clarity_score)
                
                # Exposure (using histogram analysis)
                hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
                exposure_score = self._analyze_exposure(hist)
                analysis['exposure_scores'].append(exposure_score)
                
                # Basic composition (rule of thirds, contrast)
                composition_score = self._analyze_composition(frame, gray)
                analysis['composition_scores'].append(composition_score)
                
                # Color balance
                color_balance_score = self._analyze_color_balance(frame)
                analysis['color_balance_scores'].append(color_balance_score)
            
            # Calculate average scores
            analysis['average_clarity'] = np.mean(analysis['clarity_scores']) if analysis['clarity_scores'] else 0
            analysis['average_exposure'] = np.mean(analysis['exposure_scores']) if analysis['exposure_scores'] else 0
            analysis['average_composition'] = np.mean(analysis['composition_scores']) if analysis['composition_scores'] else 0
            analysis['average_color_balance'] = np.mean(analysis['color_balance_scores']) if analysis['color_balance_scores'] else 0
            
            # Overall visual score
            analysis['overall_visual_score'] = (
                analysis['average_clarity'] * 0.3 +
                analysis['average_exposure'] * 0.25 +
                analysis['average_composition'] * 0.25 +
                analysis['average_color_balance'] * 0.2
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Visual content analysis failed: {e}")
            return {'error': str(e)}
    
    def _analyze_exposure(self, histogram) -> float:
        """Analyze exposure quality from histogram"""
        # Check for proper distribution
        total_pixels = np.sum(histogram)
        if total_pixels == 0:
            return 0.0
        
        # Avoid extreme over/under exposure
        underexposed = np.sum(histogram[:25]) / total_pixels  # Very dark pixels
        overexposed = np.sum(histogram[230:]) / total_pixels  # Very bright pixels
        
        # Good exposure should have most pixels in middle ranges
        mid_range = np.sum(histogram[50:200]) / total_pixels
        
        # Score based on distribution
        if underexposed > 0.3 or overexposed > 0.3:  # Too much clipping
            return 30.0
        elif mid_range > 0.6:  # Good distribution
            return 90.0
        else:
            return 60.0
    
    def _analyze_composition(self, frame, gray_frame) -> float:
        """Basic composition analysis"""
        height, width = gray_frame.shape
        
        # Calculate contrast
        contrast = gray_frame.std()
        contrast_score = min(100.0, contrast / 50.0 * 100)
        
        # Simple edge detection for detail
        edges = cv2.Canny(gray_frame, 50, 150)
        edge_density = np.sum(edges > 0) / (width * height)
        detail_score = min(100.0, edge_density * 1000)
        
        return (contrast_score + detail_score) / 2
    
    def _analyze_color_balance(self, frame) -> float:
        """Analyze color balance"""
        # Calculate channel means
        b_mean = np.mean(frame[:, :, 0])
        g_mean = np.mean(frame[:, :, 1])
        r_mean = np.mean(frame[:, :, 2])
        
        # Good balance should have similar channel values
        channel_diff = max(abs(r_mean - g_mean), abs(g_mean - b_mean), abs(r_mean - b_mean))
        balance_score = max(0.0, 100.0 - (channel_diff / 255.0 * 100))
        
        return balance_score
    
    def _analyze_transcript_content(self, transcript_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze content quality from transcript"""
        try:
            # Extract text content
            if 'segments' in transcript_data:
                text_segments = [seg.get('text', '') for seg in transcript_data['segments']]
                full_text = ' '.join(text_segments)
            else:
                full_text = transcript_data.get('text', '')
            
            if not full_text.strip():
                return {'error': 'No transcript content found'}
            
            # Use AI to analyze content quality
            content_prompt = f"""
            Analyze the following video transcript for content quality. Provide scores (0-100) and feedback for:
            
            1. Clarity and coherence of message
            2. Engagement and audience appeal
            3. Information density and value
            4. Professional presentation
            5. Overall content quality
            
            Transcript:
            {full_text[:2000]}...
            
            Return your analysis as JSON with:
            - clarity_score (0-100)
            - engagement_score (0-100)
            - information_score (0-100)
            - professionalism_score (0-100)
            - overall_score (0-100)
            - strengths (list of strings)
            - improvements (list of strings)
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": content_prompt}],
                temperature=0.3
            )
            
            try:
                analysis = json.loads(response.choices[0].message.content)
                return analysis
            except json.JSONDecodeError:
                # Fallback to basic analysis
                return self._basic_content_analysis(full_text)
                
        except Exception as e:
            logger.error(f"Transcript content analysis failed: {e}")
            return {'error': str(e)}
    
    def _basic_content_analysis(self, text: str) -> Dict[str, Any]:
        """Basic content analysis fallback"""
        word_count = len(text.split())
        sentence_count = len([s for s in text.split('.') if s.strip()])
        
        # Basic metrics
        avg_words_per_sentence = word_count / max(1, sentence_count)
        
        return {
            'clarity_score': 70.0 if 10 <= avg_words_per_sentence <= 20 else 50.0,
            'engagement_score': min(80.0, word_count / 10),  # More words = potentially more engaging
            'information_score': 65.0,  # Neutral score
            'professionalism_score': 70.0,  # Assume decent
            'overall_score': 65.0,
            'strengths': ['Content present', 'Readable transcript'],
            'improvements': ['Detailed analysis requires AI processing']
        }
    
    def _analyze_pacing(self, video_path: str) -> Dict[str, Any]:
        """Analyze video pacing and flow"""
        try:
            # Basic pacing analysis using scene detection
            result = subprocess.run([
                "ffprobe", "-f", "lavfi", "-i", f"movie={video_path},select=gt(scene\\,0.3)",
                "-show_entries", "frame=pkt_pts_time", "-of", "csv=p=0", "-v", "quiet"
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                scene_times = [float(line) for line in result.stdout.strip().split('\n') if line]
                
                if len(scene_times) > 1:
                    # Calculate average shot length
                    shot_lengths = [scene_times[i+1] - scene_times[i] for i in range(len(scene_times)-1)]
                    avg_shot_length = np.mean(shot_lengths)
                    shot_variety = np.std(shot_lengths)
                    
                    # Score pacing (good range is 3-8 seconds per shot)
                    if 3 <= avg_shot_length <= 8:
                        pacing_score = 90.0
                    elif 1 <= avg_shot_length <= 12:
                        pacing_score = 70.0
                    else:
                        pacing_score = 50.0
                    
                    # Variety in shot lengths is good
                    variety_score = min(100.0, shot_variety * 20)
                    
                    return {
                        'scene_count': len(scene_times),
                        'average_shot_length': avg_shot_length,
                        'shot_variety': shot_variety,
                        'pacing_score': pacing_score,
                        'variety_score': variety_score,
                        'overall_pacing_score': (pacing_score + variety_score) / 2
                    }
            
            # Fallback if scene detection fails
            return {
                'scene_count': 1,
                'pacing_score': 60.0,
                'overall_pacing_score': 60.0,
                'note': 'Basic pacing analysis - scene detection unavailable'
            }
            
        except Exception as e:
            logger.error(f"Pacing analysis failed: {e}")
            return {'error': str(e)}

class AIQualityScorer:
    """Main AI Quality Scoring System"""
    
    def __init__(self):
        self.technical_analyzer = TechnicalAnalyzer()
        self.content_analyzer = ContentAnalyzer()
    
    def score_video(self, video_path: str, transcript_path: str = None) -> VideoQualityAssessment:
        """Complete quality assessment of a video"""
        start_time = time.time()
        
        try:
            logger.info(f"Starting quality assessment for {video_path}")
            
            # Technical analysis
            technical_analysis = self.technical_analyzer.analyze_video(video_path)
            
            # Content analysis
            content_analysis = self.content_analyzer.analyze_content(video_path, transcript_path)
            
            # Calculate individual quality scores
            scores = self._calculate_quality_scores(technical_analysis, content_analysis)
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(scores)
            overall_category = self._score_to_category(overall_score)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(scores, technical_analysis, content_analysis)
            
            # Identify strengths and weaknesses
            strengths, weaknesses = self._identify_strengths_weaknesses(scores)
            
            processing_time = time.time() - start_time
            
            assessment = VideoQualityAssessment(
                video_path=video_path,
                overall_score=overall_score,
                overall_category=overall_category,
                scores=scores,
                technical_analysis=technical_analysis,
                content_analysis=content_analysis,
                recommendations=recommendations,
                strengths=strengths,
                weaknesses=weaknesses,
                processed_at=datetime.now(),
                processing_time=processing_time
            )
            
            logger.info(f"Quality assessment completed in {processing_time:.1f}s - Overall score: {overall_score:.1f}")
            return assessment
            
        except Exception as e:
            logger.error(f"Quality scoring failed: {e}")
            raise
    
    def _calculate_quality_scores(self, technical_analysis: Dict[str, Any], 
                                 content_analysis: Dict[str, Any]) -> Dict[QualityMetric, QualityScore]:
        """Calculate individual quality metric scores"""
        scores = {}
        
        # Technical Overall
        if 'video' in technical_analysis and 'audio' in technical_analysis:
            video_score = technical_analysis['video'].get('quality_scores', {}).get('overall', 50.0)
            audio_score = technical_analysis['audio'].get('quality_scores', {}).get('overall', 50.0)
            tech_score = (video_score * 0.7 + audio_score * 0.3)
        else:
            tech_score = 50.0
        
        scores[QualityMetric.TECHNICAL_OVERALL] = QualityScore(
            metric=QualityMetric.TECHNICAL_OVERALL,
            score=tech_score,
            category=self._score_to_category(tech_score),
            confidence=0.9,
            details={'video_score': video_score if 'video' in technical_analysis else None,
                    'audio_score': audio_score if 'audio' in technical_analysis else None},
            recommendations=self._get_technical_recommendations(tech_score, technical_analysis)
        )
        
        # Visual Clarity
        visual_score = content_analysis.get('visual', {}).get('overall_visual_score', 60.0)
        scores[QualityMetric.VISUAL_CLARITY] = QualityScore(
            metric=QualityMetric.VISUAL_CLARITY,
            score=visual_score,
            category=self._score_to_category(visual_score),
            confidence=0.8,
            details=content_analysis.get('visual', {}),
            recommendations=self._get_visual_recommendations(visual_score, content_analysis.get('visual', {}))
        )
        
        # Audio Quality (from technical analysis)
        audio_score = technical_analysis.get('audio', {}).get('quality_scores', {}).get('overall', 50.0)
        scores[QualityMetric.AUDIO_QUALITY] = QualityScore(
            metric=QualityMetric.AUDIO_QUALITY,
            score=audio_score,
            category=self._score_to_category(audio_score),
            confidence=0.9,
            details=technical_analysis.get('audio', {}),
            recommendations=self._get_audio_recommendations(audio_score, technical_analysis.get('audio', {}))
        )
        
        # Edit Flow (from pacing analysis)
        pacing_score = content_analysis.get('pacing', {}).get('overall_pacing_score', 60.0)
        scores[QualityMetric.EDIT_FLOW] = QualityScore(
            metric=QualityMetric.EDIT_FLOW,
            score=pacing_score,
            category=self._score_to_category(pacing_score),
            confidence=0.7,
            details=content_analysis.get('pacing', {}),
            recommendations=self._get_pacing_recommendations(pacing_score, content_analysis.get('pacing', {}))
        )
        
        # Content Engagement (from content analysis)
        engagement_score = content_analysis.get('content', {}).get('engagement_score', 65.0)
        scores[QualityMetric.CONTENT_ENGAGEMENT] = QualityScore(
            metric=QualityMetric.CONTENT_ENGAGEMENT,
            score=engagement_score,
            category=self._score_to_category(engagement_score),
            confidence=0.6,
            details=content_analysis.get('content', {}),
            recommendations=self._get_engagement_recommendations(engagement_score, content_analysis.get('content', {}))
        )
        
        # Production Value (composite score)
        production_score = (tech_score * 0.4 + visual_score * 0.3 + pacing_score * 0.3)
        scores[QualityMetric.PRODUCTION_VALUE] = QualityScore(
            metric=QualityMetric.PRODUCTION_VALUE,
            score=production_score,
            category=self._score_to_category(production_score),
            confidence=0.8,
            details={'composite_of': ['technical', 'visual', 'pacing']},
            recommendations=self._get_production_recommendations(production_score)
        )
        
        return scores
    
    def _calculate_overall_score(self, scores: Dict[QualityMetric, QualityScore]) -> float:
        """Calculate weighted overall quality score"""
        weights = {
            QualityMetric.TECHNICAL_OVERALL: 0.25,
            QualityMetric.VISUAL_CLARITY: 0.20,
            QualityMetric.AUDIO_QUALITY: 0.15,
            QualityMetric.EDIT_FLOW: 0.20,
            QualityMetric.CONTENT_ENGAGEMENT: 0.15,
            QualityMetric.PRODUCTION_VALUE: 0.05
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for metric, weight in weights.items():
            if metric in scores:
                total_score += scores[metric].score * weight
                total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _score_to_category(self, score: float) -> QualityCategory:
        """Convert numeric score to quality category"""
        if score >= 90:
            return QualityCategory.EXCELLENT
        elif score >= 75:
            return QualityCategory.GOOD
        elif score >= 60:
            return QualityCategory.ACCEPTABLE
        elif score >= 40:
            return QualityCategory.POOR
        else:
            return QualityCategory.CRITICAL
    
    def _get_technical_recommendations(self, score: float, analysis: Dict[str, Any]) -> List[str]:
        """Generate technical improvement recommendations"""
        recommendations = []
        
        if score < 70:
            if 'video' in analysis:
                video = analysis['video']
                if video.get('quality_scores', {}).get('bitrate', 100) < 70:
                    recommendations.append("Increase video bitrate for better quality")
                if video.get('quality_scores', {}).get('resolution', 100) < 80:
                    recommendations.append("Consider higher resolution recording/export")
                if video.get('quality_scores', {}).get('codec', 100) < 80:
                    recommendations.append("Use higher quality codec (H.265, ProRes)")
            
            if 'audio' in analysis:
                audio = analysis['audio']
                if audio.get('quality_scores', {}).get('bitrate', 100) < 70:
                    recommendations.append("Increase audio bitrate to at least 192kbps")
                if audio.get('quality_scores', {}).get('sample_rate', 100) < 90:
                    recommendations.append("Use 48kHz sample rate for professional audio")
        
        return recommendations
    
    def _get_visual_recommendations(self, score: float, analysis: Dict[str, Any]) -> List[str]:
        """Generate visual improvement recommendations"""
        recommendations = []
        
        if score < 70:
            if analysis.get('average_clarity', 0) < 60:
                recommendations.append("Improve focus and image sharpness")
            if analysis.get('average_exposure', 0) < 60:
                recommendations.append("Adjust exposure and lighting")
            if analysis.get('average_color_balance', 0) < 60:
                recommendations.append("Correct color balance and white balance")
            if analysis.get('average_composition', 0) < 60:
                recommendations.append("Improve composition and visual contrast")
        
        return recommendations
    
    def _get_audio_recommendations(self, score: float, analysis: Dict[str, Any]) -> List[str]:
        """Generate audio improvement recommendations"""
        recommendations = []
        
        if score < 70:
            if analysis.get('quality_scores', {}).get('bitrate', 100) < 70:
                recommendations.append("Use higher audio bitrate")
            if analysis.get('channels', 0) < 2:
                recommendations.append("Consider stereo audio recording")
            recommendations.append("Check for audio clipping and noise")
        
        return recommendations
    
    def _get_pacing_recommendations(self, score: float, analysis: Dict[str, Any]) -> List[str]:
        """Generate pacing improvement recommendations"""
        recommendations = []
        
        if score < 70:
            avg_shot = analysis.get('average_shot_length', 0)
            if avg_shot > 10:
                recommendations.append("Consider shorter shots for better pacing")
            elif avg_shot < 2:
                recommendations.append("Allow shots to breathe - avoid over-cutting")
            if analysis.get('variety_score', 0) < 50:
                recommendations.append("Vary shot lengths for more dynamic pacing")
        
        return recommendations
    
    def _get_engagement_recommendations(self, score: float, analysis: Dict[str, Any]) -> List[str]:
        """Generate engagement improvement recommendations"""
        recommendations = []
        
        if score < 70:
            recommendations.append("Improve content structure and flow")
            recommendations.append("Add more engaging hooks and transitions")
            if analysis.get('clarity_score', 0) < 70:
                recommendations.append("Make the message clearer and more focused")
        
        return recommendations
    
    def _get_production_recommendations(self, score: float) -> List[str]:
        """Generate production value recommendations"""
        if score < 70:
            return [
                "Focus on improving technical quality",
                "Enhance visual presentation",
                "Refine editing and post-production"
            ]
        return []
    
    def _generate_recommendations(self, scores: Dict[QualityMetric, QualityScore],
                                technical_analysis: Dict[str, Any],
                                content_analysis: Dict[str, Any]) -> List[str]:
        """Generate comprehensive improvement recommendations"""
        all_recommendations = []
        
        # Collect recommendations from all metrics
        for score in scores.values():
            all_recommendations.extend(score.recommendations)
        
        # Remove duplicates and prioritize
        unique_recommendations = list(dict.fromkeys(all_recommendations))
        
        # Add overall recommendations based on lowest scores
        sorted_scores = sorted(scores.items(), key=lambda x: x[1].score)
        if sorted_scores:
            lowest_metric, lowest_score = sorted_scores[0]
            if lowest_score.score < 60:
                unique_recommendations.insert(0, f"Priority: Improve {lowest_metric.value.replace('_', ' ')}")
        
        return unique_recommendations[:10]  # Limit to top 10 recommendations
    
    def _identify_strengths_weaknesses(self, scores: Dict[QualityMetric, QualityScore]) -> Tuple[List[str], List[str]]:
        """Identify strengths and weaknesses from scores"""
        strengths = []
        weaknesses = []
        
        for metric, score in scores.items():
            metric_name = metric.value.replace('_', ' ').title()
            
            if score.score >= 80:
                strengths.append(f"Strong {metric_name.lower()} ({score.score:.0f}/100)")
            elif score.score < 60:
                weaknesses.append(f"Needs improvement in {metric_name.lower()} ({score.score:.0f}/100)")
        
        return strengths, weaknesses
    
    def save_assessment(self, assessment: VideoQualityAssessment, output_path: str = None):
        """Save quality assessment to JSON file"""
        if not output_path:
            video_name = Path(assessment.video_path).stem
            output_path = f"{video_name}_quality_assessment.json"
        
        # Convert to serializable format
        data = {
            'video_path': assessment.video_path,
            'overall_score': assessment.overall_score,
            'overall_category': assessment.overall_category.value,
            'scores': {
                metric.value: {
                    'score': score.score,
                    'category': score.category.value,
                    'confidence': score.confidence,
                    'details': score.details,
                    'recommendations': score.recommendations
                }
                for metric, score in assessment.scores.items()
            },
            'technical_analysis': assessment.technical_analysis,
            'content_analysis': assessment.content_analysis,
            'recommendations': assessment.recommendations,
            'strengths': assessment.strengths,
            'weaknesses': assessment.weaknesses,
            'processed_at': assessment.processed_at.isoformat(),
            'processing_time': assessment.processing_time
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Quality assessment saved to {output_path}")

def main():
    """Demo the AI Quality Scoring System"""
    scorer = AIQualityScorer()
    
    # Test with existing render
    test_video = "renders/portalcam-30s-v3.mp4"
    test_transcript = "nycap-portalcam_transcript_enhanced.json"
    
    if Path(test_video).exists():
        print(f"🎬 Analyzing quality of {test_video}...")
        
        transcript_path = test_transcript if Path(test_transcript).exists() else None
        assessment = scorer.score_video(test_video, transcript_path)
        
        # Display results
        print(f"\n📊 QUALITY ASSESSMENT RESULTS")
        print(f"Overall Score: {assessment.overall_score:.1f}/100 ({assessment.overall_category.value.upper()})")
        print(f"Processing Time: {assessment.processing_time:.1f} seconds")
        
        print(f"\n📈 Individual Scores:")
        for metric, score in assessment.scores.items():
            print(f"  {metric.value.replace('_', ' ').title()}: {score.score:.1f}/100 ({score.category.value})")
        
        print(f"\n✅ Strengths:")
        for strength in assessment.strengths:
            print(f"  • {strength}")
        
        print(f"\n⚠️ Areas for Improvement:")
        for weakness in assessment.weaknesses:
            print(f"  • {weakness}")
        
        print(f"\n💡 Recommendations:")
        for rec in assessment.recommendations[:5]:  # Show top 5
            print(f"  • {rec}")
        
        # Save assessment
        scorer.save_assessment(assessment)
        print(f"\n💾 Assessment saved to JSON file")
        
    else:
        print(f"Test video not found: {test_video}")
        print("Please ensure you have rendered videos in the renders/ directory.")

if __name__ == "__main__":
    main()
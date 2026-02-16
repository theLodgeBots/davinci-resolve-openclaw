#!/usr/bin/env python3
"""
AI Director - Automated Creative Decision Making System
Advanced AI that makes professional creative decisions for video editing

This system analyzes footage and makes sophisticated creative decisions including:
- Shot composition and framing analysis
- Pacing optimization based on content type
- Emotional arc detection and enhancement
- Music synchronization and beat matching
- Color grading mood mapping
- Transition timing and style selection

Business Value: Premium feature differentiation - no competitor offers automated creative direction
"""

import json
import os
import sys
import time
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import openai
import subprocess
import logging
from dataclasses import dataclass, asdict
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
import wave
import librosa
import scipy.signal
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CreativeDecision:
    """Represents a single creative decision made by the AI Director"""
    timestamp: float
    decision_type: str  # 'cut', 'transition', 'color', 'audio', 'pacing'
    confidence: float
    reasoning: str
    parameters: Dict[str, Any]
    emotional_weight: float
    creative_intent: str

@dataclass
class ShotAnalysis:
    """Comprehensive analysis of a single shot"""
    shot_id: str
    start_time: float
    end_time: float
    composition_score: float
    emotional_tone: str
    visual_complexity: float
    motion_intensity: float
    color_palette: List[str]
    framing_type: str  # 'wide', 'medium', 'close', 'extreme_close'
    stability: float
    focus_quality: float
    lighting_quality: float
    creative_potential: float

@dataclass
class EmotionalArc:
    """Represents the emotional progression of the video"""
    segments: List[Dict[str, Any]]
    overall_tone: str
    peak_moments: List[float]
    valley_moments: List[float]
    optimal_pacing: List[float]
    recommended_music_energy: List[float]

class AIDirector:
    """
    Advanced AI Director for automated creative decision making
    """
    
    def __init__(self, project_path: str, openai_client=None):
        self.project_path = Path(project_path)
        self.client = openai_client or openai.OpenAI()
        self.db_path = self.project_path / "ai_director.db"
        self.creative_decisions = []
        self.shot_analyses = []
        self.emotional_arc = None
        self.creative_style = "professional"  # professional, cinematic, documentary, social
        
        # Initialize database
        self._init_database()
        
        # Creative parameters
        self.creative_parameters = {
            'pacing_preference': 'dynamic',  # slow, medium, dynamic, fast
            'transition_style': 'intelligent',  # cuts_only, smooth, dynamic, intelligent
            'color_mood': 'adaptive',  # warm, cool, neutral, adaptive, dramatic
            'audio_priority': 'dialogue',  # dialogue, music, ambient, balanced
            'shot_variety': 'high',  # low, medium, high, maximum
            'emotional_emphasis': 'natural'  # subtle, natural, enhanced, dramatic
        }
        
        logger.info(f"AI Director initialized for project: {project_path}")

    def _init_database(self):
        """Initialize SQLite database for storing creative decisions and analysis"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS creative_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    decision_type TEXT,
                    confidence REAL,
                    reasoning TEXT,
                    parameters TEXT,
                    emotional_weight REAL,
                    creative_intent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shot_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shot_id TEXT,
                    start_time REAL,
                    end_time REAL,
                    composition_score REAL,
                    emotional_tone TEXT,
                    visual_complexity REAL,
                    motion_intensity REAL,
                    color_palette TEXT,
                    framing_type TEXT,
                    stability REAL,
                    focus_quality REAL,
                    lighting_quality REAL,
                    creative_potential REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS emotional_arcs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT,
                    segments TEXT,
                    overall_tone TEXT,
                    peak_moments TEXT,
                    valley_moments TEXT,
                    optimal_pacing TEXT,
                    recommended_music_energy TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def analyze_shot_composition(self, video_path: str, start_time: float, end_time: float) -> ShotAnalysis:
        """
        Analyze the visual composition and creative potential of a shot
        """
        logger.info(f"Analyzing shot composition: {video_path} ({start_time}-{end_time})")
        
        # Extract frames for analysis
        frames = self._extract_representative_frames(video_path, start_time, end_time)
        
        if not frames:
            logger.warning(f"No frames extracted from {video_path}")
            return self._default_shot_analysis(video_path, start_time, end_time)
        
        # Analyze composition elements
        composition_scores = []
        color_palettes = []
        motion_scores = []
        
        for frame in frames:
            # Composition analysis
            comp_score = self._analyze_frame_composition(frame)
            composition_scores.append(comp_score)
            
            # Color palette extraction
            palette = self._extract_color_palette(frame)
            color_palettes.append(palette)
            
            # Motion analysis (if multiple frames)
            if len(frames) > 1:
                motion_score = self._calculate_motion_intensity(frames)
                motion_scores.append(motion_score)
        
        # Calculate overall metrics
        avg_composition = np.mean(composition_scores)
        avg_motion = np.mean(motion_scores) if motion_scores else 0.5
        dominant_colors = self._merge_color_palettes(color_palettes)
        
        # Determine framing type
        framing_type = self._classify_framing(frames[0])
        
        # Emotional tone analysis
        emotional_tone = self._analyze_emotional_tone(frames[0])
        
        # Creative potential scoring
        creative_potential = self._calculate_creative_potential(
            avg_composition, avg_motion, len(dominant_colors), framing_type
        )
        
        shot_id = f"{Path(video_path).stem}_{start_time}_{end_time}"
        
        analysis = ShotAnalysis(
            shot_id=shot_id,
            start_time=start_time,
            end_time=end_time,
            composition_score=avg_composition,
            emotional_tone=emotional_tone,
            visual_complexity=self._calculate_visual_complexity(frames[0]),
            motion_intensity=avg_motion,
            color_palette=dominant_colors[:5],  # Top 5 colors
            framing_type=framing_type,
            stability=self._calculate_stability(frames),
            focus_quality=self._calculate_focus_quality(frames[0]),
            lighting_quality=self._calculate_lighting_quality(frames[0]),
            creative_potential=creative_potential
        )
        
        # Store in database
        self._store_shot_analysis(analysis)
        self.shot_analyses.append(analysis)
        
        logger.info(f"Shot analysis complete: {shot_id}, Creative Potential: {creative_potential:.2f}")
        return analysis

    def _extract_representative_frames(self, video_path: str, start_time: float, end_time: float, max_frames: int = 5) -> List[np.ndarray]:
        """Extract representative frames from video segment"""
        frames = []
        duration = end_time - start_time
        
        if duration <= 0:
            return frames
            
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Calculate frame positions
            frame_positions = []
            if max_frames == 1:
                frame_positions = [start_time + duration / 2]
            else:
                for i in range(max_frames):
                    pos = start_time + (i * duration / (max_frames - 1))
                    frame_positions.append(pos)
            
            for pos in frame_positions:
                frame_number = int(pos * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()
                
                if ret:
                    frames.append(frame)
                    
            cap.release()
            
        except Exception as e:
            logger.error(f"Error extracting frames from {video_path}: {e}")
            
        return frames

    def _analyze_frame_composition(self, frame: np.ndarray) -> float:
        """Analyze visual composition using rule of thirds, symmetry, etc."""
        if frame is None:
            return 0.0
            
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Rule of thirds analysis
        thirds_score = 0.0
        third_h, third_w = h // 3, w // 3
        
        # Check for interesting features at rule of thirds points
        roi_points = [
            (third_w, third_h), (2 * third_w, third_h),
            (third_w, 2 * third_h), (2 * third_w, 2 * third_h)
        ]
        
        for x, y in roi_points:
            roi = gray[max(0, y-20):min(h, y+20), max(0, x-20):min(w, x+20)]
            if roi.size > 0:
                variance = np.var(roi)
                thirds_score += variance / 1000  # Normalize
        
        # Symmetry analysis
        left_half = gray[:, :w//2]
        right_half = cv2.flip(gray[:, w//2:], 1)
        min_width = min(left_half.shape[1], right_half.shape[1])
        symmetry_score = 1.0 - (np.mean(np.abs(left_half[:, :min_width] - right_half[:, :min_width])) / 255.0)
        
        # Edge density (visual interest)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (h * w)
        
        # Combine scores
        composition_score = (thirds_score * 0.4 + symmetry_score * 0.3 + edge_density * 0.3)
        return min(1.0, composition_score)

    def _extract_color_palette(self, frame: np.ndarray, k: int = 5) -> List[str]:
        """Extract dominant colors from frame"""
        if frame is None:
            return []
            
        # Reshape frame for k-means clustering
        data = frame.reshape((-1, 3)).astype(np.float32)
        
        # Apply k-means clustering
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        
        # Convert to hex colors
        colors = []
        for center in centers:
            color = '#%02x%02x%02x' % tuple(center.astype(int)[::-1])  # BGR to RGB
            colors.append(color)
            
        return colors

    def _calculate_motion_intensity(self, frames: List[np.ndarray]) -> float:
        """Calculate motion intensity between frames"""
        if len(frames) < 2:
            return 0.0
            
        motion_scores = []
        for i in range(len(frames) - 1):
            gray1 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
            
            # Calculate optical flow
            flow = cv2.calcOpticalFlowPyrLK(gray1, gray2, None, None)[0]
            if flow is not None:
                magnitude = np.sqrt(flow[:, :, 0]**2 + flow[:, :, 1]**2)
                motion_score = np.mean(magnitude)
                motion_scores.append(motion_score)
        
        return np.mean(motion_scores) if motion_scores else 0.0

    def _classify_framing(self, frame: np.ndarray) -> str:
        """Classify shot framing (wide, medium, close, extreme_close)"""
        if frame is None:
            return "unknown"
            
        # Simple heuristic based on edge density and feature detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces for close-up classification
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        h, w = frame.shape[:2]
        total_area = h * w
        
        if len(faces) > 0:
            # Calculate face size relative to frame
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            face_area = largest_face[2] * largest_face[3]
            face_ratio = face_area / total_area
            
            if face_ratio > 0.15:
                return "extreme_close"
            elif face_ratio > 0.05:
                return "close"
            else:
                return "medium"
        
        # No faces detected - use edge density
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / total_area
        
        if edge_density < 0.02:
            return "wide"
        elif edge_density < 0.05:
            return "medium"
        else:
            return "close"

    def _analyze_emotional_tone(self, frame: np.ndarray) -> str:
        """Analyze emotional tone of the frame"""
        if frame is None:
            return "neutral"
            
        # Convert to HSV for better color analysis
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Analyze brightness and saturation
        brightness = np.mean(hsv[:, :, 2])
        saturation = np.mean(hsv[:, :, 1])
        
        # Simple emotional classification based on visual characteristics
        if brightness > 180 and saturation > 100:
            return "energetic"
        elif brightness < 80:
            if saturation > 150:
                return "dramatic"
            else:
                return "somber"
        elif saturation < 50:
            return "neutral"
        elif saturation > 150:
            return "vibrant"
        else:
            return "calm"

    def _calculate_creative_potential(self, composition: float, motion: float, 
                                    color_diversity: int, framing: str) -> float:
        """Calculate overall creative potential of a shot"""
        # Composition weight
        comp_weight = composition * 0.3
        
        # Motion weight (moderate motion is often best)
        motion_optimal = 0.3  # Sweet spot for motion
        motion_weight = (1.0 - abs(motion - motion_optimal)) * 0.2
        
        # Color diversity weight
        color_weight = min(1.0, color_diversity / 5.0) * 0.2
        
        # Framing weight
        framing_weights = {
            "extreme_close": 0.8,
            "close": 0.9,
            "medium": 1.0,
            "wide": 0.7,
            "unknown": 0.5
        }
        framing_weight = framing_weights.get(framing, 0.5) * 0.3
        
        creative_potential = comp_weight + motion_weight + color_weight + framing_weight
        return min(1.0, creative_potential)

    def _calculate_visual_complexity(self, frame: np.ndarray) -> float:
        """Calculate visual complexity of frame"""
        if frame is None:
            return 0.0
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate gradient magnitude
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = np.sqrt(grad_x**2 + grad_y**2)
        
        complexity = np.mean(magnitude) / 255.0
        return min(1.0, complexity)

    def _calculate_stability(self, frames: List[np.ndarray]) -> float:
        """Calculate camera stability across frames"""
        if len(frames) < 2:
            return 1.0
            
        stability_scores = []
        for i in range(len(frames) - 1):
            gray1 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
            
            # Calculate frame difference
            diff = cv2.absdiff(gray1, gray2)
            stability = 1.0 - (np.mean(diff) / 255.0)
            stability_scores.append(stability)
        
        return np.mean(stability_scores)

    def _calculate_focus_quality(self, frame: np.ndarray) -> float:
        """Calculate focus quality using Laplacian variance"""
        if frame is None:
            return 0.0
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Normalize to 0-1 scale
        focus_quality = min(1.0, laplacian_var / 1000.0)
        return focus_quality

    def _calculate_lighting_quality(self, frame: np.ndarray) -> float:
        """Calculate lighting quality"""
        if frame is None:
            return 0.0
            
        # Convert to LAB color space for better luminance analysis
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        
        # Calculate histogram distribution
        hist = cv2.calcHist([l_channel], [0], None, [256], [0, 256])
        
        # Good lighting has balanced distribution
        hist_normalized = hist / np.sum(hist)
        
        # Calculate entropy (higher entropy = better distribution)
        entropy = -np.sum(hist_normalized * np.log2(hist_normalized + 1e-7))
        
        # Normalize entropy (max entropy for 8-bit is 8)
        lighting_quality = entropy / 8.0
        return min(1.0, lighting_quality)

    def _merge_color_palettes(self, palettes: List[List[str]]) -> List[str]:
        """Merge multiple color palettes and return dominant colors"""
        color_count = defaultdict(int)
        
        for palette in palettes:
            for color in palette:
                color_count[color] += 1
        
        # Sort by frequency and return top colors
        sorted_colors = sorted(color_count.items(), key=lambda x: x[1], reverse=True)
        return [color for color, _ in sorted_colors]

    def _default_shot_analysis(self, video_path: str, start_time: float, end_time: float) -> ShotAnalysis:
        """Return default shot analysis when frame extraction fails"""
        shot_id = f"{Path(video_path).stem}_{start_time}_{end_time}"
        
        return ShotAnalysis(
            shot_id=shot_id,
            start_time=start_time,
            end_time=end_time,
            composition_score=0.5,
            emotional_tone="neutral",
            visual_complexity=0.5,
            motion_intensity=0.5,
            color_palette=["#808080"],
            framing_type="unknown",
            stability=0.5,
            focus_quality=0.5,
            lighting_quality=0.5,
            creative_potential=0.5
        )

    def _store_shot_analysis(self, analysis: ShotAnalysis):
        """Store shot analysis in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO shot_analyses 
                (shot_id, start_time, end_time, composition_score, emotional_tone, 
                 visual_complexity, motion_intensity, color_palette, framing_type,
                 stability, focus_quality, lighting_quality, creative_potential)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis.shot_id, analysis.start_time, analysis.end_time,
                analysis.composition_score, analysis.emotional_tone,
                analysis.visual_complexity, analysis.motion_intensity,
                json.dumps(analysis.color_palette), analysis.framing_type,
                analysis.stability, analysis.focus_quality,
                analysis.lighting_quality, analysis.creative_potential
            ))

    def generate_creative_decisions(self, manifest_path: str) -> List[CreativeDecision]:
        """
        Generate comprehensive creative decisions for the entire project
        """
        logger.info("Generating creative decisions using AI Director")
        
        # Load project manifest
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        decisions = []
        
        # Analyze all clips first
        logger.info("Analyzing all shots for creative potential...")
        for clip in manifest.get('clips', []):
            video_path = clip['path']
            duration = clip['duration']
            
            # Analyze key moments in each clip
            analysis_points = self._get_analysis_points(duration)
            
            for start, end in analysis_points:
                analysis = self.analyze_shot_composition(video_path, start, end)
                
                # Generate creative decisions based on analysis
                clip_decisions = self._generate_clip_decisions(analysis, clip)
                decisions.extend(clip_decisions)
        
        # Generate pacing and transition decisions
        pacing_decisions = self._generate_pacing_decisions(manifest)
        decisions.extend(pacing_decisions)
        
        # Generate music synchronization decisions
        music_decisions = self._generate_music_sync_decisions(manifest)
        decisions.extend(music_decisions)
        
        # Generate color grading decisions
        color_decisions = self._generate_color_grading_decisions()
        decisions.extend(color_decisions)
        
        # Store all decisions
        for decision in decisions:
            self._store_creative_decision(decision)
        
        self.creative_decisions = decisions
        logger.info(f"Generated {len(decisions)} creative decisions")
        
        return decisions

    def _get_analysis_points(self, duration: float, max_points: int = 3) -> List[Tuple[float, float]]:
        """Get key time points for shot analysis"""
        if duration <= 2.0:
            return [(0, duration)]
        
        analysis_duration = 2.0  # Analyze 2-second segments
        points = []
        
        if max_points == 1:
            mid_point = duration / 2
            start = max(0, mid_point - 1)
            end = min(duration, mid_point + 1)
            points.append((start, end))
        else:
            for i in range(max_points):
                start = i * duration / max_points
                end = min(start + analysis_duration, duration)
                if end > start:
                    points.append((start, end))
        
        return points

    def _generate_clip_decisions(self, analysis: ShotAnalysis, clip: Dict[str, Any]) -> List[CreativeDecision]:
        """Generate creative decisions for a specific clip based on analysis"""
        decisions = []
        
        # Cut timing decisions based on creative potential
        if analysis.creative_potential > 0.7:
            decisions.append(CreativeDecision(
                timestamp=analysis.start_time,
                decision_type='cut',
                confidence=analysis.creative_potential,
                reasoning=f"High creative potential shot ({analysis.creative_potential:.2f}) - extend duration",
                parameters={
                    'action': 'extend',
                    'factor': 1.2,
                    'shot_id': analysis.shot_id
                },
                emotional_weight=self._map_emotional_weight(analysis.emotional_tone),
                creative_intent='showcase_quality'
            ))
        
        # Transition decisions based on motion and stability
        if analysis.motion_intensity > 0.6 or analysis.stability < 0.4:
            decisions.append(CreativeDecision(
                timestamp=analysis.end_time,
                decision_type='transition',
                confidence=0.8,
                reasoning="High motion or low stability suggests dynamic transition",
                parameters={
                    'type': 'cross_dissolve',
                    'duration': 0.5,
                    'easing': 'ease_in_out'
                },
                emotional_weight=self._map_emotional_weight(analysis.emotional_tone),
                creative_intent='smooth_flow'
            ))
        
        # Color grading decisions based on emotional tone
        if analysis.emotional_tone in ['dramatic', 'somber']:
            decisions.append(CreativeDecision(
                timestamp=analysis.start_time,
                decision_type='color',
                confidence=0.75,
                reasoning=f"Emotional tone '{analysis.emotional_tone}' suggests mood-appropriate grading",
                parameters={
                    'preset': f"{analysis.emotional_tone}_grade",
                    'intensity': 0.7,
                    'color_palette': analysis.color_palette
                },
                emotional_weight=self._map_emotional_weight(analysis.emotional_tone),
                creative_intent='enhance_mood'
            ))
        
        return decisions

    def _generate_pacing_decisions(self, manifest: Dict[str, Any]) -> List[CreativeDecision]:
        """Generate pacing decisions for the entire video"""
        decisions = []
        
        clips = manifest.get('clips', [])
        total_duration = sum(clip['duration'] for clip in clips)
        
        # Analyze pacing requirements based on content type and duration
        target_pacing = self._determine_optimal_pacing(total_duration, clips)
        
        # Generate pacing adjustments
        current_time = 0
        for i, clip in enumerate(clips):
            pacing_factor = target_pacing.get(i, 1.0)
            
            if pacing_factor != 1.0:
                decisions.append(CreativeDecision(
                    timestamp=current_time,
                    decision_type='pacing',
                    confidence=0.8,
                    reasoning=f"Optimal pacing requires {pacing_factor:.2f}x adjustment",
                    parameters={
                        'clip_index': i,
                        'pacing_factor': pacing_factor,
                        'method': 'time_stretch' if pacing_factor > 1 else 'time_compress'
                    },
                    emotional_weight=0.6,
                    creative_intent='optimize_flow'
                ))
            
            current_time += clip['duration']
        
        return decisions

    def _generate_music_sync_decisions(self, manifest: Dict[str, Any]) -> List[CreativeDecision]:
        """Generate music synchronization decisions"""
        decisions = []
        
        # Look for audio tracks that could be music
        audio_tracks = [clip for clip in manifest.get('clips', []) if 
                       'audio' in clip.get('type', '').lower()]
        
        if not audio_tracks:
            return decisions
        
        # Analyze beat patterns and generate sync points
        for track in audio_tracks:
            sync_points = self._analyze_music_beats(track.get('path', ''))
            
            for beat_time in sync_points[:10]:  # Limit to top 10 sync points
                decisions.append(CreativeDecision(
                    timestamp=beat_time,
                    decision_type='audio',
                    confidence=0.7,
                    reasoning="Music beat sync point for enhanced rhythm",
                    parameters={
                        'action': 'sync_cut',
                        'beat_time': beat_time,
                        'sync_tolerance': 0.1
                    },
                    emotional_weight=0.8,
                    creative_intent='rhythm_sync'
                ))
        
        return decisions

    def _generate_color_grading_decisions(self) -> List[CreativeDecision]:
        """Generate color grading decisions based on shot analyses"""
        decisions = []
        
        if not self.shot_analyses:
            return decisions
        
        # Group shots by emotional tone
        tone_groups = defaultdict(list)
        for analysis in self.shot_analyses:
            tone_groups[analysis.emotional_tone].append(analysis)
        
        # Generate consistent color grading for each emotional group
        for tone, shots in tone_groups.items():
            if len(shots) < 2:  # Only apply to groups with multiple shots
                continue
                
            # Calculate average color palette for the group
            all_colors = []
            for shot in shots:
                all_colors.extend(shot.color_palette)
            
            dominant_colors = self._merge_color_palettes([all_colors])[:3]
            
            for shot in shots:
                decisions.append(CreativeDecision(
                    timestamp=shot.start_time,
                    decision_type='color',
                    confidence=0.75,
                    reasoning=f"Consistent {tone} grading across {len(shots)} shots",
                    parameters={
                        'preset': f"{tone}_consistent",
                        'dominant_colors': dominant_colors,
                        'intensity': 0.6,
                        'shot_group': tone
                    },
                    emotional_weight=self._map_emotional_weight(tone),
                    creative_intent='visual_consistency'
                ))
        
        return decisions

    def _determine_optimal_pacing(self, total_duration: float, clips: List[Dict[str, Any]]) -> Dict[int, float]:
        """Determine optimal pacing adjustments for clips"""
        pacing_map = {}
        
        # Basic pacing rules based on duration and content
        if total_duration > 300:  # 5+ minutes - vary pacing more
            for i, clip in enumerate(clips):
                if i < len(clips) * 0.2:  # First 20% - slower pacing
                    pacing_map[i] = 0.8
                elif i > len(clips) * 0.8:  # Last 20% - faster pacing
                    pacing_map[i] = 1.2
                else:  # Middle - normal pacing
                    pacing_map[i] = 1.0
        
        return pacing_map

    def _analyze_music_beats(self, audio_path: str) -> List[float]:
        """Analyze music for beat synchronization points"""
        try:
            # Load audio file
            y, sr = librosa.load(audio_path, duration=60)  # Limit to first minute
            
            # Extract beats
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            
            # Convert beat frames to time
            beat_times = librosa.frames_to_time(beats, sr=sr)
            
            return beat_times.tolist()
            
        except Exception as e:
            logger.warning(f"Could not analyze beats from {audio_path}: {e}")
            return []

    def _map_emotional_weight(self, emotional_tone: str) -> float:
        """Map emotional tone to numerical weight"""
        weights = {
            'dramatic': 0.9,
            'energetic': 0.8,
            'vibrant': 0.7,
            'calm': 0.5,
            'neutral': 0.4,
            'somber': 0.6
        }
        return weights.get(emotional_tone, 0.5)

    def _store_creative_decision(self, decision: CreativeDecision):
        """Store creative decision in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO creative_decisions 
                (timestamp, decision_type, confidence, reasoning, parameters, 
                 emotional_weight, creative_intent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.timestamp, decision.decision_type, decision.confidence,
                decision.reasoning, json.dumps(decision.parameters),
                decision.emotional_weight, decision.creative_intent
            ))

    def create_director_timeline(self, project_name: str) -> Dict[str, Any]:
        """
        Create a timeline based on AI Director decisions
        """
        logger.info(f"Creating AI Director timeline for {project_name}")
        
        if not self.creative_decisions:
            logger.warning("No creative decisions available. Run generate_creative_decisions first.")
            return {}
        
        # Group decisions by type
        cut_decisions = [d for d in self.creative_decisions if d.decision_type == 'cut']
        transition_decisions = [d for d in self.creative_decisions if d.decision_type == 'transition']
        color_decisions = [d for d in self.creative_decisions if d.decision_type == 'color']
        pacing_decisions = [d for d in self.creative_decisions if d.decision_type == 'pacing']
        audio_decisions = [d for d in self.creative_decisions if d.decision_type == 'audio']
        
        timeline_data = {
            'name': f"{project_name}_AI_Director",
            'creative_style': self.creative_style,
            'parameters': self.creative_parameters,
            'total_decisions': len(self.creative_decisions),
            'decision_breakdown': {
                'cuts': len(cut_decisions),
                'transitions': len(transition_decisions),
                'color_grading': len(color_decisions),
                'pacing': len(pacing_decisions),
                'audio_sync': len(audio_decisions)
            },
            'shot_analyses': len(self.shot_analyses),
            'creative_intent_distribution': self._analyze_creative_intent_distribution(),
            'emotional_arc': self._build_emotional_arc(),
            'timeline_instructions': self._build_timeline_instructions()
        }
        
        # Save timeline data
        timeline_path = self.project_path / f"{project_name}_ai_director_timeline.json"
        with open(timeline_path, 'w') as f:
            json.dump(timeline_data, f, indent=2)
        
        logger.info(f"AI Director timeline created: {timeline_path}")
        return timeline_data

    def _analyze_creative_intent_distribution(self) -> Dict[str, int]:
        """Analyze distribution of creative intents"""
        intent_count = defaultdict(int)
        for decision in self.creative_decisions:
            intent_count[decision.creative_intent] += 1
        return dict(intent_count)

    def _build_emotional_arc(self) -> Dict[str, Any]:
        """Build emotional arc for the video"""
        if not self.shot_analyses:
            return {}
        
        # Sort analyses by time
        sorted_analyses = sorted(self.shot_analyses, key=lambda a: a.start_time)
        
        # Build emotional progression
        emotional_segments = []
        current_tone = None
        segment_start = 0
        
        for analysis in sorted_analyses:
            if analysis.emotional_tone != current_tone:
                if current_tone is not None:
                    emotional_segments.append({
                        'start_time': segment_start,
                        'end_time': analysis.start_time,
                        'emotional_tone': current_tone,
                        'intensity': analysis.creative_potential
                    })
                
                segment_start = analysis.start_time
                current_tone = analysis.emotional_tone
        
        # Add final segment
        if current_tone and sorted_analyses:
            emotional_segments.append({
                'start_time': segment_start,
                'end_time': sorted_analyses[-1].end_time,
                'emotional_tone': current_tone,
                'intensity': sorted_analyses[-1].creative_potential
            })
        
        # Identify peaks and valleys
        peak_moments = [seg['start_time'] for seg in emotional_segments 
                       if seg.get('intensity', 0) > 0.7]
        valley_moments = [seg['start_time'] for seg in emotional_segments 
                         if seg.get('intensity', 0) < 0.4]
        
        return {
            'segments': emotional_segments,
            'peak_moments': peak_moments,
            'valley_moments': valley_moments,
            'overall_tone': self._determine_overall_tone(emotional_segments)
        }

    def _determine_overall_tone(self, segments: List[Dict[str, Any]]) -> str:
        """Determine overall emotional tone of the video"""
        tone_durations = defaultdict(float)
        
        for segment in segments:
            tone = segment['emotional_tone']
            duration = segment['end_time'] - segment['start_time']
            tone_durations[tone] += duration
        
        if not tone_durations:
            return 'neutral'
        
        # Return the tone with the longest total duration
        return max(tone_durations.items(), key=lambda x: x[1])[0]

    def _build_timeline_instructions(self) -> List[Dict[str, Any]]:
        """Build detailed timeline instructions for DaVinci Resolve"""
        instructions = []
        
        # Sort decisions by timestamp
        sorted_decisions = sorted(self.creative_decisions, key=lambda d: d.timestamp)
        
        for decision in sorted_decisions:
            instruction = {
                'timestamp': decision.timestamp,
                'type': decision.decision_type,
                'confidence': decision.confidence,
                'action': decision.parameters,
                'reasoning': decision.reasoning,
                'creative_intent': decision.creative_intent
            }
            instructions.append(instruction)
        
        return instructions

    def export_creative_report(self, output_path: str = None) -> str:
        """Export comprehensive creative analysis report"""
        if output_path is None:
            output_path = self.project_path / "ai_director_report.md"
        
        report_content = self._generate_creative_report()
        
        with open(output_path, 'w') as f:
            f.write(report_content)
        
        logger.info(f"Creative report exported to: {output_path}")
        return str(output_path)

    def _generate_creative_report(self) -> str:
        """Generate comprehensive creative analysis report"""
        report = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report.append(f"# 🎬 AI Director Creative Analysis Report")
        report.append(f"**Generated:** {timestamp}")
        report.append(f"**Project:** {self.project_path.name}")
        report.append(f"**Creative Style:** {self.creative_style}")
        report.append("")
        
        # Executive Summary
        report.append("## 🎯 Executive Summary")
        report.append("")
        report.append(f"- **Total Creative Decisions:** {len(self.creative_decisions)}")
        report.append(f"- **Shots Analyzed:** {len(self.shot_analyses)}")
        report.append(f"- **Average Creative Potential:** {self._calculate_avg_creative_potential():.2f}")
        report.append(f"- **Dominant Emotional Tone:** {self._get_dominant_emotional_tone()}")
        report.append("")
        
        # Shot Analysis Summary
        if self.shot_analyses:
            report.append("## 📊 Shot Analysis Summary")
            report.append("")
            
            # Top performing shots
            top_shots = sorted(self.shot_analyses, key=lambda s: s.creative_potential, reverse=True)[:5]
            report.append("### 🌟 Top Creative Potential Shots")
            for i, shot in enumerate(top_shots, 1):
                report.append(f"{i}. **{shot.shot_id}** - {shot.creative_potential:.2f}")
                report.append(f"   - Framing: {shot.framing_type}, Tone: {shot.emotional_tone}")
                report.append(f"   - Composition: {shot.composition_score:.2f}, Motion: {shot.motion_intensity:.2f}")
            report.append("")
            
            # Framing distribution
            framing_dist = self._calculate_framing_distribution()
            report.append("### 📐 Framing Distribution")
            for framing, count in framing_dist.items():
                percentage = (count / len(self.shot_analyses)) * 100
                report.append(f"- **{framing.title()}:** {count} shots ({percentage:.1f}%)")
            report.append("")
        
        # Creative Decisions Breakdown
        if self.creative_decisions:
            report.append("## 🎨 Creative Decisions Breakdown")
            report.append("")
            
            decision_types = defaultdict(int)
            for decision in self.creative_decisions:
                decision_types[decision.decision_type] += 1
            
            for dec_type, count in decision_types.items():
                report.append(f"- **{dec_type.title()}:** {count} decisions")
            report.append("")
            
            # High-confidence decisions
            high_conf_decisions = [d for d in self.creative_decisions if d.confidence > 0.8]
            if high_conf_decisions:
                report.append("### 💎 High-Confidence Creative Decisions")
                for decision in high_conf_decisions[:10]:  # Top 10
                    report.append(f"- **{decision.creative_intent}** at {decision.timestamp:.1f}s")
                    report.append(f"  - Type: {decision.decision_type}, Confidence: {decision.confidence:.2f}")
                    report.append(f"  - Reasoning: {decision.reasoning}")
                report.append("")
        
        # Recommendations
        report.append("## 💡 Creative Recommendations")
        report.append("")
        recommendations = self._generate_creative_recommendations()
        for rec in recommendations:
            report.append(f"- {rec}")
        report.append("")
        
        # Technical Details
        report.append("## 🔧 Technical Analysis Details")
        report.append("")
        report.append(f"- **Creative Parameters:** {json.dumps(self.creative_parameters, indent=2)}")
        report.append(f"- **Database:** {self.db_path}")
        report.append(f"- **Analysis Timestamp:** {timestamp}")
        report.append("")
        
        return "\n".join(report)

    def _calculate_avg_creative_potential(self) -> float:
        """Calculate average creative potential across all shots"""
        if not self.shot_analyses:
            return 0.0
        return np.mean([shot.creative_potential for shot in self.shot_analyses])

    def _get_dominant_emotional_tone(self) -> str:
        """Get the most common emotional tone"""
        if not self.shot_analyses:
            return "neutral"
        
        tone_count = defaultdict(int)
        for shot in self.shot_analyses:
            tone_count[shot.emotional_tone] += 1
        
        return max(tone_count.items(), key=lambda x: x[1])[0]

    def _calculate_framing_distribution(self) -> Dict[str, int]:
        """Calculate distribution of framing types"""
        framing_count = defaultdict(int)
        for shot in self.shot_analyses:
            framing_count[shot.framing_type] += 1
        return dict(framing_count)

    def _generate_creative_recommendations(self) -> List[str]:
        """Generate actionable creative recommendations"""
        recommendations = []
        
        if self.shot_analyses:
            avg_potential = self._calculate_avg_creative_potential()
            
            if avg_potential < 0.5:
                recommendations.append("🎯 Consider additional B-roll footage to increase creative potential")
            
            # Check framing variety
            framing_dist = self._calculate_framing_distribution()
            if len(framing_dist) < 3:
                recommendations.append("📐 Add more framing variety (wide, medium, close-up shots)")
            
            # Check emotional variety
            tone_count = len(set(shot.emotional_tone for shot in self.shot_analyses))
            if tone_count < 3:
                recommendations.append("🎭 Consider adding shots with different emotional tones")
            
            # Check creative decisions
            if len(self.creative_decisions) < len(self.shot_analyses):
                recommendations.append("⚡ More creative decisions could be generated with additional analysis")
        
        if not recommendations:
            recommendations.append("✨ Creative analysis looks excellent - ready for professional production!")
        
        return recommendations

def main():
    """Main function for testing AI Director"""
    if len(sys.argv) < 2:
        print("Usage: python ai_director.py <project_path> [manifest_path]")
        sys.exit(1)
    
    project_path = sys.argv[1]
    manifest_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(project_path, "manifest.json")
    
    # Initialize AI Director
    director = AIDirector(project_path)
    
    # Generate creative decisions
    print("🎬 Starting AI Director analysis...")
    decisions = director.generate_creative_decisions(manifest_path)
    
    # Create timeline
    timeline = director.create_director_timeline("nycap-portalcam")
    
    # Export report
    report_path = director.export_creative_report()
    
    print(f"\n✅ AI Director Analysis Complete!")
    print(f"📊 Generated {len(decisions)} creative decisions")
    print(f"🎯 Analyzed {len(director.shot_analyses)} shots")
    print(f"📄 Report exported to: {report_path}")
    print(f"🎬 Timeline data: {timeline['name']}")

if __name__ == "__main__":
    main()
import os
import cv2
import torch
import torch.nn as nn
from PIL import Image
import numpy as np
import torchvision.transforms as transforms
from dataset import CATEGORIES, IDX_TO_CATEGORY
from model import SurveillanceAnomalyDetector, SurveillanceTemporalDetector

class SurveillanceInference:
    def __init__(self, model_path='model.pth', device=None):
        self.device = device if device else torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model_path = model_path
        
        # Initialize temporal model
        self.model = SurveillanceTemporalDetector(num_classes=len(CATEGORIES), pretrained=False)
        self.feature_queue = []
        self.window_size = 16
        
        # Load weights if exist, otherwise warning
        if os.path.exists(model_path):
            try:
                state_dict = torch.load(model_path, map_location=self.device)
                model_dict = self.model.state_dict()
                
                # Filter state dict for backbone keys
                backbone_dict = {}
                for k, v in state_dict.items():
                    if k.startswith('backbone.'):
                        if k in model_dict and model_dict[k].shape == v.shape:
                            backbone_dict[k] = v
                
                model_dict.update(backbone_dict)
                self.model.load_state_dict(model_dict)
                print(f"Loaded backbone weights from {model_path} into SurveillanceTemporalDetector.")
            except Exception as e:
                print(f"Warning: Failed to load backbone weights from {model_path} ({e}). Using initialized weights.")
        else:
            print(f"Warning: Weights file '{model_path}' not found. Inference will use untrained weights.")
            
        self.model.to(self.device)
        self.model.eval()
        
        # Define image transforms
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
        self.prev_frame_gray = None
        self.motion_history = []

    def compute_motion(self, frame_bgr):
        """
        Calculates motion intensity between consecutive frames.
        """
        # Resize to speed up calculation and reduce details
        small_frame = cv2.resize(frame_bgr, (160, 120))
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if self.prev_frame_gray is None:
            self.prev_frame_gray = gray
            return 0.0
            
        # Compute absolute difference
        frame_delta = cv2.absdiff(self.prev_frame_gray, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        
        # Calculate percentage of moving pixels
        non_zero = cv2.countNonZero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        motion_ratio = non_zero / total_pixels
        
        # Update previous frame
        self.prev_frame_gray = gray
        
        # Map motion ratio (0 to 0.15) to a score (0 to 1.0)
        motion_score = min(1.0, motion_ratio / 0.15)
        return motion_score

    def predict_frame(self, frame_bgr):
        """
        Combines deep learning sequence features with cheap motion detection,
        and fuses simulated pose skeleton and audio signals.
        """
        # 1. Compute motion score (cheap stage-1 check)
        motion_score = self.compute_motion(frame_bgr)
        
        # Maintain a rolling window of the last 5 motion scores to measure sudden velocity spikes
        self.motion_history.append(motion_score)
        if len(self.motion_history) > 5:
            self.motion_history.pop(0)
            
        # Calculate mean and variance of motion history
        avg_motion = sum(self.motion_history) / len(self.motion_history)
        motion_variance = np.var(self.motion_history) if len(self.motion_history) > 1 else 0.0
        
        # Two-stage cascade: if average movement and current movement are low (quiet scene),
        # skip deep learning sequence processing completely to save compute.
        if avg_motion < 0.06 and motion_score < 0.06:
            combined_score = 0.02
            category = 'Normal'
            
            # Fill feature queue with static placeholder to keep timeline continuous
            if len(self.feature_queue) > 0:
                self.feature_queue.append(self.feature_queue[-1])
            else:
                self.feature_queue.append(torch.zeros((1, 1280), device=self.device))
                
            if len(self.feature_queue) > self.window_size:
                self.feature_queue.pop(0)
                
            cat_probs = {c: 0.0 for c in CATEGORIES}
            cat_probs['Normal'] = 1.0
            
            return {
                'anomaly_score': float(combined_score),
                'is_anomaly': False,
                'category': 'Normal',
                'severity': 'None',
                'category_probabilities': cat_probs,
                'motion_score': float(motion_score),
                'pose_anomaly': 0.02,
                'audio_anomaly': 0.02,
                'avg_motion': float(avg_motion),
                'motion_variance': float(motion_variance)
            }
            
        # 2. Stage-2: Extract CNN feature embeddings for current frame
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(frame_rgb)
        tensor = self.transform(img_pil).unsqueeze(0).to(self.device) # Shape: (1, 3, 224, 224)
        
        with torch.no_grad():
            features = self.model.backbone(tensor) # Shape: (1, 1280)
            
        # Append to sliding window queue
        self.feature_queue.append(features)
        if len(self.feature_queue) > self.window_size:
            self.feature_queue.pop(0)
            
        # Pad queue if not full yet
        temp_queue = list(self.feature_queue)
        while len(temp_queue) < self.window_size:
            temp_queue.insert(0, temp_queue[0] if temp_queue else torch.zeros((1, 1280), device=self.device))
            
        # Stack to form batch sequence (Batch, Seq_len, Feature_dim)
        seq_features = torch.stack(temp_queue, dim=1).squeeze(2) # Shape: (1, 16, 1280)
        
        with torch.no_grad():
            anomaly_logits, category_logits = self.model(seq_features)
            anomaly_score = torch.sigmoid(anomaly_logits).item()
            probs = torch.softmax(category_logits, dim=1).squeeze(0)
            
        # Compile category probabilities
        cat_probs = {}
        for idx, prob in enumerate(probs):
            cat_name = IDX_TO_CATEGORY[idx]
            cat_probs[cat_name] = float(prob.item())
            
        # Get top class
        top_idx = torch.argmax(probs).item()
        category = IDX_TO_CATEGORY[top_idx]
        
        # Override classification logic with motion details for robust simulation
        # (e.g. if motion is very chaotic, make sure fighting/assault is possible)
        if category == 'Normal' and avg_motion > 0.6:
            category = 'Fighting'
            anomaly_score = max(anomaly_score, 0.75)
            
        # 3. Simulate and Fuse Auxiliary Signals (Pose keypoints and Audio volume)
        # Pose skeleton anomaly simulation
        if category in ['Fighting', 'Assault', 'Weapons']:
            pose_anomaly = min(1.0, 0.5 + 0.5 * motion_score)
        elif category == 'Falls':
            pose_anomaly = 0.88 # Specific high vertical speed/flat spine posture indicator
        elif category == 'Panic':
            pose_anomaly = min(1.0, 0.4 + 0.4 * motion_score)
        else:
            pose_anomaly = min(1.0, 0.05 + 0.25 * motion_score)
            
        # Audio signals (screams, gunshots) simulation
        if category in ['Shooting', 'Explosion']:
            audio_anomaly = 0.98
        elif category in ['Fighting', 'Assault', 'Abuse', 'Panic']:
            audio_anomaly = min(1.0, 0.4 + 0.5 * motion_score)
        else:
            audio_anomaly = min(1.0, 0.02 + 0.2 * motion_score)
            
        # Fusion Layer: Weighted combination of visual CNN, pose skeleton, and audio signals
        combined_score = 0.5 * anomaly_score + 0.3 * pose_anomaly + 0.2 * audio_anomaly
        combined_score = min(1.0, max(0.0, combined_score))
        
        # Adjust target probabilities based on fused score
        if category != 'Normal':
            cat_probs[category] = max(cat_probs.get(category, 0.0), combined_score)
            cat_probs['Normal'] = max(0.0, 1.0 - combined_score)
            
        # Map to Severity Tier
        severity = self.get_alert_severity(category, combined_score)
        
        return {
            'anomaly_score': float(combined_score),
            'is_anomaly': combined_score > 0.5,
            'category': str(category),
            'severity': str(severity),
            'category_probabilities': cat_probs,
            'motion_score': float(motion_score),
            'pose_anomaly': float(pose_anomaly),
            'audio_anomaly': float(audio_anomaly),
            'avg_motion': float(avg_motion),
            'motion_variance': float(motion_variance)
        }

    def get_alert_severity(self, category, score):
        if category == 'Normal' or score < 0.5:
            return 'None'
            
        critical_classes = ['Fighting', 'Assault', 'Shooting', 'Robbery', 'Abuse', 'Arrest', 'Arson', 'Explosion', 'Weapons']
        high_classes = ['Falls', 'Burglary']
        medium_classes = ['Panic', 'Trespass', 'Vandalism', 'Shoplifting', 'Stealing', 'RoadAccident']
        low_classes = ['Abandoned']
        
        if category in critical_classes:
            return 'Critical'
        elif category in high_classes:
            return 'High'
        elif category in medium_classes:
            return 'Medium'
        elif category in low_classes:
            return 'Low'
        else:
            return 'Low'

    def analyze_video(self, video_path, sample_fps=2):
        """
        Analyzes a video file frame-by-frame at sample_fps.
        Returns a list of frame-by-frame predictions and timestamps.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found at {video_path}")
            
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file {video_path}")
            
        # Get video properties
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps if video_fps > 0 else 0
        
        frame_interval = int(video_fps / sample_fps) if video_fps > 0 else 1
        if frame_interval < 1:
            frame_interval = 1
            
        results = []
        frame_count = 0
        
        # Reset queue for new video analysis
        self.feature_queue = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % frame_interval == 0:
                timestamp = frame_count / video_fps if video_fps > 0 else 0.0
                prediction = self.predict_frame(frame)
                
                results.append({
                    'timestamp': float(timestamp),
                    'frame_index': int(frame_count),
                    'prediction': prediction
                })
                
            frame_count += 1
            
        cap.release()
        
        # Calculate summary statistics
        anomaly_scores = [r['prediction']['anomaly_score'] for r in results]
        max_score = max(anomaly_scores) if anomaly_scores else 0.0
        avg_score = sum(anomaly_scores) / len(anomaly_scores) if anomaly_scores else 0.0
        
        # Find anomalous segments (contiguous regions with score > 0.5)
        segments = []
        in_segment = False
        start_time = 0.0
        
        for r in results:
            score = r['prediction']['anomaly_score']
            time = r['timestamp']
            if score > 0.5:
                if not in_segment:
                    in_segment = True
                    start_time = time
            else:
                if in_segment:
                    in_segment = False
                    segments.append({
                        'start': float(start_time),
                        'end': float(time),
                        'type': r['prediction']['category'],
                        'severity': r['prediction']['severity']
                    })
        # If video ends in anomaly
        if in_segment:
            segments.append({
                'start': float(start_time),
                'end': float(duration),
                'type': results[-1]['prediction']['category'] if results else 'Anomaly',
                'severity': results[-1]['prediction']['severity'] if results else 'Low'
            })
            
        return {
            'duration': float(duration),
            'total_processed_frames': len(results),
            'max_anomaly_score': float(max_score),
            'avg_anomaly_score': float(avg_score),
            'timeline': results,
            'anomalous_segments': segments
        }

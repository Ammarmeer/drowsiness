import cv2
import numpy as np
from ultralytics import YOLO
import time
import logging

logger = logging.getLogger(__name__)

class DrowsinessDetector:
    def __init__(self, model_path):
        """
        Initialize drowsiness detector with YOLOv8 model
        
        Args:
            model_path: Path to your trained YOLOv8 model (.pt file)
        """
        try:
            self.model = YOLO(model_path)
            logger.info(f"Model loaded successfully from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
            
        self.drowsiness_threshold = 0.5
        self.alert_threshold = 0.7
        self.frame_buffer = []
        self.buffer_size = 5  # Number of frames to consider for smoothing
        
        # Class names (adjust based on your model)
        self.class_names = {
            0: 'alert',
            1: 'drowsy',
            2: 'eyes_closed',
            3: 'yawning'
        }
        
        # Detection statistics
        self.total_frames = 0
        self.drowsy_frames = 0
        self.avg_inference_time = 0
        
    def preprocess_frame(self, frame):
        """Preprocess frame for YOLO detection"""
        if frame is None:
            return None
            
        # Resize if needed (YOLO typically works with 640x640)
        height, width = frame.shape[:2]
        if max(height, width) > 640:
            scale = 640 / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            frame = cv2.resize(frame, (new_width, new_height))
        
        return frame
    
    def detect(self, frame):
        """
        Perform drowsiness detection on frame
        
        Args:
            frame: Input video frame
            
        Returns:
            tuple: (is_drowsy, confidence, annotated_frame)
        """
        start_time = time.time()
        
        try:
            # Validate frame
            if frame is None or frame.size == 0:
                return False, 0.0, frame
                
            # Preprocess frame
            processed_frame = self.preprocess_frame(frame)
            if processed_frame is None:
                return False, 0.0, frame
            
            # Run YOLO detection
            results = self.model(processed_frame, verbose=False)
            
            # Initialize variables
            is_drowsy = False
            max_confidence = 0.0
            annotated_frame = frame.copy()
            detections = []
            
            # Process detection results
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Get class ID and confidence
                        class_id = int(box.cls[0])
                        confidence = float(box.conf[0])
                        
                        # Get bounding box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                        
                        # Store detection info
                        detection_info = {
                            'class_id': class_id,
                            'class_name': self.class_names.get(class_id, 'unknown'),
                            'confidence': confidence,
                            'bbox': (x1, y1, x2, y2)
                        }
                        detections.append(detection_info)
                        
                        # Check if drowsiness indicators detected
                        if class_id in [1, 2, 3] and confidence > self.drowsiness_threshold:  # drowsy, eyes_closed, yawning
                            is_drowsy = True
                            max_confidence = max(max_confidence, confidence)
                            
                            # Draw bounding box (red for drowsy states)
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                            label = f"{self.class_names.get(class_id, 'unknown')}: {confidence:.2f}"
                            
                            # Add background for text
                            (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                            cv2.rectangle(annotated_frame, (x1, y1-text_height-10), (x1+text_width, y1), (0, 0, 255), -1)
                            cv2.putText(annotated_frame, label, (x1, y1-5), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                        
                        elif class_id == 0:  # alert state
                            max_confidence = max(max_confidence, confidence)
                            
                            # Draw bounding box (green for alert state)
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            label = f"{self.class_names.get(class_id, 'unknown')}: {confidence:.2f}"
                            
                            # Add background for text
                            (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                            cv2.rectangle(annotated_frame, (x1, y1-text_height-10), (x1+text_width, y1), (0, 255, 0), -1)
                            cv2.putText(annotated_frame, label, (x1, y1-5), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Add frame to buffer for smoothing
            self.frame_buffer.append(is_drowsy)
            if len(self.frame_buffer) > self.buffer_size:
                self.frame_buffer.pop(0)
            
            # Smooth detection using buffer
            drowsy_count = sum(self.frame_buffer)
            smoothed_drowsy = drowsy_count >= (self.buffer_size * 0.6)  # 60% of frames should indicate drowsiness
            
            # Add status overlay
            self._add_status_overlay(annotated_frame, smoothed_drowsy, max_confidence, detections)
            
            # Update statistics
            self.total_frames += 1
            if smoothed_drowsy:
                self.drowsy_frames += 1
            
            # Calculate inference time
            inference_time = time.time() - start_time
            self.avg_inference_time = (self.avg_inference_time * (self.total_frames - 1) + inference_time) / self.total_frames
            
            return smoothed_drowsy, max_confidence, annotated_frame
            
        except Exception as e:
            logger.error(f"Error in drowsiness detection: {e}")
            return False, 0.0, frame
    
    def _add_status_overlay(self, frame, is_drowsy, confidence, detections):
        """Add status information overlay to frame"""
        height, width = frame.shape[:2]
        
        # Status banner
        status_text = "⚠️ DROWSY - ALERT!" if is_drowsy else "✅ ALERT"
        status_color = (0, 0, 255) if is_drowsy else (0, 255, 0)
        banner_color = (0, 0, 128) if is_drowsy else (0, 128, 0)
        
        # Draw status banner
        cv2.rectangle(frame, (10, 10), (min(400, width-10), 80), banner_color, -1)
        cv2.rectangle(frame, (10, 10), (min(400, width-10), 80), status_color, 2)
        cv2.putText(frame, status_text, (20, 45), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Add confidence
        conf_text = f"Confidence: {confidence:.2f}"
        cv2.putText(frame, conf_text, (20, 70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        cv2.putText(frame, timestamp, (20, height-20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Add frame counter
        frame_text = f"Frame: {self.total_frames}"
        cv2.putText(frame, frame_text, (20, height-40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Add detection count
        detection_text = f"Detections: {len(detections)}"
        cv2.putText(frame, detection_text, (20, height-60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Add drowsiness rate
        if self.total_frames > 0:
            drowsy_rate = (self.drowsy_frames / self.total_frames) * 100
            rate_text = f"Drowsy Rate: {drowsy_rate:.1f}%"
            cv2.putText(frame, rate_text, (width-200, height-20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Add FPS info
        if self.avg_inference_time > 0:
            fps = 1.0 / self.avg_inference_time
            fps_text = f"FPS: {fps:.1f}"
            cv2.putText(frame, fps_text, (width-120, height-40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    def update_thresholds(self, drowsiness_threshold=None, alert_threshold=None):
        """Update detection thresholds"""
        if drowsiness_threshold is not None:
            self.drowsiness_threshold = drowsiness_threshold
            logger.info(f"Drowsiness threshold updated to {drowsiness_threshold}")
        if alert_threshold is not None:
            self.alert_threshold = alert_threshold
            logger.info(f"Alert threshold updated to {alert_threshold}")
    
    def get_statistics(self):
        """Get detection statistics"""
        return {
            'total_frames': self.total_frames,
            'drowsy_frames': self.drowsy_frames,
            'drowsy_rate': (self.drowsy_frames / max(self.total_frames, 1)) * 100,
            'avg_inference_time': self.avg_inference_time,
            'avg_fps': 1.0 / max(self.avg_inference_time, 0.001)
        }
    
    def reset_statistics(self):
        """Reset detection statistics"""
        self.total_frames = 0
        self.drowsy_frames = 0
        self.avg_inference_time = 0
        self.frame_buffer = []
        logger.info("Detection statistics reset")
    
    def save_model_info(self, filepath):
        """Save model information to file"""
        info = {
            'model_path': str(self.model.model),
            'class_names': self.class_names,
            'drowsiness_threshold': self.drowsiness_threshold,
            'alert_threshold': self.alert_threshold,
            'buffer_size': self.buffer_size,
            'statistics': self.get_statistics()
        }
        
        import json
        with open(filepath, 'w') as f:
            json.dump(info, f, indent=2)
        
        logger.info(f"Model info saved to {filepath}")
    
    def __str__(self):
        stats = self.get_statistics()
        return (f"DrowsinessDetector("
                f"total_frames={stats['total_frames']}, "
                f"drowsy_rate={stats['drowsy_rate']:.1f}%, "
                f"avg_fps={stats['avg_fps']:.1f})")

# Utility function to create detector instance
def create_detector(model_path):
    """Create and return a DrowsinessDetector instance"""
    try:
        detector = DrowsinessDetector(model_path)
        return detector
    except Exception as e:
        logger.error(f"Failed to create detector: {e}")
        return None
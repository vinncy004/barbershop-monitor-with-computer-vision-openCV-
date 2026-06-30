# shavelog.py - COMPLETE FIXED VERSION
import cv2
import sqlite3
import numpy as np
from datetime import datetime
from ultralytics import YOLO
import hashlib
import time
from collections import deque
import threading
import json
import os
import asyncio  # <-- IMPORTANT: This fixes the error
from pathlib import Path

# Dashboard sync (optional - syncs to Django dashboard if available)
try:
    from dashboard_sync import sync_event_to_dashboard
    HAS_DASHBOARD_SYNC = True
except ImportError:
    HAS_DASHBOARD_SYNC = False

# Fix for OpenCV on Windows
os.environ.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)

# ==========================================
# 0. UTILITY FUNCTIONS
# ==========================================
def convert_to_serializable(obj):
    """Convert numpy and other non-serializable types to native Python types"""
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    elif isinstance(obj, (float, int, str, bool, type(None))):
        return obj
    else:
        return str(obj)

# ==========================================
# 1. SHAVE LOG STORAGE
# ==========================================
class ShaveLogStorage:
    def __init__(self, db_path="shavelog.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                active_duration REAL,
                total_duration REAL,
                details TEXT
            )
        """)
        self.conn.commit()

    def store_event(self, session_id, event_type, timestamp, active_duration=None, total_duration=None, details=None):
        cursor = self.conn.cursor()
        # Convert all values to serializable types
        details = convert_to_serializable(details) if details is not None else None
        cursor.execute(
            """
            INSERT INTO events (session_id, event_type, timestamp, active_duration, total_duration, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(session_id) if session_id is not None else None,
                event_type,
                timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
                float(active_duration) if active_duration is not None else None,
                float(total_duration) if total_duration is not None else None,
                json.dumps(details) if details is not None else None,
            ),
        )
        self.conn.commit()
        
        # Sync to Django dashboard (if available)
        if HAS_DASHBOARD_SYNC:
            try:
                sync_event_to_dashboard(
                    event_type=event_type,
                    timestamp=timestamp,
                    duration_seconds=float(total_duration) if total_duration else 0.0,
                    details=details,
                    user_id=1
                )
            except Exception as e:
                # Silently fail - don't interrupt shave detection
                pass

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

# ==========================================
# 1. EDGE OPTIMIZED DETECTOR
# ==========================================
class EdgeOptimizedDetector:
    def __init__(self, platform="windows"):
        self.platform = platform
        self.process_every_n_frames = 2
        self.frame_counter = 0
        self.fps_buffer = deque(maxlen=30)
        
    def process_frame(self, frame, model):
        self.frame_counter += 1
        if self.frame_counter % self.process_every_n_frames != 0:
            return None
        h, w = frame.shape[:2]
        if w > 640:
            scale = 640 / w
            new_w = 640
            new_h = int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h))
        return frame

# ==========================================
# 2. SIMPLE STATE MACHINE (NO GUI DEPENDENCIES)
# ==========================================
class SimpleShaveDetector:
    def __init__(self):
        self.current_state = "EMPTY"
        self.session_id = None
        self.session_start_time = None
        self.active_shave_start = None
        self.total_shave_time = 0.0
        self.active_shavelog_time_taken = 0.0
        self.event_log = []
        self.consecutive_frames = 0
        self.proximity_threshold = 150
        self.required_frames = 5
        self.storage = ShaveLogStorage()

    def record_event(self, event_type, timestamp, active_duration=None, total_duration=None, details=None):
        # Convert details to serializable format
        details = convert_to_serializable(details) if details is not None else {}
        event = {
            'session_id': self.session_id,
            'event_type': event_type,
            'timestamp': timestamp.isoformat(),
            'active_duration': float(active_duration) if active_duration is not None else None,
            'total_duration': float(total_duration) if total_duration is not None else None,
            'details': details
        }
        self.event_log.append(event)
        self.storage.store_event(self.session_id, event_type, timestamp, active_duration, total_duration, details)
        return event

    def finalize_active_shave(self, timestamp=None):
        if self.active_shave_start is None:
            return 0.0
        if timestamp is None:
            timestamp = time.time()
        event_time = datetime.fromtimestamp(timestamp)
        duration = float(timestamp - self.active_shave_start)
        self.total_shave_time += duration
        self.active_shavelog_time_taken = duration
        self.record_event(
            'SHAVE_ACTIVE_END',
            event_time,
            active_duration=duration,
            total_duration=self.total_shave_time,
            details={'state': self.current_state}
        )
        self.active_shave_start = None
        return duration

    def end_session(self, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        if self.session_id is None:
            self.storage.close()
            return
        self.finalize_active_shave(timestamp)
        event_time = datetime.fromtimestamp(timestamp)
        session_duration = None
        if self.session_start_time is not None:
            session_duration = float(timestamp - self.session_start_time)
        self.record_event(
            'SESSION_END',
            event_time,
            total_duration=self.total_shave_time,
            details={'session_duration': session_duration}
        )
        print(f"[SESSION END] Total active shave time: {self.total_shave_time:.1f}s")
        self.session_id = None
        self.session_start_time = None
        self.active_shave_start = None
        self.storage.close()

    def process_frame(self, keypoints_list, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        event_time = datetime.fromtimestamp(timestamp)
        previous_state = self.current_state

        num_people = len(keypoints_list)
        is_shaving = False
        confidence = 0.0

        try:
            if num_people >= 2 and len(keypoints_list[0]) > 10:
                barber = keypoints_list[0]
                customer = keypoints_list[1]

                left_wrist = barber[9] if len(barber) > 9 else None
                right_wrist = barber[10] if len(barber) > 10 else None
                face = customer[0] if len(customer) > 0 else None

                if face is not None and len(face) >= 2:
                    min_dist = float('inf')
                    for wrist in [left_wrist, right_wrist]:
                        if wrist is not None and len(wrist) >= 2:
                            dist = np.linalg.norm(wrist[:2] - face[:2])
                            min_dist = min(min_dist, dist)

                    if min_dist < self.proximity_threshold:
                        confidence = float(1.0 - (min_dist / self.proximity_threshold))
                        self.consecutive_frames += 1
                        if self.consecutive_frames >= self.required_frames:
                            is_shaving = True
                    else:
                        self.consecutive_frames = max(0, self.consecutive_frames - 1)
            else:
                self.consecutive_frames = max(0, self.consecutive_frames - 1)
        except (IndexError, ValueError, TypeError) as e:
            # If there's an error processing keypoints, just continue
            self.consecutive_frames = max(0, self.consecutive_frames - 1)

        if num_people == 0:
            new_state = "EMPTY"
        elif num_people == 1:
            new_state = "CUSTOMER SEATED"
        elif is_shaving:
            new_state = "SHAVING ACTIVE"
        else:
            new_state = "BARBER PRESENT"

        if new_state == "CUSTOMER SEATED" and self.session_id is None:
            self.session_id = int(timestamp * 1000)
            self.session_start_time = timestamp
            self.record_event(
                'SESSION_START',
                event_time,
                details={'people': num_people}
            )
            print(f"[SESSION START] Session {self.session_id}")

        if new_state == "SHAVING ACTIVE":
            if self.active_shave_start is None:
                self.active_shave_start = timestamp
                self.record_event(
                    'SHAVE_ACTIVE_START',
                    event_time,
                    details={'confidence': confidence}
                )
        else:
            if self.active_shave_start is not None:
                self.finalize_active_shave(timestamp)

        if new_state == "EMPTY" and self.session_id is not None:
            session_duration = None
            if self.session_start_time is not None:
                session_duration = float(timestamp - self.session_start_time)
            self.record_event(
                'SESSION_END',
                event_time,
                total_duration=self.total_shave_time,
                details={'session_duration': session_duration}
            )
            print(f"[SESSION END] Total active shave time: {self.total_shave_time:.1f}s")
            self.session_id = None
            self.session_start_time = None

        if new_state != previous_state:
            self.record_event(
                new_state,
                event_time,
                total_duration=self.total_shave_time,
                details={'people': num_people}
            )

        self.current_state = new_state

        return {
            'shaving': bool(is_shaving),
            'state': self.current_state,
            'confidence': float(confidence),
            'session_id': self.session_id,
            'total_shave_time': float(self.total_shave_time),
            'active_shavelog_time_taken': float(self.active_shavelog_time_taken),
            'people': int(num_people),
            'events': list(self.event_log)
        }

# ==========================================
# 3. MAIN SYSTEM (NO WEBSOCKET/ASYNC ISSUES)
# ==========================================
class ShaveDetectionSystem:
    def __init__(self):
        print("[INIT] Starting Shave Detection System...")
        self.detector = SimpleShaveDetector()
        self.model = None
        self.running = True
        
    def load_model(self):
        """Load YOLO model"""
        print("[MODEL] Loading YOLOv8-pose...")
        try:
            self.model = YOLO("yolov8n-pose.pt")
            print("[MODEL] Successfully loaded!")
            return True
        except Exception as e:
            print(f"[MODEL] Error: {e}")
            return False
    
    def draw_overlay(self, frame, data):
        """Draw information on frame"""
        h, w = frame.shape[:2]
        
        # Background panel
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (400, 180), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
        
        # State color
        colors = {
            "EMPTY": (128, 128, 128),
            "CUSTOMER SEATED": (0, 0, 255),
            "BARBER PRESENT": (0, 165, 255),
            "SHAVING ACTIVE": (0, 255, 0)
        }
        color = colors.get(data['state'], (255, 255, 255))
        
        # Draw text
        y = 40
        cv2.putText(frame, f"State: {data['state']}", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        y += 35
        
        cv2.putText(frame, f"People: {data['people']}", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y += 25
        
        cv2.putText(frame, f"Confidence: {data['confidence']:.1%}", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                   (0, 255, 0) if data['confidence'] > 0.6 else (0, 165, 255), 1)
        y += 25
        
        cv2.putText(frame, f"Shave Time: {data['total_shave_time']}s", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y += 25
        
        cv2.putText(frame, f"Session: {data['session_id'] or 'None'}", (20, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        
        # Recording indicator
        if data['shaving']:
            cv2.circle(frame, (w - 50, 50), 12, (0, 0, 255), -1)
            cv2.circle(frame, (w - 50, 50), 12, (0, 0, 255), 3)
            cv2.putText(frame, "RECORDING", (w - 140, 55), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Instructions
        cv2.putText(frame, "Q: Quit | S: Stats", (w - 200, h - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        return frame
    
    def run(self):
        """Main run loop"""
        print("\n" + "="*60)
        print("   BARBERSHOP SHAVE DETECTION SYSTEM")
        print("="*60)
        
        # Load model
        if not self.load_model():
            print("[ERROR] Cannot start without model")
            return
        
        # Open camera
        print("\n[CAMERA] Opening webcam...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[ERROR] Cannot open camera")
            return
        
        # Set camera properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        print("\n[READY] System running!")
        print("Press 'q' to quit, 's' for statistics")
        print("="*60 + "\n")
        
        frame_count = 0
        
        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    print("[WARN] Failed to read frame")
                    break
                
                frame_count += 1
                
                try:
                    # Run detection every frame
                    results = self.model(frame, verbose=False)
                    
                    # Extract keypoints
                    keypoints_list = []
                    if results and len(results) > 0 and results[0].keypoints is not None:
                        keypoints_list = results[0].keypoints.data.cpu().numpy()
                    
                    # Process detection
                    detection = self.detector.process_frame(keypoints_list, timestamp=time.time())
                    
                    # Draw skeleton if available
                    try:
                        annotated = results[0].plot()
                    except:
                        annotated = frame.copy()
                    
                    # Add overlay
                    annotated = self.draw_overlay(annotated, detection)
                    
                    # Show frame
                    cv2.imshow("Shave Detection System", annotated)
                
                except Exception as e:
                    # If detection fails, just show the frame and continue
                    print(f"[WARN] Detection error: {e}")
                    cv2.imshow("Shave Detection System", frame)
                
                # Handle keys
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n[SHUTDOWN] User requested quit...")
                    break
                elif key == ord('s'):
                    self.show_stats(detection)
        
        except KeyboardInterrupt:
            print("\n[INTERRUPT] Shutting down...")
        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            cap.release()
            cv2.destroyAllWindows()
            self.show_final_report()
    
    def show_stats(self, detection):
        """Show statistics"""
        print("\n" + "="*50)
        print("CURRENT STATISTICS")
        print("="*50)
        print(f"State: {detection['state']}")
        print(f"People detected: {detection['people']}")
        print(f"Confidence: {detection['confidence']:.1%}")
        print(f"Total shave time: {detection['total_shave_time']} seconds")
        print(f"Active shave segment time: {detection['active_shavelog_time_taken']:.1f} seconds")
        if detection['total_shave_time'] > 0:
            print(f"Shave time: {detection['total_shave_time']/60:.1f} minutes")
        print(f"Session ID: {detection['session_id']}")
        print("="*50)
    
    def show_final_report(self):
        """Show final report"""
        print("\n" + "="*60)
        print("FINAL REPORT")
        print("="*60)
        print(f"Total shave time: {self.detector.total_shave_time} seconds")
        print(f"Total shave time: {self.detector.total_shave_time/60:.1f} minutes")
        if self.detector.total_shave_time > 0:
            amount = 15.00 + max(0, (self.detector.total_shave_time/60 - 10)) * 2.00
            print(f"Estimated charge: ${amount:.2f}")
        print("="*60)
        print("\n[SHUTDOWN] System stopped")

# ==========================================
# MAIN ENTRY POINT
# ==========================================
if __name__ == "__main__":
    system = ShaveDetectionSystem()
    system.run()
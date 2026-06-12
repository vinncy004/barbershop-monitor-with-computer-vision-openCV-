# video_evidence/selective_recorder.py
import cv2
import sqlite3
from pathlib import Path
import threading
from queue import Queue
import time
from datetime import datetime, timedelta

class SelectiveVideoRecorder:
    """Record video only when needed for evidence"""
    
    def __init__(self, storage_path="./evidence", max_gb=100):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.max_storage_bytes = max_gb * 1024 * 1024 * 1024
        
        self.active_recordings = {}
        self.recording_lock = threading.Lock()
        self.cleanup_thread = None
        
    def start_recording_for_session(self, session_id, chair_id, camera_url):
        """Start recording when low confidence or dispute detected"""
        with self.recording_lock:
            if session_id not in self.active_recordings:
                output_path = self.storage_path / f"session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                
                recorder = SessionRecorder(
                    session_id=session_id,
                    chair_id=chair_id,
                    camera_url=camera_url,
                    output_path=output_path
                )
                recorder.start()
                self.active_recordings[session_id] = recorder
                
                print(f"[RECORDER] Started recording for session {session_id}")
                return True
        return False
    
    def stop_recording_for_session(self, session_id, reason="normal"):
        """Stop recording and save evidence"""
        with self.recording_lock:
            if session_id in self.active_recordings:
                recorder = self.active_recordings[session_id]
                recorder.stop()
                
                # Check if we should keep this recording
                if reason == "dispute" or self.should_keep_recording(session_id):
                    recorder.finalize()
                    print(f"[RECORDER] Saved evidence for session {session_id}")
                else:
                    recorder.delete()
                    print(f"[RECORDER] Discarded recording for session {session_id}")
                
                del self.active_recordings[session_id]
    
    def should_keep_recording(self, session_id):
        """Determine if recording should be kept as evidence"""
        with sqlite3.connect("barbershop_innovation.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT confidence_score, verification_status 
                FROM camera_sessions 
                WHERE session_id = ?
            """, (session_id,))
            result = cursor.fetchone()
            
            if not result:
                return False
            
            confidence, status = result
            
            # Keep if low confidence or disputed
            return confidence < 0.5 or status == 'Disputed'
    
    def start_auto_cleanup(self):
        """Start automatic cleanup of old recordings"""
        def cleanup_loop():
            while True:
                self.cleanup_old_recordings()
                time.sleep(3600)  # Check every hour
        
        self.cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def cleanup_old_recordings(self):
        """Remove recordings older than 30 days or exceeding storage limit"""
        cutoff_date = datetime.now() - timedelta(days=30)
        total_size = 0
        
        # Calculate total size and remove old files
        for video_file in self.storage_path.glob("session_*.mp4"):
            file_age = datetime.fromtimestamp(video_file.stat().st_mtime)
            
            if file_age < cutoff_date:
                video_file.unlink()
                print(f"[CLEANUP] Removed old video: {video_file.name}")
            else:
                total_size += video_file.stat().st_size
        
        # Remove oldest files if over limit
        if total_size > self.max_storage_bytes:
            files = sorted(self.storage_path.glob("session_*.mp4"), 
                          key=lambda x: x.stat().st_mtime)
            
            for file in files:
                if total_size <= self.max_storage_bytes * 0.9:  # 90% target
                    break
                
                total_size -= file.stat().st_size
                file.unlink()
                print(f"[CLEANUP] Removed old video (storage limit): {file.name}")

class SessionRecorder:
    """Record video for a specific session"""
    
    def __init__(self, session_id, chair_id, camera_url, output_path, 
                 buffer_seconds=30):
        self.session_id = session_id
        self.chair_id = chair_id
        self.camera_url = camera_url
        self.output_path = output_path
        self.buffer_seconds = buffer_seconds  # Keep pre-event buffer
        
        self.ring_buffer = deque(maxlen=int(buffer_seconds * 30))  # 30 FPS
        self.writer = None
        self.recording = False
        self.frame_count = 0
        
    def start(self):
        """Start the recording thread"""
        self.recording = True
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()
    
    def _record_loop(self):
        """Main recording loop with ring buffer"""
        cap = cv2.VideoCapture(self.camera_url)
        
        # Set up video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = 30
        frame_size = (1280, 720)
        self.writer = cv2.VideoWriter(str(self.output_path), fourcc, fps, frame_size)
        
        while self.recording:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Add to ring buffer (pre-event)
            self.ring_buffer.append(frame.copy())
            
            # Write to file
            self.writer.write(frame)
            self.frame_count += 1
            
            # Add timestamp overlay
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            cv2.putText(frame, timestamp, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        cap.release()
    
    def stop(self):
        """Stop recording"""
        self.recording = False
        if self.thread:
            self.thread.join(timeout=5)
        if self.writer:
            self.writer.release()
    
    def finalize(self):
        """Save recording with metadata"""
        # Add metadata file
        metadata = {
            'session_id': self.session_id,
            'chair_id': self.chair_id,
            'start_time': datetime.now().isoformat(),
            'frame_count': self.frame_count,
            'duration_seconds': self.frame_count / 30
        }
        
        metadata_path = self.output_path.with_suffix('.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def delete(self):
        """Delete recording (no evidence needed)"""
        if self.output_path.exists():
            self.output_path.unlink()
        
        metadata_path = self.output_path.with_suffix('.json')
        if metadata_path.exists():
            metadata_path.unlink()
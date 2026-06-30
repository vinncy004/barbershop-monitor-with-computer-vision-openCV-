# multi_camera/multi_chair_manager.py
import cv2
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import asyncio
import websockets
from collections import deque
import numpy as np

class MultiChairManager:
    """Manage multiple camera feeds with temporal synchronization"""
    
    def __init__(self, num_chairs=4):
        self.chairs = {}
        self.sync_lock = threading.Lock()
        self.global_timestamp = None
        self.sync_threshold_ms = 50  # Max allowed desync in milliseconds
        self.executor = ThreadPoolExecutor(max_workers=num_chairs)
        
        # Camera configurations
        # Default camera configurations — update IP/port/credentials as needed.
        # For Hikvision mainstream the common RTSP path for channel 1 mainstream is:
        # rtsp://<user>:<pass>@<ip>:<port>/Streaming/Channels/101
        self.camera_configs = {
            1: {"url": "rtsp://admin:AmsNat_2023@192.168.0.200:544/Streaming/Channels/101", "roi": (100, 100, 540, 380)},
            2: {"url": "rtsp://admin:AmsNat_2023@192.168.0.200:544/Streaming/Channels/101", "roi": (600, 100, 1040, 380)},
            3: {"url": "rtsp://admin:AmsNat_2023@192.168.0.200:544/Streaming/Channels/101", "roi": (100, 420, 540, 700)},
            4: {"url": "rtsp://admin:AmsNat_2023@192.168.0.200:544/Streaming/Channels/101", "roi": (600, 420, 1040, 700)}
        }
        
        # PTP time synchronization
        self.ptp_master = "192.168.1.100"  # NTP/PTP server
        
    def initialize_chairs(self):
        """Initialize all chair detection systems"""
        for chair_id, config in self.camera_configs.items():
            chair = OptimizedChairDetector(
                chair_id=chair_id,
                camera_url=config["url"],
                roi=config["roi"]
            )
            self.chairs[chair_id] = chair
            chair.start()
        
        # Start synchronization thread
        self.start_sync_thread()
    
    def start_sync_thread(self):
        """Thread for maintaining camera synchronization"""
        def sync_loop():
            while True:
                self.synchronize_timestamps()
                time.sleep(1)  # Sync every second
        
        sync_thread = threading.Thread(target=sync_loop, daemon=True)
        sync_thread.start()
    
    def synchronize_timestamps(self):
        """Synchronize timestamps across all cameras"""
        with self.sync_lock:
            # Get reference timestamp from master clock
            master_time = self.get_ptp_time()
            
            for chair_id, chair in self.chairs.items():
                offset = chair.get_time_offset()
                if abs(offset) > self.sync_threshold_ms:
                    chair.adjust_timestamp(master_time)
                    print(f"[SYNC] Chair {chair_id} adjusted by {offset}ms")
            
            self.global_timestamp = master_time
    
    def get_ptp_time(self):
        """Get Precision Time Protocol timestamp"""
        import socket
        import struct
        
        # Simplified PTP client
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        
        # Send PTP sync request
        sock.sendto(b'\x01\x02\x03\x04', (self.ptp_master, 319))
        
        try:
            data, _ = sock.recvfrom(1024)
            timestamp = struct.unpack('!Q', data[:8])[0]
            return timestamp / 1e9  # Convert to seconds
        except:
            return time.time()  # Fallback to system time
    
    def process_all_chairs_parallel(self):
        """Process all chairs in parallel"""
        futures = []
        
        for chair_id, chair in self.chairs.items():
            future = self.executor.submit(chair.process_frame)
            futures.append((chair_id, future))
        
        results = {}
        for chair_id, future in futures:
            try:
                results[chair_id] = future.result(timeout=0.033)  # ~30 FPS
            except Exception as e:
                print(f"[ERROR] Chair {chair_id}: {e}")
                results[chair_id] = None
        
        return results
    
    def get_unified_dashboard(self):
        """Combine all chair views into single dashboard"""
        dashboard_width = 1920
        dashboard_height = 1080
        dashboard = np.zeros((dashboard_height, dashboard_width, 3), dtype=np.uint8)
        
        # Layout: 2x2 grid for 4 chairs
        positions = {
            1: (0, 0, dashboard_width//2, dashboard_height//2),
            2: (dashboard_width//2, 0, dashboard_width, dashboard_height//2),
            3: (0, dashboard_height//2, dashboard_width//2, dashboard_height),
            4: (dashboard_width//2, dashboard_height//2, dashboard_width, dashboard_height)
        }
        
        for chair_id, chair in self.chairs.items():
            if chair.current_frame is not None:
                x1, y1, x2, y2 = positions[chair_id]
                resized = cv2.resize(chair.current_frame, (x2-x1, y2-y1))
                dashboard[y1:y2, x1:x2] = resized
                
                # Add chair label
                cv2.putText(dashboard, f"Chair {chair_id}", 
                           (x1+10, y1+30), cv2.FONT_HERSHEY_SIMPLEX, 
                           1, (255, 255, 255), 2)
                
                # Add status overlay
                status_color = {
                    "EMPTY": (100, 100, 100),
                    "OCCUPIED": (0, 0, 255),
                    "SHAVING": (0, 255, 0)
                }.get(chair.current_state, (255, 255, 255))
                
                cv2.rectangle(dashboard, (x1, y2-40), (x2, y2), status_color, -1)
                cv2.putText(dashboard, chair.current_state, 
                           (x1+10, y2-10), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.6, (255, 255, 255), 1)
        
        return dashboard

class OptimizedChairDetector:
    """Individual chair detector with frame buffer"""
    
    def __init__(self, chair_id, camera_url, roi=None):
        self.chair_id = chair_id
        self.camera_url = camera_url
        self.roi = roi
        self.current_frame = None
        self.current_state = "EMPTY"
        self.frame_buffer = deque(maxlen=30)
        self.capture_thread = None
        self.running = False
        
        # Timestamp synchronization
        self.time_offset = 0
        self.last_sync_time = time.time()
        
    def start(self):
        """Start capture thread"""
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
    
    def _capture_loop(self):
        """Continuous capture loop"""
        cap = cv2.VideoCapture(self.camera_url)
        
        # Set buffer size to reduce latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        while self.running:
            ret, frame = cap.read()
            if ret:
                if self.roi:
                    x1, y1, x2, y2 = self.roi
                    frame = frame[y1:y2, x1:x2]
                
                # Apply timestamp
                frame_timestamp = time.time() + self.time_offset
                self.frame_buffer.append((frame_timestamp, frame))
                self.current_frame = frame
            else:
                print(f"[WARN] Chair {self.chair_id}: Failed to read frame")
                time.sleep(0.001)
        
        cap.release()
    
    def process_frame(self):
        """Process latest frame with state detection"""
        if not self.frame_buffer:
            return None
        
        timestamp, frame = self.frame_buffer[-1]
        
        # Run detection (simplified for example)
        # In production, call optimized detector here
        
        return {
            'chair_id': self.chair_id,
            'timestamp': timestamp,
            'frame': frame,
            'state': self.current_state
        }
    
    def get_time_offset(self):
        """Get current time offset in milliseconds"""
        return (time.time() - self.last_sync_time) * 1000
    
    def adjust_timestamp(self, master_time):
        """Adjust frame timestamps"""
        self.time_offset = master_time - time.time()
        self.last_sync_time = time.time()


def verify_camera_url(url, timeout=5):
    """Try to open an RTSP stream and read a frame within `timeout` seconds.

    Returns (True, frame_shape) on success, (False, None) on failure.
    """
    cap = cv2.VideoCapture(url)
    start = time.time()
    while time.time() - start < timeout:
        ret, frame = cap.read()
        if ret and frame is not None:
            shape = frame.shape
            cap.release()
            return True, shape
        time.sleep(0.2)
    cap.release()
    return False, None


if __name__ == "__main__":
    # Quick CLI verification of configured camera URLs
    mgr = MultiChairManager(num_chairs=4)
    for cid, cfg in mgr.camera_configs.items():
        url = cfg.get('url')
        if not url:
            print(f"Chair {cid}: no URL configured")
            continue
        print(f"Verifying Chair {cid}: {url}")
        ok, shape = verify_camera_url(url, timeout=8)
        if ok:
            print(f"[OK] Chair {cid} stream opened, frame size: {shape}")
        else:
            print(f"[FAIL] Chair {cid} stream not reachable")
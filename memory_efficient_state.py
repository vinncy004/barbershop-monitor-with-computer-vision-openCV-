# edge_deployment/memory_efficient_state.py
import sqlite3
from collections import deque
import json
import pickle
from threading import Lock

class MemoryEfficientStateMachine:
    """Reduced memory footprint for edge devices"""
    
    def __init__(self, chair_id, memory_limit_mb=256):
        self.chair_id = chair_id
        self.memory_limit = memory_limit_mb * 1024 * 1024  # Convert to bytes
        
        # Use smaller buffers
        self.wrist_history = deque(maxlen=15)  # Reduced from 30
        self.confidence_buffer = deque(maxlen=10)
        
        # Batch database writes
        self.event_buffer = []
        self.batch_size = 10
        self.buffer_lock = Lock()
        
        # Memory monitoring
        self.current_memory_usage = 0
        
    def batch_write_events(self):
        """Batch database writes to reduce I/O"""
        with self.buffer_lock:
            if len(self.event_buffer) >= self.batch_size:
                with sqlite3.connect("barbershop_innovation.db") as conn:
                    cursor = conn.cursor()
                    cursor.executemany("""
                        INSERT INTO shave_events 
                        (session_id, chair_id, event_timestamp, event_type, 
                         proximity_distance, confidence)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, self.event_buffer)
                    conn.commit()
                self.event_buffer.clear()
    
    def serialize_state(self):
        """Efficient state serialization for checkpointing"""
        state = {
            'chair_id': self.chair_id,
            'current_state': self.current_state,
            'active_session_start': self.active_session_start.isoformat() if self.active_session_start else None,
            'wrist_history': list(self.wrist_history),
            'confidence_buffer': list(self.confidence_buffer)
        }
        
        # Use msgpack for smaller serialization
        import msgpack
        return msgpack.packb(state)
    
    def restore_state(self, serialized_data):
        """Restore state from checkpoint"""
        import msgpack
        state = msgpack.unpackb(serialized_data)
        self.current_state = state['current_state']
        self.wrist_history.extend(state['wrist_history'])
        self.confidence_buffer.extend(state['confidence_buffer'])
"""
Utility module to sync shave events from shavelog.db to Django dashboard.

This can be imported by shavelog.py to automatically sync events
to the dashboard database as they're created.

Usage in shavelog.py:
    from dashboard_sync import sync_event_to_dashboard
    
    # When creating an event in shavelog:
    storage.store_event(session_id, event_type, timestamp, active_duration, total_duration, details)
    sync_event_to_dashboard(event_type, timestamp, total_duration, details, user_id=1)
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime


def get_django_db_path():
    """Get path to Django database"""
    return Path(__file__).parent / "dashboard_ui" / "db.sqlite3"


def sync_event_to_dashboard(event_type, timestamp, duration_seconds=0.0, 
                            details=None, user_id=1):
    """
    Sync a single event to the Django dashboard database.
    
    Args:
        event_type: Type of event (e.g., 'SESSION_START', 'CUSTOMER SEATED')
        timestamp: Event timestamp (datetime or ISO string)
        duration_seconds: Duration of the event in seconds (default: 0.0)
        details: Additional event details (dict, optional)
        user_id: Django user ID to associate with the event (default: 1)
    
    Returns:
        bool: True if sync succeeded, False otherwise
    """
    try:
        django_db = get_django_db_path()
        
        if not django_db.exists():
            print(f"[DASHBOARD SYNC] Warning: Django database not found at {django_db}")
            return False
        
        # Parse timestamp
        if isinstance(timestamp, str):
            if 'T' in timestamp:
                ts = datetime.fromisoformat(timestamp)
            else:
                ts = datetime.fromisoformat(timestamp)
        else:
            ts = timestamp
        
        # Ensure details is JSON serializable
        if details is not None:
            details_json = json.dumps(_serialize_for_json(details))
        else:
            details_json = None
        
        # Connect and insert
        conn = sqlite3.connect(str(django_db))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO dashboard_app_reportevent 
            (user_id, timestamp, event_type, duration_seconds, details)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            ts.isoformat(),
            event_type,
            float(duration_seconds) if duration_seconds else 0.0,
            details_json
        ))
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"[DASHBOARD SYNC] Error syncing event: {e}")
        return False


def _serialize_for_json(obj):
    """Recursively convert non-JSON-serializable objects to JSON-safe types"""
    import numpy as np
    
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    elif isinstance(obj, (float, int, str, bool, type(None))):
        return obj
    else:
        return str(obj)


# Example usage (for testing):
if __name__ == "__main__":
    # Test sync
    from datetime import datetime
    result = sync_event_to_dashboard(
        event_type="TEST_EVENT",
        timestamp=datetime.now(),
        duration_seconds=5.5,
        details={"note": "This is a test event"},
        user_id=1
    )
    print(f"Sync result: {result}")

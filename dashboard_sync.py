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

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add the Django project to sys.path so this standalone module can use ORM
PROJECT_ROOT = Path(__file__).resolve().parent / "dashboard_ui"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_ui.settings")

import django
from django.utils import timezone

django.setup()

from dashboard_app.models import ReportEvent, User


def sync_event_to_dashboard(event_type, timestamp, duration_seconds=0.0, details=None, user_id=1):
    """Sync a single event into the Django dashboard database."""
    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        if timestamp.tzinfo is None:
            timestamp = timezone.make_aware(timestamp)

        details = _serialize_for_json(details) if details is not None else None

        user = User.objects.filter(id=user_id).first()
        if not user:
            print(f"[DASHBOARD SYNC] User with ID {user_id} not found")
            return False

        ReportEvent.objects.create(
            user=user,
            timestamp=timestamp,
            event_type=event_type,
            duration_seconds=float(duration_seconds or 0.0),
            details=details,
        )

        return True
    except Exception as e:
        print(f"[DASHBOARD SYNC] Error syncing event: {e}")
        return False


def _serialize_for_json(obj):
    """Recursively convert non-JSON-serializable objects to JSON-safe types."""
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


if __name__ == "__main__":
    from datetime import datetime
    result = sync_event_to_dashboard(
        event_type="TEST_EVENT",
        timestamp=datetime.now(),
        duration_seconds=5.5,
        details={"note": "This is a test event"},
        user_id=1,
    )
    print(f"Sync result: {result}")

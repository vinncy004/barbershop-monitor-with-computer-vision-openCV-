#!/usr/bin/env python
"""
Sync shavelog events to Django dashboard database.
Run this script to transfer all shave detection events from shavelog.db
to the Django dashboard's ReportEvent table.
"""

import json
import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

# Add the Django project to sys.path so we can use ORM from this script
PROJECT_ROOT = Path(__file__).resolve().parent / "dashboard_ui"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_ui.settings")

import django
from django.utils import timezone

django.setup()

from dashboard_app.models import ReportEvent, User

# Paths
SHAVELOG_DB = Path(__file__).parent / "shavelog.db"

# Default user ID (first user in Django)
DEFAULT_USER_ID = 1


def sync_shavelog_to_dashboard():
    """Sync all events from shavelog.db into the Django dashboard database."""

    if not SHAVELOG_DB.exists():
        print(f"ERROR: shavelog.db not found at {SHAVELOG_DB}")
        return False

    user = User.objects.filter(id=DEFAULT_USER_ID).first()
    if not user:
        print(f"ERROR: Django user with ID {DEFAULT_USER_ID} not found")
        return False

    shavelog_conn = None
    try:
        shavelog_conn = sqlite3.connect(str(SHAVELOG_DB))
        shavelog_conn.row_factory = sqlite3.Row
        shavelog_cur = shavelog_conn.cursor()

        shavelog_cur.execute("""
            SELECT id, session_id, event_type, timestamp,
                   active_duration, total_duration, details
            FROM events
            ORDER BY id
        """)
        events = shavelog_cur.fetchall()

        print(f"Found {len(events)} events in shavelog.db")

        existing_count = ReportEvent.objects.filter(user=user).count()
        print(f"Dashboard already has {existing_count} events")

        if existing_count > 0:
            print("Skipping sync (events already exist)")
            return True

        synced_count = 0
        for event in events:
            try:
                timestamp_str = event["timestamp"]
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str)
                else:
                    timestamp = datetime.now()

                if timestamp.tzinfo is None:
                    timestamp = timezone.make_aware(timestamp)

                details = None
                if event["details"]:
                    try:
                        details = json.loads(event["details"])
                    except (json.JSONDecodeError, TypeError):
                        details = {"raw": str(event["details"])}

                ReportEvent.objects.create(
                    user=user,
                    timestamp=timestamp,
                    event_type=event["event_type"],
                    duration_seconds=float(event["total_duration"] or 0.0),
                    details=details,
                )
                synced_count += 1
            except Exception as e:
                print(f"  Error syncing event {event['id']}: {e}")
                continue

        print(f"\n[SUCCESS] Synced {synced_count} events to dashboard!")
        print(f"   User ID: {DEFAULT_USER_ID}")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if shavelog_conn is not None:
            shavelog_conn.close()


if __name__ == "__main__":
    success = sync_shavelog_to_dashboard()
    sys.exit(0 if success else 1)

#!/usr/bin/env python
"""
Sync shavelog events to Django dashboard database.
Run this script to transfer all shave detection events from shavelog.db
to the Django dashboard's ReportEvent table.
"""

import sqlite3
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Paths
SHAVELOG_DB = Path(__file__).parent / "shavelog.db"
DJANGO_DB = Path(__file__).parent / "dashboard_ui" / "db.sqlite3"

# Default user ID (first user in Django)
DEFAULT_USER_ID = 1


def sync_shavelog_to_dashboard():
    """Sync all events from shavelog.db to Django dashboard database"""
    
    if not SHAVELOG_DB.exists():
        print(f"ERROR: shavelog.db not found at {SHAVELOG_DB}")
        return False
    
    if not DJANGO_DB.exists():
        print(f"ERROR: Django db.sqlite3 not found at {DJANGO_DB}")
        return False
    
    try:
        # Open shavelog database
        shavelog_conn = sqlite3.connect(str(SHAVELOG_DB))
        shavelog_conn.row_factory = sqlite3.Row
        shavelog_cur = shavelog_conn.cursor()
        
        # Open Django database
        django_conn = sqlite3.connect(str(DJANGO_DB))
        django_cur = django_conn.cursor()
        
        # Get all events from shavelog
        shavelog_cur.execute("""
            SELECT id, session_id, event_type, timestamp, 
                   active_duration, total_duration, details
            FROM events
            ORDER BY id
        """)
        events = shavelog_cur.fetchall()
        
        print(f"Found {len(events)} events in shavelog.db")
        
        # Check how many are already synced
        django_cur.execute("SELECT COUNT(*) FROM dashboard_app_reportevent")
        existing_count = django_cur.fetchone()[0]
        print(f"Dashboard already has {existing_count} events")
        
        if existing_count > 0:
            print("Skipping sync (events already exist)")
            return True
        
        # Sync each event
        synced_count = 0
        for event in events:
            try:
                # Parse timestamp
                timestamp_str = event['timestamp']
                if timestamp_str:
                    # Convert ISO format to datetime
                    if 'T' in timestamp_str:
                        timestamp = datetime.fromisoformat(timestamp_str)
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str)
                else:
                    timestamp = datetime.now()
                
                # Parse details JSON
                details = None
                if event['details']:
                    try:
                        details = json.loads(event['details'])
                    except (json.JSONDecodeError, TypeError):
                        details = {'raw': str(event['details'])}
                
                # Insert into Django dashboard
                django_cur.execute("""
                    INSERT INTO dashboard_app_reportevent 
                    (user_id, timestamp, event_type, duration_seconds, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    DEFAULT_USER_ID,
                    timestamp,
                    event['event_type'],
                    event['total_duration'] if event['total_duration'] is not None else 0.0,
                    json.dumps(details) if details else None
                ))
                
                synced_count += 1
                
            except Exception as e:
                print(f"  Error syncing event {event['id']}: {e}")
                continue
        
        # Commit changes
        django_conn.commit()
        
        print(f"\n[SUCCESS] Synced {synced_count} events to dashboard!")
        print(f"   User ID: {DEFAULT_USER_ID}")
        print(f"   Database: {DJANGO_DB}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            shavelog_conn.close()
        except:
            pass
        try:
            django_conn.close()
        except:
            pass


if __name__ == "__main__":
    success = sync_shavelog_to_dashboard()
    sys.exit(0 if success else 1)

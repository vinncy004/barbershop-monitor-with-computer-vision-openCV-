"""
Django management command to sync events from shavelog.db to the dashboard.

Usage:
    python manage.py sync_shavelog
    python manage.py sync_shavelog --user-id 1
    python manage.py sync_shavelog --user-email petervinny0@gmail.com
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard_app.models import ReportEvent, User


class Command(BaseCommand):
    help = "Sync shave events from shavelog.db to the dashboard database"

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID to associate events with (default: 1)',
        )
        parser.add_argument(
            '--user-email',
            type=str,
            help='User email to associate events with',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sync even if events already exist',
        )

    def handle(self, *args, **options):
        # Find user
        user = None
        if options['user_email']:
            try:
                user = User.objects.get(email=options['user_email'])
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"User with email {options['user_email']} not found")
                )
                return
        elif options['user_id']:
            try:
                user = User.objects.get(id=options['user_id'])
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"User with ID {options['user_id']} not found")
                )
                return
        else:
            # Default to first user
            user = User.objects.first()
            if not user:
                self.stdout.write(
                    self.style.ERROR("No users found in database")
                )
                return

        self.stdout.write(f"Using user: {user.email} (ID: {user.id})")

        # Check if events already exist
        existing_count = ReportEvent.objects.filter(user=user).count()
        if existing_count > 0 and not options['force']:
            self.stdout.write(
                self.style.WARNING(
                    f"User already has {existing_count} events. Use --force to re-sync."
                )
            )
            return

        if options['force'] and existing_count > 0:
            self.stdout.write(f"Deleting {existing_count} existing events...")
            ReportEvent.objects.filter(user=user).delete()

        # Sync from shavelog.db
        shavelog_db = Path(__file__).resolve().parent.parent.parent.parent.parent / "shavelog.db"
        
        if not shavelog_db.exists():
            self.stdout.write(
                self.style.ERROR(f"shavelog.db not found at {shavelog_db}")
            )
            return

        try:
            conn = sqlite3.connect(str(shavelog_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, session_id, event_type, timestamp, 
                       active_duration, total_duration, details
                FROM events
                ORDER BY id
            """)
            events = cursor.fetchall()

            self.stdout.write(f"Found {len(events)} events in shavelog.db")

            synced_count = 0
            errors = 0

            for event in events:
                try:
                    # Parse timestamp
                    timestamp_str = event['timestamp']
                    if timestamp_str:
                        if 'T' in timestamp_str:
                            timestamp = datetime.fromisoformat(timestamp_str)
                        else:
                            timestamp = datetime.fromisoformat(timestamp_str)
                        # Convert to timezone-aware
                        if timestamp.tzinfo is None:
                            timestamp = timezone.make_aware(timestamp)
                    else:
                        timestamp = timezone.now()

                    # Parse details
                    details = None
                    if event['details']:
                        try:
                            details = json.loads(event['details'])
                        except (json.JSONDecodeError, TypeError):
                            details = {'raw': str(event['details'])}

                    # Create event
                    ReportEvent.objects.create(
                        user=user,
                        timestamp=timestamp,
                        event_type=event['event_type'],
                        duration_seconds=float(event['total_duration'] or 0.0),
                        details=details
                    )

                    synced_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error syncing event {event['id']}: {e}")
                    )
                    errors += 1
                    continue

            conn.close()

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully synced {synced_count} events!"
                )
            )
            if errors:
                self.stdout.write(
                    self.style.WARNING(f"  {errors} events had errors")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            import traceback
            traceback.print_exc()

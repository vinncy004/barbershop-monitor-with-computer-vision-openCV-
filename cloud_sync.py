# cloud_sync/hybrid_sync.py
import sqlite3
import boto3
from google.cloud import storage
import azure.storage.blob
import json
from datetime import datetime, timedelta
import threading
import time
import gzip
from pathlib import Path

class CloudSyncManager:
    """Hybrid cloud sync with offline-first architecture"""
    
    def __init__(self, cloud_provider="aws", sync_interval=300):
        self.cloud_provider = cloud_provider
        self.sync_interval = sync_interval
        self.sync_queue = []
        self.sync_lock = threading.Lock()
        self.last_sync = datetime.now()
        
        # Initialize cloud clients
        self.clients = self._init_cloud_clients()
        
        # Local cache directory
        self.cache_dir = Path("./cloud_cache")
        self.cache_dir.mkdir(exist_ok=True)
        
    def _init_cloud_clients(self):
        """Initialize cloud storage clients"""
        clients = {}
        
        if self.cloud_provider == "aws":
            clients['s3'] = boto3.client(
                's3',
                aws_access_key_id='YOUR_ACCESS_KEY',
                aws_secret_access_key='YOUR_SECRET_KEY',
                region_name='us-east-1'
            )
            clients['bucket'] = 'barbershop-data'
            
        elif self.cloud_provider == "gcp":
            clients['storage'] = storage.Client.from_service_account_json(
                'service-account-key.json'
            )
            clients['bucket'] = clients['storage'].bucket('barbershop-data')
            
        elif self.cloud_provider == "azure":
            clients['blob'] = azure.storage.blob.BlobServiceClient.from_connection_string(
                'YOUR_CONNECTION_STRING'
            )
            clients['container'] = clients['blob'].get_container_client('barbershop-data')
        
        return clients
    
    def sync_session_data(self, session_id):
        """Sync session data to cloud"""
        with sqlite3.connect("barbershop_innovation.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get session data
            cursor.execute("""
                SELECT * FROM camera_sessions WHERE session_id = ?
            """, (session_id,))
            session = cursor.fetchone()
            
            # Get associated events
            cursor.execute("""
                SELECT * FROM shave_events WHERE session_id = ?
            """, (session_id,))
            events = cursor.fetchall()
        
        # Prepare data package
        data_package = {
            'session': dict(session),
            'events': [dict(event) for event in events],
            'sync_timestamp': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        # Compress data
        json_str = json.dumps(data_package, default=str)
        compressed = gzip.compress(json_str.encode())
        
        # Upload to cloud
        blob_name = f"sessions/{session_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
        
        if self.cloud_provider == "aws":
            self.clients['s3'].put_object(
                Bucket=self.clients['bucket'],
                Key=blob_name,
                Body=compressed
            )
        elif self.cloud_provider == "gcp":
            blob = self.clients['bucket'].blob(blob_name)
            blob.upload_from_string(compressed)
        elif self.cloud_provider == "azure":
            self.clients['container'].upload_blob(blob_name, compressed)
        
        # Update sync status in local DB
        with sqlite3.connect("barbershop_innovation.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE camera_sessions 
                SET verification_status = 'Cloud Synced'
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
        
        print(f"[CLOUD SYNC] Session {session_id} synced to {self.cloud_provider}")
        return True
    
    def sync_all_pending(self):
        """Sync all unsynced sessions"""
        with sqlite3.connect("barbershop_innovation.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id FROM camera_sessions 
                WHERE verification_status NOT IN ('Cloud Synced', 'Syncing')
                AND end_time IS NOT NULL
            """)
            pending = cursor.fetchall()
        
        for (session_id,) in pending:
            # Update status to syncing
            with sqlite3.connect("barbershop_innovation.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE camera_sessions 
                    SET verification_status = 'Syncing'
                    WHERE session_id = ?
                """, (session_id,))
                conn.commit()
            
            # Attempt sync with retry
            retries = 3
            for attempt in range(retries):
                try:
                    self.sync_session_data(session_id)
                    break
                except Exception as e:
                    print(f"[SYNC ERROR] Attempt {attempt+1}: {e}")
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        self.last_sync = datetime.now()
    
    def start_auto_sync(self):
        """Start automatic sync thread"""
        def sync_loop():
            while True:
                time.sleep(self.sync_interval)
                self.sync_all_pending()
        
        sync_thread = threading.Thread(target=sync_loop, daemon=True)
        sync_thread.start()
    
    def download_session(self, session_id, local_path):
        """Download session from cloud for audit"""
        blob_pattern = f"sessions/{session_id}/*.json.gz"
        
        # Find latest blob
        if self.cloud_provider == "aws":
            response = self.clients['s3'].list_objects_v2(
                Bucket=self.clients['bucket'],
                Prefix=f"sessions/{session_id}/"
            )
            
            latest = max(response.get('Contents', []), 
                        key=lambda x: x['LastModified'])
            
            # Download and decompress
            compressed = self.clients['s3'].get_object(
                Bucket=self.clients['bucket'],
                Key=latest['Key']
            )['Body'].read()
            
        elif self.cloud_provider == "gcp":
            blobs = list(self.clients['bucket'].list_blobs(prefix=f"sessions/{session_id}/"))
            latest = max(blobs, key=lambda x: x.updated)
            compressed = latest.download_as_string()
        
        # Decompress and save
        data = gzip.decompress(compressed)
        session_data = json.loads(data)
        
        with open(local_path, 'w') as f:
            json.dump(session_data, f, indent=2, default=str)
        
        return session_data
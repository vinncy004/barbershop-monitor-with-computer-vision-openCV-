# mobile_dashboard/websocket_server.py
import asyncio
import websockets
import json
from datetime import datetime
import sqlite3
from typing import Set
import threading

class DashboardServer:
    """WebSocket server for real-time mobile dashboard"""
    
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.alert_callbacks = []
        
    async def register(self, websocket):
        """Register new client connection"""
        self.connected_clients.add(websocket)
        print(f"[DASHBOARD] Client connected: {websocket.remote_address}")
        
        # Send initial state
        await self.send_initial_state(websocket)
        
        try:
            await websocket.wait_closed()
        finally:
            self.connected_clients.remove(websocket)
    
    async def send_initial_state(self, websocket):
        """Send current system state to new client"""
        with sqlite3.connect("barbershop_innovation.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get today's statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_sessions,
                    SUM(total_shave_duration_seconds) as total_shave_time,
                    AVG(confidence_score) as avg_confidence
                FROM camera_sessions
                WHERE DATE(start_time) = DATE('now')
            """)
            stats = cursor.fetchone()
            
            # Get active sessions
            cursor.execute("""
                SELECT session_id, chair_id, start_time 
                FROM camera_sessions 
                WHERE end_time IS NULL
            """)
            active = cursor.fetchall()
        
        initial_data = {
            'type': 'initial_state',
            'data': {
                'stats': dict(stats),
                'active_sessions': [dict(s) for s in active],
                'server_time': datetime.now().isoformat()
            }
        }
        
        await websocket.send(json.dumps(initial_data))
    
    async def broadcast_alert(self, alert_type, data):
        """Broadcast alert to all connected clients"""
        if not self.connected_clients:
            return
        
        message = {
            'type': 'alert',
            'alert_type': alert_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        
        # Trigger callbacks for external notifications
        for callback in self.alert_callbacks:
            callback(alert_type, data)
        
        # Send to all connected clients
        await asyncio.gather(
            *[client.send(json.dumps(message)) for client in self.connected_clients],
            return_exceptions=True
        )
    
    async def broadcast_state_update(self, chair_id, state_data):
        """Broadcast chair state update"""
        message = {
            'type': 'state_update',
            'chair_id': chair_id,
            'data': state_data,
            'timestamp': datetime.now().isoformat()
        }
        
        await asyncio.gather(
            *[client.send(json.dumps(message)) for client in self.connected_clients],
            return_exceptions=True
        )
    
    async def start_server(self):
        """Start WebSocket server"""
        async with websockets.serve(self.register, self.host, self.port):
            print(f"[DASHBOARD] Server running on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever

# Alert notification handlers
class AlertManager:
    """Manage real-time alerts to managers"""
    
    def __init__(self):
        self.sms_gateway = "your_sms_gateway_api"
        self.push_notification_key = "your_fcm_key"
        
    def send_sms_alert(self, phone_number, message):
        """Send SMS alert for critical events"""
        # Example using Twilio
        from twilio.rest import Client
        
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=message,
            from_='+1234567890',
            to=phone_number
        )
    
    def send_push_notification(self, device_token, title, message):
        """Send push notification via Firebase"""
        import firebase_admin
        from firebase_admin import messaging
        
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        notification = messaging.Notification(
            title=title,
            body=message
        )
        
        message = messaging.Message(
            notification=notification,
            token=device_token
        )
        
        messaging.send(message)
    
    def check_alert_conditions(self, state_machine):
        """Check if any alert conditions are met"""
        alerts = []
        
        # Long session alert (> 30 minutes of shaving)
        if state_machine.debug_data.get('total_shave_duration', 0) > 1800:
            alerts.append({
                'type': 'long_session',
                'severity': 'warning',
                'message': f"Chair {state_machine.chair_id} has been shaving for >30 minutes"
            })
        
        # Low confidence alert (possible detection issue)
        if state_machine.debug_data.get('confidence', 1) < 0.4:
            alerts.append({
                'type': 'low_confidence',
                'severity': 'info',
                'message': f"Chair {state_machine.chair_id} has low detection confidence"
            })
        
        # Empty chair during busy hours
        if (state_machine.current_state == "EMPTY" and 
            self.is_busy_hour() and 
            state_machine.chair_id in self.busy_chairs):
            alerts.append({
                'type': 'missed_opportunity',
                'severity': 'info',
                'message': f"Chair {state_machine.chair_id} is empty during peak hours"
            })
        
        return alerts
    
    def is_busy_hour(self):
        """Check if current time is during busy hours"""
        current_hour = datetime.now().hour
        return 10 <= current_hour <= 12 or 16 <= current_hour <= 19
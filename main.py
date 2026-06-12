# main_production_system.py
"""Complete production-ready shave detection system"""

import threading
import asyncio
from edge_deployment.optimized_detector import EdgeOptimizedDetector
from multi_camera.multi_chair_manager import MultiChairManager
from payment_integration.payment_webhook import PaymentIntegration
from cloud_sync.hybrid_sync import CloudSyncManager
from mobile_dashboard.websocket_server import DashboardServer
from video_evidence.selective_recorder import SelectiveVideoRecorder

class ProductionShaveSystem:
    """Main production system integrating all components"""
    
    def __init__(self):
        self.detector = EdgeOptimizedDetector(platform="jetson_nano")
        self.chair_manager = MultiChairManager(num_chairs=4)
        self.payment = PaymentIntegration("api_key", "api_secret")
        self.cloud_sync = CloudSyncManager(cloud_provider="aws")
        self.dashboard = DashboardServer()
        self.recorder = SelectiveVideoRecorder()
        
    def start(self):
        """Start all system components"""
        print("[SYSTEM] Starting Production Shave Detection System...")
        
        # Initialize components
        self.chair_manager.initialize_chairs()
        self.cloud_sync.start_auto_sync()
        self.recorder.start_auto_cleanup()
        
        # Start dashboard in separate thread
        dashboard_thread = threading.Thread(
            target=lambda: asyncio.run(self.dashboard.start_server()),
            daemon=True
        )
        dashboard_thread.start()
        
        # Main processing loop
        self.main_loop()
    
    def main_loop(self):
        """Main processing loop for all chairs"""
        while True:
            # Process all chairs in parallel
            results = self.chair_manager.process_all_chairs_parallel()
            
            for chair_id, result in results.items():
                if result and result.get('state') == 'SHAVING ACTIVE':
                    # Check for payment trigger
                    if result.get('total_shave_duration', 0) > 300:  # 5 minutes
                        self.handle_payment_trigger(result)
                    
                    # Check for evidence recording
                    if result.get('confidence', 1) < 0.6:
                        self.recorder.start_recording_for_session(
                            result['session_id'], 
                            chair_id, 
                            self.chair_manager.camera_configs[chair_id]['url']
                        )
                    else:
                        self.recorder.stop_recording_for_session(
                            result['session_id'],
                            reason="normal"
                        )
                    
                    # Sync to cloud periodically
                    if result['session_id'] % 10 == 0:
                        self.cloud_sync.sync_session_data(result['session_id'])
            
            # Update dashboard
            dashboard_view = self.chair_manager.get_unified_dashboard()
            cv2.imshow("Barbershop Dashboard", dashboard_view)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    def handle_payment_trigger(self, session_data):
        """Trigger payment processing"""
        amount = PaymentIntegration.calculate_payment_amount(None, session_data)
        payment_intent = self.payment.create_payment_intent(
            session_data['session_id'],
            amount
        )
        
        if payment_intent:
            print(f"[PAYMENT] Intent created for session {session_data['session_id']}: ${amount}")

if __name__ == "__main__":
    system = ProductionShaveSystem()
    system.start()
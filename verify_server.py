import subprocess
import time
import urllib.request
import urllib.parse
import json
import base64
import os

def test_server():
    print("Launching Flask server subprocess...")
    # Start server.py as a subprocess
    server_process = subprocess.Popen(
        ['python', 'server.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Test 1: GET /api/stats
        print("Testing GET /api/stats...")
        response = urllib.request.urlopen("http://127.0.0.1:5000/api/stats")
        assert response.getcode() == 200
        stats = json.loads(response.read().decode('utf-8'))
        print("  Stats:", list(stats.keys()))
        assert 'active_cameras' in stats
        assert 'total_alerts' in stats
        print("  GET /api/stats PASSED!")
        
        # Test 2: GET /api/alerts
        print("Testing GET /api/alerts...")
        response = urllib.request.urlopen("http://127.0.0.1:5000/api/alerts")
        assert response.getcode() == 200
        alerts = json.loads(response.read().decode('utf-8'))
        print(f"  Alerts: {len(alerts)} items")
        assert len(alerts) > 0
        print("  GET /api/alerts PASSED!")
        
        # Test 3: POST /api/predict_frame
        print("Testing POST /api/predict_frame...")
        # Create a tiny 10x10 dummy PNG to encode in base64
        import cv2
        import numpy as np
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        _, buffer = cv2.imencode('.jpg', img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        data = json.dumps({'image': img_base64}).encode('utf-8')
        req = urllib.request.Request(
            "http://127.0.0.1:5000/api/predict_frame",
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req)
        assert response.getcode() == 200
        prediction = json.loads(response.read().decode('utf-8'))
        print(f"  Prediction category: {prediction['category']}")
        print(f"  Anomaly score: {prediction['anomaly_score']:.4f}")
        assert 'anomaly_score' in prediction
        print("  POST /api/predict_frame PASSED!")
        
        print("Server integration verification PASSED!")
        
    except Exception as e:
        print(f"Server integration verification FAILED: {e}")
        # Print subprocess output if it failed
        stdout, stderr = server_process.communicate(timeout=1)
        print("Server stdout:", stdout)
        print("Server stderr:", stderr)
        raise e
    finally:
        # Terminate server
        print("Stopping Flask server...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")

if __name__ == '__main__':
    test_server()

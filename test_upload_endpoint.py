import urllib.request
import urllib.parse
import json

def test_upload():
    print("Testing upload_clip endpoint on running server...")
    
    # 1. Create a dummy multipart form data payload
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    
    # Dummy video file bytes
    file_content = b"fake video bytes representing a 10s clip"
    
    # Construct multipart request body
    parts = []
    # alert_id field
    parts.append(f'--{boundary}')
    parts.append('Content-Disposition: form-data; name="alert_id"\r\n')
    parts.append('1') # Alert ID 1
    # file field
    parts.append(f'--{boundary}')
    parts.append('Content-Disposition: form-data; name="file"; filename="test_clip.webm"')
    parts.append('Content-Type: video/webm\r\n')
    
    body = b''
    body += parts[0].encode('utf-8') + b'\r\n' + parts[1].encode('utf-8') + b'\r\n' + parts[2].encode('utf-8') + b'\r\n'
    body += parts[3].encode('utf-8') + b'\r\n' + parts[4].encode('utf-8') + b'\r\n' + parts[5].encode('utf-8') + b'\r\n' + file_content + b'\r\n'
    body += f'--{boundary}--\r\n'.encode('utf-8')
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }
    
    try:
        req = urllib.request.Request("http://127.0.0.1:5000/api/upload_clip", data=body, headers=headers)
        response = urllib.request.urlopen(req)
        assert response.getcode() == 200
        result = json.loads(response.read().decode('utf-8'))
        print("Upload Result:", result)
        assert result['success'] is True
        assert 'clip_url' in result
        print("Upload endpoint test PASSED!")
        
        # Test 2: Verify that GET /api/alerts now contains the clip_url
        print("Verifying that the alert contains the clip_url...")
        response = urllib.request.urlopen("http://127.0.0.1:5000/api/alerts")
        alerts = json.loads(response.read().decode('utf-8'))
        # Find alert with ID '1'
        alert1 = next(a for a in alerts if a['id'] == '1')
        print("  Updated Alert 1:", alert1)
        assert 'clip_url' in alert1
        assert alert1['clip_url'].startswith('/alerts/')
        print("Verification PASSED!")
        
    except Exception as e:
        print("Upload endpoint test FAILED:", e)
        raise e

if __name__ == '__main__':
    test_upload()

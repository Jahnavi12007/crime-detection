import urllib.request
import re

url = 'https://www.kaggle.com/code/pushkalpandey3/ufc-crime-dataset'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
req = urllib.request.Request(url, headers=headers)

try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        print(f"HTML Length: {len(html)}")
        
        # Let's search for script tags containing data
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        print(f"Found {len(scripts)} scripts")
        for i, script in enumerate(scripts):
            if 'KAGGLE_JUPYTERLAB_PATH' in script or 'initialData' in script or 'pushkal' in script:
                print(f"Script {i} (length {len(script)}): {script[:200]}...")
                # Write script to file for inspection
                with open(f"script_{i}.txt", "w", encoding="utf-8") as f:
                    f.write(script)
except Exception as e:
    print(f"Error: {e}")

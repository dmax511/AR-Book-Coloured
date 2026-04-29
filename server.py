from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import base64
import os

app = Flask(__name__)
CORS(app, resources={r"/google-lens-search": {"origins": "*"}})

SERPAPI_KEY = "c11b99eb983388f815841b4d0f45bb1b6af080ef6895ec2a3cac91bf916372b0"

@app.route('/google-lens-search', methods=['POST', 'OPTIONS'])
def google_lens_search():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided'}), 400
        
        base64_image = data['image']
        image_bytes = base64.b64decode(base64_image)
        
        files = {
            'image': ('image.jpg', image_bytes, 'image/jpeg')
        }
        params = {
            'engine': 'google_lens',
            'api_key': SERPAPI_KEY
        }
        
        print(f"Sending {len(image_bytes)} bytes to SerpAPI...")
        response = requests.post(
            'https://serpapi.com/search',
            files=files,
            data=params,
            timeout=60
        )
        
        print(f"SerpAPI response status: {response.status_code}")
        
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({
                'error': f'SerpAPI error {response.status_code}',
                'details': response.text[:500]
            }), response.status_code
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/', methods=['GET'])
def home():
    return jsonify({'message': 'Google Lens Proxy API', 'endpoints': ['/google-lens-search', '/health']})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

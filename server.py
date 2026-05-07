from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import base64

app = Flask(__name__)
CORS(app, resources={r"/google-lens-search": {"origins": "*"}})

# Your SerpAPI key
SERPAPI_KEY = "c11b99eb983388f815841b4d0f45bb1b6af080ef6895ec2a3"

@app.route('/google-lens-search', methods=['POST', 'OPTIONS'])
def google_lens_search():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': 'No image provided'}), 400
        
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        
        print(f"Sending {len(image_bytes)} bytes to SerpAPI...")
        
        # Prepare multipart form data for SerpAPI
        files = {
            'image': ('image.jpg', image_bytes, 'image/jpeg')
        }
        
        params = {
            'engine': 'google_lens',
            'api_key': SERPAPI_KEY,
            'hl': 'en',  # Language
            'country': 'us'  # Country
        }
        
        # FIXED: Correct SerpAPI endpoint with .json extension
        response = requests.post(
            'https://serpapi.com/search.json',
            files=files,
            data=params,
            timeout=30
        )
        
        print(f"SerpAPI response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success! Found {len(result.get('visual_matches', []))} visual matches")
            return jsonify(result)
        else:
            print(f"❌ Error response: {response.text}")
            return jsonify({
                'error': f'SerpAPI error {response.status_code}',
                'details': response.text
            }), response.status_code
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return jsonify({
        'message': 'Google Lens Proxy API', 
        'endpoints': ['/google-lens-search']
    })

if __name__ == '__main__':
    print("🚀 Starting Google Lens Proxy Server...")
    print(f"📡 API Key: {SERPAPI_KEY[:20]}...")
    app.run(host='0.0.0.0', port=5000, debug=True)

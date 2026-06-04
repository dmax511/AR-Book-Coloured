from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import base64
import os
from io import BytesIO

app = Flask(__name__)
CORS(app, resources={r"/google-lens-search": {"origins": "*"}})

SERPAPI_KEY = "c11b99eb983388f815841b4d0f45bb1b6af080ef6895ec2a3cac91bf916372b0"

@app.route('/google-lens-search', methods=['POST', 'OPTIONS'])
def google_lens_search():
    print(f"Received {request.method} request to /google-lens-search")
    print(f"Headers: {dict(request.headers)}")
    
    if request.method == 'OPTIONS':
        print("Handling CORS preflight")
        return '', 200
    
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided'}), 400
        
        base64_image = data['image']
        
        # Decode base64 to binary
        try:
            image_bytes = base64.b64decode(base64_image)
            print(f"Decoded image: {len(image_bytes)} bytes")
        except Exception as e:
            return jsonify({'error': f'Invalid base64 image: {str(e)}'}), 400
        
        # Step 1: Upload image to ImgBB to get a public URL
        print(f"Uploading {len(image_bytes)} bytes to ImgBB...")
        imgbb_response = requests.post(
            'https://api.imgbb.com/1/upload',
            data={
                'key': 'b94f12d5f327b50bccca5be87c763675',
                'image': base64_image
            },
            timeout=30
        )
        
        print(f"ImgBB Response Status: {imgbb_response.status_code}")
        
        if imgbb_response.status_code != 200:
            print(f"ImgBB Error: {imgbb_response.text[:500]}")
            return jsonify({
                'error': 'Failed to upload image to ImgBB',
                'details': imgbb_response.text[:500]
            }), 500
        
        imgbb_data = imgbb_response.json()
        if not imgbb_data.get('success'):
            print(f"ImgBB upload failed: {imgbb_data}")
            return jsonify({
                'error': 'ImgBB upload failed',
                'details': str(imgbb_data)
            }), 500
            
        image_url = imgbb_data['data']['url']
        print(f"Image uploaded to ImgBB: {image_url}")
        
        # Step 2: Send the image URL to SerpAPI Google Lens using GET
        params = {
            'engine': 'google_lens',
            'url': image_url,
            'api_key': SERPAPI_KEY,
            'hl': 'en'
        }
        
        print(f"Sending request to SerpAPI with URL: {image_url}")
        response = requests.get(
            'https://serpapi.com/search',
            params=params,
            timeout=60
        )
        
        print(f"SerpAPI Response Status: {response.status_code}")
        print(f"SerpAPI Response Text: {response.text[:1000]}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Results: {len(result.get('visual_matches', []))} visual matches")
            return jsonify(result), 200
        else:
            return jsonify({
                'error': f'SerpAPI error {response.status_code}',
                'details': response.text[:500]
            }), response.status_code
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
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

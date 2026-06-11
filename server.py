import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests
import base64
import os
from io import BytesIO
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/google-lens-search": {"origins": "*"}})

SERPAPI_KEY = "c11b99eb983388f815841b4d0f45bb1b6af080ef6895ec2a3cac91bf916372b0"

# Configure Cloudinary
cloudinary.config(
    cloud_name="dk0tw389c",
    api_key="773315794418384",
    api_secret="UBUT_Jn67D8Kpl9spiSN1fVEXj4"
)

def upload_to_cloudinary(image_bytes):
    # Step 1: Upload image to Cloudinary to get a public URL
    print(f"Attempting upload of {len(image_bytes)} bytes to Cloudinary...")
    try:
        # Cloudinary can directly upload raw bytes from BytesIO
        upload_result = cloudinary.uploader.upload(BytesIO(image_bytes), folder="colab_onboarding")
        
        # Check for successful response format similar to ImgBB logic
        if upload_result and 'secure_url' in upload_result:
            return upload_result['secure_url'], None
        return None, "Cloudinary upload failed: No secure_url in response"
    except Exception as e:
        return None, str(e)

@app.route('/google-lens-search', methods=['POST', 'OPTIONS'])
def google_lens_search():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided'}), 400
        
        image_bytes = base64.b64decode(data['image'])
        
        # --- Image Upload Process (Modular for multiple servers) ---
        # To add more servers, simply define a new function and add it to this list
        upload_methods = [upload_to_cloudinary]
        image_url = None
        last_error = "No uploaders executed"

        for upload_fn in upload_methods:
            image_url, error = upload_fn(image_bytes)
            if image_url:
                break
            last_error = error

        # Handle final result with appropriate API response
        if not image_url:
            return jsonify({'error': 'Upload failed', 'details': last_error}), 500
        
        # Step 2: Send the image URL to SerpAPI Google Lens
        params = {
            'engine': 'google_lens',
            'url': image_url,
            'api_key': SERPAPI_KEY,
            'hl': 'en'
        }
        response = requests.get('https://serpapi.com/search', params=params, timeout=60)
        return jsonify(response.json()), response.status_code
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

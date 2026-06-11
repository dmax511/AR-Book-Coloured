from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import base64
import os
from io import BytesIO

app = Flask(__name__)
CORS(app, resources={r"/google-lens-search": {"origins": "*"}})

SERPAPI_KEY = "c11b99eb983388f815841b4d0f45bb1b6af080ef6895ec2a3cac91bf916372b0"

# Cloudinary credentials (from previous steps)
cloud_name = "dk0tw389c"
api_key = "773315794418384"
api_secret = "UBUT_Jn67D8Kpl9spiSN1fVEXj4"

# --- 1. Ensure Cloudinary imports and configuration are present ---
# This was done in a previous step, but we ensure it here if it's somehow missing
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Configure Cloudinary (inline configuration)
cloudinary.config(
    cloud_name="dk0tw389c",  # Your Cloud Name
    api_key="773315794418384",      # Your API Key
    api_secret="UBUT_Jn67D8Kpl9spiSN1fVEXj4"  # Your API Secret
)

print("Cloudinary configured successfully.")


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
     
def upload_to_cloudinary(image_bytes):
    print(f"Attempting upload of {len(image_bytes)} bytes to Cloudinary...")
    try:
        upload_result = cloudinary.uploader.upload(BytesIO(image_bytes), folder="colab_onboarding")
        
       
        if upload_result and 'secure_url' in upload_result:
            image_url = upload_result['secure_url']
            print(f"Image successfully uploaded to Cloudinary: {image_url}")
            return image_url, None
        else:
            return None, "Cloudinary upload failed: No secure_url in response"
            
    except Exception as e:
        return None, str(e)

# --- Image Upload Process (Modular for multiple servers) ---
# To add more servers, simply define a new function and add it to this list
upload_methods = [upload_to_cloudinary]
image_url = None
last_error = "No uploaders executed"

for upload_fn in upload_methods:
    image_url, error = upload_fn(image_bytes)
    if image_url:
        break
    else:
        last_error = error
        print(f"Uploader failed: {error}. Trying next...")

# Handle final result with appropriate API response
if not image_url:
    print(f"All image uploads failed. Last error: {last_error}")
    # Returning a 500 error 
return jsonify({'error': 'Failed to upload image to any server', 'details': last_error}), 500
else:
    print(f"Final Image URL ready for SerpAPI: {image_url}")
        
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

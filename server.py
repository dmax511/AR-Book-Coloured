from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import base64
from io import BytesIO
import json

app = Flask(__name__)
CORS(app, resources={r"/google-lens-search": {"origins": "*"}})

# Your SerpAPI key
# It's recommended to load this from an environment variable for production
SERPAPI_KEY = "c11b99eb983388f815841b4d0f45bb1b6af080ef6895ec2a3cac91bf916372b0"

@app.route('/google-lens-search', methods=['POST', 'OPTIONS'])
def google_lens_search():
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided'}), 400

        base64_image = data['image']

        # Decode base64 to get image bytes
        try:
            image_bytes = base64.b64decode(base64_image)
        except Exception as e:
            return jsonify({'error': f'Invalid base64 image: {str(e)}'}), 400

        # Send to SerpAPI
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
            error_text = response.text[:500]  # First 500 chars of error
            return jsonify({
                'error': f'SerpAPI error {response.status_code}',
                'details': error_text
            }), response.status_code

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': 'Flask server is running'})

# This block runs the Flask app directly when the script is executed
if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(host='0.0.0.0', port=5000, debug=False)

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import base64
import subprocess
import tempfile
import os
from pathlib import Path
from PIL import Image
from io import BytesIO

app = Flask(__name__)
CORS(app, resources={
    r"/google-lens-search": {"origins": "*"}, 
    r"/create-zpt": {"origins": "*"},
    r"/assets/*": {"origins": "*"}
})

# Your SerpAPI key
SERPAPI_KEY = "c11b99eb983388f815841b4d0f45bb1b6af080ef6895ec2a3"

# Path to store generated .zpt files and source images
PROJECT_ROOT = os.path.dirname(__file__)
ZPT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'assets', 'tracking')
IMAGES_DIR = os.path.join(PROJECT_ROOT, 'assets', 'images')

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

@app.route('/create-zpt', methods=['POST', 'OPTIONS'])
def create_zpt():
    """
    Create a .zpt tracking file from captured image data
    1. Save source image to /assets/images
    2. Use Zapworks CLI to create .zpt file
    3. Save .zpt to /assets/tracking
    4. Return path for ImageTracker to use
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        image_data = data.get('image')
        filename = data.get('filename', 'snapshot_tracking')
        
        if not image_data:
            return jsonify({'error': 'No image provided'}), 400
        
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        
        print(f"📸 Received {len(image_bytes)} bytes for ZPT creation...")
        
        # Create directories if they don't exist
        os.makedirs(ZPT_OUTPUT_DIR, exist_ok=True)
        os.makedirs(IMAGES_DIR, exist_ok=True)
        
        # Step 1: Save source image to /assets/images
        source_image_filename = f"{filename}.jpg"
        source_image_path = os.path.join(IMAGES_DIR, source_image_filename)
        
        # Convert to JPEG for optimal size
        try:
            img = Image.open(BytesIO(image_bytes))
            # Resize if too large (Zapworks works best with images < 2048px)
            max_size = 2048
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                print(f"📐 Resized image to {new_size}")
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # Save optimized JPEG
            img.save(source_image_path, 'JPEG', quality=85, optimize=True)
            print(f"💾 Source image saved to: {source_image_path}")
            
        except Exception as img_error:
            print(f"⚠️ Image optimization failed: {img_error}, saving raw...")
            with open(source_image_path, 'wb') as f:
                f.write(image_bytes)
        
        # Step 2: Create .zpt file using Zapworks CLI
        output_filename = f"{filename}.zpt"
        output_path = os.path.join(ZPT_OUTPUT_DIR, output_filename)
        
        print(f"🔨 Creating .zpt file with Zapworks CLI...")
        
        try:
            # Run Zapworks CLI command to train the image
            result = subprocess.run(
                ['zapworks', 'train', source_image_path, '-o', output_path],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=PROJECT_ROOT
            )
            
            if result.returncode != 0:
                print(f"❌ Zapworks CLI error: {result.stderr}")
                return jsonify({
                    'error': 'Zapworks CLI training failed',
                    'details': result.stderr,
                    'stdout': result.stdout
                }), 500
            
            print(f"✅ .zpt file created: {output_path}")
            
            # Check if file was actually created
            if not os.path.exists(output_path):
                return jsonify({
                    'error': 'ZPT file was not created',
                    'details': 'CLI completed but no output file found'
                }), 500
            
            file_size = os.path.getsize(output_path)
            source_size = os.path.getsize(source_image_path)
            print(f"📦 ZPT file size: {file_size} bytes")
            print(f"📦 Source image size: {source_size} bytes")
            
            # Return file-relative paths that work with Mattercraft
            return jsonify({
                'success': True,
                'source_image': f'./assets/images/{source_image_filename}',
                'zpt_file': output_filename,
                'zpt_path': f'./assets/tracking/{output_filename}',
                'file_size': file_size,
                'source_size': source_size,
                'message': 'Tracking file created successfully'
            })
            
        except FileNotFoundError:
            return jsonify({
                'error': 'Zapworks CLI not found',
                'details': 'Please install Zapworks CLI: npm install -g @zappar/zapworks-cli'
            }), 500
        except subprocess.TimeoutExpired:
            return jsonify({
                'error': 'Zapworks CLI timeout',
                'details': 'Training took too long (>120s)'
            }), 500
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/assets/<path:filepath>')
def serve_assets(filepath):
    """Serve asset files (images, .zpt files, etc.)"""
    return send_from_directory('assets', filepath)

@app.route('/')
def index():
    return jsonify({
        'message': 'Google Lens Proxy API with Zapworks Integration', 
        'endpoints': [
            '/google-lens-search',
            '/create-zpt',
            '/assets/<path>'
        ],
        'status': 'online'
    })

if __name__ == '__main__':
    print("🚀 Starting Google Lens Proxy Server with Zapworks CLI...")
    print(f"📡 SerpAPI Key: {SERPAPI_KEY[:20]}...")
    print(f"📁 ZPT Output Directory: {ZPT_OUTPUT_DIR}")
    print(f"📁 Images Directory: {IMAGES_DIR}")
    print(f"📁 Project Root: {PROJECT_ROOT}")
    
    # Create directories if they don't exist
    os.makedirs(ZPT_OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)

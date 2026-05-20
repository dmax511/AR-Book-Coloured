from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import base64
import subprocess
import os
from PIL import Image
from io import BytesIO

app = Flask(__name__)

# Enable CORS for all routes
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# SerpAPI key for Google Lens searches
SERPAPI_KEY = "c11b99eb983388f815841b4d0f45bb1b6af080ef6895ec2a3"

# Directories for tracking files and images
PROJECT_ROOT = os.path.dirname(__file__) or os.getcwd()
ZPT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'assets', 'tracking')
IMAGES_DIR = os.path.join(PROJECT_ROOT, 'assets', 'images')

# Ensure directories exist
os.makedirs(ZPT_OUTPUT_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

@app.route('/google-lens-search', methods=['POST', 'OPTIONS'])
def google_lens_search():
    """Google Lens image search via SerpAPI"""
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
        print(f"📤 Sending {len(image_bytes)} bytes to SerpAPI...")
        
        # Call SerpAPI Google Lens endpoint
        response = requests.post(
            'https://serpapi.com/search.json',
            files={'image': ('image.jpg', image_bytes, 'image/jpeg')},
            params={
                'engine': 'google_lens',
                'api_key': SERPAPI_KEY,
                'hl': 'en',
                'country': 'us'
            },
            timeout=30
        )
        
        print(f"📥 SerpAPI status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            matches = len(result.get('visual_matches', []))
            print(f"✅ Found {matches} visual matches")
            return jsonify(result)
        else:
            print(f"❌ SerpAPI error: {response.text}")
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
    Create a .zpt tracking file from a captured image:
    1. Save source image to /assets/images
    2. Use Zapworks CLI to create .zpt file
    3. Return path for live ImageTracker updates
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        image_data = data.get('image')
        filename = data.get('filename', 'live_snapshot')
        
        if not image_data:
            return jsonify({'error': 'No image provided'}), 400
        
        # Remove data URL prefix
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        print(f"📸 Creating ZPT from {len(image_bytes)} bytes...")
        
        # Save source image
        source_filename = f"{filename}.jpg"
        source_path = os.path.join(IMAGES_DIR, source_filename)
        
        # Optimize image for tracking
        img = Image.open(BytesIO(image_bytes))
        
        # Resize if needed (Zapworks optimal < 2048px)
        if max(img.size) > 2048:
            ratio = 2048 / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            print(f"📐 Resized to {new_size}")
        
        # Convert to RGB
        if img.mode != 'RGB':
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode in ('RGBA', 'LA'):
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        
        # Save optimized JPEG
        img.save(source_path, 'JPEG', quality=85, optimize=True)
        print(f"💾 Saved: {source_path}")
        
        # Create .zpt file
        zpt_filename = f"{filename}.zpt"
        zpt_path = os.path.join(ZPT_OUTPUT_DIR, zpt_filename)
        
        print(f"🔨 Training with Zapworks CLI...")
        
        # Find Zapworks CLI
        zapworks_cli = os.path.join(PROJECT_ROOT, 'node_modules', '.bin', 'zapworks')
        if not os.path.exists(zapworks_cli):
            zapworks_cli = 'zapworks'
        
        # Train the image
        result = subprocess.run(
            [zapworks_cli, 'train', source_path, '-o', zpt_path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=PROJECT_ROOT
        )
        
        if result.returncode != 0:
            print(f"❌ CLI error: {result.stderr}")
            return jsonify({
                'error': 'Zapworks training failed',
                'details': result.stderr
            }), 500
        
        if not os.path.exists(zpt_path):
            return jsonify({'error': 'ZPT file not created'}), 500
        
        file_size = os.path.getsize(zpt_path)
        print(f"✅ Created {zpt_filename} ({file_size} bytes)")
        
        # Return paths for Mattercraft
        return jsonify({
            'success': True,
            'zpt_file': zpt_filename,
            'zpt_path': f'./assets/tracking/{zpt_filename}',
            'source_image': f'./assets/images/{source_filename}',
            'file_size': file_size
        })
        
    except FileNotFoundError:
        return jsonify({
            'error': 'Zapworks CLI not found',
            'details': 'Run: npm install -g @zappar/zapworks-cli'
        }), 500
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Training timeout (>120s)'}), 500
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/assets/<path:filepath>')
def serve_assets(filepath):
    """Serve static asset files"""
    return send_from_directory('assets', filepath)

@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'service': 'Google Lens + ZPT Live Tracking',
        'endpoints': {
            '/google-lens-search': 'POST - Search with Google Lens',
            '/create-zpt': 'POST - Generate .zpt tracking file',
            '/assets/<path>': 'GET - Serve asset files',
            '/health': 'GET - Health check'
        }
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'zpt_dir': os.path.exists(ZPT_OUTPUT_DIR),
        'images_dir': os.path.exists(IMAGES_DIR)
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("🚀 Starting ZPT Live Tracking Server")
    print(f"📁 Tracking: {ZPT_OUTPUT_DIR}")
    print(f"📁 Images: {IMAGES_DIR}")
    print(f"🌐 Port: {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False)

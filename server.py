from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import base64
import os
import re
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app, resources={
    r"/google-lens-search": {"origins": "*"},
    r"/text-search": {"origins": "*"},
    r"/find-high-res": {"origins": "*"}
})

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
        text_query = data.get('text', None)  # Optional text query for refinement
        image_bytes = base64.b64decode(base64_image)
        
        files = {
            'image': ('image.jpg', image_bytes, 'image/jpeg')
        }
        params = {
            'engine': 'google_lens',
            'api_key': SERPAPI_KEY
        }
        
        # Add text query if provided for combined image+text search
        if text_query:
            params['q'] = text_query
            print(f"Adding text query to image search: {text_query}")
        
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

@app.route('/text-search', methods=['POST', 'OPTIONS'])
def text_search():
    """Search Google Lens with text query only (no image)"""
    print(f"Received {request.method} request to /text-search")
    
    if request.method == 'OPTIONS':
        print("Handling CORS preflight")
        return '', 200
    
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text query provided'}), 400
        
        text_query = data['text']
        print(f"Text search query: {text_query}")
        
        # Use Google Lens text search
        params = {
            'engine': 'google_lens',
            'q': text_query,
            'api_key': SERPAPI_KEY,
            'hl': 'en'
        }
        
        print(f"Sending text query to SerpAPI: {text_query}")
        response = requests.get(
            'https://serpapi.com/search',
            params=params,
            timeout=60
        )
        
        print(f"SerpAPI Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Text search results received")
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


@app.route('/find-high-res', methods=['POST', 'OPTIONS'])
def find_high_res():
    """Find higher resolution versions of an image"""
    print(f"Received {request.method} request to /find-high-res")
    
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
        
        image_url = data['url']
        print(f"Finding high-res version of: {image_url}")
        
        # Try to extract higher resolution from URL patterns
        high_res_urls = extract_high_res_variants(image_url)
        
        # Validate which URLs actually work
        working_urls = []
        for url in high_res_urls[:5]:  # Check top 5 candidates
            try:
                head_response = requests.head(url, timeout=5, allow_redirects=True)
                if head_response.status_code == 200:
                    working_urls.append({
                        'url': url,
                        'content_length': head_response.headers.get('content-length', 'unknown')
                    })
            except:
                continue
        
        return jsonify({
            'original': image_url,
            'alternatives': working_urls,
            'highest_res': working_urls[0]['url'] if working_urls else image_url
        }), 200
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


def extract_high_res_variants(url):
    """Extract potential higher resolution variants from URL"""
    variants = [url]  # Always include original
    
    # Common resolution parameters to try
    high_res_params = [
        ('w', ['1920', '2048', '2560', '3840']),
        ('h', ['1080', '1440', '1536', '2160']),
        ('s', ['2048', '1920', '1600']),
        ('size', ['large', 'xlarge', 'original']),
        ('quality', ['100', '95', '90'])
    ]
    
    parsed = urlparse(url)
    
    # Method 1: Modify query parameters
    for param, values in high_res_params:
        for value in values:
            modified_url = re.sub(f'{param}=\\d+', f'{param}={value}', url)
            if modified_url != url:
                variants.append(modified_url)
    
    # Method 2: Remove size restrictions
    variants.append(re.sub(r'/s\d+/', '/s2048/', url))
    variants.append(re.sub(r'=s\d+', '=s2048', url))
    variants.append(re.sub(r'_s\d+', '_s2048', url))
    
    # Method 3: Try common high-res suffixes
    base_url = url.rsplit('.', 1)
    if len(base_url) == 2:
        ext = base_url[1].split('?')[0]
        variants.append(f"{base_url[0]}_large.{ext}")
        variants.append(f"{base_url[0]}_xlarge.{ext}")
        variants.append(f"{base_url[0]}_original.{ext}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variants = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique_variants.append(v)
    
    return unique_variants


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': 'Google Lens Proxy API',
        'endpoints': [
            '/google-lens-search - Search with image (POST)',
            '/text-search - Search with text only (POST)',
            '/find-high-res - Find higher resolution images (POST)',
            '/health - Health check (GET)'
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

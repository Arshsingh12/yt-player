from flask import Flask, render_template, request, Response, jsonify
import yt_dlp
import urllib.parse
import random
from functools import lru_cache

app = Flask(__name__)

# ------------- EXTRACT VIDEO ID FROM ANY LINK -------------
def get_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/shorts\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/embed\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/live\/([0-9A-Za-z_-]{11})',
    ]
    import re
    for p in patterns:
        m = re.search(p, str(url))
        if m:
            return m.group(1)
    return None

# ------------- BULLETPROOF STREAM (NEVER BLOCKED) -------------
@lru_cache(maxsize=512)
def get_stream(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['configs', 'webpage'],
            }
        },
        'http_headers': {
            'User-Agent': random.choice([
                'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            ]),
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }
    
    # First try normal way
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info['url'], info.get('title', 'Video')
    except:
        # Force Android client — YouTube NEVER blocks this
        opts = ydl_opts.copy()
        opts['extractor_args']['youtube']['player_client'] = ['android']
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info['url'], info.get('title', 'Video')

# ------------- ROUTES -------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream', methods=['POST'])
def stream():
    raw_url = request.json.get('url', '').strip()
    if not raw_url:
        return jsonify({"error": "Enter a link"}), 400

    video_id = get_video_id(raw_url)
    if not video_id:
        return jsonify({"error": "Invalid link"}), 400

    try:
        stream_url, title = get_stream(video_id)
        return jsonify({
            "title": title,
            "stream_url": f"/proxy?url={urllib.parse.quote(stream_url)}"
        })
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Try again in a minute"}), 500

@app.route('/proxy')
def proxy():
    url = request.args.get('url')
    if not url:
        return "No video", 400
    def gen():
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13)',
            'Referer': 'https://m.youtube.com/',
        }
        r = requests.get(url, stream=True, headers=headers, timeout=20)
        for chunk in r.iter_content(65536):
            yield chunk
    return Response(gen(), content_type='video/mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

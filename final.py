from flask import Flask, render_template, request, Response, jsonify
import yt_dlp
import urllib.parse
import random
import time
from functools import lru_cache

app = Flask(__name__)

# ------------------- BEST VIDEO ID EXTRACTOR -------------------
def get_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/shorts\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/live\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/embed\/([0-9A-Za-z_-]{11})',
    ]
    import re
    for p in patterns:
        m = re.search(p, str(url))
        if m:
            return m.group(1)
    return None

# ------------------- ULTRA-FAST + ANTI-BLOCK STREAM -------------------
@lru_cache(maxsize=512)
def get_stream(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    # These options bypass 429, visitor data, and bot detection
    ydl_opts = {
        'format': 'best[ext=mp4]/best[height<=1080]',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],
                'player_client': ['web', 'android'],
                'player_skip': ['webpage', 'configs'],
            }
        },
        'http_headers': {
            'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            ]),
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            best = None
            for f in info['formats']:
                if f.get('ext') == 'mp4' and f.get('acodec') != 'none' and f.get('vcodec') != 'none':
                    if not best or f.get('height', 0) > best.get('height', 0):
                        best = f
            if not best:
                best = info['formats'][-1]
            return best['url'], info.get('title', 'Video')
    except:
        # Fallback: force android client (almost never blocked)
        fallback_opts = ydl_opts.copy()
        fallback_opts['extractor_args']['youtube']['player_client'] = ['android']
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info['url'], info.get('title', 'Video')

# ------------------- ROUTES -------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream', methods=['POST'])
def stream():
    raw_url = request.json.get('url', '').strip()
    if not raw_url:
        return jsonify({"error": "Enter a YouTube link"}), 400

    video_id = get_video_id(raw_url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube link"}), 400

    try:
        direct_url, title = get_stream(video_id)
        return jsonify({
            "title": title,
            "stream_url": f"/proxy?url={urllib.parse.quote(direct_url)}"
        })
    except Exception as e:
        print("Final error:", e)
        return jsonify({"error": "Video temporarily unavailable"}), 500

@app.route('/proxy')
def proxy():
    url = request.args.get('url')
    if not url:
        return "No video", 400

    def gen():
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.youtube.com/',
        }
        r = requests.get(url, stream=True, headers=headers, timeout=20)
        for chunk in r.iter_content(65536):
            yield chunk

    return Response(gen(), content_type='video/mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

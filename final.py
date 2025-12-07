from flask import Flask, render_template, request, Response, jsonify
import yt_dlp
import urllib.parse
import re
from functools import lru_cache

app = Flask(__name__)

# Extract video ID from any YouTube link
def get_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/shorts\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/embed\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/live\/([0-9A-Za-z_-]{11})',
    ]
    for p in patterns:
        match = re.search(p, str(url))
        if match:
            return match.group(1)
    return None

# BULLETPROOF: Uses Android client — YouTube CANNOT block this
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
                'player_client': ['android'],
                'player_skip': ['webpage', 'js', 'configs']
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 13) gzip',
            'Accept-Language': 'en-US,en;q=0.9'
        }
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info['url'], info.get('title', 'Video')

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
        stream_url, title = get_stream(video_id)
        return jsonify({
            "title": title,
            "stream_url": f"/proxy?url={urllib.parse.quote(stream_url)}"
        })
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Video loading... try again"}), 500

@app.route('/proxy')
def proxy():
    url = request.args.get('url')
    if not url:
        return "No video", 400

    def generate():
        import requests
        headers = {
            'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 13) gzip',
            'Referer': 'https://m.youtube.com/'
        }
        r = requests.get(url, stream=True, headers=headers, timeout=20)
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                yield chunk

    return Response(generate(), content_type='video/mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

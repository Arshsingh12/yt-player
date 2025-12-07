from flask import Flask, render_template, request, Response, jsonify
import yt_dlp
import urllib.parse

app = Flask(__name__)

# Universal YouTube extractor — accepts ANY valid YouTube link
def extract_youtube_url(raw_url):
    parsed = urllib.parse.urlparse(raw_url.strip())
    if not parsed.scheme:
        raw_url = "https://" + raw_url
    
    # Let yt-dlp handle all validation and normalization
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(raw_url, download=False, process=False)
            if info and 'id' in info:
                return info['original_url'] or raw_url, info.get('title', 'YouTube Video')
    except:
        pass
    return None, None

def get_stream_url(youtube_url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best[height<=1080]',  # Best quality, fast start
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return info['url'], info.get('title', 'YouTube Video')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream', methods=['POST'])
def stream():
    raw_url = request.json.get('url', '').strip()
    if not raw_url:
        return jsonify({"error": "Please paste a YouTube link"}), 400

    print(f"Raw input: {raw_url}")

    # Step 1: Normalize & validate with yt-dlp itself (most reliable)
    valid_url, title_guess = extract_youtube_url(raw_url)
    if not valid_url:
        return jsonify({"error": "Not a valid YouTube link. Please check the URL."}), 400

    try:
        direct_stream_url, title = get_stream_url(valid_url)
        return jsonify({
            "title": title,
            "stream_url": f"/proxy?url={urllib.parse.quote(direct_stream_url)}"
        })
    except Exception as e:
        print("Stream error:", e)
        return jsonify({"error": "This video cannot be streamed (private, live, or blocked)"}), 400

@app.route('/proxy')
def proxy():
    url = request.args.get('url')
    if not url:
        return "Missing URL", 400

    def generate():
        import requests
        r = requests.get(url, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                yield chunk

    return Response(generate(), content_type='video/mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
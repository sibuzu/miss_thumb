import sys
import re
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

def main():
    if len(sys.argv) < 2:
        print("Usage: python miss_thumb.py <url_or_id>")
        sys.exit(1)

    user_input = sys.argv[1]
    
    if user_input.startswith("http"):
        url = user_input
    else:
        url = f"https://missav.ai/ja/{user_input}"
        
    print(f"Target URL: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, 
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page) 
        
        try:
            page.goto(url)
            
            try:
                # Wait for main content, shorter timeout as we primarily scan HTML
                page.wait_for_selector(".plyr__progress", timeout=15000)
            except:
                pass # Proceed to scan content even if timeout

            content = page.content()
            
            # 1. Extract String
            match = re.search(r"'([^']+)'\.split\('\|'\)", content)
            if match:
                raw_string = match.group(1)
                print(f"Extracted String: {raw_string}")
                
                # Synthesize URL
                # Input: m3u8|part5|part4|part3|part2|part1|com|surrit|https|video|1280x720|...
                # Target: https://surrit.com/part1-part2-part3-part4-part5/1280x720/video.m3u8
                # Note: The user example shows the UUID parts are reversed in the raw string relative to the URL?
                # User Example:
                # Raw: m3u8|43cdb0f23fd7|aa6d|4d37|70ad|7ee563f7|...
                # Target: .../7ee563f7-70ad-4d37-aa6d-43cdb0f23fd7/...
                # So indices: 5, 4, 3, 2, 1
                
                parts = raw_string.split('|')
                if len(parts) > 10:
                    # Construct URL
                    # {8}://{7}.{6}/{5}-{4}-{3}-{2}-{1}/{10}/{9}.{0}
                    m3u8_url = f"{parts[8]}://{parts[7]}.{parts[6]}/{parts[5]}-{parts[4]}-{parts[3]}-{parts[2]}-{parts[1]}/{parts[10]}/{parts[9]}.{parts[0]}"
                    print(f"Stream URL: {m3u8_url}")
                    
                    uuid = f"{parts[5]}-{parts[4]}-{parts[3]}-{parts[2]}-{parts[1]}"
                    seek_base = f"https://nineyu.com/{uuid}/seek"
                    seek_url = f"{seek_base}/_0.jpg"
                    print(f"Seek URL: {seek_url}")
                else:
                    print("Stream URL: Parse Error (Not enough parts)")
                    seek_base = None
            else:
                print("Extracted String: Not Found")
                print("Stream URL: Not Found")
                seek_base = None

            # 2. Extract Duration
            duration = "Not Found"
            # Try specific element
            duration_el = page.query_selector("span[class*='text-secondary'] .font-medium")
            if not duration_el:
                duration_el = page.query_selector(".plyr__time--duration")
            
            if duration_el:
                duration = duration_el.inner_text()
            else:
                # Fallback Regex
                dur_match = re.search(r'(\d{1,2}:\d{2}:\d{2})', content)
                if dur_match:
                    duration = dur_match.group(1)
            
            print(f"Duration: {duration}")

            # 3. Generate Viewer
            if seek_base and duration and duration != "Not Found":
                try:
                    # Parse duration to seconds
                    time_parts = list(map(int, duration.split(':')))[::-1]
                    total_seconds = 0
                    for i, part in enumerate(time_parts):
                        total_seconds += part * (60 ** i)
                    
                    # Calculate number of snapshots (every 72 seconds)
                    num_snapshots = int(total_seconds / 72) + 1
                    print(f"Total Seconds: {total_seconds}, Snapshots: {num_snapshots}")

                    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MissAV Viewer - {user_input}</title>
    <style>
        body {{ background: #222; color: #fff; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
        h1 {{ margin-bottom: 10px; }}
        .container {{ width: 100%; max-width: 1000px; text-align: center; }}
        .img-container {{ margin: 20px 0; background: #000; min-height: 400px; display: flex; align-items: center; justify-content: center; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
        img {{ max-width: 100%; max-height: 80vh; display: block; }}
        .controls {{ display: flex; gap: 10px; justify-content: center; align-items: center; flex-wrap: wrap; margin-bottom: 20px; }}
        button {{ background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 16px; transition: background 0.2s; }}
        button:hover {{ background: #2563eb; }}
        button:disabled {{ background: #555; cursor: not-allowed; }}
        input[type=range] {{ width: 300px; cursor: pointer; }}
        input[type=number] {{ width: 60px; padding: 5px; text-align: center; border-radius: 4px; border: none; }}
        .info {{ font-size: 1.2em; margin-bottom: 15px; background: #333; padding: 10px 20px; border-radius: 20px; display: inline-block; }}
        .time-range {{ color: #4ade80; font-weight: bold; margin-left: 10px; }}
        .nav-links {{ margin-bottom: 20px; color: #aaa; }}
        a {{ color: #60a5fa; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>{user_input}</h1>
    <div class="nav-links">
        <a href="{url}" target="_blank">Original Video</a> | 
        <a href="{m3u8_url}" target="_blank">M3U8 Stream</a>
    </div>

    <div class="container">
        <div class="info">
            <span id="index-display">Image 0 / {num_snapshots - 1}</span>
            <span class="time-range" id="time-display">00:00:00 ~ 00:01:12</span>
        </div>

        <div class="controls">
            <button onclick="prev()">Previous</button>
            <input type="range" id="slider" min="0" max="{num_snapshots - 1}" value="0" oninput="jumpTo(this.value)">
            <button onclick="next()">Next</button>
            
            <span style="margin-left: 20px; border-left: 1px solid #555; padding-left: 20px;">
                Jump to: <input type="number" id="jump-input" min="0" max="{num_snapshots - 1}" value="0" onchange="jumpTo(this.value)">
            </span>
        </div>

        <div class="img-container">
            <img id="viewer-img" src="" alt="Snapshot">
        </div>
    </div>

    <script>
        const seekBase = "{seek_base}";
        const totalSnapshots = {num_snapshots};
        let currentIndex = 0;

        function formatTime(totalSeconds) {{
            const h = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
            const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
            const s = (totalSeconds % 60).toString().padStart(2, '0');
            return `${{h}}:${{m}}:${{s}}`;
        }}

        function updateView() {{
            // Clamp index
            if (currentIndex < 0) currentIndex = 0;
            if (currentIndex >= totalSnapshots) currentIndex = totalSnapshots - 1;

            // Update Image
            const imgUrl = `${{seekBase}}/_${{currentIndex}}.jpg`;
            document.getElementById('viewer-img').src = imgUrl;

            // Update Info
            const startTime = currentIndex * 72;
            const endTime = startTime + 72;
            document.getElementById('index-display').innerText = `Image ${{currentIndex}} / ${{totalSnapshots - 1}}`;
            document.getElementById('time-display').innerText = `${{formatTime(startTime)}} ~ ${{formatTime(endTime)}}`;

            // Update Controls
            document.getElementById('slider').value = currentIndex;
            document.getElementById('jump-input').value = currentIndex;
        }}

        function prev() {{
            currentIndex--;
            updateView();
        }}

        function next() {{
            currentIndex++;
            updateView();
        }}

        function jumpTo(val) {{
            currentIndex = parseInt(val);
            updateView();
        }}

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') prev();
            if (e.key === 'ArrowRight') next();
        }});

        // Init
        updateView();
    </script>
</body>
</html>
"""
                    with open("viewer.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                    print("Viewer generated: viewer.html")

                except Exception as e:
                    print(f"Failed to generate viewer: {e}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
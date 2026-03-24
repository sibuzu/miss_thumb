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

                    width_pixels = 720
                    height_pixels = 405
                    
                    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MissAV Viewer - {user_input}</title>
    <style>
        body {{ background: #222; color: #eee; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
        h1 {{ margin: 0 0 10px 0; font-size: 1.5rem; }}
        .container {{ width: 100%; max-width: 1000px; text-align: center; }}
        
        .nav-links {{ margin-bottom: 20px; color: #aaa; }}
        a {{ color: #60a5fa; text-decoration: none; }}
        
        /* Viewer Area */
        .viewer-area {{ position: relative; display: inline-block; margin: 20px 0; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }}
        .img-container {{ display: block; }}
        img {{ display: block; max-width: 100%; height: auto; }}
        
        /* Grid Overlay */
        .grid-overlay {{ 
            position: absolute; top: 0; left: 0; right: 0; bottom: 0; 
            display: grid; 
            grid-template-columns: repeat(6, 1fr); 
            grid-template-rows: repeat(6, 1fr); 
        }}
        .grid-cell {{ 
            border: 1px solid rgba(255,255,255,0.1); 
            cursor: pointer; 
            position: relative;
        }}
        .grid-cell:hover {{ background: rgba(255,255,255,0.2); }}
        .grid-cell.selected {{ background: rgba(74, 222, 128, 0.4); border: 1px solid rgba(74, 222, 128, 0.8); }}
        .grid-cell.pending-start {{ background: rgba(96, 165, 250, 0.6); box-shadow: inset 0 0 0 3px #2563eb; }}
        .grid-cell.active-cursor {{ box-shadow: inset 0 0 0 2px #fff; }}

        /* Controls */
        .controls-row {{ display: flex; gap: 10px; justify-content: center; align-items: center; flex-wrap: wrap; margin-bottom: 15px; }}
        button {{ background: #374151; color: white; border: 1px solid #555; padding: 8px 16px; border-radius: 4px; cursor: pointer; transition: 0.2s; }}
        button:hover {{ background: #4b5563; }}
        button.primary {{ background: #2563eb; border-color: #2563eb; }}
        button.primary:hover {{ background: #1d4ed8; }}
        button.danger {{ background: #dc2626; border-color: #dc2626; }}
        button.danger:hover {{ background: #b91c1c; }}
        
        input[type=range] {{ width: 200px; }}
        input[type=number] {{ width: 60px; padding: 5px; background: #1f2937; border: 1px solid #374151; color: white; border-radius: 4px; }}
        
        .info-panel {{ background: #1f2937; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: left; display: inline-block; min-width: 600px; }}
        .info-row {{ display: flex; justify-content: space-between; margin-bottom: 5px; }}
        .highlight {{ color: #4ade80; font-weight: bold; }}
        
        .command-box {{ width: 100%; box-sizing: border-box; background: #111; color: #4ade80; padding: 10px; border-radius: 4px; border: 1px solid #333; font-family: monospace; margin-top: 10px; word-break: break-all; white-space: pre; overflow-x: auto; }}
        
        .selection-actions {{ margin-top: 10px; border-top: 1px solid #333; padding-top: 10px; }}
    </style>
</head>
<body>
    <h1>{user_input}</h1>
    <div class="nav-links">
        <a href="{url}" target="_blank">Original Video</a> | 
        <a href="{m3u8_url}" target="_blank">M3U8 Stream</a>
    </div>

    <div class="container">
        <!-- Info & Selection Status -->
        <div class="info-panel">
            <div class="info-row">
                <span>Main Snapshot: <span id="main-idx" class="highlight">0</span> / {num_snapshots - 1}</span>
                <span>Time: <span id="main-time" class="highlight">00:00:00</span></span>
            </div>
            <div class="info-row">
                <span>Hovered Sub-Snap: <span id="sub-idx">--</span> (+<span id="sub-time">--</span>s)</span>
                <span>Selection: <span id="sel-count" class="highlight">0</span> ranges</span>
            </div>
            
            <input type="hidden" id="pending-start" value="-1">

            <div class="selection-actions">
                <small>Selection Controls:</small><br>
                <div style="margin-top: 5px;">
                    <button class="primary" onclick="setStart()">1. Set Start Snap</button>
                    <button class="primary" onclick="setEnd()">2. Set End Snap</button>
                    <button class="danger" onclick="clearAll()" style="margin-left: 20px;">Clear All Selection</button>
                </div>
                <div style="margin-top: 5px; font-style: italic; color: #aaa; font-size: 0.9em;">
                    Create multiple ranges by setting Start/End repeatedly.
                </div>
            </div>

            <div style="margin-top: 15px;">
                 <strong>Download & Merge Command (FFmpeg):</strong>
                 <textarea id="ffmpeg-cmd" class="command-box" rows="10" readonly></textarea>
                 <div style="display: flex; gap: 10px; margin-top: 5px;">
                     <button onclick="copyCmd()" style="flex: 1;">Copy Command</button>
                     <button onclick="downloadCmd()" style="flex: 1; background: #059669; border-color: #059669;">Download .sh</button>
                 </div>
            </div>
        </div>

        <!-- Navigation -->
        <div class="controls-row">
            <button onclick="prev()">Previous</button>
            <input type="range" id="slider" min="0" max="{num_snapshots - 1}" value="0" oninput="jumpTo(this.value)">
            <button onclick="next()">Next</button>
            
            <span style="margin-left: 15px; border-left: 1px solid #555; padding-left: 15px;">
                Jump: <input type="number" id="jump-input" min="0" max="{num_snapshots - 1}" value="0" onchange="jumpTo(this.value)">
            </span>
        </div>

        <!-- Viewer -->
        <div class="viewer-area">
            <div class="img-container">
                <img id="viewer-img" src="" alt="Snapshot">
            </div>
            <div id="grid-overlay" class="grid-overlay">
                <!-- Grid items generated by JS -->
            </div>
        </div>
    </div>

    <script>
        const seekBase = "{seek_base}";
        const totalSnapshots = {num_snapshots};
        const m3u8Url = "{m3u8_url}";
        const videoId = "{user_input}"; 
        
        let currentIndex = 0;
        let activeSubIndex = null; 
        
        const CELLS_PER_SHEET = 36;
        const SECONDS_PER_CELL = 2;
        const SECONDS_PER_SHEET = CELLS_PER_SHEET * SECONDS_PER_CELL; // 72

        // Ranges: Array of [startGlobal, endGlobal]
        let ranges = [];
        let pendingStart = -1;
        
        const gridOverlay = document.getElementById('grid-overlay');
        for(let i=0; i<CELLS_PER_SHEET; i++) {{
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            cell.dataset.idx = i;
            cell.onclick = (e) => onCellClick(i, e);
            cell.onmouseover = () => onCellHover(i);
            gridOverlay.appendChild(cell);
        }}

        function formatTime(totalSeconds) {{
            const h = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
            const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
            const s = (totalSeconds % 60).toString().padStart(2, '0');
            return `${{h}}:${{m}}:${{s}}`;
        }}

        function updateView() {{
            if (currentIndex < 0) currentIndex = 0;
            if (currentIndex >= totalSnapshots) currentIndex = totalSnapshots - 1;

            const imgUrl = `${{seekBase}}/_${{currentIndex}}.jpg`;
            document.getElementById('viewer-img').src = imgUrl;

            const startTime = currentIndex * SECONDS_PER_SHEET;
            document.getElementById('main-idx').innerText = currentIndex;
            document.getElementById('main-time').innerText = formatTime(startTime);
            
            document.getElementById('slider').value = currentIndex;
            document.getElementById('jump-input').value = currentIndex;

            renderGridSelection();
        }}

        function onCellHover(subIdx) {{
            const timeOffset = subIdx * SECONDS_PER_CELL;
            document.getElementById('sub-idx').innerText = subIdx;
            document.getElementById('sub-time').innerText = timeOffset;
        }}

        function onCellClick(subIdx, e) {{
            activeSubIndex = subIdx;
            renderGridSelection();
        }}
        
        function getGlobalIndex(sheetIdx, subIdx) {{
            return sheetIdx * CELLS_PER_SHEET + subIdx;
        }}

        function setStart() {{
            if (activeSubIndex === null) return alert("Select a snapshot cell first.");
            pendingStart = getGlobalIndex(currentIndex, activeSubIndex);
            renderGridSelection();
        }}

        function setEnd() {{
            if (activeSubIndex === null) return alert("Select a snapshot cell first.");
            if (pendingStart === -1) return alert("Please set Start Snap first (Key '1').");
            
            const endGlob = getGlobalIndex(currentIndex, activeSubIndex);
            
            // Normalize start/end
            const s = Math.min(pendingStart, endGlob);
            const e = Math.max(pendingStart, endGlob);
            
            // Add range
            ranges.push([s, e]);
            pendingStart = -1; // Reset pending
            
            // Merge overlaps? 
            // Simple merge strategy: Sort by start, then merge
            ranges.sort((a,b) => a[0] - b[0]);
            
            let merged = [];
            if(ranges.length > 0) {{
                let curr = ranges[0];
                for(let i=1; i<ranges.length; i++) {{
                    if (ranges[i][0] <= curr[1] + 1) {{ // +1 allows adjacent merging
                        curr[1] = Math.max(curr[1], ranges[i][1]);
                    }} else {{
                        merged.push(curr);
                        curr = ranges[i];
                    }}
                }}
                merged.push(curr);
            }}
            ranges = merged;
            
            renderGridSelection();
            updateCommand();
        }}

        function clearAll() {{
            ranges = [];
            pendingStart = -1;
            renderGridSelection();
            updateCommand();
        }}

        function renderGridSelection() {{
            const cells = document.querySelectorAll('.grid-cell');
            cells.forEach(cell => {{
                const subIdx = parseInt(cell.dataset.idx);
                const globalIdx = getGlobalIndex(currentIndex, subIdx);
                
                cell.className = 'grid-cell'; // Reset logic

                // Active Cursor
                if (subIdx === activeSubIndex) cell.classList.add('active-cursor');

                // Pending Start
                if (pendingStart !== -1 && globalIdx === pendingStart) {{
                    cell.classList.add('pending-start');
                }}

                // Selected Ranges
                let isSelected = false;
                for(const r of ranges) {{
                    if (globalIdx >= r[0] && globalIdx <= r[1]) {{
                        isSelected = true;
                        break;
                    }}
                }}
                if (isSelected) cell.classList.add('selected');
            }});
        }}

        function updateCommand() {{
            document.getElementById('sel-count').innerText = ranges.length;
            
            if (ranges.length === 0) {{
                document.getElementById('ffmpeg-cmd').value = "";
                return;
            }}

            let cmds = "#!/bin/bash\\n\\n";
            let mergeTxtContent = "";
            let generatedFiles = [];

            ranges.forEach((rng, idx) => {{
                const startIdx = rng[0];
                const endIdx = rng[1];
                const count = endIdx - startIdx + 1;
                
                const startSec = startIdx * SECONDS_PER_CELL;
                const durSec = count * SECONDS_PER_CELL;
                
                const outName = `${{videoId}}_part${{idx+1}}.mp4`;
                generatedFiles.push(outName);
                
                cmds += `# Part ${{idx+1}}: ${{formatTime(startSec)}} (Duration: ${{durSec}}s)\\n`;
                cmds += `ffmpeg -nostdin -ss ${{startSec}} -i "${{m3u8Url}}" -t ${{durSec}} -c copy "${{outName}}" -y\\n`;
                
                mergeTxtContent += `file '${{outName}}'\\n`;
            }});
            
            if (generatedFiles.length > 1) {{
                cmds += "\\n# Merge all parts\\n";
                // We use printf to create the list file to avoid confusing quote escaping in JS strings
                cmds += `cat <<EOF > merge_list.txt\\n${{mergeTxtContent}}EOF\\n`;
                cmds += `ffmpeg -nostdin -f concat -safe 0 -i merge_list.txt -c copy "${{videoId}}_merged.mp4" -y\\n`;
                cmds += `rm merge_list.txt\\n`;
                // Optional: cleanup parts
                // cmds += `rm ${{generatedFiles.join(' ')}}`; 
            }}
            
            document.getElementById('ffmpeg-cmd').value = cmds;
        }}

        function copyCmd() {{
            const el = document.getElementById('ffmpeg-cmd');
            el.select();
            document.execCommand('copy');
        }}

        function downloadCmd() {{
             const content = document.getElementById('ffmpeg-cmd').value;
             if (!content) return alert("Nothing to download.");
             
             const blob = new Blob([content], {{ type: 'text/x-shellscript' }});
             const url = URL.createObjectURL(blob);
             const a = document.createElement('a');
             a.href = url;
             a.download = 'download.sh';
             document.body.appendChild(a);
             a.click();
             document.body.removeChild(a);
             URL.revokeObjectURL(url);
        }}

        function prev() {{ currentIndex--; updateView(); activeSubIndex = null; }}
        function next() {{ currentIndex++; updateView(); activeSubIndex = null; }}
        function jumpTo(val) {{ currentIndex = parseInt(val); updateView(); activeSubIndex = null; }}

        document.addEventListener('keydown', (e) => {{
            // Ignore if in inputs
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            if (e.key === 'ArrowLeft') prev();
            if (e.key === 'ArrowRight') next();
            if (e.key === '1') setStart();
            if (e.key === '2') setEnd();
        }});

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
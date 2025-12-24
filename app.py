from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import re
import sys

app = Flask(__name__)

def extract_m3u8(url_or_id):
    # Determine full URL
    if url_or_id.startswith('http'):
        url = url_or_id
    else:
        # Default base URL constructed from ID
        # User example: huntb-604 -> https://missav.ai/ja/huntb-604
        # We might need to handle different ID formats, but this is a starter
        url = f"https://missav.ai/ja/{url_or_id}"

    print(f"Processing URL: {url}")
    
    extracted_string = None
    error_message = None

    try:
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
                
                # Wait for potential cloudflare or page load
                # Using a shorter timeout for wait_for_selector combined with a general wait
                # Because sometimes we just want the HTML which might be there even if selector fails
                try:
                    page.wait_for_selector(".plyr__progress", timeout=15000)
                except:
                    print("Selector timeout, checking content anyway...")

                content = page.content()
                
                # Regex matching
                # Pattern: '...'.split('|')
                match = re.search(r"'([^']+)'\.split\('\|'\)", content)
                if match:
                    extracted_string = match.group(1)
                else:
                    error_message = "Could not find the obfuscated string pattern in page content."
                
                # Extract Duration
                duration = None
                # Try 1: Meta tag
                try:
                    # Often in <meta property="video:duration" content="1234"> (seconds)
                    # Or specific text on page
                    duration_el = page.query_selector("span[class*='text-secondary'] .font-medium") # Generic guess based on Tailwind usage
                    if not duration_el: 
                         # Try Plyr duration if visible
                         duration_el = page.query_selector(".plyr__time--duration")
                    
                    if duration_el:
                         duration = duration_el.inner_text()
                    else:
                        # Fallback: Regex for time format in source code (e.g. "duration":"12:34")
                        dur_match = re.search(r'(\d{1,2}:\d{2}:\d{2})', content)
                        if dur_match:
                            duration = dur_match.group(1)
                except Exception as e:
                    print(f"Duration extraction failed: {e}")

            except Exception as e:
                error_message = str(e)
            finally:
                browser.close()
                
    except Exception as e:
        error_message = f"Browser launch failed: {str(e)}"

    return extracted_string, duration, error_message

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    data = request.json
    user_input = data.get('input', '')
    
    if not user_input:
        return jsonify({'success': False, 'error': 'No input provided'})

    result, duration, error = extract_m3u8(user_input)
    
    if result:
        return jsonify({'success': True, 'data': result, 'duration': duration})
    else:
        return jsonify({'success': False, 'error': error})

if __name__ == '__main__':
    print("Starting server at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)

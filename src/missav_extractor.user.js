// ==UserScript==
// @name         MissAV Extractor
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Extract M3U8 string and video duration from MissAV
// @author       You
// @match        https://missav.ai/*/sw-*
// @match        https://missav.ai/*/huntb-*
// @match        https://missav.ai/*/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    function extractData() {
        console.log("MissAV Extractor: Starting...");
        
        // 1. Extract the obfuscated string
        const bodyContent = document.body.innerHTML;
        // Regex to find '...'.split('|')
        // We look for the exact pattern from the python script
        const stringMatch = document.body.innerHTML.match(/'([^']+)'\.split\('\|'\)/);
        let extractedString = "Not found";
        if (stringMatch && stringMatch[1]) {
            extractedString = stringMatch[1];
        }

        // 2. Extract Duration
        let duration = "Not found";
        // Try meta tag first
        // <meta property="video:duration" content="..."> is NOT standard on all sites, but let's check generic meta
        // MissAV often puts duration in a specific span. 
        // Based on previous analysis: span inside text-secondary or plyr
        
        // Try Plyr duration (best if player loaded)
        const plyrDuration = document.querySelector('.plyr__time--duration');
        if (plyrDuration) {
            duration = plyrDuration.innerText;
        } else {
            // Try generic metadata regex in source
            // "duration":"12:34" or similar
            const durationMatch = document.body.innerHTML.match(/(\d{1,2}:\d{2}:\d{2})/);
            if (durationMatch) {
                duration = durationMatch[1];
            }
        }

        return { string: extractedString, duration: duration };
    }

    function createOverlay(data) {
        const div = document.createElement('div');
        div.style.position = 'fixed';
        div.style.top = '10px';
        div.style.right = '10px';
        div.style.zIndex = '9999';
        div.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        div.style.color = '#fff';
        div.style.padding = '15px';
        div.style.borderRadius = '5px';
        div.style.fontFamily = 'monospace';
        div.style.maxWidth = '400px';
        div.style.wordBreak = 'break-all';
        div.style.fontSize = '12px';

        div.innerHTML = `
            <div style="margin-bottom: 8px; font-weight: bold; font-size: 14px; border-bottom: 1px solid #555; padding-bottom: 5px;">
                MissAV Extractor
                <button id="missav-close" style="float: right; border: none; background: transparent; color: #fff; cursor: pointer;">✕</button>
            </div>
            <div style="margin-bottom: 5px;">
                <strong>Duration:</strong> <span style="color: #4ade80;">${data.duration}</span>
            </div>
            <div>
                <strong>String:</strong><br>
                <div style="background: #333; padding: 5px; margin-top: 5px; border-radius: 3px; max-height: 100px; overflow-y: auto;">
                    ${data.string}
                </div>
                <button id="missav-copy" style="margin-top: 8px; width: 100%; padding: 5px; background: #2563eb; color: white; border: none; border-radius: 3px; cursor: pointer;">Copy String</button>
            </div>
        `;

        document.body.appendChild(div);

        document.getElementById('missav-close').addEventListener('click', () => div.remove());
        document.getElementById('missav-copy').addEventListener('click', () => {
            navigator.clipboard.writeText(data.string);
            const btn = document.getElementById('missav-copy');
            btn.innerText = "Copied!";
            setTimeout(() => btn.innerText = "Copy String", 2000);
        });
    }

    // Wait for page load
    window.addEventListener('load', () => {
        // Delay slightly to ensure dynamic content might be ready, though 'split' is usually in static source
        setTimeout(() => {
            const data = extractData();
            createOverlay(data);
        }, 1000);
    });

})();

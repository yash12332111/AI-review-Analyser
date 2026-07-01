(function() {
    function showPulseIntro() {
        if (document.getElementById('pulse-intro-overlay')) return;

        // Create overlay
        const overlay = document.createElement('div');
        overlay.id = 'pulse-intro-overlay';
        overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(35,34,42,0.6);backdrop-filter:blur(6px);z-index:9999;display:flex;align-items:center;justify-content:center;opacity:0;transition:opacity 0.3s ease';

        // The modal
        const modal = document.createElement('div');
        modal.style.cssText = 'background:#fcf9f1;width:600px;max-width:90%;border-radius:20px;border:1px solid #ece6d4;box-shadow:0 15px 50px rgba(0,0,0,0.15);overflow:hidden;transform:translateY(20px);transition:transform 0.3s ease;font-family:"Figtree",sans-serif;color:#2c2933;';
        
        // Stop clicks inside modal from closing it
        modal.addEventListener('click', (e) => e.stopPropagation());

        modal.innerHTML = `
            <div style="padding:24px 28px;border-bottom:1px solid #ece6d4;display:flex;align-items:center;justify-content:space-between">
                <h2 style="margin:0;font-size:20px;font-weight:700;color:#2c2933"><span style="color:#1ed760">Pulse</span> Overview</h2>
                <button id="pulse-intro-close-icon" style="background:none;border:none;font-size:24px;color:#8d8a7f;cursor:pointer;padding:0;line-height:1">&times;</button>
            </div>
            <div style="padding:24px 28px;font-size:14.5px;line-height:1.6;color:#3c3945">
                <p style="margin:0 0 16px 0;">This is an AI engine that reads thousands of real Spotify user reviews and surfaces the patterns around music discovery, organised into three tabs:</p>
                <ul style="margin:0 0 24px 0;padding-left:20px;display:flex;flex-direction:column;gap:12px;color:#2c2933">
                    <li><strong style="color:#1ed760;font-weight:700">Dashboard</strong> — a high-level overview of the feedback: total reviews analysed, sentiment breakdown, top complaints, common topics, user workarounds, and a filterable feed of real quotes.</li>
                    <li><strong style="color:#1ed760;font-weight:700">Discovery Themes</strong> — the themes the system automatically clustered from the reviews (not pre-defined): browse Frustrations, Behaviours, and Unmet needs, and click any theme to see its size, where it appears, and representative quotes.</li>
                    <li><strong style="color:#1ed760;font-weight:700">Research Chat</strong> — ask plain-English questions about the feedback and get answers grounded in real, cited reviews; it only answers from actual review data and won't invent quotes.</li>
                </ul>
                
                <div style="display:flex;align-items:center;justify-content:space-between;padding-top:16px;border-top:1px solid #ebe5d3">
                    <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;color:#7d7a71">
                        <input type="checkbox" id="pulse-intro-dont-show" style="accent-color:#1ed760;cursor:pointer;width:16px;height:16px" ${window.name === 'pulse_intro_dismissed' ? 'checked' : ''}>
                        Don't show again
                    </label>
                    <button id="pulse-intro-got-it" style="background:#1ed760;color:#2c2933;border:none;border-radius:8px;padding:9px 20px;font-family:'Figtree';font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 2px 5px rgba(30,215,96,0.2)">Got it, explore</button>
                </div>
            </div>
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Fade in
        requestAnimationFrame(() => {
            overlay.style.opacity = '1';
            modal.style.transform = 'translateY(0)';
        });

        const closeOverlay = () => {
            const dontShow = document.getElementById('pulse-intro-dont-show').checked;
            if (dontShow) {
                window.name = 'pulse_intro_dismissed'; // persists across navigation
            } else {
                window.name = ''; // allow reappearing if unchecked
            }
            
            overlay.style.opacity = '0';
            modal.style.transform = 'translateY(10px)';
            setTimeout(() => overlay.remove(), 300);
        };

        // Event listeners
        document.getElementById('pulse-intro-close-icon').addEventListener('click', closeOverlay);
        document.getElementById('pulse-intro-got-it').addEventListener('click', closeOverlay);
        overlay.addEventListener('click', closeOverlay);
    }

    function createHelpButton() {
        if (document.getElementById('pulse-help-button')) return;

        const btn = document.createElement('button');
        btn.id = 'pulse-help-button';
        btn.innerHTML = '?';
        btn.title = 'Show overview';
        btn.style.cssText = 'position:fixed;bottom:24px;right:24px;width:40px;height:40px;border-radius:50%;background:#fcf9f1;border:1px solid #ece6d4;color:#2c2933;font-family:"Figtree",sans-serif;font-size:18px;font-weight:700;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.1);z-index:9998;transition:transform 0.2s, background 0.2s;';
        
        btn.addEventListener('mouseover', () => {
            btn.style.transform = 'scale(1.05)';
            btn.style.background = '#ffffff';
        });
        btn.addEventListener('mouseout', () => {
            btn.style.transform = 'scale(1)';
            btn.style.background = '#fcf9f1';
        });
        
        btn.addEventListener('click', showPulseIntro);
        document.body.appendChild(btn);
    }

    // Initialize
    createHelpButton();
    if (window.name !== 'pulse_intro_dismissed') {
        showPulseIntro();
    }
})();

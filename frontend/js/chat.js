document.addEventListener('DOMContentLoaded', () => {
    const chatThread = document.getElementById('chat-thread');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const suggestionsContainer = document.getElementById('suggestions-container');
    const filterSource = document.getElementById('filter-source');
    const filterSentiment = document.getElementById('filter-sentiment');

    let isWaiting = false;

    // Wake up Render's free-tier backend if it's sleeping.
    // Shows a status pill in the chat thread while waiting.
    async function ensureBackendAwake() {
        const MAX_TRIES = 8;
        const POLL_MS   = 7000;

        let wakeMsg = null;

        for (let i = 0; i < MAX_TRIES; i++) {
            try {
                const res = await fetch(`${BACKEND_URL}/api/health`, { method: 'GET' });
                if (res.ok) {
                    if (wakeMsg) wakeMsg.remove();
                    return true;   // backend is up
                }
            } catch (_) { /* network error — keep trying */ }

            // Show / update the wake-up pill on first failure
            if (!wakeMsg) {
                wakeMsg = document.createElement('div');
                wakeMsg.className = 'message ai';
                wakeMsg.innerHTML = `<div class="bubble" style="background:#fffbe8;border:1px solid #f0d96e;color:#7a6200;font-size:13px;padding:12px 16px;">
                    ⏳ <strong>Server is waking up</strong> — Render's free tier sleeps when idle.<br>
                    <span id="wake-countdown">This usually takes 30–60 seconds. Please wait…</span>
                </div>`;
                chatThread.appendChild(wakeMsg);
                chatThread.scrollTop = chatThread.scrollHeight;
            } else {
                const cd = wakeMsg.querySelector('#wake-countdown');
                if (cd) cd.textContent = `Still warming up… attempt ${i + 1}/${MAX_TRIES}`;
            }

            await new Promise(r => setTimeout(r, POLL_MS));
        }

        // Backend never came up
        if (wakeMsg) {
            wakeMsg.querySelector('.bubble').innerHTML = '❌ The server could not be reached. Please try again in a minute.';
        }
        return false;
    }

    // Load suggestions
    fetch(`${BACKEND_URL}/api/chat/suggest`)
        .then(res => res.json())
        .then(data => {
            const suggestions = data.suggestions || [];
            suggestions.forEach(q => {
                const btn = document.createElement('button');
                btn.className = 'suggestion-btn';
                btn.textContent = q;
                btn.onclick = () => {
                    chatInput.value = q;
                    sendMessage();
                };
                suggestionsContainer.appendChild(btn);
            });
        })
        .catch(err => console.error("Error loading suggestions:", err));

    function createMessageElement(type, content) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${type}`;
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        
        // Basic markdown-to-html for paragraphs and bold
        let htmlContent = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n\n/g, '<br><br>')
            .replace(/\n/g, '<br>');
            
        bubble.innerHTML = htmlContent;
        msgDiv.appendChild(bubble);
        return msgDiv;
    }

    function createSourceCard(sourceObj) {
        const card = document.createElement('div');
        card.className = 'source-card';
        
        const header = document.createElement('div');
        header.className = 'source-card-header';
        
        const badge = document.createElement('span');
        badge.textContent = `${sourceObj.source} • ${sourceObj.sentiment}`;
        
        const dateSpan = document.createElement('span');
        if (sourceObj.date) {
            dateSpan.textContent = new Date(sourceObj.date).toLocaleDateString();
        }
        
        header.appendChild(badge);
        header.appendChild(dateSpan);
        
        const body = document.createElement('div');
        body.className = 'source-card-body';
        body.textContent = `"${sourceObj.quote}"`;
        
        card.appendChild(body);
        
        if (sourceObj.quote_translated) {
            const trans = document.createElement('div');
            trans.className = 'source-card-translation';
            trans.textContent = `English translation: "${sourceObj.quote_translated}"`;
            card.appendChild(trans);
        }
        
        card.appendChild(header);
        
        return card;
    }

    function showLoading() {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ai loading-msg`;
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.innerHTML = `
            <div class="loading-indicator">
                <div class="dot"></div>
                <div class="dot"></div>
                <div class="dot"></div>
            </div>
        `;
        msgDiv.appendChild(bubble);
        chatThread.appendChild(msgDiv);
        chatThread.scrollTop = chatThread.scrollHeight;
    }

    function hideLoading() {
        const loadingMsgs = document.querySelectorAll('.loading-msg');
        loadingMsgs.forEach(el => el.remove());
    }

    async function sendMessage() {
        if (isWaiting) return;
        const text = chatInput.value.trim();
        if (!text) return;

        // Display user message
        chatThread.appendChild(createMessageElement('user', text));
        chatInput.value = '';
        chatThread.scrollTop = chatThread.scrollHeight;

        // Prepare request
        const filters = {};
        if (filterSource.value) filters.source = filterSource.value;
        if (filterSentiment.value) filters.sentiment = filterSentiment.value;

        isWaiting = true;
        sendBtn.disabled = true;
        showLoading();

        // Wake up Render free-tier if needed before actually sending
        const backendReady = await ensureBackendAwake();
        if (!backendReady) {
            hideLoading();
            isWaiting = false;
            sendBtn.disabled = false;
            return;
        }

        try {
            const response = await fetch(`${BACKEND_URL}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, filters: filters })
            });

            if (!response.ok) {
                throw new Error("Server error");
            }

            const data = await response.json();
            hideLoading();
            
            // Render AI answer
            const aiMsg = createMessageElement('ai', data.answer);
            
            // Render sources if any
            if (data.sources && data.sources.length > 0) {
                // deduplicate identical sources for display cleanliness
                const uniqueSources = [];
                const uniqueQuotes = new Set();
                data.sources.forEach(s => {
                    if (!uniqueQuotes.has(s.quote)) {
                        uniqueQuotes.add(s.quote);
                        uniqueSources.push(s);
                    }
                });

                if (uniqueSources.length > 0) {
                    const sourcesWrapper = document.createElement('div');
                    sourcesWrapper.className = 'sources-wrapper';
                    sourcesWrapper.style.marginTop = '16px';

                    const toggleRow = document.createElement('div');
                    toggleRow.className = 'sources-toggle';
                    toggleRow.textContent = `CITED SOURCES (${uniqueSources.length}) ▸`;
                    toggleRow.style.fontFamily = "'IBM Plex Mono', monospace";
                    toggleRow.style.fontSize = '10.5px';
                    toggleRow.style.letterSpacing = '.1em';
                    toggleRow.style.textTransform = 'uppercase';
                    toggleRow.style.color = '#8d8a7f';
                    toggleRow.style.cursor = 'pointer';
                    toggleRow.style.display = 'inline-block';
                    toggleRow.style.userSelect = 'none';

                    const sourcesContainer = document.createElement('div');
                    sourcesContainer.className = 'sources-container';
                    sourcesContainer.style.display = 'none';
                    sourcesContainer.style.marginTop = '8px';
                    
                    uniqueSources.forEach(s => {
                        sourcesContainer.appendChild(createSourceCard(s));
                    });

                    toggleRow.onclick = () => {
                        if (sourcesContainer.style.display === 'none') {
                            sourcesContainer.style.display = 'flex';
                            toggleRow.textContent = `CITED SOURCES (${uniqueSources.length}) ▾`;
                        } else {
                            sourcesContainer.style.display = 'none';
                            toggleRow.textContent = `CITED SOURCES (${uniqueSources.length}) ▸`;
                        }
                    };

                    sourcesWrapper.appendChild(toggleRow);
                    sourcesWrapper.appendChild(sourcesContainer);
                    aiMsg.querySelector('.bubble').appendChild(sourcesWrapper);
                }
            }
            
            chatThread.appendChild(aiMsg);
            chatThread.scrollTop = chatThread.scrollHeight;

        } catch (error) {
            hideLoading();
            chatThread.appendChild(createMessageElement('ai', 'Sorry, an error occurred while processing your request.'));
        } finally {
            isWaiting = false;
            sendBtn.disabled = false;
            chatInput.focus();
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

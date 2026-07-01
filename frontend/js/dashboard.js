// State
let currentOffset = 0;
const limit = 50;

// Chart instances
let sentimentChartObj = null;
let topicsChartObj = null;
let trendsChartObj = null;

// DOM Elements
const filterDate = document.getElementById('filter-date');
const filterSource = document.getElementById('filter-source');
const filterCountry = document.getElementById('filter-country');
const filterSentiment = document.getElementById('filter-sentiment');
const filterDiscovery = document.getElementById('filter-discovery');

// Event Listeners
[filterDate, filterSource, filterCountry, filterSentiment, filterDiscovery].forEach(el => {
    if (!el) return;
    el.addEventListener('change', () => {
        currentOffset = 0;
        document.getElementById('quotes-container').innerHTML = '';
        fetchDashboardData();
    });
});

document.getElementById('btn-load-more').addEventListener('click', () => {
    currentOffset += limit;
    fetchQuotes(true);
});


// Initialization
document.addEventListener('DOMContentLoaded', () => {
    // Set theme colors for charts
    Chart.defaults.color = '#8d8a7f';
    Chart.defaults.font.family = "'Figtree', sans-serif";
    fetchDashboardData();
});

function getFilterParams() {
    const params = new URLSearchParams();
    
    // Date parsing
    const dateVal = filterDate.value;
    if (dateVal !== 'all') {
        const d = new Date();
        if (dateVal === '7d') d.setDate(d.getDate() - 7);
        if (dateVal === '30d') d.setDate(d.getDate() - 30);
        params.append('date_from', d.toISOString().split('T')[0]);
    }
    
    if (filterSource.value) params.append('source', filterSource.value);
    if (filterCountry.value) params.append('country', filterCountry.value);
    if (filterSentiment.value) params.append('sentiment', filterSentiment.value);
    if (filterDiscovery && filterDiscovery.value === 'true') params.append('discovery_filter', 'true');
    
    return params;
}

async function fetchDashboardData() {
    const params = getFilterParams();
    const qs = params.toString() ? `?${params.toString()}` : '';

    try {
        const [summary, topics, complaints, workarounds, quotes] = await Promise.all([
            fetch(`${BACKEND_URL}/api/dashboard/summary${qs}`).then(r => r.json()),
            fetch(`${BACKEND_URL}/api/dashboard/topics${qs}`).then(r => r.json()),
            fetch(`${BACKEND_URL}/api/dashboard/complaints${qs}`).then(r => r.json()),
            fetch(`${BACKEND_URL}/api/dashboard/workarounds${qs}`).then(r => r.json()),
            fetchQuotes(false) // Fetch quotes sets its own qs
        ]);

        // If no data, show empty state
        if (summary.total_feedback === 0) {
            document.getElementById('dashboard-content').style.display = 'none';
            document.getElementById('empty-state').style.display = 'block';
            document.getElementById('stat-total').textContent = '0';
            document.getElementById('stat-sources').textContent = '0';
            document.getElementById('stat-negative-pct').textContent = '0%';
            return;
        }

        document.getElementById('dashboard-content').style.display = 'contents';
        document.getElementById('empty-state').style.display = 'none';

        renderSummary(summary);
        renderSentimentChart(summary.by_sentiment);
        renderTopicsChart(topics);
        renderComplaints(complaints);
        renderWorkarounds(workarounds);
        

        // Fetch trends independently because it doesn't use filters (always 30 days)
        fetchTrends();

    } catch (err) {
        console.error('Error fetching dashboard data:', err);
    }
}

async function fetchTrends() {
    try {
        const trends = await fetch(`${BACKEND_URL}/api/dashboard/trends`).then(r => r.json());
        renderTrendsChart(trends);
    } catch (err) {
        console.error('Error fetching trends:', err);
    }
}

async function fetchQuotes(append = false) {
    const params = getFilterParams();
    params.append('limit', limit);
    params.append('offset', currentOffset);
    
    const qs = `?${params.toString()}`;
    const response = await fetch(`${BACKEND_URL}/api/dashboard/quotes${qs}`).then(r => r.json());
    
    renderQuotes(response.data, append);
    
    const btn = document.getElementById('btn-load-more');
    if (response.has_more) {
        btn.style.display = 'block';
    } else {
        btn.style.display = 'none';
    }
    return response;
}

// Renderers
function renderSummary(summary) {
    const classifiedTotal = Object.values(summary.by_sentiment).reduce((a,b) => a+b, 0);
    document.getElementById('stat-total').textContent = classifiedTotal.toLocaleString();
    document.getElementById('stat-sources').textContent = Object.keys(summary.by_source).length;
    
    const negative = summary.by_sentiment['negative'] || 0;
    const pct = classifiedTotal > 0 ? Math.round((negative / classifiedTotal) * 100) : 0;
    document.getElementById('stat-negative-pct').textContent = `${pct}%`;
}

function renderSentimentChart(data) {
    const ctx = document.getElementById('sentimentChart').getContext('2d');
    
    if (sentimentChartObj) sentimentChartObj.destroy();
    
    const colors = {
        positive: '#1ed760',
        negative: '#ef4444',
        mixed: '#f59e0b',
        neutral: '#bdb6a3'
    };
    
    const classifiedTotal = Object.values(data).reduce((a,b) => a+b, 0);
    const sentKeys = Object.keys(data);
    const values = Object.values(data);
    const bgColors = sentKeys.map(k => colors[k.toLowerCase()] || '#8888a0');
    
    const labels = sentKeys.map(k => {
        const count = data[k];
        const pct = classifiedTotal > 0 ? Math.round((count / classifiedTotal) * 100) : 0;
        return `${k.charAt(0).toUpperCase() + k.slice(1)} (${pct}%)`;
    });

    sentimentChartObj = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: bgColors,
                borderWidth: 0,
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { 
                    position: 'right',
                    labels: {
                        usePointStyle: true,
                        padding: 20,
                        font: { family: "'Figtree', sans-serif", size: 13, weight: 500 },
                        color: '#3c3945'
                    }
                }
            },
            cutout: '72%',
            onClick: (event, elements) => {
                if (elements && elements.length > 0) {
                    const idx = elements[0].index;
                    const clickedSentiment = sentKeys[idx];
                    openSentimentModal(clickedSentiment);
                }
            }
        }
    });
}

async function openSentimentModal(sentiment) {
    const modal = document.getElementById('sentiment-modal');
    const content = document.getElementById('sentiment-modal-content');
    const subtitle = document.getElementById('sentiment-modal-subtitle');
    
    document.getElementById('sentiment-modal-title').textContent = `${sentiment} Reviews`;
    subtitle.textContent = `Loading...`;
    content.innerHTML = '';
    modal.style.display = 'flex';
    
    const params = getFilterParams();
    params.set('sentiment', sentiment); // override sentiment filter
    params.set('limit', 50);
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/dashboard/quotes?${params.toString()}`).then(r => r.json());
        subtitle.textContent = `Showing ${response.data.length} recent ${sentiment} reviews`;
        
        if (response.data.length === 0) {
            content.innerHTML = '<div class="empty-state">No quotes found.</div>';
            return;
        }
        
        response.data.forEach(q => {
            const div = document.createElement('div');
            div.style.cssText = "padding:16px;background:#fff;border:1px solid #ece6d4;border-radius:12px";
            const date = q.posted_at ? new Date(q.posted_at).toLocaleDateString() : 'Unknown date';
            
            div.innerHTML = `
                <div style="font-size:13px;color:#2c2933;line-height:1.5;margin-bottom:12px">"${q.pattern_evidence || q.content}"</div>
                ${q.quote_translated && q.quote_translated !== (q.pattern_evidence || q.content) ? `<div style="font-size:12px;color:#8d8a7f;font-style:italic;margin-bottom:12px">Translation: "${q.quote_translated}"</div>` : ''}
                <div style="display:flex;justify-content:space-between;font-family:'IBM Plex Mono';font-size:10.5px;color:#8d8a7f">
                    <span>${q.source} &middot; ${q.country || 'Unknown'}</span>
                    <span>${date}</span>
                </div>
            `;
            content.appendChild(div);
        });
        
    } catch (err) {
        subtitle.textContent = `Error loading reviews`;
        console.error(err);
    }
}

function renderTopicsChart(topics) {
    const container = document.getElementById('topicsChart');
    container.innerHTML = '';
    
    let displayData = topics.slice(0, 8);

    displayData.forEach(t => {
        const div = document.createElement('div');
        const pct = t.percentage ? t.percentage.toFixed(1) : 0;
        div.innerHTML = `
            <div style="display:flex;justify-content:space-between;gap:10px;margin-bottom:7px"><span style="font-size:12.5px;color:#3c3945;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${t.value}">${t.value}</span><span style="font-family:'IBM Plex Mono';font-size:12px;color:#7d7a71">${pct}%</span></div>
            <div style="height:7px;background:#ebe5d3;border-radius:4px;overflow:hidden"><div style="height:100%;border-radius:4px;width:${pct}%;background:#8b5cf6"></div></div>
        `;
        container.appendChild(div);
    });
}

function renderTrendsChart(trends) {
    const ctx = document.getElementById('trendsChart').getContext('2d');
    if (trendsChartObj) trendsChartObj.destroy();

    // Pivot data: day -> { topic: count }
    const dates = [...new Set(trends.map(t => t.day))].sort();
    const topTopics = [...new Set(trends.map(t => t.topic))].slice(0, 5); // top 5 topics overall for clarity
    
    const datasets = topTopics.map((topic, i) => {
        const colors = ['#8b5cf6', '#1ed760', '#ef4444', '#f59e0b', '#3b82f6'];
        const data = dates.map(d => {
            const match = trends.find(t => t.day === d && t.topic === topic);
            return match ? match.count : 0;
        });
        
        return {
            label: topic,
            data: data,
            borderColor: colors[i % colors.length],
            backgroundColor: colors[i % colors.length] + '22', // Add transparency
            tension: 0.4,
            fill: true
        };
    });

    trendsChartObj = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: { grid: { color: '#ebe5d3' }, border: { display: false } },
                y: { grid: { color: '#ebe5d3' }, border: { display: false }, beginAtZero: true }
            }
        }
    });
}

function renderComplaints(complaints) {
    const container = document.getElementById('complaints-container');
    container.innerHTML = '';
    
    if (complaints.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding:1rem;">No complaints found</div>';
        return;
    }
    
    complaints.forEach(c => {
        const div = document.createElement('div');
        div.className = 'complaint-item';
        div.style.cssText = "display:flex;align-items:center;gap:14px;padding:13px 0;border-bottom:1px solid #ebe5d3";
        div.innerHTML = `
            <div style="font-family:'IBM Plex Mono';font-size:12px;color:#a8a598;width:32px;text-align:right">${c.count}</div>
            <div style="flex:1;font-size:13.5px;color:#2c2933" title="${c.value}">${c.value}</div>
        `;
        container.appendChild(div);
    });
}

function renderWorkarounds(workarounds) {
    const container = document.getElementById('workarounds-container');
    container.innerHTML = '';
    
    if (workarounds.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding:1rem;">No workarounds found</div>';
        return;
    }
    
    workarounds.forEach(w => {
        const div = document.createElement('div');
        div.className = 'workaround-item';
        div.style.cssText = "padding:13px 14px;background:#f4efe1;border:1px solid #ece6d4;border-left:2px solid #f59e0b;border-radius:9px;margin-bottom:11px";
        
        const date = w.date ? new Date(w.date).toLocaleDateString() : '';
        const sourceLabel = w.source === 'appstore' ? 'App Store' : 
                           w.source === 'playstore' ? 'Play Store' : 'Community';
                           
        div.innerHTML = `
            <div style="font-size:13px;color:#34313c;font-style:italic;line-height:1.5">"${w.content}"</div>
            <div style="font-family:'IBM Plex Mono';font-size:10.5px;color:#8d8a7f;margin-top:8px;letter-spacing:.04em">${sourceLabel} &middot; ${date}</div>
        `;
        container.appendChild(div);
    });
}


function renderQuotes(quotes, append = false) {
    const container = document.getElementById('quotes-container');
    if (!append) container.innerHTML = '';
    
    if (quotes.length === 0 && !append) {
        container.innerHTML = '<div class="empty-state">No quotes found matching filters.</div>';
        return;
    }
    
    quotes.forEach(q => {
        const div = document.createElement('div');
        div.className = 'quote-card';
        div.style.cssText = "padding:20px;background:#fffdf6;border:1px solid #e7e0ce;border-radius:13px;display:flex;flex-direction:column;justify-content:space-between";
        
        const date = q.posted_at ? new Date(q.posted_at).toLocaleDateString() : 'Unknown date';
        
        // Original quote text
        let quoteContentHtml = `<div style="font-size:13.5px;color:#2c2933;line-height:1.55">"${q.pattern_evidence || q.content}"</div>`;
        
        // Quote translated directly beneath if different (indicating non-English original)
        if (q.quote_translated && q.quote_translated !== (q.pattern_evidence || q.content)) {
            quoteContentHtml += `<div style="font-size:12.5px;color:#8d8a7f;font-style:italic;margin-top:8px;padding-left:10px;border-left:2px solid #e7e0ce">Translation: "${q.quote_translated}"</div>`;
        }
        
        let sentColor = q.sentiment === 'negative' ? '#ef4444' : q.sentiment === 'positive' ? '#1ed760' : q.sentiment === 'mixed' ? '#f59e0b' : '#8d8a7f';
        let sentBg = q.sentiment === 'negative' ? 'rgba(239,68,68,.15)' : q.sentiment === 'positive' ? 'rgba(30,215,96,.15)' : q.sentiment === 'mixed' ? 'rgba(245,158,11,.15)' : 'rgba(141,138,127,.15)';

        div.innerHTML = `
            ${quoteContentHtml}
            <div style="display:flex;align-items:center;gap:7px;margin-top:13px;flex-wrap:wrap">
                <span style="font-family:'IBM Plex Mono';font-size:10.5px;color:#706d65;background:#ece6d4;padding:3px 8px;border-radius:6px">📍 ${q.source}</span>
                <span style="font-family:'IBM Plex Mono';font-size:10.5px;color:${sentColor};background:${sentBg};padding:3px 8px;border-radius:6px;text-transform:capitalize">${q.sentiment}</span>
                ${q.country ? `<span style="font-family:'IBM Plex Mono';font-size:10.5px;color:#706d65;background:#ece6d4;padding:3px 8px;border-radius:6px">${q.country}</span>` : ''}
                <span style="flex:1"></span>
                <span style="font-family:'IBM Plex Mono';font-size:10.5px;color:#9b988c">${date}</span>
            </div>
            <div style="font-family:'IBM Plex Mono';font-size:10.5px;color:#9b988c;margin-top:8px;border-top:1px solid #ebe5d3;padding-top:8px">
                Topic: ${q.topic || 'N/A'} &middot; Complaint: ${q.core_complaint || 'None'}
            </div>
        `;
        container.appendChild(div);
    });
}

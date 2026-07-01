const ThemesRenderer = {
    // State
    themesData: [],
    activeThemeType: 'core_complaint',
    containerListId: 'theme-list',
    containerDetailId: 'theme-detail',
    isCompact: true,

    async init(themes, options = {}) {
        this.themesData = themes || [];
        this.containerListId = options.listId || 'theme-list';
        this.containerDetailId = options.detailId || 'theme-detail';
        this.isCompact = options.isCompact !== undefined ? options.isCompact : true;

        if (options.activeType) {
            this.activeThemeType = options.activeType;
        }

        if (!window.SharedConfig) {
            try {
                const response = await fetch(`${BACKEND_URL}/api/dashboard/config`);
                window.SharedConfig = await response.json();
            } catch (e) {
                console.error("Failed to load config", e);
                window.SharedConfig = { discovery_keywords: [] };
            }
        }

        // Dynamically update the page title with the real total review count
        const titleEl = document.getElementById('themes-page-title');
        if (titleEl) {
            const totalReviews = this.themesData.reduce((sum, t) => sum + t.member_count, 0);
            titleEl.textContent = `Auto-clustered from ${totalReviews.toLocaleString()} reviews`;
        }

        this.bindTabs();
        this.renderThemes();
    },

    bindTabs() {
        document.querySelectorAll('.theme-tab').forEach(tab => {
            // Remove old listeners to avoid duplicates if re-inited
            const newTab = tab.cloneNode(true);
            
            // Add transitions and initial inline styles
            newTab.style.transition = 'background .18s ease, color .18s ease, border-color .18s ease';
            if (newTab.classList.contains('active')) {
                newTab.style.color = '#ffffff';
                newTab.style.background = '#222226';
                newTab.style.borderColor = '#222226';
            } else {
                newTab.style.color = '#7d7a71';
                newTab.style.background = 'transparent';
                newTab.style.borderColor = 'transparent';
            }

            tab.parentNode.replaceChild(newTab, tab);
            
            newTab.addEventListener('click', (e) => {
                document.querySelectorAll('.theme-tab').forEach(t => {
                    t.classList.remove('active');
                    t.style.color = '#7d7a71';
                    t.style.background = 'transparent';
                    t.style.borderColor = 'transparent';
                });
                e.target.classList.add('active');
                e.target.style.color = '#ffffff';
                e.target.style.background = '#222226';
                e.target.style.borderColor = '#222226';
                
                this.activeThemeType = e.target.dataset.type;
                this.renderThemes();
            });
        });
    },

    renderThemes() {
        const container = document.getElementById(this.containerListId);
        const detailContainer = document.getElementById(this.containerDetailId);
        if (!container || !detailContainer) return;
        
        container.innerHTML = '';
        
        let filteredThemes = [];
        if (this.activeThemeType === 'music_discovery') {
            const keywords = window.SharedConfig?.discovery_keywords || [];
            filteredThemes = this.themesData.filter(t => {
                const content = ((t.label || '') + ' ' + (t.summary || '') + ' ' + (t.topic || '')).toLowerCase();
                return keywords.some(k => content.includes(k));
            });
        } else {
            filteredThemes = this.themesData.filter(t => t.cluster_type === this.activeThemeType);
        }
        
        if (filteredThemes.length === 0) {
            container.innerHTML = '<div class="empty-state">No themes generated for this filter.</div>';
            detailContainer.innerHTML = '<div class="empty-state">Select a theme to view details</div>';
            return;
        }
        
        // Inject styles for active states if they don't exist
        if (!document.getElementById('theme-card-styles')) {
            const style = document.createElement('style');
            style.id = 'theme-card-styles';
            style.innerHTML = `
                .theme-card-inner { background: #fffdf6; border-color: #e7e0ce; }
                .theme-item.active .theme-card-inner { background: #ebf9f0; border-color: #1ed760; }
                .theme-card-pct { color: #8b5cf6; background: #f1ebdd; }
                .theme-item.active .theme-card-pct { color: #1ed760; background: #e7e1ce; }
                .theme-card-bar { background: #8b5cf6; }
                .theme-item.active .theme-card-bar { background: #1ed760; }
            `;
            document.head.appendChild(style);
        }

        // Render list
        filteredThemes.forEach((theme, idx) => {
            const div = document.createElement('div');
            div.className = `theme-item ${idx === 0 ? 'active' : ''}`;
            
            // Calculate dynamic percentage based on sum of member_counts in filtered list
            const totalFiltered = filteredThemes.reduce((sum, t) => sum + t.member_count, 0);
            const dynamicPct = totalFiltered > 0 ? Math.round((theme.member_count / totalFiltered) * 100) : 0;

            if (this.isCompact) {
                div.innerHTML = `
                    <div class="theme-name" title="${theme.label}">${theme.label}</div>
                    <div class="theme-pct">${dynamicPct}%</div>
                `;
            } else {
                div.innerHTML = `
                    <div class="theme-card-inner" style="display:block;width:100%;text-align:left;padding:15px 16px;border-radius:13px;cursor:pointer;font-family:'Figtree';border:1px solid;box-shadow:0 1px 3px rgba(0,0,0,0.05);transition:all .2s ease">
                        <div style="display:flex;align-items:center;gap:10px;margin-bottom:11px">
                            <span class="theme-card-pct" style="font-family:'IBM Plex Mono';font-size:11px;padding:2px 7px;border-radius:5px;font-weight:600;transition:all .2s ease">${dynamicPct}%</span>
                            <span style="flex:1;font-size:13.5px;font-weight:600;color:#2c2933;line-height:1.3">${theme.label}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:10px">
                            <div style="flex:1;height:5px;background:#ebe5d4;border-radius:3px;overflow:hidden"><div class="theme-card-bar" style="height:100%;border-radius:3px;width:${dynamicPct}%;transition:all .2s ease"></div></div>
                            <span style="font-family:'IBM Plex Mono';font-size:11px;color:#7d7a71;width:34px;text-align:right">${theme.member_count}</span>
                        </div>
                    </div>
                `;
            }
            
            div.addEventListener('click', () => {
                // ALWAYS render details first so a styling error can't block it
                this.renderThemeDetail(theme, dynamicPct, totalFiltered);

                // Safely update the active class toggle
                document.querySelectorAll(`#${this.containerListId} .theme-item`).forEach(el => {
                    el.classList.remove('active');
                });
                div.classList.add('active');
            });
            
            container.appendChild(div);
        });
        
        // Render first theme details automatically
        if (filteredThemes.length > 0) {
            const totalFiltered = filteredThemes.reduce((sum, t) => sum + t.member_count, 0);
            const dynamicPct = totalFiltered > 0 ? Math.round((filteredThemes[0].member_count / totalFiltered) * 100) : 0;
            this.renderThemeDetail(filteredThemes[0], dynamicPct, totalFiltered);
        }
    },

    renderThemeDetail(theme, pct, totalContext) {
        const container = document.getElementById(this.containerDetailId);
        if (!container) return;
        
        const sourcesMap = {'appstore': 'App Store', 'playstore': 'Play Store', 'spotify_community': 'Community'};
        
        if (this.isCompact) {
            let sourcesHtmlCompact = Object.entries(theme.sources_breakdown)
                .sort((a,b) => b[1]-a[1])
                .map(([k,v]) => `${sourcesMap[k] || k} (${Math.round((v/theme.member_count)*100)}%)`)
                .join(', ');
                
            let countriesHtmlCompact = Object.entries(theme.countries_breakdown)
                .sort((a,b) => b[1]-a[1])
                .slice(0, 5) // top 5
                .map(([k,v]) => `${k} (${Math.round((v/theme.member_count)*100)}%)`)
                .join(', ');

            // Dashboard Layout (As-Is)
            let quotesHtml = theme.representative_quotes.map(q => `<div class="theme-quote">${q}</div>`).join('');
            
            container.innerHTML = `
                <div class="theme-detail-header">
                    <h3>${theme.label}</h3>
                </div>
                <div class="theme-meta">
                    <div><strong>Count:</strong> ${theme.member_count} reviews</div>
                    <div><strong>Share:</strong> ${pct}% of total</div>
                </div>
                <div class="theme-meta">
                    <div><strong>Sources:</strong> ${sourcesHtmlCompact || 'N/A'}</div>
                    <div><strong>Countries:</strong> ${countriesHtmlCompact || 'N/A'}</div>
                </div>
                <div class="theme-quotes">
                    <strong>Representative Quotes:</strong>
                    ${quotesHtml || '<div class="text-muted">No quotes available</div>'}
                </div>
            `;
        } else {
            // New Page Layout (Pulse styled inline markup)
            let sourcesHtml = Object.entries(theme.sources_breakdown)
                .sort((a,b) => b[1]-a[1])
                .map(([k,v]) => {
                    const sourcePct = Math.round((v/theme.member_count)*100);
                    const sourceName = sourcesMap[k] || k;
                    return `<div style="display:flex;align-items:center;gap:11px"><span style="width:78px;font-size:12px;color:#48454f">${sourceName}</span><div style="flex:1;height:7px;background:#ebe5d3;border-radius:4px;overflow:hidden"><div style="height:100%;border-radius:4px;width:${sourcePct}%;background:#1ed760"></div></div><span style="font-family:'IBM Plex Mono';font-size:11px;color:#7d7a71;width:30px;text-align:right">${v}</span></div>`;
                })
                .join('');
                
            let countriesHtml = Object.entries(theme.countries_breakdown)
                .sort((a,b) => b[1]-a[1])
                .slice(0, 5)
                .map(([k,v]) => {
                    const countryPct = Math.round((v/theme.member_count)*100);
                    return `<div style="display:flex;align-items:center;gap:11px"><span style="width:34px;font-family:'IBM Plex Mono';font-size:11.5px;color:#48454f">${k}</span><div style="flex:1;height:7px;background:#ebe5d3;border-radius:4px;overflow:hidden"><div style="height:100%;border-radius:4px;width:${countryPct}%;background:#8b5cf6"></div></div><span style="font-family:'IBM Plex Mono';font-size:11px;color:#7d7a71;width:30px;text-align:right">${v}</span></div>`;
                })
                .join('');

            let quotesHtml = '';
            if (theme.representative_quotes && theme.representative_quotes.length > 0) {
                theme.representative_quotes.forEach(q => {
                    quotesHtml += `
                        <div style="padding:14px 16px;background:#f4efe1;border:1px solid #ece6d4;border-left:2px solid #8b5cf6;border-radius:10px;font-size:13.5px;color:#2c2933;line-height:1.55;font-style:italic">“${q}”</div>
                    `;
                });
            } else {
                quotesHtml = '<div style="font-size:12px;color:#86837a;">No quotes available</div>';
            }
            
            // Render full expanded view using exact Pulse inline markup
            container.innerHTML = `
                <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px;padding-bottom:20px;border-bottom:1px solid #e7e0ce">
                    <div>
                        <div style="display:inline-flex;align-items:center;gap:7px;font-family:'IBM Plex Mono';font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:#8b5cf6;font-weight:600;margin-bottom:10px"><span style="width:6px;height:6px;border-radius:50%;background:#8b5cf6"></span>Cluster detail</div>
                        <h2 style="margin:0;font-family:'Figtree';font-size:23px;font-weight:600;letter-spacing:-.3px;max-width:520px;line-height:1.25">${theme.label}</h2>
                    </div>
                    <div style="text-align:right;flex-shrink:0">
                        <div style="font-family:'Figtree';font-size:32px;font-weight:600;line-height:1">${theme.member_count}</div>
                        <div style="font-size:11px;color:#86837a;margin-top:3px">mentions · ${pct}%</div>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-bottom:24px">
                    <div>
                        <div style="font-size:12px;color:#86837a;font-weight:500;margin-bottom:14px">By source</div>
                        <div style="display:flex;flex-direction:column;gap:11px">
                            ${sourcesHtml || '<div style="font-size:12px;color:#86837a;">N/A</div>'}
                        </div>
                    </div>
                    <div>
                        <div style="font-size:12px;color:#86837a;font-weight:500;margin-bottom:14px">By region</div>
                        <div style="display:flex;flex-direction:column;gap:11px">
                            ${countriesHtml || '<div style="font-size:12px;color:#86837a;">N/A</div>'}
                        </div>
                    </div>
                </div>

                <div style="font-size:12px;color:#86837a;font-weight:500;margin-bottom:12px">Representative quotes</div>
                <div style="display:flex;flex-direction:column;gap:10px">
                    ${quotesHtml}
                </div>
            `;
        }
    }
};

window.ThemesRenderer = ThemesRenderer;

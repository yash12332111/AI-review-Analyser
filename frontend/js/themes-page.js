document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Fetch themes without date filters to show the full corpus themes
        const response = await fetch(`${BACKEND_URL}/api/dashboard/themes`);
        if (!response.ok) throw new Error('Failed to fetch themes');
        
        const themes = await response.json();
        
        if (window.ThemesRenderer) {
            window.ThemesRenderer.init(themes, {
                listId: 'page-theme-list',
                detailId: 'page-theme-detail',
                isCompact: false // Enables the expanded Pulse layout for this page
            });
        }
    } catch (err) {
        console.error('Error loading themes for dedicated page:', err);
        const container = document.getElementById('page-theme-list');
        if (container) {
            container.innerHTML = '<div class="empty-state">Failed to load themes. Ensure the server is running.</div>';
        }
    }
});

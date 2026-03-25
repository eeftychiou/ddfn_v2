/**
 * Theme management for DDFN dashboards
 */
const ThemeManager = {
    STORAGE_KEY: 'ddfn-theme-preference',
    
    init() {
        const savedTheme = localStorage.getItem(this.STORAGE_KEY);
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme) {
            this.setTheme(savedTheme);
        } else if (prefersDark) {
            this.setTheme('dark');
        } else {
            this.setTheme('light');
        }
        
        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem(this.STORAGE_KEY)) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
    },
    
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(this.STORAGE_KEY, theme);
        this.updateThemeIcon();
        
        // Dispatch custom event for components that need to react
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
    },
    
    toggle() {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        this.setTheme(next);
    },
    
    getCurrent() {
        return document.documentElement.getAttribute('data-theme') || 'light';
    },
    
    updateThemeIcon() {
        const icon = document.querySelector('.theme-icon');
        if (icon) {
            icon.textContent = this.getCurrent() === 'dark' ? '☀️' : '🌙';
        }
    }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => ThemeManager.init());

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ThemeManager;
}

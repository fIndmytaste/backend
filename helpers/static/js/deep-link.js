/**
 * Deep Link JavaScript Utilities for FindMyTaste App
 * 
 * Provides client-side deep linking functionality including
 * app detection, smart redirects, and analytics tracking.
 */

class DeepLinkManager {
    constructor(config = {}) {
        this.config = {
            appScheme: 'findmytaste',
            iosAppStoreUrl: '',
            androidPlayStoreUrl: '',
            fallbackDelay: 3000,
            appOpenTimeout: 2000,
            ...config
        };
        
        this.isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        this.isAndroid = /Android/.test(navigator.userAgent);
        this.isMobile = this.isIOS || this.isAndroid;
        this.isApp = this.detectApp();
        
        this.init();
    }
    
    init() {
        // Set up event listeners
        this.setupEventListeners();
        
        // Handle page load deep linking
        this.handlePageLoad();
    }
    
    detectApp() {
        // Check if running in the mobile app
        const userAgent = navigator.userAgent.toLowerCase();
        return userAgent.includes('findmytaste') || 
               window.webkit?.messageHandlers?.findMyTaste ||
               window.Android?.findMyTaste;
    }
    
    setupEventListeners() {
        // Listen for deep link clicks
        document.addEventListener('click', (event) => {
            const link = event.target.closest('[data-deep-link]');
            if (link) {
                event.preventDefault();
                this.handleDeepLinkClick(link);
            }
        });
        
        // Listen for app state changes
        document.addEventListener('visibilitychange', () => {
            this.handleVisibilityChange();
        });
        
        // Listen for page focus/blur
        window.addEventListener('blur', () => {
            this.handleWindowBlur();
        });
        
        window.addEventListener('focus', () => {
            this.handleWindowFocus();
        });
    }
    
    handlePageLoad() {
        // Check if this page should trigger an app redirect
        const shouldRedirect = document.body.dataset.autoRedirect === 'true';
        const route = document.body.dataset.deepLinkRoute;
        
        if (shouldRedirect && route && this.isMobile && !this.isApp) {
            this.redirectToApp(route, this.getPageParams());
        }
    }
    
    handleDeepLinkClick(element) {
        const route = element.dataset.deepLink;
        const params = this.parseParams(element.dataset.deepLinkParams);
        const trackingId = element.dataset.trackingId;
        
        // Track the click
        this.trackClick(route, params, trackingId);
        
        // Redirect to app
        this.redirectToApp(route, params);
    }
    
    redirectToApp(route, params = {}) {
        if (this.isApp) {
            // Already in app, just navigate
            this.navigateInApp(route, params);
            return;
        }
        
        if (!this.isMobile) {
            // Desktop - show QR code or redirect to web
            this.handleDesktopRedirect(route, params);
            return;
        }
        
        // Mobile - attempt app redirect
        this.attemptAppRedirect(route, params);
    }
    
    attemptAppRedirect(route, params = {}) {
        const deepLink = this.buildDeepLink(route, params);
        const fallbackUrl = this.buildFallbackUrl(route, params);
        
        // Show loading state
        this.showLoadingState();
        
        // Track redirect attempt
        this.trackRedirectAttempt(route, params);
        
        // Attempt to open app
        this.openApp(deepLink, fallbackUrl);
    }
    
    buildDeepLink(route, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const paramString = queryString ? `?${queryString}` : '';
        
        return `${this.config.appScheme}://${route}${paramString}`;
    }
    
    buildFallbackUrl(route, params = {}) {
        if (this.isIOS) {
            return this.config.iosAppStoreUrl;
        } else if (this.isAndroid) {
            return this.config.androidPlayStoreUrl;
        }
        
        return '/';
    }
    
    openApp(deepLink, fallbackUrl) {
        let appOpened = false;
        let fallbackTimer;
        
        // Set up fallback timer
        fallbackTimer = setTimeout(() => {
            if (!appOpened) {
                this.handleAppOpenFailed(fallbackUrl);
            }
        }, this.config.fallbackDelay);
        
        // Attempt to open app
        if (this.isIOS) {
            this.openAppIOS(deepLink, fallbackUrl, () => {
                appOpened = true;
                clearTimeout(fallbackTimer);
            });
        } else if (this.isAndroid) {
            this.openAppAndroid(deepLink, fallbackUrl, () => {
                appOpened = true;
                clearTimeout(fallbackTimer);
            });
        }
    }
    
    openAppIOS(deepLink, fallbackUrl, successCallback) {
        // Try Universal Link first
        const universalLink = deepLink.replace(`${this.config.appScheme}://`, 'https://findmytaste.app/dl/');
        
        // Create invisible iframe for app redirect
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.src = universalLink;
        document.body.appendChild(iframe);
        
        // Clean up iframe
        setTimeout(() => {
            document.body.removeChild(iframe);
        }, 1000);
        
        // Check if app opened
        setTimeout(() => {
            if (document.hidden || document.webkitHidden) {
                successCallback();
                this.trackAppOpened();
            }
        }, this.config.appOpenTimeout);
    }
    
    openAppAndroid(deepLink, fallbackUrl, successCallback) {
        // Try intent URL first
        const intentUrl = `intent://${deepLink.replace(`${this.config.appScheme}://`, '')}#Intent;scheme=${this.config.appScheme};package=com.findmytaste.app;end`;
        
        try {
            window.location.href = intentUrl;
            
            // Check if app opened
            setTimeout(() => {
                if (document.hidden || document.webkitHidden) {
                    successCallback();
                    this.trackAppOpened();
                }
            }, this.config.appOpenTimeout);
            
        } catch (error) {
            // Fallback to custom scheme
            window.location.href = deepLink;
        }
    }
    
    handleAppOpenFailed(fallbackUrl) {
        this.hideLoadingState();
        this.trackAppOpenFailed();
        
        // Show app download prompt
        this.showAppDownloadPrompt(fallbackUrl);
    }
    
    showLoadingState() {
        // Create loading overlay
        const overlay = document.createElement('div');
        overlay.id = 'deep-link-loading';
        overlay.innerHTML = `
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                color: white;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            ">
                <div style="text-align: center;">
                    <div style="
                        width: 40px;
                        height: 40px;
                        border: 3px solid #f3f3f3;
                        border-top: 3px solid #667eea;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                        margin: 0 auto 20px;
                    "></div>
                    <div style="font-size: 18px; margin-bottom: 10px;">Opening FindMyTaste...</div>
                    <div style="font-size: 14px; opacity: 0.8;">Please wait while we redirect you to the app</div>
                </div>
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;
        
        document.body.appendChild(overlay);
    }
    
    hideLoadingState() {
        const overlay = document.getElementById('deep-link-loading');
        if (overlay) {
            overlay.remove();
        }
    }
    
    showAppDownloadPrompt(fallbackUrl) {
        const modal = document.createElement('div');
        modal.id = 'app-download-modal';
        modal.innerHTML = `
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10001;
                padding: 20px;
            ">
                <div style="
                    background: white;
                    border-radius: 12px;
                    padding: 30px;
                    max-width: 400px;
                    width: 100%;
                    text-align: center;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                ">
                    <div style="font-size: 48px; margin-bottom: 20px;">🍽️</div>
                    <h2 style="margin: 0 0 15px; color: #333;">Get the FindMyTaste App</h2>
                    <p style="color: #666; margin-bottom: 25px;">
                        For the best experience, download our mobile app from the ${this.isIOS ? 'App Store' : 'Play Store'}.
                    </p>
                    <div style="display: flex; gap: 10px; justify-content: center;">
                        <a href="${fallbackUrl}" style="
                            background: #667eea;
                            color: white;
                            padding: 12px 24px;
                            border-radius: 8px;
                            text-decoration: none;
                            font-weight: 600;
                        ">Download App</a>
                        <button onclick="this.closest('#app-download-modal').remove()" style="
                            background: #f8f9fa;
                            color: #666;
                            padding: 12px 24px;
                            border: 1px solid #dee2e6;
                            border-radius: 8px;
                            font-weight: 600;
                            cursor: pointer;
                        ">Continue on Web</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (modal.parentNode) {
                modal.remove();
            }
        }, 10000);
    }
    
    handleDesktopRedirect(route, params) {
        // Show QR code for desktop users
        this.showQRCode(route, params);
    }
    
    showQRCode(route, params) {
        const qrModal = document.createElement('div');
        qrModal.id = 'qr-code-modal';
        
        // Generate QR code URL
        const deepLink = this.buildDeepLink(route, params);
        const qrUrl = `/dl/qr/${route}/?${new URLSearchParams(params).toString()}`;
        
        qrModal.innerHTML = `
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10001;
                padding: 20px;
            ">
                <div style="
                    background: white;
                    border-radius: 12px;
                    padding: 30px;
                    max-width: 400px;
                    width: 100%;
                    text-align: center;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                ">
                    <h2 style="margin: 0 0 20px; color: #333;">Scan to Open in App</h2>
                    <div style="margin-bottom: 20px;">
                        <img src="${qrUrl}" alt="QR Code" style="max-width: 200px; width: 100%;" />
                    </div>
                    <p style="color: #666; margin-bottom: 25px; font-size: 14px;">
                        Scan this QR code with your mobile device to open in the FindMyTaste app.
                    </p>
                    <button onclick="this.closest('#qr-code-modal').remove()" style="
                        background: #667eea;
                        color: white;
                        padding: 12px 24px;
                        border: none;
                        border-radius: 8px;
                        font-weight: 600;
                        cursor: pointer;
                    ">Close</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(qrModal);
    }
    
    navigateInApp(route, params) {
        // Send message to native app
        if (window.webkit?.messageHandlers?.findMyTaste) {
            // iOS
            window.webkit.messageHandlers.findMyTaste.postMessage({
                action: 'navigate',
                route: route,
                params: params
            });
        } else if (window.Android?.findMyTaste) {
            // Android
            window.Android.findMyTaste.navigate(JSON.stringify({
                route: route,
                params: params
            }));
        }
    }
    
    parseParams(paramsString) {
        if (!paramsString) return {};
        
        try {
            return JSON.parse(paramsString);
        } catch (error) {
            console.warn('Failed to parse deep link params:', error);
            return {};
        }
    }
    
    getPageParams() {
        const params = {};
        const urlParams = new URLSearchParams(window.location.search);
        
        for (const [key, value] of urlParams) {
            params[key] = value;
        }
        
        return params;
    }
    
    // Analytics methods
    trackClick(route, params, trackingId) {
        this.sendAnalytics('deep_link_click', {
            route: route,
            params: params,
            tracking_id: trackingId,
            timestamp: Date.now(),
            user_agent: navigator.userAgent,
            platform: this.getPlatform()
        });
    }
    
    trackRedirectAttempt(route, params) {
        this.sendAnalytics('redirect_attempt', {
            route: route,
            params: params,
            timestamp: Date.now(),
            platform: this.getPlatform()
        });
    }
    
    trackAppOpened() {
        this.sendAnalytics('app_opened', {
            timestamp: Date.now(),
            platform: this.getPlatform()
        });
    }
    
    trackAppOpenFailed() {
        this.sendAnalytics('app_open_failed', {
            timestamp: Date.now(),
            platform: this.getPlatform()
        });
    }
    
    sendAnalytics(event, data) {
        // Send analytics to server
        fetch('/dl/analytics/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify({
                event: event,
                data: data
            })
        }).catch(error => {
            console.warn('Failed to send analytics:', error);
        });
    }
    
    getPlatform() {
        if (this.isIOS) return 'ios';
        if (this.isAndroid) return 'android';
        return 'web';
    }
    
    getCSRFToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        return '';
    }
    
    handleVisibilityChange() {
        if (document.hidden) {
            // Page became hidden - might indicate app opened
            this.trackAppOpened();
        }
    }
    
    handleWindowBlur() {
        // Window lost focus - might indicate app opened
        this.lastBlurTime = Date.now();
    }
    
    handleWindowFocus() {
        // Window gained focus
        if (this.lastBlurTime && Date.now() - this.lastBlurTime > 2000) {
            // User was away for more than 2 seconds - might have been in app
            this.trackAppOpened();
        }
    }
}

// Smart Banner functionality
class SmartBanner {
    constructor(config = {}) {
        this.config = {
            appName: 'FindMyTaste',
            appDescription: 'Get the app for the best experience',
            iosAppStoreUrl: '',
            androidPlayStoreUrl: '',
            dismissDuration: 86400000, // 24 hours
            ...config
        };
        
        this.isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        this.isAndroid = /Android/.test(navigator.userAgent);
        this.isMobile = this.isIOS || this.isAndroid;
        this.isApp = /findmytaste/i.test(navigator.userAgent);
        
        this.init();
    }
    
    init() {
        if (!this.shouldShow()) return;
        
        this.createBanner();
        this.setupEventListeners();
    }
    
    shouldShow() {
        // Don't show if not mobile
        if (!this.isMobile) return false;
        
        // Don't show if already in app
        if (this.isApp) return false;
        
        // Don't show if user dismissed recently
        const dismissed = localStorage.getItem('smart_banner_dismissed');
        if (dismissed && Date.now() - parseInt(dismissed) < this.config.dismissDuration) {
            return false;
        }
        
        return true;
    }
    
    createBanner() {
        const banner = document.createElement('div');
        banner.id = 'smart-banner';
        banner.innerHTML = this.getBannerHTML();
        
        // Insert at top of body
        document.body.insertBefore(banner, document.body.firstChild);
        
        // Add margin to body to account for banner
        document.body.style.marginTop = '70px';
    }
    
    getBannerHTML() {
        const appStoreUrl = this.isIOS ? this.config.iosAppStoreUrl : this.config.androidPlayStoreUrl;
        const platform = this.isIOS ? 'iOS' : 'Android';
        
        return `
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                background: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
                padding: 10px 15px;
                z-index: 9999;
                display: flex;
                align-items: center;
                justify-content: space-between;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 14px;
            ">
                <div style="display: flex; align-items: center;">
                    <div style="
                        width: 40px;
                        height: 40px;
                        background: #667eea;
                        border-radius: 8px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin-right: 12px;
                        font-size: 20px;
                    ">🍽️</div>
                    <div>
                        <div style="font-weight: 600; color: #333;">${this.config.appName}</div>
                        <div style="color: #666; font-size: 12px;">${this.config.appDescription}</div>
                    </div>
                </div>
                <div style="display: flex; gap: 8px;">
                    <a href="${appStoreUrl}" style="
                        background: #667eea;
                        color: white;
                        padding: 8px 16px;
                        border-radius: 6px;
                        text-decoration: none;
                        font-weight: 500;
                        font-size: 12px;
                    ">GET</a>
                    <button id="smart-banner-close" style="
                        background: none;
                        border: none;
                        color: #666;
                        font-size: 18px;
                        cursor: pointer;
                        padding: 0;
                        width: 24px;
                        height: 24px;
                    ">×</button>
                </div>
            </div>
        `;
    }
    
    setupEventListeners() {
        const closeButton = document.getElementById('smart-banner-close');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                this.dismiss();
            });
        }
    }
    
    dismiss() {
        const banner = document.getElementById('smart-banner');
        if (banner) {
            banner.remove();
            document.body.style.marginTop = '';
        }
        
        // Remember dismissal
        localStorage.setItem('smart_banner_dismissed', Date.now().toString());
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Get configuration from page data
    const config = window.deepLinkConfig || {};
    
    // Initialize deep link manager
    window.deepLinkManager = new DeepLinkManager(config);
    
    // Initialize smart banner if enabled
    if (config.enableSmartBanner !== false) {
        window.smartBanner = new SmartBanner(config);
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DeepLinkManager, SmartBanner };
}
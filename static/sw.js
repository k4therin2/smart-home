/**
 * Smart Home Assistant - Service Worker
 *
 * Provides offline support, caching, and push notification handling.
 * Part of PWA implementation for mobile-optimized experience.
 */

const CACHE_NAME = 'smarthome-v1';
const CACHE_URLS = [
    '/',
    '/static/style.css',
    '/static/app.js',
    '/static/icons/icon.svg',
    '/manifest.json'
];

// API requests that should never be cached
const NO_CACHE_PATTERNS = [
    '/api/command',
    '/api/status',
    '/api/history',
    '/api/csrf-token',
    '/api/notifications'
];

/**
 * Install Event - Cache static assets
 */
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Installing...');

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[ServiceWorker] Caching app shell');
                return cache.addAll(CACHE_URLS);
            })
            .then(() => {
                // Activate immediately, don't wait for old SW to close
                return self.skipWaiting();
            })
    );
});

/**
 * Activate Event - Clean up old caches
 */
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activating...');

    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== CACHE_NAME)
                        .map((name) => {
                            console.log('[ServiceWorker] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                // Take control of all pages immediately
                return self.clients.claim();
            })
    );
});

/**
 * Fetch Event - Serve from cache, fallback to network
 *
 * Strategy: Cache-First for static assets, Network-First for API calls
 */
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    // Check if this is an API request that shouldn't be cached
    const isApiRequest = NO_CACHE_PATTERNS.some(pattern =>
        url.pathname.includes(pattern)
    );

    if (isApiRequest) {
        // Network-first for API requests
        event.respondWith(networkFirst(event.request));
    } else {
        // Cache-first for static assets
        event.respondWith(cacheFirst(event.request));
    }
});

/**
 * Cache-First Strategy
 * Try cache first, fall back to network
 */
async function cacheFirst(request) {
    const cachedResponse = await caches.match(request);

    if (cachedResponse) {
        // Return cached version, but update cache in background
        fetchAndCache(request);
        return cachedResponse;
    }

    return fetchAndCache(request);
}

/**
 * Network-First Strategy
 * Try network first, fall back to cache
 */
async function networkFirst(request) {
    try {
        const response = await fetch(request);
        return response;
    } catch (error) {
        // Network failed, try cache as fallback
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }

        // Return offline fallback for navigation requests
        if (request.mode === 'navigate') {
            return caches.match('/');
        }

        throw error;
    }
}

/**
 * Fetch and update cache
 */
async function fetchAndCache(request) {
    try {
        const response = await fetch(request);

        // Only cache successful responses
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }

        return response;
    } catch (error) {
        console.error('[ServiceWorker] Fetch failed:', error);
        throw error;
    }
}

/**
 * Push Event - Handle push notifications from server
 */
self.addEventListener('push', (event) => {
    console.log('[ServiceWorker] Push received');

    let data = {
        title: 'Smart Home Alert',
        body: 'You have a new notification',
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/icon-72.png'
    };

    if (event.data) {
        try {
            data = { ...data, ...event.data.json() };
        } catch (error) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: data.icon,
        badge: data.badge,
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1,
            url: data.url || '/'
        },
        actions: [
            {
                action: 'open',
                title: 'Open App',
                icon: '/static/icons/icon-72.png'
            },
            {
                action: 'dismiss',
                title: 'Dismiss'
            }
        ],
        tag: data.tag || 'smarthome-notification',
        renotify: true
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

/**
 * Notification Click Event - Handle notification interactions
 */
self.addEventListener('notificationclick', (event) => {
    console.log('[ServiceWorker] Notification clicked');

    event.notification.close();

    if (event.action === 'dismiss') {
        return;
    }

    // Open the app or focus existing window
    const urlToOpen = event.notification.data?.url || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((windowClients) => {
                // Check if there's already a window open
                for (const client of windowClients) {
                    if (client.url.includes(self.location.origin) && 'focus' in client) {
                        client.navigate(urlToOpen);
                        return client.focus();
                    }
                }

                // Open new window if none found
                if (clients.openWindow) {
                    return clients.openWindow(urlToOpen);
                }
            })
    );
});

/**
 * Message Event - Handle messages from the main thread
 */
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }

    if (event.data && event.data.type === 'CACHE_URLS') {
        const urls = event.data.urls;
        event.waitUntil(
            caches.open(CACHE_NAME).then((cache) => cache.addAll(urls))
        );
    }
});

const CACHE = 'gesture-ctrl-v1';

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(['/']))
  );
});

self.addEventListener('fetch', e => {
  // Don't cache video feed or API calls
  if (e.request.url.includes('/video_feed') || e.request.url.includes('/api/')) {
    return fetch(e.request);
  }
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});

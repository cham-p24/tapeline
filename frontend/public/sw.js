/**
 * Tapeline Service Worker — handles incoming Web Push notifications.
 *
 * Browsers (Chrome, Firefox, Edge, iOS Safari with PWA install) call this
 * worker when the push service delivers a payload. We render a notification,
 * and on click we open the URL embedded in the payload.
 *
 * Payload shape (sent by backend services/web_push.py):
 *   {"title": "...", "body": "...", "url": "/app/scanner"}
 */

self.addEventListener("install", (event) => {
  // Activate immediately on first install rather than waiting for next tab close
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Take control of any open Tapeline tabs immediately
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "Tapeline", body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "Tapeline";
  const opts = {
    body: data.body || "",
    icon: "/favicon.svg",
    badge: "/favicon.svg",
    tag: data.tag || "tapeline-alert",
    data: { url: data.url || "/app/scanner" },
    requireInteraction: false,
  };
  event.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/app/scanner";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      // If a Tapeline tab is already open, focus it and navigate
      for (const client of clientList) {
        if ("focus" in client && client.url.includes(self.location.origin)) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      // Otherwise open a new tab
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })
  );
});

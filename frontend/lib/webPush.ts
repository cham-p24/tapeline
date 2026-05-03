/**
 * Web Push subscription helpers — registers the Service Worker, requests
 * notification permission, subscribes via pushManager, and POSTs the
 * resulting subscription to /api/me/push.
 *
 * iOS Safari note: only works on installed PWAs (16.4+). Will throw on
 * non-installed iOS Safari — caller should catch and surface the install hint.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const buf = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
  return buf;
}

export async function isWebPushSupported(): Promise<boolean> {
  return (
    typeof window !== "undefined"
    && "serviceWorker" in navigator
    && "PushManager" in window
    && "Notification" in window
  );
}

export async function getWebPushStatus(): Promise<"granted" | "denied" | "default" | "unsupported"> {
  if (!(await isWebPushSupported())) return "unsupported";
  return Notification.permission;
}

export async function subscribeToWebPush(): Promise<{ ok: true } | { ok: false; reason: string }> {
  if (!(await isWebPushSupported())) {
    return { ok: false, reason: "Your browser doesn't support web push (try Chrome, Firefox, or Edge)" };
  }

  // Step 1: register the Service Worker
  let registration: ServiceWorkerRegistration;
  try {
    registration = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;
  } catch (e: any) {
    return { ok: false, reason: `Service worker failed to register: ${e.message}` };
  }

  // Step 2: request notification permission
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    return { ok: false, reason: "You denied notification permission. Re-enable in browser settings to retry." };
  }

  // Step 3: get the VAPID public key from the backend
  const vapidRes = await fetch(`${API_BASE}/api/me/vapid`, { credentials: "include", cache: "no-store" });
  const vapidBody = await vapidRes.json();
  const publicKey: string = vapidBody.public_key || "";
  if (!publicKey) {
    return { ok: false, reason: "Web push isn't configured server-side (VAPID keys not set). Tell the operator." };
  }

  // Step 4: subscribe via pushManager
  let subscription: PushSubscription;
  try {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      // Cast to BufferSource — newer TS narrows Uint8Array<ArrayBufferLike>
      // away from the expected BufferSource union here
      applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
    });
  } catch (e: any) {
    return { ok: false, reason: `Push subscribe failed: ${e.message}` };
  }

  // Step 5: POST the subscription to the backend
  const subJson = subscription.toJSON();
  const post = await fetch(`${API_BASE}/api/me/push`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: subJson.endpoint,
      keys: subJson.keys,
      user_agent: navigator.userAgent,
    }),
  });
  if (!post.ok) {
    const body = await post.json().catch(() => ({} as any));
    return { ok: false, reason: body.detail || `Server rejected subscription (${post.status})` };
  }

  return { ok: true };
}

export async function unsubscribeFromWebPush(): Promise<{ ok: true } | { ok: false; reason: string }> {
  if (!(await isWebPushSupported())) return { ok: false, reason: "unsupported" };
  const reg = await navigator.serviceWorker.getRegistration();
  if (!reg) return { ok: true };
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return { ok: true };
  const endpoint = sub.endpoint;
  await sub.unsubscribe();
  await fetch(`${API_BASE}/api/me/push?endpoint=${encodeURIComponent(endpoint)}`, {
    method: "DELETE",
    credentials: "include",
  });
  return { ok: true };
}

export async function testWebPush(): Promise<{ ok: true; delivered: number; total: number } | { ok: false; reason: string }> {
  const r = await fetch(`${API_BASE}/api/me/push/test`, { method: "POST", credentials: "include" });
  const body = await r.json();
  if (!r.ok) return { ok: false, reason: body.detail || `${r.status}` };
  return { ok: true, delivered: body.delivered, total: body.total };
}

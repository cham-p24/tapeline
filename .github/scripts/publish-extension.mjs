/**
 * Upload (and optionally publish) the extension to the Chrome Web Store.
 *
 * No dependencies — Node 20's fetch is enough, and adding an npm package to a
 * job that handles publishing credentials is a supply-chain surface we don't
 * need.
 *
 * Credentials (repo secrets, see docs/CHROME_WEB_STORE_SETUP.md):
 *   CWS_CLIENT_ID       OAuth client id      (Google Cloud console)
 *   CWS_CLIENT_SECRET   OAuth client secret
 *   CWS_REFRESH_TOKEN   long-lived refresh token for the developer account
 *   CWS_EXTENSION_ID    the item id, from the store dashboard URL
 *
 * Env:
 *   ZIP_PATH            path to the packaged extension
 *   PUBLISH_TARGET      "none" (upload only) | "trustedTesters" | "default"
 *
 * DEFAULT IS UPLOAD-ONLY, deliberately. Since Chrome 117 a policy takedown
 * turns the entire install base into a one-click "Remove" prompt via Safety
 * Check, so the cost of publishing something wrong is much higher than the cost
 * of a human glancing at the draft first.
 */

const {
  CWS_CLIENT_ID,
  CWS_CLIENT_SECRET,
  CWS_REFRESH_TOKEN,
  CWS_EXTENSION_ID,
  ZIP_PATH = "extension.zip",
  PUBLISH_TARGET = "none",
} = process.env;

const API = "https://www.googleapis.com/chromewebstore/v1.1";
const UPLOAD = "https://www.googleapis.com/upload/chromewebstore/v1.1";

function die(msg, extra) {
  console.error(`\n✖ ${msg}`);
  if (extra) console.error(typeof extra === "string" ? extra : JSON.stringify(extra, null, 2));
  process.exit(1);
}

function requireEnv() {
  const missing = ["CWS_CLIENT_ID", "CWS_CLIENT_SECRET", "CWS_REFRESH_TOKEN", "CWS_EXTENSION_ID"]
    .filter((k) => !process.env[k]);
  if (missing.length) {
    die(
      `Missing secret(s): ${missing.join(", ")}`,
      "Add them under Settings → Secrets and variables → Actions.\n" +
        "See docs/CHROME_WEB_STORE_SETUP.md for how to generate each one."
    );
  }
}

/** Refresh tokens don't expire on their own, but access tokens last ~1 hour. */
async function accessToken() {
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: CWS_CLIENT_ID,
      client_secret: CWS_CLIENT_SECRET,
      refresh_token: CWS_REFRESH_TOKEN,
      grant_type: "refresh_token",
    }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || !body.access_token) {
    die(
      "Could not exchange the refresh token for an access token.",
      body.error === "invalid_grant"
        ? "invalid_grant usually means the refresh token was revoked, or it was " +
          "issued for a different OAuth client than CWS_CLIENT_ID. Regenerate it " +
          "following docs/CHROME_WEB_STORE_SETUP.md."
        : body
    );
  }
  return body.access_token;
}

async function upload(token, zip) {
  console.log(`→ uploading ${zip.byteLength.toLocaleString()} bytes to item ${CWS_EXTENSION_ID}`);
  const res = await fetch(`${UPLOAD}/items/${CWS_EXTENSION_ID}?uploadType=media`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "x-goog-api-version": "2",
      "Content-Type": "application/zip",
    },
    body: zip,
  });
  const body = await res.json().catch(() => ({}));

  if (body.uploadState === "SUCCESS") {
    console.log("✓ upload accepted — the draft in the dashboard is now this build");
    return;
  }

  // The API reports rejections in-band with HTTP 200, so status alone is not
  // enough to tell whether this worked.
  const errs = body.itemError || [];
  const versionClash = errs.some((e) => /version/i.test(e.error_detail || ""));
  die(
    `Upload rejected (uploadState=${body.uploadState || res.status}).`,
    versionClash
      ? "The version in extension/manifest.json must be HIGHER than the one " +
        "already in the store. Bump it and re-run.\n\n" +
        JSON.stringify(errs, null, 2)
      : errs.length
        ? errs
        : body
  );
}

async function publish(token, target) {
  console.log(`→ publishing to "${target}"`);
  const res = await fetch(`${API}/items/${CWS_EXTENSION_ID}/publish`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "x-goog-api-version": "2",
      "Content-Length": "0",
    },
  });
  const body = await res.json().catch(() => ({}));
  const status = body.status || [];

  if (!res.ok) die(`Publish failed (HTTP ${res.status}).`, body);

  // OK and the friction warning are both successes; the warning just means a
  // human reviewer will look at it before it goes fully live.
  const good = status.some((s) =>
    ["OK", "PUBLISHED_WITH_FRICTION_WARNING", "ITEM_PENDING_REVIEW"].includes(s)
  );
  console.log(`   status: ${status.join(", ") || "(none)"}`);
  if (body.statusDetail?.length) console.log(`   detail: ${body.statusDetail.join(" | ")}`);

  if (!good) {
    die(
      "Publish did not succeed.",
      status.includes("ITEM_NOT_UPDATABLE")
        ? "ITEM_NOT_UPDATABLE means the item is already in review. Wait for that " +
          "review to finish before publishing again."
        : body
    );
  }
  console.log("✓ published (Chrome review can still take days — check the dashboard)");
}

async function main() {
  requireEnv();

  const { readFile } = await import("node:fs/promises");
  let zip;
  try {
    zip = await readFile(ZIP_PATH);
  } catch {
    die(`Could not read the package at ${ZIP_PATH}. Did the packaging step run?`);
  }

  const token = await accessToken();
  await upload(token, zip);

  if (PUBLISH_TARGET === "none") {
    console.log(
      "\nUpload only — nothing was published.\n" +
        "Review the draft at https://chrome.google.com/webstore/devconsole, then " +
        "re-run this workflow with publish=default to make it live."
    );
    return;
  }
  await publish(token, PUBLISH_TARGET);
}

main().catch((err) => die("Unexpected failure.", err?.stack || String(err)));

# Chrome Web Store — setup and publishing

Publishing a new version is one GitHub Action run. Getting to that point needs a
handful of one-time human steps, because the store dashboard refuses automation
("The extensions gallery cannot be scripted") and the Chrome Web Store API can only
update an item that already exists.

The Google Cloud half of this is **already done** (section 2 is a record of it, not a
to-do). What is left is the store dashboard and one refresh token.

---

## State of play — 2026-08-23

| Secret | Status |
|---|---|
| `CWS_CLIENT_ID` | **set** in repo secrets |
| `CWS_CLIENT_SECRET` | **set** in repo secrets |
| `CWS_REFRESH_TOKEN` | **missing** — mint it with section 3 |
| `CWS_EXTENSION_ID` | **missing** — does not exist until the store item is created, section 1 |

Already true:

- Google Cloud project **`tapeline-extension`**, Chrome Web Store API enabled on it.
- OAuth client **`tapeline-publisher`**, type **Desktop app**.
  Client ID `855150440398-10nadfi7f16q1nu6020d056gaii4h983.apps.googleusercontent.com`
  (client IDs are not secret; the secret is).
- Consent screen publishing status: **In production** (deliberately — see 2.3).
- Listing copy, final, written: `C:/Tapeline/CHROME_STORE_LISTING.md`
- Package ready to upload: `C:/Tapeline/tapeline-extension-v1.2.1.zip`
  (verified: `manifest.json` at the archive root, 11 files, no dev artefacts)

**Next action:** section 1 — pay the US$5 registration fee, create the item, paste the
listing copy, upload that zip, copy the item ID. Nothing else can proceed until the
item exists.

**Read section 6 before you start.** The API this pipeline uses is switched off on
15 October 2026, which is 53 days from today.

---

## What can and cannot be automated

Cannot, ever — a human does these once:

- Registering as a Chrome Web Store developer, including the **US$5 one-off fee**.
- **Creating** the store item. Neither v1 nor v2 of the API can create one.
- Listing copy: description, category, permission justifications, privacy answers.
- Screenshots and promo images.
- The Google account consent click that mints the refresh token (section 3).

Can, from then on — the workflow does these with no dashboard visit:

- Package `extension/` into `extension.zip`.
- Sanity-check the manifest before wasting review days on a rejection.
- Upload the new version over the existing item.
- Optionally publish it live.

---

## 1. Register, create the item, get its ID

1. Go to <https://chrome.google.com/webstore/devconsole> and sign in with the Google
   account that should **own** the extension. Use an account you control long-term —
   moving an item between accounts later is a support ticket, not a setting.
   It does **not** have to be the account that owns the `tapeline-extension` Cloud
   project; that project only hosts the OAuth client, and nothing binds project
   ownership to store-item ownership. What must match is section 3: the account you
   click **Allow** with there has to be this same store-owner account, because that is
   the identity the refresh token carries.
2. Turn on **hardware-key 2FA** on that account before anything else. Extension
   developer accounts are actively phished; the Cyberhaven compromise (~400,000 users)
   started with a "your extension violates policy" email. Treat any such email as
   phishing until you have confirmed it inside the dashboard.
3. Pay the one-off **US$5** registration fee.
4. **Add new item** → upload `C:/Tapeline/tapeline-extension-v1.2.1.zip`.
5. Fill the listing from `C:/Tapeline/CHROME_STORE_LISTING.md` — description, category,
   privacy answers, and the per-permission justifications. Do not improvise these; the
   justifications are the part that gets a submission rejected.
   Note the manifest declares `optional_host_permissions: ["https://*/*"]`. A reviewer
   will ask about it. The justification for it is in the listing file.
6. Upload the screenshots.
7. **Save draft. Do not submit yet.**
8. Copy the **item ID** — the 32-character string in the dashboard URL:
   `.../devconsole/.../<THIS-32-CHAR-ID>/edit`. That is `CWS_EXTENSION_ID`.

### 1.1 If you need to rebuild the zip by hand

The committed workflow builds the package, but the workflow needs `CWS_EXTENSION_ID`,
which needs the item, which needs a package — so the first one is built locally.

This mirrors the packaging step in `.github/workflows/publish-extension.yml` (stage a
copy, delete dev files, zip), so the *contents* match what CI would produce: same 11
files, same layout, `manifest.json` at the root. The **bytes will not match** — zip
embeds per-entry timestamps and a creator-version byte, so a local build and a CI build
never hash the same. Verify by comparing the `unzip -l` file list, never by checksum.

Git Bash on Windows ships `unzip` but **not** `zip`, so the archive step shells out to
PowerShell 7:

```bash
cd "$(git rev-parse --show-toplevel)"
git status -sb | head -1     # confirm an up-to-date branch, not a stale detached HEAD
rm -rf build extension.zip && mkdir -p build
cp -r extension/. build/
rm -f build/test-detection.js build/icons/make-icons.js build/.storeignore build/README.md
pwsh -NoProfile -Command "Compress-Archive -Path 'build/*' -DestinationPath 'extension.zip' -Force"
unzip -l extension.zip       # expect 11 files, manifest.json at the root, no build/ prefix
```

Two things that matter about that `pwsh` line:

- It must be **`pwsh`** (PowerShell 7), not `powershell` (Windows PowerShell 5.1).
  5.1's `Compress-Archive` writes backslash path separators, which the store rejects.
  Verified on this machine: pwsh 7.6.5 produces forward slashes with `manifest.json` at
  the root, 11 entries, byte-for-byte the same file list as
  `C:/Tapeline/tapeline-extension-v1.2.1.zip`.
- On Linux or macOS, `cd build && zip -rq ../extension.zip . && cd ..` does the same
  job — that is exactly what the CI runner does, and CI has `zip` installed.

Do **not** upload a downloaded GitHub artifact directly. The artifact is named
`tapeline-extension-v<VERSION>` and *contains* `extension.zip`, so the download is a zip
inside a zip and the store rejects it with "manifest.json not at root". Unzip once first.

---

## 2. Google Cloud — done, recorded here

Do not redo this. It exists. This section is what was configured and, more usefully,
the three things that wasted an hour.

Current config:

- Project `tapeline-extension`, **Chrome Web Store API** enabled (APIs & Services →
  Library — that path is still accurate).
- OAuth client `tapeline-publisher`, type **Desktop app**.
- Scope in use: `https://www.googleapis.com/auth/chromewebstore` (full read/write; the
  `.readonly` variant cannot upload).
- Publishing status: **In production**.

Navigation note: the consent-screen settings are no longer under "APIs & Services →
OAuth consent screen". They live under **Google Auth Platform**, split into
**Branding / Audience / Clients / Data Access**. Test users are under **Audience**;
OAuth clients are under **Clients**.

### 2.1 Trap: the Branding banner silently discards Test users

If the OAuth config is incomplete — App name blank, or App-domain URLs filled in
without a matching entry under **Authorized domains** — the **Audience** page shows:

> Your app's OAuth configuration is incomplete... Please visit the Branding page

While that banner is up, adding **Test users** *appears to save* and the list stays at
0. No error. Fix **Branding** first, then Audience.

### 2.2 Trap: client secrets cannot be read after creation

The client detail page shows only a masked suffix. There is no "download JSON" that
recovers a lost secret. If it is lost:

- Client → **Add secret**. A client holds **at most 2 secrets**; to add a third you must
  disable and delete one first.
- Refresh tokens bind to the **client_id**, not the secret. A refresh token minted under
  secret A keeps working after A is deleted, as long as another valid secret exists and
  `CWS_CLIENT_SECRET` matches one that is live.
- If you rotate the secret in GitHub, update `CWS_CLIENT_SECRET` only — the existing
  `CWS_REFRESH_TOKEN` stays valid.

### 2.3 Why the app is "In production", and what you will see

Even with Branding complete, Test users would not persist in this project. The fix was
**Audience → Publish app → Confirm**, moving publishing status from *Testing* to
*In production*. Two consequences, both good:

- The test-user allowlist requirement disappears entirely.
- Refresh tokens stop expiring after 7 days. Google expires refresh tokens issued to
  external apps in **Testing** status after 7 days — that is the classic "CI worked for
  a week then started returning `invalid_grant`" failure. In production, they do not
  expire on their own.

The cost: the app is unverified, so the consent screen shows **"Google hasn't verified
this app"**. Click **Advanced → Go to \<App name\> (unsafe) → Allow**.

\<App name\> is whatever is set on the **Branding** page of Google Auth Platform —
*not* the OAuth client name `tapeline-publisher`, which is a different field on a
different page. If you want to know in advance what that link will say, read Branding
first. Clicking through is expected and fine here: you are the owner of the project
granting your own publishing token to your own account. It is also **reversible**:
Audience → **Back to testing**.

Remaining refresh-token lifetime limits, for the record: a token dies after **6 months
of non-use**, and there is a cap of **100 refresh tokens per Google account per client
ID** — minting number 101 silently invalidates the oldest.

---

## 3. Mint the refresh token

One-time. Run this on your own machine, signed into the browser as the store-owner
account.

If you would rather not hold a refresh token at all, read section 6 first — the v2 API
supports service accounts and removes this whole section. What follows is the path that
works with the code committed today.

**The out-of-band flow (`redirect_uri=urn:ietf:wg:oauth:2.0:oob`) is dead.** Google
blocked it for new clients in February 2022 and for all clients by January 2023. Any
guide that tells you to copy a code off a Google page is stale; on a client created
today it returns an error page, not a code. The working flow for a Desktop-app client
is a **loopback redirect** caught by a local listener.

1. Save this as `mint-token.mjs` somewhere outside the repo (it prints an auth code —
   keep it out of git):

```js
// mint-token.mjs — run once:  node mint-token.mjs
//                  or:        PORT=8791 node mint-token.mjs   (if 8765 is taken)
import { createServer } from "node:http";
import { randomBytes } from "node:crypto";

const CLIENT_ID = "855150440398-10nadfi7f16q1nu6020d056gaii4h983.apps.googleusercontent.com";
const PORT = Number(process.env.PORT || 8765);
const HOST = "127.0.0.1";                    // Google documents the loopback redirect as
const REDIRECT = `http://${HOST}:${PORT}`;   // 127.0.0.1 or [::1]. The `localhost` hostname
                                             // is ambiguous across IP stacks and can trip
                                             // client firewalls — see the listen() note.
const state = randomBytes(16).toString("hex");

const authUrl =
  "https://accounts.google.com/o/oauth2/v2/auth?" +
  new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT,
    response_type: "code",
    scope: "https://www.googleapis.com/auth/chromewebstore",
    access_type: "offline",
    prompt: "consent",
    state,
  });

let done = false;

const server = createServer((req, res) => {
  const url = new URL(req.url, REDIRECT);

  // Chrome asks for /favicon.ico immediately after landing on the callback page, over
  // the same keep-alive connection. Without this guard that request re-enters the
  // handler with no `state` and prints a bogus "state mismatch" under the real code.
  if (url.pathname !== "/" || done) {
    res.writeHead(404, { "Content-Type": "text/plain", Connection: "close" });
    res.end("not the callback");
    return;
  }

  const q = url.searchParams;
  res.writeHead(200, { "Content-Type": "text/plain", Connection: "close" });

  if (q.get("error")) {
    res.end(`error: ${q.get("error")}`);
    console.error("DENIED:", q.get("error"));
  } else if (q.get("state") !== state) {
    res.end("state mismatch - start again");
    console.error("state mismatch - discarded; still listening");
    return;                                  // stay up: that was not the real callback
  } else {
    res.end("Code received. Close this tab.");
    console.log("\nAUTH CODE (single use, expires in minutes):\n" + q.get("code") + "\n");
  }

  done = true;
  server.close(() => process.exit(0));
});

// Bind ONE explicit address so a port collision surfaces as a real error. With no host
// argument Node binds dual-stack and will happily take [::]:PORT while another process
// already owns 127.0.0.1:PORT — no EADDRINUSE, no error, and the browser hands the code
// to that other process while this terminal waits forever.
server.on("error", (e) => {
  console.error(e.code === "EADDRINUSE"
    ? `Port ${PORT} is already taken. Re-run on a free one: PORT=8791 node mint-token.mjs`
    : e);
  process.exit(1);
});

server.listen(PORT, HOST, () => {
  console.log("Open this in the browser signed in as the store owner:\n\n" + authUrl + "\n");
});
```

2. Check the port is free, then run it:

```bash
pwsh -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen"   # expect nothing
node mint-token.mjs
```

   If something else holds the port, pick another: `PORT=8791 node mint-token.mjs`.
   Whatever port you land on must be used consistently in steps 3–5. A Desktop-app
   client accepts any loopback port without pre-registering it, but the auth URL and the
   token exchange have to agree.

3. Open the printed URL. Pick the store-owner account. At **"Google hasn't verified this
   app"**, click **Advanced → Go to \<App name\> (unsafe)** — 2.3 explains where that
   name comes from — then **Allow**.
4. The browser lands on `http://127.0.0.1:8765/?code=...`; the terminal prints the code
   and the server exits.
5. Exchange the code within a couple of minutes — it is single-use, and a retry means
   starting again at step 2:

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
  -d client_id=855150440398-10nadfi7f16q1nu6020d056gaii4h983.apps.googleusercontent.com \
  --data-urlencode "client_secret=$CLIENT_SECRET" \
  -d code=THE_CODE_FROM_STEP_4 \
  -d grant_type=authorization_code \
  -d redirect_uri=http://127.0.0.1:8765
```

`redirect_uri` must byte-match the one in the auth URL, or you get `redirect_uri_mismatch`
— including the port, if you changed it in step 2.
`access_type=offline` and `prompt=consent` are what make Google return a
`refresh_token` at all — without them you get an access token only, which is the most
common way this step silently goes wrong.

The `refresh_token` field in the response is `CWS_REFRESH_TOKEN`.

6. Verify it before pasting it into GitHub. This is the exact call
   `.github/scripts/publish-extension.mjs` makes on every run:

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
  -d client_id=855150440398-10nadfi7f16q1nu6020d056gaii4h983.apps.googleusercontent.com \
  --data-urlencode "client_secret=$CLIENT_SECRET" \
  --data-urlencode "refresh_token=$REFRESH_TOKEN" \
  -d grant_type=refresh_token
```

An `access_token` in the response means CI will work. `invalid_grant` means it will not.

Both snippets read `$CLIENT_SECRET` and `$REFRESH_TOKEN` from shell variables on
purpose: a secret typed directly on a command line lands in shell history and is visible
in `ps` to every process on the machine. Set the variables with a leading space so the
assignment itself is not recorded, clear the history line afterwards, and never commit
these values or paste them into an issue, a PR, or a chat.

---

## 4. Add the secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**. Names are
read verbatim by `publish-extension.mjs` and must match exactly:

| Secret | Value | Status |
|---|---|---|
| `CWS_CLIENT_ID` | the `tapeline-publisher` client ID | already set |
| `CWS_CLIENT_SECRET` | its client secret (section 2.2 if lost) | already set |
| `CWS_REFRESH_TOKEN` | from section 3 | **to do** |
| `CWS_EXTENSION_ID` | the 32-char item ID from section 1 step 8 | **to do** |

The script fails fast and names any that are missing, so a typo shows up in the first
few seconds of the run rather than halfway through an upload.

---

## 5. Publishing, from then on

1. Bump `version` in `extension/manifest.json`. It must be strictly higher than what is
   in the store; the API rejects anything else.

   **Note for the very first run:** section 1 step 4 puts version **1.2.1** into the
   store, and the repo manifest is still **1.2.1**. So the first workflow run must ship
   **1.2.2 or higher** — including a run you only intend as a `publish: none` smoke test
   of the secrets. Bump before you test, or the run fails on the version clash and tells
   you nothing about whether the refresh token works.
2. Merge that.
3. **Actions → Publish extension → Run workflow**, and choose `publish`:

| `publish` | What actually happens |
|---|---|
| `none` *(default)* | Uploads and replaces the draft. Nothing goes live. Review it in the dashboard, then re-run with `default`. |
| `trustedTesters` | **Publishes publicly — same as `default`.** See the warning below. |
| `default` | Live to everyone, subject to Chrome review. |

**`trustedTesters` does not work as labelled.** `publish()` in
`.github/scripts/publish-extension.mjs` POSTs to `/items/{id}/publish` with no
`publishTarget`, so the API applies its default — public. Selecting `trustedTesters`
loses you exactly the safety property you selected it for. Until that call passes
`?publishTarget=${target}`, treat the option as broken and do not use it.

Upload-only is the default deliberately. Since Chrome 117 a policy takedown turns the
whole install base into a one-click "Remove" prompt via Safety Check, so shipping
something wrong costs far more than a human glancing at the draft first. For the same
reason the workflow is `workflow_dispatch` only and never runs on push.

What the run does, in order (`.github/workflows/publish-extension.yml`):

1. Prints name and version from the manifest.
2. Sanity-checks the manifest: `manifest_version` is 3, numeric dotted version, name
   ≤45 chars, description ≤132 chars, every declared icon file exists, no `tabs`
   permission, no `host_permissions` entry containing the literal `*://*/*`.
   Be precise about that last check: it reads **only** `host_permissions`, and only that
   literal substring. It does not look at `optional_host_permissions` (this manifest has
   `https://*/*` there), `content_scripts[].matches`, or `web_accessible_resources`.
   Passing this step is not a guarantee the reviewer will be happy.
3. Packages by staging a copy of `extension/` and deleting `test-detection.js`,
   `icons/make-icons.js`, `.storeignore`, `README.md` — then verifies none of them
   leaked, and greps the listing for `manifest.json`.
   Be precise about that second check too: it is a bare substring match over the whole
   `unzip -l` output, so an archive containing `build/manifest.json` would pass it
   cleanly. It does **not** prove the manifest sits at the archive root. The packaging
   step is what puts it there. If you ever hand-build a zip (1.1), check the root
   yourself with `unzip -l`.
4. Uploads `extension.zip` (env `ZIP_PATH`) and applies `PUBLISH_TARGET`.
5. Keeps the exact uploaded bytes as artifact `tapeline-extension-v<VERSION>` for
   **90 days**, even if the publish step failed (`if: always()`).

Chrome review still takes days. The workflow finishing is not the same as the version
being live — check the dashboard.

---

## 6. Deadline: the API this uses dies 15 October 2026

`publish-extension.mjs` targets Chrome Web Store API **v1.1**
(`https://www.googleapis.com/chromewebstore/v1.1` and the matching `/upload` host).
Google deprecated v1 and supports it only until **15 October 2026**.

That is **53 days away as of 2026-08-23**. Everything in section 5 stops working on that
date, and Chrome review alone takes days — so treat the v2 migration as in-scope for
this quarter, not "later".

Practical consequence for today: if you would rather not mint a refresh token at all,
skip section 3 and go straight to v2 with a **service account** — no consent screen, no
unverified-app interstitial, no token to re-mint and none to expire. Otherwise mint the
token, ship the first version, and schedule the v2 migration before October.

What migrating involves:

- A new base URL, with the publisher ID as a **path segment** in every call:
  `https://chromewebstore.googleapis.com/v2/publishers/{publisherId}/items/...`, plus a
  separate upload host `https://chromewebstore.googleapis.com/upload/v2/publishers/`.
- New method shapes — `:upload`, `:publish`, `:fetchStatus`, plus additions such as
  `:cancelSubmission` and `:setPublishedDeployPercentage`.
- A **publisher ID**, which v1 did not need at all. Find it in the Developer Dashboard.
- Service-account auth instead of the refresh-token dance, if you want it.

v2 still cannot **create** items, so section 1 stays a manual, human step either way.

One smaller note on the current script: it sends `x-goog-api-version: 2`, which the live
v1 reference no longer mentions — harmless, and never the cause of a failure, so do not
go chasing it. And the v1 API reports upload rejections **in-band with HTTP 200**, which
is why the script inspects `uploadState` rather than trusting the status code.

---

## When it goes wrong

| Symptom | Cause and fix |
|---|---|
| `bash: zip: command not found` while hand-building the zip | Git Bash on Windows ships `unzip` but not `zip`. Use the `pwsh -NoProfile -Command "Compress-Archive ..."` line in 1.1. |
| Hand-built zip rejected for backslash paths | You used `powershell` (5.1) instead of `pwsh` (7). Only PowerShell 7's `Compress-Archive` writes forward slashes. |
| Auth URL shows "app is blocked" / `invalid_request` | You used the retired `urn:ietf:wg:oauth:2.0:oob` redirect. Use the loopback flow in section 3. |
| `redirect_uri_mismatch` at the token exchange | The `redirect_uri` in step 5 does not byte-match the one in the auth URL. Both must be `http://127.0.0.1:8765` — same scheme, same host literal, same port. |
| Browser hangs at `127.0.0.1:8765`, terminal never prints a code | Another process owns that port. Node does **not** raise `EADDRINUSE` when it can still bind the other IP stack, so a listener created without an explicit host silently splits and re-running changes nothing. The script in section 3 binds `127.0.0.1` explicitly and errors properly. Check with `pwsh -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen"`, then re-run on a free port: `PORT=8791 node mint-token.mjs`. Use that same port in the step 5 `redirect_uri`. |
| Terminal prints "state mismatch" straight after the code | An older copy of the script with no path guard: Chrome's `/favicon.ico` request re-enters the handler over the same keep-alive connection. The version above 404s anything that is not `/`. |
| "Google hasn't verified this app" | Expected — the app is unverified by design. **Advanced → Go to \<App name\> (unsafe) → Allow**, where \<App name\> is the Branding-page name, not the client name `tapeline-publisher` (2.3). |
| `access_denied` | You clicked Cancel, or you are signed into the wrong Google account. Not a Test-users problem — the app is In production and has no allowlist. |
| No `refresh_token` in the step 5 response | `access_type=offline` or `prompt=consent` was missing, or you had already consented. Re-run with both. |
| `invalid_grant` in CI | The refresh token was revoked; or it was minted under a different client than `CWS_CLIENT_ID`; or the project got moved **back to Testing** (7-day expiry); or 6 months of non-use. Confirm Audience still says *In production*, then re-mint via section 3. |
| Test users will not save | The Branding banner (2.1). Fix Branding, or ignore it — production status makes test users unnecessary. |
| Client secret lost | It cannot be read back. Client → **Add secret** (max 2), update `CWS_CLIENT_SECRET`. The existing refresh token survives (2.2). |
| `Missing secret(s): ...` | Exactly what it says — check the names in section 4 character for character. |
| `Could not read the package at extension.zip` | The packaging step did not run or failed. Read the earlier steps in the run log. |
| Upload rejected, version error | `extension/manifest.json` version is not higher than the published one. On the first run that is 1.2.1 against 1.2.1 — see section 5 step 1. Bump and re-run. |
| `ITEM_NOT_UPDATABLE` | The item is already in review. Wait for that review to finish. |
| Store rejects the upload: "manifest.json not at root" | You uploaded the GitHub artifact download, which wraps `extension.zip`. Unzip once and upload the inner file (1.1). CI will not catch this for you — its check only greps for the substring (5). |

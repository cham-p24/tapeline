# Chrome Web Store — one-time setup

After this, publishing a new extension version is a single GitHub Action run and
never needs the dashboard again.

Everything here has to be done by a human: it involves creating an account,
paying a fee, and granting OAuth access to a Google account. Roughly 30 minutes,
once, forever.

---

## 1. Register as a developer — $5, once

1. Go to <https://chrome.google.com/webstore/devconsole>
2. Sign in with the Google account that should own the extension.
   **Use an account you control long-term.** The item belongs to this account,
   and moving an extension between accounts later is a support ticket, not a
   setting.
3. Pay the one-off **$5 USD** registration fee.
4. Turn on **hardware-key 2FA** on that account before doing anything else.
   Extension developer accounts are actively phished — the Cyberhaven compromise
   (~400,000 users) started with a "your extension violates policy" email. Treat
   any such email as phishing until you have confirmed it inside the dashboard.

## 2. Create the item and get its ID

1. In the dashboard: **Add new item**.
2. Upload `tapeline-extension-v*.zip` (the current package).
3. Fill the listing from `CHROME_STORE_LISTING.md` — every field is written out
   there, including the permission justifications and the privacy answers.
4. Save as draft. **Do not submit yet.**
5. Copy the **item ID** from the dashboard URL:
   `.../devconsole/.../<THIS-32-CHAR-ID>/edit` → that is `CWS_EXTENSION_ID`.

Doing the first upload by hand is deliberate: the API can replace an existing
item, but it cannot create one or fill in listing copy.

## 3. Enable the API and create OAuth credentials

1. Open <https://console.cloud.google.com> with the **same Google account**.
2. Create a project (any name — `tapeline-extension` is fine).
3. **APIs & Services → Library** → enable **Chrome Web Store API**.
4. **APIs & Services → OAuth consent screen**:
   - User type: **External**
   - Fill the required fields; you do **not** need to submit for verification.
   - Under **Test users**, add the same Google account. Without this the token
     request fails with `access_denied` and the reason is not obvious.
5. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**
   - Save the **Client ID** and **Client secret** → `CWS_CLIENT_ID`,
     `CWS_CLIENT_SECRET`.

## 4. Mint a refresh token

Refresh tokens don't expire on their own, so this is also a one-time step.

**a.** Open this URL in a browser, with your client id substituted:

```
https://accounts.google.com/o/oauth2/auth?response_type=code&access_type=offline&prompt=consent&client_id=YOUR_CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&scope=https://www.googleapis.com/auth/chromewebstore
```

`access_type=offline` and `prompt=consent` are both required — without them
Google returns an access token but **no refresh token**, which is the most
common way this step goes wrong.

**b.** Approve, then copy the authorisation code Google shows you.

**c.** Exchange it for a refresh token (run this locally, once):

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET \
  -d code=THE_CODE_FROM_STEP_B \
  -d grant_type=authorization_code \
  -d redirect_uri=urn:ietf:wg:oauth:2.0:oob
```

The `refresh_token` in the response is `CWS_REFRESH_TOKEN`. The code is
single-use — if you need to retry, start again from step (a).

## 5. Add the four secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | From |
|---|---|
| `CWS_CLIENT_ID` | step 3 |
| `CWS_CLIENT_SECRET` | step 3 |
| `CWS_REFRESH_TOKEN` | step 4 |
| `CWS_EXTENSION_ID` | step 2 |

---

## Publishing, from then on

**Actions → Publish extension → Run workflow**, and pick where it goes:

| `publish` | What happens |
|---|---|
| `none` *(default)* | Uploads and replaces the draft. Nothing goes live. Review it in the dashboard first. |
| `trustedTesters` | Live only to the tester list on the item. |
| `default` | Live to everyone, subject to Chrome review. |

The default is upload-only on purpose. A store submission isn't a deploy you can
roll back, and since Chrome 117 a policy takedown turns your whole install base
into a one-click "Remove" prompt via Safety Check. Uploading is cheap; being
taken down is not.

Before each run, **bump `version` in `extension/manifest.json`** — the store
rejects any upload whose version isn't higher than what's already there. The
workflow surfaces that specific error rather than a generic failure.

The workflow also sanity-checks the manifest before uploading (MV3, name and
description lengths, icons present, no broad `tabs` or `*://*/*` host
permissions) and verifies no dev artefacts leaked into the package, because
each of those is a rejection that costs days of review.

Every run keeps the exact uploaded zip as a build artefact for 90 days, so
"what was actually in version 1.2.0" is always answerable.

## When it goes wrong

| Symptom | Cause |
|---|---|
| `invalid_grant` | Refresh token revoked, or issued for a different OAuth client than `CWS_CLIENT_ID`. Redo step 4. |
| `access_denied` at step 4a | The Google account isn't in **Test users** on the consent screen. |
| No `refresh_token` in the step 4c response | `access_type=offline` or `prompt=consent` was missing from the auth URL. |
| Upload rejected, version error | `manifest.json` version isn't higher than the published one. |
| `ITEM_NOT_UPDATABLE` | The item is already in review. Wait for it to finish. |

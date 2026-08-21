/**
 * First run: accept the disclosure, then go straight to sign-in.
 *
 * The account is required, so making the user discover the toolbar popup on
 * their own before they can use anything is a dead end — most people would
 * install, see nothing happen on the next stock page, and uninstall. Instead
 * the accept button carries them into the sign-in / sign-up step in the same
 * motion, which is the only moment we reliably have their attention.
 *
 * Until the accept is clicked, content.js returns before any network call: the
 * consent gate is real, not a notice you can dismiss by navigating away.
 */
const CONNECT_URL =
  "https://tapeline.io/extension/connect?utm_source=extension&utm_medium=welcome";

const ok = document.getElementById("ok");
const done = document.getElementById("done");

/** Already connected? Then this is a re-open, not a first run — say so. */
async function alreadyConnected() {
  try {
    const got = await chrome.storage.local.get("account");
    return Boolean(got.account);
  } catch (_) {
    return false;
  }
}

(async () => {
  if (await alreadyConnected()) {
    ok.hidden = true;
    done.textContent = "You're connected. The score shows on stock pages.";
    done.hidden = false;
  }
})();

ok.addEventListener("click", async () => {
  try {
    await chrome.storage.local.set({ consentAt: Date.now() });
  } catch (_) {}

  ok.hidden = true;
  done.textContent = "Opening sign-in…";
  done.hidden = false;

  // Navigate this tab rather than opening another: the user came here from the
  // install, and stacking a second tab on top is how people lose the thread.
  window.location.href = CONNECT_URL;
});

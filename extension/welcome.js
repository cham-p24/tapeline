/**
 * The affirmative accept for the first-run disclosure.
 *
 * Until this is clicked, content.js returns before any network call — the
 * consent gate is real, not a notice you can dismiss by navigating away.
 */
document.getElementById("ok").addEventListener("click", async () => {
  try {
    await chrome.storage.local.set({ consentAt: Date.now() });
  } catch (_) {}
  document.getElementById("ok").hidden = true;
  document.getElementById("done").hidden = false;
});

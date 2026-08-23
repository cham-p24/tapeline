"use client";

import { useEffect, type RefObject } from "react";

/**
 * Shared modal-dialog accessibility behaviour, applied by any component that
 * renders a focus-trapping overlay (CancelInterceptModal, ExitIntentModal, …).
 *
 * While `open` is true and `panelRef` points at the dialog panel this:
 *   - moves focus into the modal on open (first focusable element, or the
 *     panel itself if it has none), so keyboard/screen-reader users land
 *     inside the dialog rather than behind it;
 *   - TRAPS Tab / Shift+Tab within the panel — focus cycles at the edges
 *     instead of escaping to the page underneath;
 *   - closes on Escape via `onClose`;
 *   - RESTORES focus to whatever element was focused before the modal opened
 *     once it closes (or the hook unmounts).
 *
 * The panel still needs role="dialog", aria-modal="true" and an
 * aria-labelledby pointing at its heading — this hook handles focus/keyboard
 * only, not the ARIA wiring.
 */

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function focusableWithin(panel: HTMLElement): HTMLElement[] {
  return Array.from(
    panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter(
    (el) =>
      el.offsetWidth > 0 ||
      el.offsetHeight > 0 ||
      el === document.activeElement,
  );
}

export function useModalA11y(
  open: boolean,
  panelRef: RefObject<HTMLElement | null>,
  onClose: () => void,
): void {
  useEffect(() => {
    if (!open) return;

    // Remember what was focused so we can restore it on close.
    const previouslyFocused =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;

    const panel = panelRef.current;

    // Move focus into the modal: first focusable, else the panel itself
    // (which needs a tabindex to be programmatically focusable).
    if (panel) {
      const focusables = focusableWithin(panel);
      if (focusables.length > 0) {
        focusables[0].focus();
      } else {
        if (!panel.hasAttribute("tabindex")) panel.setAttribute("tabindex", "-1");
        panel.focus();
      }
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const p = panelRef.current;
      if (!p) return;
      const focusables = focusableWithin(p);
      if (focusables.length === 0) {
        // Nothing tabbable — keep focus pinned on the panel.
        e.preventDefault();
        p.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey) {
        if (active === first || !p.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last || !p.contains(active)) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener("keydown", onKeyDown, true);

    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      // Restore focus to wherever it was before the modal opened.
      previouslyFocused?.focus();
    };
  }, [open, panelRef, onClose]);
}

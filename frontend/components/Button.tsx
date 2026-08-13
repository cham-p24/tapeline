"use client";

import Link, { type LinkProps } from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

/**
 * The one Button primitive. Every CTA should route through this so shape,
 * height, radius and states can't drift page-to-page (the 2026-08 UI audit
 * found the primary button alternating between a pill and a rounded rectangle
 * across adjacent marketing pages).
 *
 * All variants are PILL-shaped (rounded-full) via the canonical `.btn` class —
 * that's the documented system (nav, hero, how-it-works already use it). The
 * variant only changes the fill, so shape/height/radius stay identical:
 *   primary  — the accent pill (the standard buy/primary action)
 *   ghost    — quiet pill (secondary action)
 *   gradient — accent→indigo pill (the pricing highlight; emphasis, same shape)
 *
 * Radius ladder for the rest of the system: inputs = rounded-md, cards =
 * rounded-xl/2xl, pills (buttons) = rounded-full.
 *
 * Renders a Next <Link> when `href` is set, otherwise a <button>.
 */

type Variant = "primary" | "secondary" | "ghost" | "gradient";

const VARIANT: Record<Variant, string> = {
  primary: "btn-primary",
  // Bordered, full-contrast secondary action (the outlined pill next to a
  // primary/gradient CTA — e.g. the Free/Premium cards beside highlighted Pro).
  secondary: "btn text-fg border border-border2 hover:bg-panel2",
  ghost: "btn-ghost",
  gradient: "btn text-white bg-gradient-to-r from-accent to-accent2 hover:opacity-90",
};

type BaseProps = { variant?: Variant; className?: string; children: ReactNode };

type AsButton = BaseProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children"> & { href?: undefined };

type AsLink = BaseProps &
  Omit<LinkProps, "className"> & {
    href: string;
    target?: string;
    rel?: string;
    "aria-label"?: string;
  };

export function Button(props: AsButton | AsLink) {
  const cls = `${VARIANT[props.variant ?? "primary"]} ${props.className ?? ""}`.trim();

  if (props.href !== undefined) {
    const { variant: _v, className: _c, children, ...linkProps } = props;
    return (
      <Link className={cls} {...linkProps}>
        {children}
      </Link>
    );
  }

  const { variant: _v, className: _c, children, href: _h, ...btn } = props;
  return (
    <button className={cls} {...btn}>
      {children}
    </button>
  );
}

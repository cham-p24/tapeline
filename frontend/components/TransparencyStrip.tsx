import Link from "next/link";

/**
 * Cross-link strip surfaced at the bottom of every transparency page.
 *
 * The five moat artefacts (formula, scorecard, system status, security,
 * changelog) reinforce each other — each one is evidence for "this team
 * shows their work". Linking them from each other keeps a curious
 * visitor inside the moat instead of bouncing back to home.
 */
type Item = { slug: string; title: string; desc: string; emoji: string };

const ITEMS: Item[] = [
  { slug: "/how-it-works",  title: "The formula",    desc: "Six factors, exact weights, public methodology.", emoji: "🧮" },
  { slug: "/data-sources",  title: "Data sources",   desc: "Every feed that powers a score. Named, dated, linked.", emoji: "🗂️" },
  { slug: "/scorecard",     title: "Public scorecard", desc: "Every top-10, back-checked vs SPY next session.", emoji: "📈" },
  { slug: "/signals",       title: "All signals",    desc: "Every Tapeline-scored ticker, live universe view.", emoji: "📊" },
  { slug: "/status",        title: "System status",  desc: "Live API + worker uptime, refreshed every 30s.",   emoji: "🟢" },
  { slug: "/security",      title: "Security",       desc: "Encryption specifics + vulnerability disclosure.", emoji: "🔒" },
  { slug: "/changelog",     title: "Changelog",      desc: "Every release, weight changes flagged ahead.",     emoji: "📝" },
];

export function TransparencyStrip({ current }: { current?: string }) {
  const others = ITEMS.filter((i) => i.slug !== current);
  return (
    <section className="mt-8">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
          More transparency artefacts
        </h2>
        <p className="mt-2 text-sm text-muted">
          Tapeline's moat is everything you can audit before you sign up.
          These pages all live publicly — each is independent evidence.
        </p>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {others.map((i) => (
            <Link
              key={i.slug}
              href={i.slug}
              className="lift group rounded-xl border border-border bg-panel/40 p-4 hover:border-accent/40"
            >
              <div className="text-base">{i.emoji}</div>
              <div className="mt-2 text-sm font-semibold group-hover:text-accent transition-colors">{i.title}</div>
              <div className="mt-1 text-xs text-muted leading-snug">{i.desc}</div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

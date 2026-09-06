# Google Ads import files

## Only one file here is safe to import

`tapeline-negative-keywords.csv` — 28 phrase negatives (police scanner, radio
scanner, document scanner, and so on). Still correct, still useful, import freely.

## Three ad-copy CSVs were deleted on 2026-09-05

`tapeline-rsa-improved.csv`, `tapeline-search-test.csv` and
`tapeline-adgroups-2-3-import.csv` were paste-ready Google Ads import files. Any
of them could have been uploaded in one action. All three were broken in three
independent ways at once, and each way is enough on its own:

**1. Every ad pointed at a page that no longer exists.** The final URL was
`https://tapeline.io/compare/finviz`. The 18 tool-comparison pages were removed
in #718; the route now correctly `notFound()`s. Google disapproves ads whose
destination does not work, and a campaign built from these would have failed
review — or worse, run briefly and sent paid clicks to a 404.

**2. Sixteen uses of banned ad vocabulary.** Headlines and descriptions used the
stock-tip nouns that paid creative may not use — the ones the ad ruleset lists
under `ad-trading-vocabulary`, deliberately not re-typed here, because spelling
them out is what tripped this very file's own check. Google's
complex-speculative-products policy names that vocabulary directly, and Meta's
classifier reads it as a stock-tip service. `--ads` mode flags all sixteen; run it
and read the matches rather than trusting a list in prose.

**3. They advertised a trial length Tapeline no longer offers.** Nine references
to the old length, hard-coded as a literal. #742 moved `TRIAL_DAYS` to 30 on
2026-09-05, and the rule that catches this (`stale-trial-length`) compares copy
against the constant rather than against a remembered number. Advertising the
wrong trial length on a financial product is precisely the class of claim the
whole descriptive-only posture exists to avoid.

They are in git history if the copy is ever wanted as a starting point. They were
not fixed in place because the destination they were built around is gone, the
campaign is paused behind an unmet gate (`PAID_MARKETING_PLAYBOOK.md` §4), and a
file that merely *looks* importable is the hazard.

## Before writing new ad copy

Run it through the ad-specific ruleset. The default pass deliberately permits
that vocabulary, because several of the words are real product routes on this
site; only `--ads` treats them as banned:

```
node scripts/lint-copy-compliance.mjs --ads <file>
```

CI runs that over the `.csv`, `.md` and `.txt` files in this folder and the
`.md`, `.txt` and `.json` files under `docs/ads/`, so a new import file *or a new
runbook* dropped in here is checked on the next push. Between 2026-09-05 and
2026-09-06 that claim was only two-thirds true: the step's file list ended a line
with a literal `\n` where a continuation was meant, bash read it as the filename
`n`, and the `.md`/`.txt` files here were never opened while the step reported
success. The linter now exits non-zero on a path it was handed and could not
read, so that failure cannot repeat silently.

A clean run means nothing was *caught*, not that the copy is compliant — a named
human still signs off.

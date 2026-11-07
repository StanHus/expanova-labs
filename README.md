# Expanova Labs

Source for [labs.expanova.io](https://labs.expanova.io), the research arm of [Expanova](https://expanova.io).

The lab runs one kind of experiment: take a cheap open model, wrap it in a harness, and let a **sound oracle** (a proof checker, a verifier, a type checker) decide what counts as solved. A claim only goes on the site if a machine checked it.

How the studies are run:

- **Pre-registered.** Hypotheses and kill criteria are committed before the run, and the commit is the seal.
- **Sound oracles only.** Lean 4, Dafny, Bend. No LLM judges deciding their own homework.
- **Red-teamed.** Every "solve" goes through a guard that rejects spec-gaming ([pnrd2-guard](https://github.com/StanHus/pnrd2-guard)).
- **Failures published.** Each study ends in SHIP, PARTIAL or KILL, and the misses stay on the page.

| Page | |
|---|---|
| `/` | The lab and its one rule |
| `/approach` | Sound oracles, pre-registration, ship/kill gates |
| `/pnrd-1` | Lean 4 theorem proving |
| `/pnrd-2` | Dafny-verified program completion, with the anti-gaming guard |

Results on the site are read at build time from `public/data/*.json`, never typed by hand.

Next.js on Vercel. Benchmarks credited on the site: miniF2F, DafnyBench.

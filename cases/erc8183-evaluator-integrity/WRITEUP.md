# Case: channel collapse in ERC-8183 evaluators

## Problem

ERC-8183 ("Agentic Commerce Protocol") is a job-escrow standard whose
`complete(jobId)` call does two things atomically, in one transaction: it
records an evaluator's verdict and releases escrow to the job's provider.
There is no separate `release()` step and no dispute path afterward — the
standard's own authors draw this contrast explicitly against Alkahest, a
related standard that does let an arbiter revise a decision. The spec also
permits the evaluator itself to be a contract "performing arbitrary checks...
aggregating off-chain signals," and real teams in the standard's author
thread confirm running LLM-backed evaluators in production, one calling it "a
single point of failure." If such an evaluator builds its prompt by
concatenating its own policy instructions and the untrusted `deliverable`
field into one flat text stream — a channel collapse, with no role/data
boundary — an attacker who controls the deliverable (as any job provider does)
can write text indistinguishable, to the model, from a real system
instruction. On this standard specifically, a successful injection is not a
bad rating; it is a final, atomic loss of funds.

The disclosure
([`erc8183-evaluator-integrity`](https://github.com/marsakahenry14-lab/erc8183-evaluator-integrity))
backs this with a tested detector (7 signal categories, 12/12 tests, validated
against real on-chain text from a companion project) and a critical piece of
honesty: a source-level check of five real ERC-8183 implementations found that
**none reads unsanitised deliverable content into a default LLM evaluator**.
Three ship no automated evaluation at all; one ships a fully rule-based
default; the one live, fully-automated LLM evaluator on Base mainnet defends
with an in-prompt instruction that held against a small synthetic attack
battery. The disclosure's own abstract is explicit that this is "not a
discovered vulnerability" — it is convergent evidence, from two independent
directions, that a structural-gate-before-model-context defense is the right
one.

## Method

Modeled the architectural pattern — not any specific live exploit — as an LBS
v0.1 hypergraph (`scenario.json`): provider control, an LLM-backed evaluator,
and the channel-collapse root cause jointly poison the evaluator's context;
the poisoned context flips the verdict; the flipped verdict reaches one or
both of two independent sinks (escrow release, and an optional
reputation-registry write the standard's own author describes as "the most
seamless loop" integration). The two sinks are modeled as disjunctive
hyperedges into a shared goal, `harm_from_injected_verdict`, exactly as the
LBS convention represents alternative paths. `sigma_completeness` is set to
`best_effort`, not `enumerated`: unlike the Potpie case, this disclosure does
not claim to enumerate every possible way to manipulate an ERC-8183 evaluator
— only this one documented pattern.

Every node in the primary (escrow) branch is cited to spec text or to
`harness/evaluator_repro.ts`. The secondary (reputation) branch is included
because it creates a structurally real second path, but its two nodes are
tagged in `scenario.json` and `SOURCES.md` with an explicit weaker-evidence
caveat: the reputation-write integration is the standard author's stated
design intent, not a behavior independently confirmed in any of the five
implementations reviewed. Re-cloned the disclosure repo fresh at its current
commit (`525b6bc`) rather than reusing a stale local dump found on disk at an
older commit (`1b22161`) — see `SOURCES.md` for why that distinction matters
here specifically.

## Result

`loadbearing` classifies 7 nodes as load-bearing: the entire chain from
`provider_controls_deliverable` through `verdict_flipped`, plus the goal
itself. All four downstream sink-side nodes — `sink_atomic_no_dispute`,
`escrow_drained`, `reputation_write_on_complete`, `reputation_falsified` — are
individually scaffolding. MLBS finds four co-load-bearing pairs, one from each
combination of {escrow-branch node} × {reputation-branch node}: knocking out
one control point from the escrow path *and* one from the reputation path
closes off harm; knocking out only one path leaves the other fully
functional. This is the same four-pair signature the repository's own
synthetic `examples/erc8183_evaluator_independence.json` produces — two
independent conditions, each contributing one blocking point, crossed against
each other. That the real case reproduces the shape of the synthetic one it
was modeled after is a reasonable sanity check on the modeling, not a
coincidence being oversold: both encode "two independent paths, break one
node from each."

## Why the LB verdicts and the "0/5 confirmed" finding do not contradict each other

This is the point of the case, not a footnote. `loadbearing`'s LB verdict
answers one question: *given this graph, is there any modeled alternative way
to reach the goal without this node?* For the primary chain, no — every node
is structurally necessary within the pattern as documented. The disclosure's
own ecosystem check answers a different question: *do real, deployed systems
currently instantiate the precondition this pattern depends on?* For the five
systems checked, no — by default, none does. These are orthogonal axes, not
competing verdicts on the same question, and conflating them is a common
failure mode in vulnerability reporting: "structurally necessary for the
attack" gets misread as "currently exploitable in production," or a low
observed prevalence gets misread as "not a real structural risk." A node can
be load-bearing — nothing else in the modeled pattern substitutes for it — and
still be empirically rare in the specific population sampled. `SOURCES.md`
keeps the ecosystem-check table explicitly out of `sigma` for exactly this
reason: feeding "we found no live target" into the same mechanism that answers
"we found no working bypass" would erase this distinction inside the tool's
own output, not just in prose around it.

## Countermeasure implication

The MLBS output agrees with the disclosure's own recommendation, arrived at
independently: `channel_collapse_no_boundary` is a single point that, if
closed, breaks every downstream path in the graph — a pre-context structural
gate (score injection shape before any content reaches a model context, as
`src/detector.ts` implements) removes the root cause rather than hardening one
of four individually-scaffolding sink-side conditions. The disclosure notes
that the most production-experienced framework reviewed (`erc8183-reference`
/ ClawWork, 20,000+ agents) independently documents almost exactly this
mitigation in its own integration guide — two lines of evidence, arrived at
from different starting points, agreeing on where the fix belongs.

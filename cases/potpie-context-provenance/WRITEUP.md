# Case: trust-provenance loss in Potpie's Context Graph

## Problem

[Potpie](https://github.com/potpie-ai/potpie) reconciles issues/PRs/tickets from
multiple sources (GitHub, Linear, agent-mediated ingestion, a public API) into a
shared `ClaimRow`/`EvidenceItem` graph, then serves that graph back to coding
agents (Claude Code, Cursor, Codex) as context. The schema tracks *epistemic*
confidence (`truth`, `confidence`, `evidence_strength`) but has no
`trust`/`provenance` field distinguishing "an authenticated maintainer said
this" from "an anonymous GitHub issue said this." Four ingress channels can
write unauthenticated or weakly-authenticated text into a claim; eight egress
channels later hand that text to an agent verbatim. A coding agent trusting its
own context tooling has no signal to tell the two apart — the disclosure
([`potpie-context-provenance`](https://github.com/marsakahenry14-lab/potpie-context-provenance),
CWE-1427) documents this as a context-poisoning primitive.

## Method

1. Modeled the disclosure's vector map as an LBS v0.1 hypergraph
   (`scenario.json`): 4 ingress nodes + schema gap → `claim_written` → 8 (now
   7) egress nodes → goal `agent_context_poisoned`. Disjunctive alternative
   channels are separate hyperedges into the same head, per the LBS
   convention — no `sigma` needed since the vector map already enumerates
   every known path (`sigma_completeness: enumerated`).
2. Ran [`lbs-core`](../../README.md) to get a mechanical LB/SC verdict per
   node, independent of the prose conclusion in the original `RESEARCH.md`.
3. Four nodes in the original vector map were tagged `"reported, not
   independently re-verified"`. Re-verified all four directly against
   `potpie-ai/potpie@b5a67742` (see `SOURCES.md` for exact citations).

## Result

`lbs-core` mechanically reproduces the disclosure's central claim: the only
load-bearing nodes are `schema_no_trust_field` and `claim_written` — the
missing trust field and the point where untrusted text becomes a claim. All
ingress/egress channels are individually scaffolding (SC): patching any one
of them does not break the attack while any alternative channel survives.
This is a three-node MLBS, all singletons — there is no combination of two or
more scaffolding nodes whose *joint* removal is required, because each
channel alone is sufficient once `claim_written` holds.

The re-verification pass confirmed three "reported" nodes as real (I-4, E-5,
E-8, now cited with file:line) and **disproved one**: E-7 claimed
`/context/graph/query` served the poisoned graph over an API-key-protected
endpoint. At commit `b5a67742` that route (`/context/query/context-graph`)
is a stub — it discards its request body and unconditionally returns HTTP
501. It was removed from the graph rather than left in as a false SC node.
Removing it doesn't change the load-bearing core (verifying a channel's
existence only ever affects the scaffolding count, never the root cause) —
but it matters for anyone using this disclosure as a checklist to actually
close: patching a channel that no longer exists is wasted effort, and citing
a disproved channel undermines the credibility of the ones that are real.

## Why this matters as a method, not just a result

The interesting output here isn't "12 vs 11 scaffolding nodes." It's that
*mechanical* LB/SC classification and *manual* re-verification of evidence
are separable, composable checks, and running both caught something neither
would have caught alone: `lbs-core` doesn't know or care whether E-7 is real
— it only reasons about graph structure, so a stale claim baked into the
graph would have sailed through as valid SC. Re-verification without a
structural model would have found the same bug, but wouldn't tell you E-7
was decorative even *before* it turned out to be fictional — patching it was
never going to matter to the attack's viability. Combining both gives a
countermeasure priority list you can trust on two independent axes:
structurally necessary (LB) and evidentially real (verified directly).

## Countermeasure implication

The MLBS output says where to spend effort: add a `trust`/`provenance` field
to `ClaimRow`/`EvidenceItem` (closes `schema_no_trust_field`) and enforce it
at the point claims are written (closes `claim_written`) — either one alone
breaks every downstream path. Hardening individual ingress/egress channels
(the SC nodes) is defense-in-depth, not a fix; the disclosure's own
recommendation and the mechanical LBS output agree on this independently.

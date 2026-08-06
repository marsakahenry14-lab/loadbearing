# loadbearing

A deterministic **load-bearing vs. scaffolding** analyzer for attack graphs and
inference graphs. Given a graph describing how some property is achieved (an
attack succeeds / a security invariant is violated), the tool says which
components actually **carry** that property and which are merely present.

The problem it solves: in security analysis of agentic and Web3 systems there
are usually many mechanisms, and only a small subset actually carries the
property. `loadbearing` separates the load-bearing core from decorative
surroundings and finds **minimal load-bearing sets** — combinations of
conditions whose joint removal breaks the attack. This is the input for
countermeasure prioritization: defend the load-bearing nodes, don't spend
resources on scaffolding.

The tool is deterministic, makes no network calls, and uses no LLM. The same
input always produces the same verdict.

See [`VISION.md`](VISION.md) for why this repository exists.

## Install and run

```bash
git clone https://github.com/marsakahenry14-lab/loadbearing.git
cd loadbearing
python3 -m lbs_core.cli examples/erc8183_evaluator_independence.json
```

Machine-readable output:

```bash
python3 -m lbs_core.cli examples/erc8183_evaluator_independence.json --json
```

Tests:

```bash
pip install pytest
python3 -m pytest tests/ -v
```

## Model

The object of analysis is an inference hypergraph:

- **nodes** — atomic claims/conditions;
- a **hyperedge** `tail → head` means "the set of conditions `tail` is
  **jointly** sufficient for `head`"; an ordinary edge is the special case of
  a single condition in `tail`;
- **disjunction** (the goal is reachable via path A **or** path B) is
  expressed as several hyperedges with the same `head`;
- the **goal** `gamma` — the node whose reachability is being checked;
- **Σ** — the pool of admissible substitutions (alternative sub-derivations);
  given extensionally.

Verdicts (semantics fixed by the LBS v0.1 specification):

- **LB (load-bearing)** — no admissible substitution restores goal
  reachability after the node is removed (full enumeration of Σ);
- **SC (scaffolding)** — a substitution exists that restores the goal without
  this node (a witness is produced);
- **UND (undetermined)** — the enumeration budget was exhausted before a full
  search completed; the node is **not** classified as load-bearing (asymmetry
  rule: "not checked" ≠ "no substitution exists");
- **MLBS** — minimal load-bearing set: the smallest set of nodes whose joint
  removal breaks the goal. Size 1 = a single load-bearing node. Size ≥ 2 =
  co-load-bearing: individually scaffolding, jointly necessary.

## Cases

The most substantive artifacts in this repository are real-world cases, not
the synthetic one.

### Potpie Context Graph — trust-provenance loss

[`cases/potpie-context-provenance/`](cases/potpie-context-provenance/) analyzes
a real disclosure
([`potpie-context-provenance`](https://github.com/marsakahenry14-lab/potpie-context-provenance),
CWE-1427): Potpie's `ClaimRow`/`EvidenceItem` schema has no trust/provenance
field, so attacker-controlled content written through any of four ingress
channels (GitHub/Linear webhooks, agent-mediated ingestion, a public API) can
reach a coding agent through any of seven egress channels, indistinguishable
from trusted context.

`loadbearing` mechanically reproduces the disclosure's central claim: the only
load-bearing nodes are the missing trust field and the point where untrusted
text becomes a claim — every ingress/egress channel is individually
scaffolding. The case also documents a re-verification pass against the
target's source at a pinned commit: three nodes originally marked "reported,
not independently re-verified" were confirmed with file:line citations, and
one (a claimed API egress channel) was disproved — the endpoint turned out to
be a stub that always returns HTTP 501 — and removed from the graph. See
[`WRITEUP.md`](cases/potpie-context-provenance/WRITEUP.md) for the full
analysis and [`SOURCES.md`](cases/potpie-context-provenance/SOURCES.md) for
the per-node evidence.

### ERC-8183 evaluator injection — channel collapse into an irreversible sink

[`cases/erc8183-evaluator-integrity/`](cases/erc8183-evaluator-integrity/)
analyzes a different domain (Web3 job escrow) and a different disclosure
([`erc8183-evaluator-integrity`](https://github.com/marsakahenry14-lab/erc8183-evaluator-integrity)):
ERC-8183's `complete(jobId)` atomically records an evaluator's verdict and
releases escrow, with no dispute path afterward. If an LLM-backed evaluator
concatenates its own policy and an untrusted `deliverable` field into one flat
prompt — a channel collapse, the root cause — an attacker-controlled
deliverable can flip the verdict and drain escrow, optionally also falsifying
an ERC-8004 reputation record in the same call.

`loadbearing` classifies the entire causal chain up to the flipped verdict as
load-bearing, and finds four co-load-bearing pairs crossing the two
independent downstream sinks (escrow release, reputation write) — the same
structural signature the repository's own synthetic example below was built
to illustrate, this time on real spec text and a real reproduction harness.
The case also carries a methodological point the disclosure itself makes
explicit: a source-level check found that **zero of five real
implementations** default to the vulnerable configuration — which does not
contradict the load-bearing verdict above, it answers a different question
(structural necessity within the pattern vs. empirical prevalence in the
population checked). See
[`WRITEUP.md`](cases/erc8183-evaluator-integrity/WRITEUP.md) for why those two
findings coexist and [`SOURCES.md`](cases/erc8183-evaluator-integrity/SOURCES.md)
for the per-node evidence.

### Potpie GraphRAG indirect prompt injection (part 1) — the control case

[`cases/potpie-graphrag-prompt-injection/`](cases/potpie-graphrag-prompt-injection/)
analyzes an earlier disclosure against the same target as the first case above
([`potpie-graphrag-prompt-injection`](https://github.com/marsakahenry14-lab/potpie-graphrag-prompt-injection),
March 2026): a docstring payload in a pull request flows, unfiltered, through
`tree-sitter`/`blar-graph` parsing, Neo4j storage, and GraphRAG retrieval into
an LLM agent's context, which then executes an outbound tool call — confirmed
by a live OAST callback.

Unlike the other two cases, this attack is a single documented kill chain with
no disjunction, and `loadbearing` reports exactly that: all seven nodes
load-bearing, zero scaffolding. That's the point of including it — proof the
tool doesn't manufacture structure where a real attack genuinely has none. The
case also declines, and documents why, an initially-tempting use of Σ to
encode model choice (`gpt-4.1-mini` vulnerable vs. `claude-sonnet-4-6`
resilient) and a tool's domain allowlist — both are configuration-dependent
preconditions, not alternative mechanisms, the same distinction the previous
case's ecosystem check is built on. A re-verification pass confirms the
described pipeline no longer exists in current `potpie-ai/potpie` (`blar-graph`
returns zero hits in the current codebase) — consistent with the disclosure's
own pre-v2.0.0 scope, and with the first case above finding the same
underlying provenance gap resurfaced in the rewrite. See
[`WRITEUP.md`](cases/potpie-graphrag-prompt-injection/WRITEUP.md) and
[`SOURCES.md`](cases/potpie-graphrag-prompt-injection/SOURCES.md).

### acp-node-v2 evaluator injection — Virtual Protocol's official ACP SDK

[`cases/acp-node-v2-evaluator-injection/`](cases/acp-node-v2-evaluator-injection/)
is the one case here that isn't a formalization of an existing write-up — it's
original source review of `Virtual-Protocol/acp-node-v2`. `JobSession.toMessages()`
tags a provider-controlled `deliverable` string `role: "system"`; the SDK's own
shipped LLM examples then coerce `role: "system"` into `role: "user"`, because
Anthropic's Messages API has no inline system role, string-concatenating
untrusted content onto the adjacent turn with no boundary. That lands exactly
when the SDK's tool-availability matrix grants `complete`/`reject` to the
`evaluator` role — and the shipped `buyer.ts` example sets the buyer as its
own job's evaluator by default, so evaluator-is-the-buyer's-own-LLM is not a
hypothetical, it's what the official example does.

All seven nodes load-bearing, zero scaffolding — same shape as the GraphRAG
control case above, except this chain is live today, with no compensating
control anywhere in it. Independently corroborated by this author's own
on-chain forensics ([`virtuals-forensics`](https://github.com/marsakahenry14-lab/virtuals-forensics),
a different kind of evidence entirely — deterministic analysis of 62,953
on-chain jobs, no code review, no LLM inference): 212 real addresses already
operate as client==evaluator on the ERC-8183 predecessor contract, and 98.5%
of near-empty deliverables still resulted in payment release. Reported to
Virtuals' security team privately on 2026-06-29; no response at any point; the
30-day disclosure window closed 2026-07-29 with the vulnerable code unchanged
before, during, and after. See
[`WRITEUP.md`](cases/acp-node-v2-evaluator-injection/WRITEUP.md),
[`SOURCES.md`](cases/acp-node-v2-evaluator-injection/SOURCES.md) (full
disclosure timeline), and
[`DISCOVERY-WALKTHROUGH.md`](cases/acp-node-v2-evaluator-injection/DISCOVERY-WALKTHROUGH.md)
for the grep-by-grep account of how this was found.

### Synthetic: ERC-8183 evaluator independence

`examples/erc8183_evaluator_independence.json` models a simplified scenario of
bypassing independent evaluation. The tool identifies:

- a **load-bearing core** (without which the attack is impossible): trust in
  the evaluator's verdict and the compromise of the evaluation itself;
- **decorative scaffolding**: the `audited` badge, verbose logging — present
  in the system but not carrying the attack;
- **four co-load-bearing sets** — four ways to close off the evaluator
  compromise, knocking out one condition from each independent path (shared
  input channel plus absent attestation, or an economic incentive to collude).
  This is a ready-made list of control points for a countermeasure designer.

## Scope and limitations (important)

The tool is honest about what it does **not** do:

- **An SC verdict ≠ "safe."** It means "in this scenario, under this Σ,
  removing this one node does not break the goal." Changing the scenario or
  expanding Σ can change the verdict.
- **Completeness of Σ is not guaranteed.** Under `sigma_completeness:
  best_effort`, an LB verdict is conditional: the node is load-bearing because
  no substitution was found in the given Σ, not because none exists. The tool
  flags this in the report.
- **Enumeration is exponential** in the size of Σ and in the size of MLBS sets
  (bounded by `--budget` and `--max-set-size`). The method is designed for
  graphs of tractable size — real attack trees are tens of nodes, where the
  bound is not a hindrance.
- **Building the graph from text is out of scope for the tool.** `loadbearing`
  analyzes an already-built graph; responsibility for the correctness of the
  model (what counts as a node, where edges go, what belongs in Σ) rests with
  the analyst.
- The tool does not discover threats and does not prove a system is safe — it
  performs **attribution** within a given scenario.

## Origin

The core semantics (hypergraph, reachability predicate, classification rules,
minimal load-bearing sets) follow the LBS v0.1 specification. While
implementing the specification in this code, six places where the
specification text was underdetermined were found and closed; each is pinned
by a regression test in `tests/test_lbs.py`.

## License

MIT.

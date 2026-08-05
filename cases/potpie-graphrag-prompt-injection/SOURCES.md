# Sources — potpie-graphrag-prompt-injection (part 1) case

Base disclosure: [`potpie-graphrag-prompt-injection`](https://github.com/marsakahenry14-lab/potpie-graphrag-prompt-injection)
(`ADVISORY.md`, `docs/EVIDENCE.md`), verified fresh at repo commit
`7bf76d15d1bd01b33228212a53bbb3e898f2b82f` (2026-08-04), cloned 2026-08-05.
Originally disclosed 8 March 2026, published after a 30-day disclosure window
closed with no response from Potpie (see `docs/TIMELINE.md`).

## Node citations

| Node | Evidence |
|---|---|
| `attacker_opens_pr_with_payload` | `ADVISORY.md` "Attack vector" step 1; CVSS `PR:L` — "Attacker needs only the ability to open a PR." Payload verbatim in `honeypot/app/schemas/compliance.py:7-19`, class `EnterpriseComplianceRecord` (the March advisory originally quoted an abbreviated paraphrase under a different class name — corrected in this repo's own `docs/EVIDENCE.md` to match the file exactly). |
| `parsing_no_data_instruction_tag` | `ADVISORY.md` "Root cause": "lack of data-instruction segregation... does not distinguish between code data... and system instructions when constructing the LLM's context." Steps 2-3 of the attack vector: `tree-sitter` + `blar-graph` parsing into a Neo4j knowledge-graph node "with no distinction from legitimate code content." |
| `graphrag_retrieves_payload` | `ADVISORY.md` step 4: "Potpie's agent retrieves the node via GraphRAG during code analysis." |
| `llm_context_mixed` | `ADVISORY.md` step 5, first half: "The LLM receives the payload as part of its context." |
| `model_executes_directive` | `docs/EVIDENCE.md` "Model resilience comparison": `gpt-4.1-mini` executed the directive; `claude-sonnet-4-6`, tested against the same payload, refused. This is the one node in the chain whose outcome is empirically config-dependent rather than structurally guaranteed — see "On model choice and tool allowlist" below. |
| `tool_executes_outbound` | `docs/EVIDENCE.md` "Execution configuration" / "Test environment": tool `http_fetch`, domain allowlist `*.oast.fun`, `*.interactsh.com`; HTTP GET completed, `200 OK`. |
| `injected_instruction_executed` (goal) | `ADVISORY.md` "Proof of concept" and `docs/EVIDENCE.md` "Callback confirmation": Interactsh Event #22, `2026-03-07 09:54 UTC`, source IP `171.225.184.153`, `GET / HTTP/1.1`, `200 OK`, 3-interaction callback chain. |

## On model choice and tool allowlist — deliberately not encoded as Σ

The case was originally sketched with `model_vulnerable` ↔ `model_resilient`
and `tool_allowlist_permits_oast` as candidate Σ substitutions — the intuition
being that they're "execution conditions, not the chain itself." On reflection,
applying the same test used for the ecosystem check in
`cases/erc8183-evaluator-integrity`, this would be a category error: Σ answers
"is there an alternative *mechanism* that reaches the same goal without this
node," and neither model choice nor the tool's domain allowlist provides one.
`claude-sonnet-4-6` refusing the injection isn't an alternate path to
`injected_instruction_executed` — it's a configuration in which the
precondition at `model_executes_directive` simply doesn't hold. Encoding it as
a Σ witness would make the tool report "the chain is scaffolding because a
substitution restores the goal," which reverses the actual claim: a resilient
model doesn't restore the goal by another route, it just means this specific
run doesn't reach the goal at all.

The same applies to the tool allowlist: `docs/EVIDENCE.md`'s "Test
environment" table describes the allowlist as the *researcher's own test
harness configuration*, not a documented default of Potpie's shipped tool
permissions. Nothing in this disclosure characterizes what Potpie's default
`http_fetch` scoping looks like outside this specific PoC run, so treating it
as an established graph node — load-bearing or otherwise — would overclaim
what's actually evidenced. It's noted here as an open gap, not folded into the
graph.

## 2026-08-05 re-verification: is the old pipeline still live?

`ADVISORY.md` itself scopes this disclosure to potpie-ai/potpie's "pre-v2.0.0
architecture" and its own Remediation section already states that the
"Structural" fix — treating externally-sourced content's provenance as
carrying through the whole pipeline — "is also the central finding of the
August 2026 follow-up research," i.e. `cases/potpie-context-provenance` in
this same repository. Checked directly rather than taken on the disclosure's
word: a GitHub code search over `potpie-ai/potpie`'s current default branch
for `blar-graph` returns **zero results**; `tree-sitter` still appears, but
now inside a rewritten, largely Rust-based parsing module
(`potpie/parsing/`, `tag_extract.rs`, `Cargo.toml`) that replaced the Python
`tree-sitter` + `blar-graph` pipeline this disclosure describes. This confirms
the disclosure's own scoping is accurate — the specific mechanism modeled in
`scenario.json` no longer exists in this exact form — and independently
corroborates the cross-reference: `cases/potpie-context-provenance` already
found, from the current codebase directly, that the same underlying gap (no
trust/provenance field on ingested content — there, `ClaimRow`/`EvidenceItem`
in the rewritten context-engine architecture) reappeared rather than having
been fixed by the rewrite. The mechanism changed; the invariant gap that
caused it did not.

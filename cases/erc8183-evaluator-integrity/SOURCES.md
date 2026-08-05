# Sources — erc8183-evaluator-integrity case

Base disclosure: [`erc8183-evaluator-integrity`](https://github.com/marsakahenry14-lab/erc8183-evaluator-integrity)
(`RESEARCH.md`, `docs/PATTERN.md`, `docs/POC-FINDINGS.md`), verified fresh at
repo commit `525b6bc50932b8636f248944af068861e49e0728` (2026-08-01), cloned and
re-read on 2026-08-05 rather than reused from an earlier local dump (a stale
local copy of this repo, at commit `1b22161`, existed on disk — it was not
used; see note below).

## Primary-chain nodes (standard-level, confirmed from spec/code)

| Node | Evidence |
|---|---|
| `provider_controls_deliverable` | `docs/PATTERN.md` §1, "Injection surface" row; ERC-8183 spec (`eips.ethereum.org/EIPS/eip-8183`). |
| `evaluator_llm_backed` | `docs/PATTERN.md` §3.3 and `RESEARCH.md` §2 property 3: spec text permits a contract evaluator "performing arbitrary checks... aggregating off-chain signals"; author thread quotes ("use an AI coordinator as our evaluator"); one live multi-model evaluator contract on Base Mainnet, `0x119299F33f918808edD5ef92bd79cefB8700C091`. |
| `channel_collapse_no_boundary` | `docs/PATTERN.md` §4, labeled "Root cause, not just symptom" in both `RESEARCH.md` and `PATTERN.md`; code citation `harness/evaluator_repro.ts`, function `buildEvaluatorPrompt()` — `job.deliverable` concatenated verbatim into the prompt string. |
| `sink_atomic_no_dispute` | `docs/PATTERN.md` §3.1-2, `RESEARCH.md` §2 properties 1-2: `complete(jobId)` atomicity and the absent dispute path, both confirmed from spec text and the authors' own contrast with Alkahest (a related standard that does allow arbiter revision). |
| `verdict_flipped` | `docs/PATTERN.md` §5 reproduction output, defense-off run: `JOB #3 provider=0xAttacker truth=bad ... verdict: COMPLETE >>> ESCROW RELEASED <<< outcome: *** WRONG — this is the exploit ***`. |
| `escrow_drained` | `docs/PATTERN.md` §1, "Impact" row. |

## Secondary-branch nodes (weaker evidentiary basis — flagged explicitly)

| Node | Evidence | Caveat |
|---|---|---|
| `reputation_write_on_complete` | `docs/PATTERN.md` §3, "Optional second impact": one author of the standard describes wiring the evaluator's verdict into ERC-8004's Reputation Registry on `complete`/`reject` as "the most seamless loop." | **Reported, not independently verified.** This is the standard author's stated design intent from the discussion thread, not a behavior confirmed in any of the five reviewed implementations — `docs/POC-FINDINGS.md`'s review scope was the injection precondition specifically, not reputation-registry wiring. |
| `reputation_falsified` | `RESEARCH.md` §2, cross-referencing `erc8004-forensics`'s finding that the Reputation Registry "constrains who can write feedback, not what a `tag`/`endpoint` field contains." | Same caveat as above — the write path itself is unconfirmed as implemented; this node inherits that status. |

These two nodes are included because the disjunction they create is
structurally real *if* the reputation-write integration exists — but readers
should not treat the resulting MLBS pairs as evidence that the reputation
branch is as well-established as the escrow branch. The node text carries this
caveat inline, matching the "verified directly" / "reported" convention used
in `cases/potpie-context-provenance`.

## Ecosystem check — five real implementations (NOT encoded as Σ)

`docs/POC-FINDINGS.md` reviews whether the shipped default evaluator of five
real ERC-8183 implementations actually reads `deliverable` into an LLM prompt
without sanitisation — the precondition this whole graph depends on being
true in a given deployment.

| # | Candidate | Deployment | LLM-backed default? | Verdict |
|---|---|---|---|---|
| 1 | `erc8183/erc8183-reference` (ClawWork) | Base Mainnet (claimed production, 20k+ agents) | No — rule-based `Reviewer` | Not confirmed |
| 2 | `AgentEscrow8183/agentescrow-erc8183` | Sepolia testnet | No — no evaluation logic at all | Not confirmed |
| 3 | `chebyte/agenthire` | Avalanche Fuji testnet | No — bare address, bring-your-own evaluator | Not confirmed |
| 4 | ThoughtProof evaluator contract | Base Mainnet | Unknown — contract source unverified | Out of scope |
| 5 | `ufosearchspace-create/ERC8183` (Iamalive) | Base Mainnet, live & verified | Yes — Claude/OpenAI, fully automated | Not confirmed — delimiter-wrapped + explicit meta-instruction defense, held 0/6 against a synthetic attack battery in local testing |

**Zero of five reached a "confirmed" verdict.** This is deliberately *not*
modeled as a Σ substitution pool in `scenario.json`. Σ in LBS answers "is
there an alternative way to reach the same goal that doesn't need this node" —
a claim about alternative *mechanisms*. What this table provides is a
different kind of claim: an empirical prevalence check of whether one specific
node (`channel_collapse_no_boundary`, specifically the "reads unsanitised"
half of it) is actually instantiated by real, deployed systems. No candidate
in this sample offers an alternative *path* to `harm_from_injected_verdict` —
they simply don't (by default) satisfy the precondition this graph starts
from. Feeding this table into `sigma` would conflate "we found no working
bypass" with "we found no live target," which are not the same claim; see
`WRITEUP.md` for why this distinction matters for how to read the LB verdicts
above.

## Note on the stale local dump

A local text dump of this repository, `erc8183-evaluator-integrity_github_dump_1b22161.txt`
(commit `1b22161`), existed on disk prior to this case being built. It was not
used — the repository was re-cloned fresh at its current `main` HEAD
(`525b6bc`) instead, following the same discipline that caught the E-7 error
in `cases/potpie-context-provenance`: cached/dumped text is not treated as
authoritative when the live source is one `git clone` away.

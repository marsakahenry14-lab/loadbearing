# Sources — acp-node-v2 evaluator-injection case

**This case is an original finding, not a formalization of an already-published
disclosure** — unlike the other three cases in this repository, none of which
had a `TIMELINE.md`/`DISCLOSURE.md` counterpart at the time this was written.
See the disclosure note at the end of this document before treating any of
this as public.

Target: [`marsakahenry14-lab/acp-node-v2`](https://github.com/marsakahenry14-lab/acp-node-v2),
a fork of [`Virtual-Protocol/acp-node-v2`](https://github.com/Virtual-Protocol/acp-node-v2)
(Virtuals Protocol's official Agentic Commerce Protocol SDK), synced by the
repo owner immediately before this analysis. Commit `8af150b673a5bfda7c93e065dcd7d961b17c390d`
(2026-07-28, "chore: update version to 0.1.10").

## Method

No prior write-up existed for this target. Found by reading the SDK's own
shipped LLM reference examples (`src/examples/llm/{buyer,seller}.ts`) end to
end, then tracing backward into the core library (`src/jobSession.ts`,
`src/acpJob.ts`, `src/acpAgent.ts`) to confirm each step from first
principles — the same "verified directly, file:line" standard the other three
cases in this repository hold external disclosures to, applied here to
original research.

## Node citations

| Node | Evidence |
|---|---|
| `provider_controls_deliverable` | `src/jobSession.ts:606-626`, `JobSession.submit(deliverable: string, transferAmount?)`. `src/acpJob.ts:72,80,95`: `deliverable: string \| null`, no schema, no validation anywhere in the call path. |
| `deliverable_tagged_system_role` | `src/jobSession.ts:720-736`. Exact code (`toMessages()`, `job.submitted` branch): `` let content = `The provider has submitted a deliverable: ${this._job?.deliverable ?? "(pending)"}`; `` ... `result.push({ role: "system", content });`. The type signature itself (`{ role: "system" \| "user" \| "assistant"; content: string }[]`) treats `"system"` as a first-class role the SDK assigns to this content. |
| `example_coerces_system_to_user` | `src/examples/llm/seller.ts` and `src/examples/llm/buyer.ts`, function `toAnthropicMessages()`: `const role = m.role === "system" ? "user" : m.role;` followed by `last.content += "\n" + m.content` when the previous message already has that role — i.e. the untrusted content is literally string-concatenated onto adjacent turn content before reaching the Anthropic API, with no delimiter. |
| `evaluator_context_poisoned` | Direct consequence of the two nodes above. No mitigation exists anywhere in this path: no delimiter wrapping, no explicit "this content may be adversarial" warning to the model (contrast `cases/erc8183-evaluator-integrity`'s Candidate 5, which has exactly this warning and was tested against it), no pre-context injection-shape scoring. |
| `evaluator_role_grants_complete_on_submitted` | `src/jobSession.ts`, `TOOL_MATRIX.evaluator.submitted = [TOOL_COMPLETE, TOOL_REJECT]`; `RESPONDERS["job.submitted"] = ["evaluator"]` inside `shouldRespond()`. Confirmed by reading `availableTools()` (iterates `TOOL_MATRIX[role][status]` for each of the agent's roles) and `executeTool()` (gates only on `available.includes(name)` — a role/status check, not a content check — before dispatching to `complete()`). |
| `verdict_flipped` | `executeTool()`'s `case "complete":` branch calls `this.complete(args.reason as string)` unconditionally once the tool name passes the availability check; `complete()` calls `this.agent.internalComplete(...)` (`src/acpAgent.ts:1004`), which executes on-chain. |
| `escrow_released_on_injected_verdict` (goal) | Direct consequence of `internalComplete()` executing. `src/examples/llm/buyer.ts:349`: `buyer.createJobByOfferingName(chain.id, offeringName, sellerAgent.walletAddress, requirement, { evaluatorAddress: buyerAddress })` — the SDK's own shipped example sets the buyer as its own job's evaluator by default, so "the evaluator is the buyer's own LLM agent" is not a hypothetical configuration, it's what `npx tsx src/examples/llm/buyer.ts` actually does. |

## Independent on-chain corroboration

This project's own earlier work, `virtuals-forensics` (deterministic on-chain
analysis of `AgenticCommerceV3`, the ERC-8183 predecessor deployed on Base
Mainnet, 62,953 indexed jobs), found two directly relevant patterns in
production, unrelated to and prior to this code-level finding:

- **Finding B, "Client-as-Evaluator Pattern":** 212 unique addresses acted as
  both client and evaluator on the same job; one address approved 226/237
  deliverables (95.3%) as `keccak256("")` — an empty hash — with escrow
  released every time.
- **Finding C, "Empty Deliverable Approved at Scale":** 398 submissions had
  `deliverable = keccak256("")`; 392 of those (98.5%) still resulted in
  `JobCompleted` + `PaymentReleased`.

Neither finding depends on this code-level analysis, and this analysis does
not depend on them — they were produced independently, from on-chain data,
with no LLM inference involved. They are cited here because they show the
structural precondition this case's chain relies on (client acting as
evaluator, evaluator approving with minimal scrutiny) is not a contrived edge
case; it is already how a meaningful fraction of this protocol family
operates in production, on a related, live contract.

## A second, structurally distinct injection surface (not modeled in scenario.json)

`src/examples/llm/seller.ts`'s `offeringContextNote()` builds a `role:
"system"` note from `offeringName` — which is `session.job?.description`, an
on-chain field the **buyer** sets when creating a job, with no constraint
requiring it to match a real offering name. When it doesn't match
(`!matched`), the function returns `` `Current offering: "${offeringName}" —
NOT in your registered catalog. Reject this job.` `` — the buyer-controlled
string is interpolated verbatim into the same kind of `role: "system"` note,
which the same `toAnthropicMessages()` coercion collapses into the
**seller's** LLM context.

This is the same root-cause pattern (untrusted on-chain field → `role:
"system"` → coerced to `"user"`), but it targets a different actor (the
seller/provider, not the evaluator) toward a different kind of harm (steering
the seller's pricing/tool behavior — e.g. an embedded instruction to ignore
the stated pricing floor — not a direct escrow release). Folding it into the
same goal as `escrow_released_on_injected_verdict` would conflate two
different victims under one claim. It's recorded here, not in `scenario.json`,
for the same reason `cases/erc8183-evaluator-integrity`'s reputation branch is
kept separate in evidentiary tagging rather than silently merged: a real
second finding is not automatically the same finding.

## Disclosure status — read before publishing or acting on this case

Unlike `cases/potpie-context-provenance`, `cases/erc8183-evaluator-integrity`,
and `cases/potpie-graphrag-prompt-injection`, **this finding has not been
responsibly disclosed to Virtual Protocol.** It targets the currently live,
maintained upstream SDK (`Virtual-Protocol/acp-node-v2`), not a historical or
already-published state. The other three cases in this repository all cite a
`docs/TIMELINE.md` or `docs/DISCLOSURE.md` documenting a disclosure window
that had already closed before publication. This case has no such record.
Publishing this write-up publicly, or otherwise acting on it, before that
process happens would be inconsistent with the disclosure standard this
author's own other work holds itself to.

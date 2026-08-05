# Case: evaluator injection in Virtual Protocol's official ACP SDK

> **This case has not been responsibly disclosed.** It targets the live,
> currently maintained upstream SDK. Read `SOURCES.md`'s "Disclosure status"
> section before publishing this write-up or its repository publicly, or
> acting on it in any other way.

## Problem

`acp-node-v2` is Virtual Protocol's official SDK for the Agentic Commerce
Protocol — the same job-escrow model `cases/erc8183-evaluator-integrity`
analyzes in ERC-8183, from the standard's predecessor's own author community.
The SDK ships two official LLM-driven reference examples
(`src/examples/llm/buyer.ts`, `src/examples/llm/seller.ts`), intended as the
integration pattern developers copy.

`JobSession.toMessages()`, part of the core library, converts a job's event
history into chat-style messages for an LLM. When a provider submits a
deliverable, it builds the string `"The provider has submitted a deliverable:
<deliverable>"` and tags it `role: "system"` — the SDK's own type system
treats this as an authoritative note, not user-supplied content. The
deliverable itself is an unvalidated, provider-controlled string with no
schema. Because Anthropic's Messages API has no inline system-role message,
both shipped examples' `toAnthropicMessages()` helper collapses `role:
"system"` into `role: "user"`, string-concatenating it onto whatever
conversational turn precedes it — untrusted deliverable content and real
chat content end up sharing one turn, with no boundary and no warning to the
model that any of it might be adversarial.

This lands exactly where it matters most: the SDK's tool-availability matrix
grants `complete`/`reject` to the `evaluator` role specifically when a job's
status is `submitted` — the same moment the poisoned note is delivered — and
`executeTool()` checks only whether a tool is available for the caller's
role and status, never its content, before dispatching to an on-chain
`complete()` call that releases escrow. In the SDK's own shipped `buyer.ts`
example, the buyer sets itself as the job's evaluator by default
(`evaluatorAddress: buyerAddress`) — so the evaluator being the buyer's own
LLM agent, reading the seller's deliverable through this exact path, is not
a hypothetical configuration. It's what running the official example does.

## Method

No prior disclosure existed to formalize — this was found by reading the
SDK's own shipped example code end to end and tracing every claim back to the
core library that backs it, holding the finding to the same "verified
directly, file:line" bar the other three cases in this repository apply to
external disclosures. The target repository is a fork the repo owner synced
to current upstream (`Virtual-Protocol/acp-node-v2`) immediately before this
analysis, specifically so the review would be against current code, not a
stale local copy — the same discipline applied in
`cases/potpie-graphrag-prompt-injection`'s re-verification pass.

Modeled the confirmed chain as a strict causal sequence in `scenario.json`:
provider control over the deliverable, the SDK's own system-role tagging, and
the example code's system-to-user coercion jointly poison the evaluator's
context; the tool-availability grant and the poisoned context jointly flip
the verdict; the flipped verdict releases escrow. A second, structurally
similar injection surface exists (buyer-controlled `job.description` reaching
the *seller's* context via `seller.ts`'s own `offeringContextNote()`) but
targets a different actor toward a different harm and is deliberately kept
out of this graph — documented instead in `SOURCES.md`, for the same reason
`cases/erc8183-evaluator-integrity` keeps its weaker-evidence branch
separately tagged rather than silently merged.

## Result

All seven nodes — the full chain plus the goal — are load-bearing, zero
scaffolding, matching the shape of `cases/potpie-graphrag-prompt-injection`.
The resemblance is the point of the contrast, not a coincidence: that case is
a *historical* linear chain, independently confirmed absent from current
code. This one is a *live* linear chain, confirmed present in the current
fork, as of this analysis, with — unlike every mitigated or partially
mitigated path in the other three cases — no compensating control anywhere
in it: no delimiter fencing, no explicit adversarial-content warning to the
model, no pre-context structural gate, no human confirmation step. Where
`cases/erc8183-evaluator-integrity`'s Candidate 5 had an in-prompt warning
that held under test, this path has nothing.

## Why the on-chain forensics matter here

`virtuals-forensics`, this author's earlier and independent on-chain analysis
of the ERC-8183 predecessor contract, found that 212 real addresses already
operate as both client and evaluator on the same job, and that 98.5% of
near-empty deliverable submissions still resulted in escrow release. Neither
finding used or anticipated this code-level analysis — they're from raw
on-chain event data, no LLM involved. Read together, they mean the structural
precondition this chain depends on (an evaluator who is also the counterparty
with an interest in approving, and who approves with minimal scrutiny of the
actual deliverable) is not a contrived worst case assembled for this write-up.
It is close to the median observed behavior of a live, related deployment.

## Countermeasure

The load-bearing set says where a fix has to land to break every instance of
this chain: `deliverable_tagged_system_role` and
`example_coerces_system_to_user` are the two structural conditions that
convert untrusted content into apparently-authoritative model context, and
either one closing (tag deliverable content as untrusted data rather than
`role: "system"`, or stop silently coercing `"system"` into `"user"` without
at minimum a delimiter and an explicit warning) breaks the chain regardless
of which specific field or example file carries the payload next time.

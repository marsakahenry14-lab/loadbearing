# How the acp-node-v2 finding was found

> A methodology record, complementary to `WRITEUP.md` and `SOURCES.md`: the
> concrete sequence of commands and source reads that produced the finding,
> not a restatement of its conclusions.

## Why I was reading this code at all

I wasn't hunting for a vulnerability. I was building the fourth
[`loadbearing`](../../README.md) case — the tool this whole `cases/`
directory exists to exercise. The other three cases (`potpie-context-provenance`,
`erc8183-evaluator-integrity`, `potpie-graphrag-prompt-injection`) each
formalize an *already-published* disclosure into an LBS hypergraph: read the
existing RESEARCH.md/ADVISORY.md, turn its attack narrative into nodes and
edges, run `loadbearing` over it, see whether the mechanical LB/SC verdict
matches the disclosure's own conclusion, and re-verify any claim the source
material had marked as unconfirmed.

`acp-node-v2` had no such document. You'd asked me to look at it with only a
one-line hint carried over from an earlier conversation: "unsanitized
deliverable-injection path into system-role LLM context." That's not a
citation, it's a hypothesis. So the graph-building process for this case
*was* the vulnerability research — there was no existing attack narrative to
formalize, only source code to read until either the hypothesis held up with
real evidence or it didn't.

Concretely, "iterating over graphs" here meant: before I can write a single
node into `scenario.json`, every node needs a real, checkable citation
(`file:line`), because that's the standard the other three cases already
hold themselves to. You can't cite a line you haven't read. So building the
graph forced reading the actual data flow end to end — and reading it end to
end is what surfaced the bug. The graph is downstream of the finding, not the
other way around.

## Step 1 — confirm I'm looking at current code, not something stale

You'd just synced the fork. First thing, before reading anything, was
confirming that actually landed:

```bash
git clone --quiet https://github.com/marsakahenry14-lab/acp-node-v2.git
cd acp-node-v2
git log -1 --format="%H %ci %s"
```

```
8af150b673a5bfda7c93e065dcd7d961b17c390d 2026-07-28 14:44:37 +0800 chore: update version to 0.1.10 in package.json and package-lock.json
```

Recent, real commit, matches `pushed_at` from the GitHub API. Not a red flag,
just a precondition — the last time skipping this step mattered was the
`erc8183-evaluator-integrity` case, where a stale local dump was sitting on
disk at an older commit than the live repo.

## Step 2 — figure out what kind of repository this even is

```bash
find . -maxdepth 2 -path ./.git -prune -o -type d -print
```

```
./scripts
./src
./src/clients
./src/core
./src/events
./src/examples
./src/providers
./src/utils
```

This is an SDK, not a deployed agent. That changes where to look: the
interesting question isn't "does this specific running service have a bug,"
it's "what does the SDK's own official integration pattern teach every
developer who builds on it" — the same shape of question that mattered for
`erc8183-reference`'s `EVALUATOR_GUIDE.md` in the second case.

## Step 3 — find where LLM code and `deliverable` actually overlap

```bash
grep -rlEi "openai|anthropic|\bllm\b|system.?prompt|role:\s*[\"']system" --include="*.ts" src/
grep -rlEi "deliverable" --include="*.ts" src/
```

The first grep returned four files; only two of them also showed up in the
second grep's much longer list: `src/examples/llm/buyer.ts` and
`src/examples/llm/seller.ts`. That intersection — files that talk to an LLM
*and* touch `deliverable` — is where I read next, in full, not with more
grepping.

## Step 4 — the tell, in the example code itself

Both example files define the same helper, to adapt the SDK's own internal
message format to Anthropic's API shape:

```ts
// src/examples/llm/seller.ts (identical helper in buyer.ts)
function toAnthropicMessages(
  raw: { role: "system" | "user" | "assistant"; content: string }[]
): Anthropic.MessageParam[] {
  const msgs: Anthropic.MessageParam[] = [];
  for (const m of raw) {
    const role = m.role === "system" ? "user" : m.role;
    const last = msgs[msgs.length - 1];
    if (last && last.role === role) {
      last.content += "\n" + m.content;
    } else {
      msgs.push({ role, content: m.content });
    }
  }
  return msgs;
}
```

This is the moment the hypothesis stopped being a hunch. Anthropic's Messages
API has no inline `"system"` role inside the `messages` array — only a
separate top-level `system` parameter — so any message the SDK itself has
typed as `role: "system"` gets silently downgraded to `"user"` here, and if
the *previous* message in the array already has `role: "user"`, it gets
**string-concatenated** onto it with a bare `"\n"`. No delimiter. No tag. No
warning to the model that the merged blob might contain two different trust
levels.

That told me what to go look for next: wherever in this SDK a message gets
tagged `role: "system"` in the first place, whatever's in that message is
about to be laundered into an ordinary, unflagged user turn. I didn't yet
know if `deliverable` was one of those messages — I knew where to check.

## Step 5 — trace `role: "system"` back to its source

```bash
grep -n "toMessages\|toContext\|role.*system\|deliverable" src/jobSession.ts
```

This landed on `JobSession.toMessages()`. Read the full function
(`src/jobSession.ts:691-750ish`), and this is the branch that mattered:

```ts
// src/jobSession.ts:720-736
} else if (event.type === "job.submitted") {
  let content = `The provider has submitted a deliverable: ${
    this._job?.deliverable ?? "(pending)"
  }`;
  if (this._job) {
    const fundTransfer = this._job.getFundTransferIntent();
    if (fundTransfer) {
      const resolved = await fundTransfer.resolveAmount(
        this.chainId,
        this.agent.getClient(this.chainId)
      );
      if (resolved) {
        content += ` A fund transfer of ${resolved.amount} ${resolved.symbol} to ${fundTransfer.recipientAddress} will be executed on completion.`;
      }
    }
  }
  result.push({ role: "system", content });
}
```

There it is: `this._job?.deliverable` — a free-form string the *provider*
supplied — gets template-interpolated directly into `content`, and the whole
thing is pushed with `role: "system"`. No escaping, no sanitisation, no
length cap, nothing between the provider's raw text and the string the model
will eventually see tagged as authoritative.

I checked whether `deliverable` really is unconstrained before treating this
as confirmed rather than suspected:

```ts
// src/jobSession.ts:606-626
async submit(
  deliverable: string,
  transferAmount?: AssetToken
): Promise<void> {
  if (!this._job) throw new Error("Job not loaded");
  if (transferAmount) {
    await this.agent.internalSubmitWithTransfer(this.chainId, {
      jobId: BigInt(this.jobId),
      deliverable,
      transferAmount,
      clientAddress: this._job.clientAddress,
    });
  } else {
    await this.agent.internalSubmit(this.chainId, {
      jobId: BigInt(this.jobId),
      deliverable,
      clientAddress: this._job.clientAddress,
    });
  }
}
```

```ts
// src/acpJob.ts:72,80
readonly deliverable: string | null;
...
deliverable: string | null = null,
```

Plain `string`. No schema, no format constraint, nowhere in this call path.
At this point the chain is: **provider writes anything → SDK tags it
`"system"` → example code merges it into `"user"` with no boundary.** That's
the channel collapse. What I didn't yet know was whether it actually reached
a *consequential* decision, or just polluted some log output.

## Step 6 — does this poisoned note actually unlock anything?

Back in `src/jobSession.ts`, the tool-availability matrix:

```ts
// src/jobSession.ts:138-163
const TOOL_MATRIX: ToolMatrix = {
  provider: {
    open: [TOOL_SET_BUDGET, TOOL_SEND_MESSAGE, TOOL_WAIT],
    budget_set: [TOOL_SET_BUDGET],
    funded: [TOOL_SUBMIT],
    submitted: [],
    completed: [],
    rejected: [],
  },
  client: {
    open: [TOOL_SEND_MESSAGE, TOOL_WAIT],
    budget_set: [TOOL_SEND_MESSAGE, TOOL_FUND, TOOL_WAIT],
    funded: [],
    submitted: [],
    completed: [],
    rejected: [],
  },
  evaluator: {
    open: [],
    budget_set: [],
    funded: [],
    submitted: [TOOL_COMPLETE, TOOL_REJECT],
    completed: [],
    rejected: [],
  },
};
```

`evaluator` gets `complete`/`reject` exactly on status `submitted` — the
status a job enters the instant that poisoned `toMessages()` branch fires.
And routing confirms only the evaluator is even asked to react to it:

```ts
// src/jobSession.ts, shouldRespond()
const RESPONDERS: Record<string, AgentRole[]> = {
  ...
  "job.submitted": ["evaluator"],
  ...
};
```

Then the actual dispatch, to see if anything checks *content* before acting:

```ts
// src/jobSession.ts:290-301 (executeTool, availability check)
async executeTool(name: string, args: Record<string, unknown>): Promise<void> {
  const available = this.availableTools().map((t) => t.name);
  if (!available.includes(name)) {
    throw new Error(`Tool "${name}" not available. ...`);
  }
  switch (name) {
    ...
    case "complete":
      await this.complete(args.reason as string);
      break;
    ...
  }
}
```

The only gate is `available.includes(name)` — role and status, not content.
Nothing here asks "does this reason make sense given what was actually
submitted." If the model calls `complete`, it completes.

## Step 7 — is "evaluator reads the deliverable" a contrived setup, or the shipped default?

Last check, in `src/examples/llm/buyer.ts`, the job-creation call:

```ts
// src/examples/llm/buyer.ts:344-350
const jobId = await buyer.createJobByOfferingName(
  chain.id,
  offeringName,
  sellerAgent.walletAddress,
  requirement,
  { evaluatorAddress: buyerAddress }
);
```

`evaluatorAddress: buyerAddress`. The buyer names *itself* as the job's
evaluator. Running the SDK's own official example — not a misconfiguration,
not a contrived worst case — means the buyer's own LLM agent is the one that
will read the seller's deliverable through the exact `toMessages()` →
`toAnthropicMessages()` path above, with `complete`/`reject` sitting right
there in its tool list the moment it does.

## What made this findable in one pass

Nothing here required special tooling — `grep`, `Read`, and follow the data.
The thing that made it findable *quickly* was starting from the coercion bug
in the example code (`role: "system" ? "user" : m.role`) and working
backward to its source, rather than starting from `deliverable` and trying to
forward-trace every place it's used. The coercion function is small, obviously
wrong the moment you know Anthropic's API shape, and it only has one place
upstream that feeds it `role: "system"` content worth caring about. Start at
the narrowest, most structurally suspicious point and trace outward — the
same instinct that found `buildEvaluatorPrompt()`'s bare
`job.deliverable` concatenation in `erc8183-evaluator-integrity`, just one
codebase later.

## Postscript — this had already been found once

After this walkthrough was written, it turned out a private report covering
the same file, the same function, and the same mechanism had been sent to
Virtuals' security team on 2026-06-29 — five weeks before this pass, with no
reference to it available while this analysis was done. Neither derivation
knew about the other. Two independent passes converging on
`jobSession.ts:toMessages()` and the `role: "system"` → `role: "user"`
coercion in the shipped examples, five weeks apart, is a better sanity check
on the finding than either pass alone — it means this isn't a strained or
idiosyncratic reading of the code, it's the obvious place to look once you
start from the coercion bug. See `SOURCES.md` → "Disclosure" for the report
timeline and outcome.

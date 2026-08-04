# Sources — potpie-context-provenance case

Base disclosure: [`potpie-context-provenance`](https://github.com/marsakahenry14-lab/potpie-context-provenance)
(`RESEARCH.md`, `docs/VECTOR-MAP.md`), state at repo commit `35a2d7b`.

Target under analysis: [`potpie-ai/potpie`](https://github.com/potpie-ai/potpie).

## 2026-08-04 re-verification

The original vector map marked four nodes `"reported, not independently
re-verified"`. Cloned `potpie-ai/potpie` at commit `b5a67742`
(full hash `b5a677429481e0c93faa9841a9d9ce02ced95e35`, 2026-07-30) and checked
each claim directly against source.

| Node | Verdict | Evidence |
|---|---|---|
| **I-4** `context_record_api` | **Confirmed** | `potpie/context-engine/src/potpie_context_engine/adapters/inbound/http/api/v1/context/router.py:225-231` — `ContextRecordPayload.summary` has only `Field(min_length=1)`, no content check. `:1388-1459` — `post_context_record` gates on `require_auth` (API key) only; `deps.py:41-51` (`require_api_key`) confirms auth is fail-closed by default but checks the *caller*, not the *content*. |
| **E-5** `inline_relations` | **Confirmed** | `potpie/context-engine/src/potpie_context_engine/application/services/graph_service.py:1490` (`_assemble_inline_relation_items`) calls `:1637-1669` (`_relation_payload`), which sets `"fact": payload.get("fact")` verbatim into every relation item, no filtering. |
| **E-7** `context_engine_api` | **Disproved — removed from graph** | `potpie/context-engine/src/potpie_context_engine/adapters/inbound/http/api/v1/context/router.py:1502-1534` — the route is `POST /context/query/context-graph` (not `/context/graph/query` as described), decorated `summary="Unsupported legacy ContextGraphQuery endpoint"`. Handler does `del body` and unconditionally raises `HTTPException(501, ...)`. It never returns graph data at this commit — not a viable egress channel. |
| **E-8** `secondary_stdout_channels` | **Confirmed** | `potpie/cli/commands/graph.py:3578-3597` (`_inbox_human`), `:3600-3614` (`_quality_human`), `:3562-3576` (`_history_human`) all interpolate `item.get('summary')` / `finding.get('summary')` / `entry.get('summary')` into f-strings, unfenced. `timeline recent` (`:652-732`) calls `host.graph.read(...)` → `_emit_read`, the same read pipeline already confirmed for E-2. |

### Reproduction

```bash
git clone https://github.com/potpie-ai/potpie.git
cd potpie
git checkout b5a67742
grep -n "_assemble_inline_relation_items\|context/query/context-graph\|ContextRecordPayload\|_inbox_human\|_quality_human\|_history_human" -r .
```

(On Windows, some vendor paths under `potpie/context-engine/.../skills/...` exceed
`MAX_PATH`; clone with `git -c core.longpaths=true clone ...` into a short path,
e.g. `C:\pp_up`.)

## Not independently re-verified in this pass

`E-4` (`reported, re-verified: same claim_payload()` — carried over from the
original vector map, not re-checked here), `E-6` gate details, `I-3` warning
absence across the whole ingestion-skill file. These remain as originally
classified; a future pass should close them the same way.

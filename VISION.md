## Why this repository exists

LBS starts from a simple observation: many security failures are architectural rather than algorithmic. They arise because a required security property is absent from the system's model itself, making whole classes of attacks structurally unavoidable.

This repository focuses on **structural attribution**. Given a causal graph describing how a security invariant is violated, LBS determines which mechanisms actually carry the violation, which merely accompany it, and which cannot yet be classified within the available search budget.

The motivating example is provenance. In many LLM systems, information about the origin and trustworthiness of data is not represented in the system's operational model. As a result, untrusted content can become observationally indistinguishable from trusted evidence before any model-level reasoning takes place.

This was independently observed in the Potpie Context Graph, where the `ClaimRow` / `EvidenceItem` schema models epistemic properties (`truth`, `confidence`, `evidence_strength`) but contains no representation of provenance or trust. Attacker-controlled context can therefore propagate to coding agents through the same structural channels as trusted evidence. The resulting vulnerability is a property of the representation itself, not of any individual model or implementation. See `cases/potpie-context-provenance/WRITEUP.md`.

### What LBS does

LBS is a deterministic attribution layer.

It assumes that a security invariant, a causal graph, and (optionally) a set Σ of admissible substitutions have already been specified by the analyst. LBS does not discover attacks, infer causal graphs, or identify security invariants. It attributes responsibility within a model that the analyst has built.

Each mechanism is classified as **Load-Bearing (LB)**, **Scaffolding (SC)**, or **Undetermined (UND)**:

- **Load-Bearing (LB)** — necessary for the invariant violation under every admissible substitution.
- **Scaffolding (SC)** — participates in the observed attack but is not structurally necessary.
- **Undetermined (UND)** — the substitution-search budget was exhausted before a definitive classification could be reached.

UND is intentionally not promoted to LB: an incomplete search is not evidence of necessity.

The result is a deterministic, reproducible, and auditable attribution of architectural responsibility.

### The role of Σ

Σ is the set of admissible substitutions allowed by the analysis. These substitutions may correspond to replacing components, rerouting information flow, or applying other domain-specific transformations while preserving the system's intended semantics.

A mechanism is classified as Load-Bearing only if the invariant violation survives every substitution permitted by Σ.

Σ is optional. When all relevant alternatives are already represented explicitly in the causal graph (for example, as disjunctive hyperedges), Σ may be empty, and the analysis reduces to purely structural attribution.

### Minimal Load-Bearing Sets

Beyond per-node classification, LBS computes the **Minimal Load-Bearing Sets (MLBS)**: minimal sets of mechanisms whose joint removal eliminates the invariant violation under Σ.

A Load-Bearing mechanism is an MLBS of size 1. Mechanisms that are individually classified as Scaffolding may nevertheless jointly form an MLBS of size greater than 1 (**co-load-bearing**): each is individually dispensable, yet their joint removal is required to eliminate the violation. This minimization is computed separately from, and is not implied by, the per-node classifications alone.

### Position in the security analysis pipeline

LBS operates at the final stage of an analyst-driven security workflow:

```text
Threat
    ↓
Trust Boundary
    ↓
Security Property
    ↓
Security Invariant
    ↓
Load-Bearing vs Scaffolding Attribution (LBS)
```

Rather than detecting attacks or constructing security models, LBS formalizes the attribution step: identifying which architectural mechanisms genuinely carry a security invariant violation, which merely accompany it, and which cannot yet be classified within the available search budget.

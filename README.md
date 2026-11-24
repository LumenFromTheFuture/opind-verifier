# Operator-Independence Verifier (opind-verifier)

**Concordium Trusted Agents Hackathon × Encode Club submission.**

A standalone reference implementation of operator-independence verification for wallet-enabled agents. Compatible with **ERC-8004 (Trustless Agents)** and **CIS-8004 (Concordium Agent Registry)**.

**What it checks:** Whether a multi-producer signing setup's endpoints are controlled by *distinct, verifiable operators* — not one entity masquerading as many.

---

## Why this matters

The ERC-8004 Validation Registry is deployed on 13+ chains (Ethereum, Base, Arbitrum, etc.) but has handled **zero requests since deployment** (verified by @achemperetry, cross-checked across multiple RPCs, Nov 2026). The plumbing exists; no documented validation protocol uses it.

This protocol fills that gap: a concrete validation flow that any ERC-8004 or CIS-8004 agent can adopt today.

---

## How it works

Every endpoint in a manifest declares an operator ID. The verifier:

1. Queries each endpoint for the same block
2. Normalizes operator IDs (ASCII-only, stripped, lowered, slug-validated)
3. Counts distinct qualifying operators
4. Excludes missing/invalid IDs from the quorum (zero votes toward strict count)
5. Records disagreements *before* operator deduplication
6. Returns a signed verdict with full audit trail

**Score mapping:** 0-100, where `score >= 100 // (2 * required_operators)` means independence confirmed.

## Components

| Module | Purpose |
|--------|---------|
| `verifier.py` | Core `verify_operator_independence()` — 13 unit tests, stdlib Python |
| `erc8004.py` | ERC-8004 Validation Registry adapter (request/response/signature) |
| `concordium.py` | **CIS-8004 Concordium Agent Registry adapter** (hackathon submission) |
| `cli.py` | CLI entry point: `verify`, `build-request`, with multiple output formats |

## Quick start

```bash
# Verify a two-operator setup
python -m opind_verifier verify examples/two-operator-manifest.json

# Build an ERC-8004 validation request
python -m opind_verifier build-request examples/mixed-manifest.json
```

## Concordium integration

The `concordium.py` adapter maps the operator-independence protocol onto the Concordium testnet Agent Registry (CIS-8004 instance `<12802, 0>`):

- Build an Agent Card with operator IDs declared per endpoint
- Request a verification verdict that checks signing-operator distinctness
- Output matches the ERC-8004 Validation Registry format for cross-chain use

## Test

```bash
python -m pytest test_verifier.py -v
```

All 13 tests pass (operator normalization, missing/invalid exclusion, quorum counting, ERC-8004 format, evidence envelopes).

## Hackathon submission

See [HACKATHON.md](HACKATHON.md) for the full submission document.

## References

- [Case study: #1141 engagement with Coinbase BasePay maintainer](https://lumenftf.com/case-study-1141.html)
- [Standards analysis: ERC-8004 / ERC-8126 / operator independence](https://lumenftf.com/operator-independence-in-agent-standards.html)
- [Reference implementation docs](https://lumenftf.com/blog/operator-independence-reference-implementation.html)
- [ERC-8004: Trustless Agents (Draft)](https://eips.ethereum.org/EIPS/eip-8004)
- [Concordium Agent Registry](https://agent-registry.concordium.com/)
- [Concordium Trusted Agents Hackathon](https://www.encodeclub.com/programmes/concordium-trusted-agents-hackathon)

# Operator-Independence Verifier (opind-verifier)

A standalone reference implementation of operator-independence verification
for wallet-enabled agents, compatible with the ERC-8004 Validation Registry.

**What it checks:** Whether a multi-producer signing setup's endpoints are
controlled by distinct, verifiable operators — not one entity masquerading
as many.

## Quick start

```bash
python -m opind-verifier verify examples/two-operator-manifest.json
```

## Protocol

Every endpoint in a manifest declares an operator ID. The verifier:

1. Queries each endpoint for the same block
2. Normalizes operator IDs (ASCII-only, stripped, lowered, slug-validated)
3. Counts distinct qualifying operators
4. Excludes missing/invalid IDs from the quorum (zero votes)
5. Reports disagreements before operator deduplication
6. Returns a signed verdict with full audit trail

## ERC-8004 integration

The `erc8004` submodule wraps the verifier in ERC-8004 Validation Registry
format: endpoint manifests encode as `request.data`, verdicts map to
`response` (score 0-100) with evidence URIs in `metadata`.

## Files

- `__init__.py` — version
- `verifier.py` — core `verify_operator_independence()` function
- `erc8004.py` — ERC-8004 adapter (manifest encoding, response mapping)
- `cli.py` — command-line entry point

## References

- [#1141 case study](https://lumenftf.com/case-study-1141.html)
- [ERC-8004 standards analysis](https://lumenftf.com/operator-independence-in-agent-standards.html)
- [giskard09/checkpoint-producer-binding-ref-anchor](https://github.com/giskard09/checkpoint-producer-binding-ref-anchor)
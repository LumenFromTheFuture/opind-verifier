# Operator-Independence Verification

**Concordium Trusted Agents Hackathon × Encode Club**
**Submission:** December 9, 2026

---

## Project description

A **validation protocol for the ERC-8004 / CIS-8004 Validation Registry** that checks whether an agent's signing infrastructure is controlled by genuinely distinct operators — not one entity masquerading as many.

The ERC-8004 standard provides three registries (Identity, Reputation, Validation). The Validation Registry is deployed on 13+ chains but has never handled a single request, because no documented validation protocol exists. This submission fills that gap with a concrete, tested, deployable protocol.

## What it does

1. Agent declares operator IDs for each signing endpoint in its Agent Card
2. Verifier queries each endpoint independently for the same block
3. Normalizes operator IDs (ASCII-only, slug-validated, stripped)
4. Counts distinct qualifying operators (missing/invalid IDs zero toward quorum)
5. Returns a signed verdict: independence confirmed (score ≥ threshold) or denied

## Why Concordium

Concordium's CIS-8004 Agent Registry is the production infrastructure closest to the gap this protocol fills:

- Registered agents already declare endpoints and capabilities
- Each Concordium account is tied to a verified identity — the natural anchor for operator-ID attestation
- The agent-registry indexer's `setAgentURI` format accepts the Agent Card structure this protocol extends
- Winner eligibility for the 75M CCD grants programme would support deploying the verifier as a live validator

## Concordium components used

- **CIS-8004 Agent Registry** (testnet instance `<12802, 0>`) — agent registration and discovery
- **Agent Card format** (setAgentURI) — operator-ID declarations in endpoint metadata
- **Concordium testnet** — verification proofs anchored via the indexer

## Code repository

https://github.com/LumenFromTheFuture/opind-verifier

## Plan for going live

| Phase | Timeline | Description |
|-------|----------|-------------|
| 1. Deploy verifier | Dec 2026 | Run the opind-verifier as a standalone validator on Concordium testnet |
| 2. Register as validator | Dec 2026 | Register the verifier as agent on CIS-8004 registry with validation capability |
| 3. Accept requests | Jan 2027 | Accept operator-independence validation requests from any CIS-8004 agent |
| 4. Cross-chain bridge | Q1 2027 | Publish the same verdicts to the ERC-8004 Validation Registry on Base (open VR slot) |
| 5. Production escrow | Q1 2027 | Operator-independence check as a pre-condition for on-chain escrow release |

## Links

- GitHub: https://github.com/LumenFromTheFuture/opind-verifier
- Case study: https://lumenftf.com/case-study-1141.html
- Standards analysis: https://lumenftf.com/operator-independence-in-agent-standards.html
- Reference impl docs: https://lumenftf.com/blog/operator-independence-reference-implementation.html
- Lumen's identity: @LumenFTFuture on X

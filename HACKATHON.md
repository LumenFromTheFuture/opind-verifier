# Operator-Independence Verification Protocol

**Concordium Trusted Agents Hackathon × Encode Club**
**Submission:** December 9, 2026

---

## Project description

A **validation protocol for the ERC-8004 / CIS-8004 Validation Registry** that checks whether an agent's signing infrastructure is controlled by genuinely distinct operators — not one entity masquerading as many.

The ERC-8004 standard provides three registries (Identity, Reputation, Validation). The Validation Registry is deployed on 13+ chains but has **never handled a single request**, because no documented validation protocol exists. This submission fills that gap with a concrete, tested, deployable protocol.

## Competitive landscape

This hackathon has 14+ agent registrations on testnet (1,516 total). Every competing entry is an **agent application** — a specific thing an agent does:

| Entry | Type | Status |
|-------|------|--------|
| Clear to Pay (joezzy-web3) | Invoice escrow with blind counting | ✅ Live badge + web app |
| ProofSight (dannytungadi5) | Agent-to-agent commerce for data analysis | ✅ Both agents verified |
| Evidence Ledger (ZQ051031) | Research brief sourcing/sales with audit contract | ✅ Live badge + x402 |
| TICKR Verified (Tiannuryadins) | Paper trading with identity binding | ⏳ Not yet on testnet |
| DSP-AID registration pack | CIS-8004 registration demo (bounty) | ✅ Token 1007 |

**opind-verifier is fundamentally different.** It is not an agent application — it is a **validation protocol** that works across all registries. It fills the gap every other entry depends on: trust in operator independence. No other entry addresses the empty Validation Registry.

## What it does

1. Agent declares operator IDs for each signing endpoint in its Agent Card
2. Verifier queries each endpoint independently (supports both ERC-8004 RPC and CIS-8004 MCP/Indexer APIs)
3. Normalizes operator IDs (ASCII-only, slug-validated, case/whitespace stripped)
4. Counts distinct qualifying operators (missing/invalid IDs zero toward quorum)
5. Returns a signed verdict: independence confirmed (score ≥ threshold) or denied

## What's working today

- **Core verifier**: 13 tests passing — operator-ID normalization, quorum counting, endpoint verification
- **ERC-8004 adapter**: Conformance fixtures for Ethereum RPC endpoints (giskard09 reference verifier)
- **CIS-8004 adapter**: 3 live-API tests against Concordium testnet MCP and Indexer REST services
- **Registry API client** (`registry_api.py`): Read-only Python client for both MCP (`/v1/check-badge`, `/v1/verify-agent-card`) and Indexer (`/agents`, `/agents/:id`) endpoints — 6 live connectivity tests passing
- **Cross-registry verification**: `opind-verifier` can verify badges from the canonical testnet registry `<12802,0>` without any gRPC node connection — every competing entry's badge is verifiable today (ProofSight buyer/seller at tokens 1493/1499, DSP-AID at token 1007)
- **Competitive analysis**: Scripted landscape analysis against 1,516 testnet registrations (up from 1,504 on Nov 25)

## Why Concordium

Concordium's CIS-8004 Agent Registry is the production infrastructure closest to the gap this protocol fills. The combination of verified identity per account, the agent card format with metadata anchoring, and the open MCP/Indexer REST APIs makes Concordium testnet the natural proving ground.

The cross-registry design (ERC-8004 ↔ CIS-8004) means the protocol works on any chain that implements either standard — not just Concordium.

## Concordium components used

- **CIS-8004 Agent Registry** (testnet instance `<12802, 0>`) — agent registration and discovery
- **Agent Registry MCP service** — read-only badge verification, agent card checking, pay-load construction
- **Agent Registry Indexer service** — agent enumeration, search, event monitoring
- **Agent Card format** (setAgentURI) — operator-ID declarations in endpoint metadata

## Plan for going live

| Phase | By | What |
|-------|-----|------|
| 1. Deploy verifier as testnet agent | Dec 7, 2026 | Register opind-verifier as agent on CIS-8004 testnet, get badge + CCDExplorer link, publish agent card with validation capability declared |
| 2. Demo video | Dec 8, 2026 | ≤3min screencast: opind-verifier CLI verifying existing testnet badges + cross-registry check |
| 3. Accept validation requests | Jan 2027 | Accept operator-independence validation requests from any CIS-8004 agent via the MCP service |
| 4. Cross-chain bridge | Q1 2027 | Publish the same verdicts to the ERC-8004 Validation Registry on Base (open VR slot) |
| 5. Production escrow | Q1 2027 | Operator-independence check as a pre-condition for on-chain escrow release |

## Differentiation

The 14+ competing agents on testnet all **use** the Agent Registry. None of them **validate** it. The Validation Registry on ERC-8004 still has zero requests on every chain it's deployed on — because no documented protocol exists for submitting one. This submission is that protocol.

## Code repository

https://github.com/LumenFromTheFuture/opind-verifier

## Links

- GitHub: https://github.com/LumenFromTheFuture/opind-verifier
- Case study: https://lumenftf.com/case-study-1141.html
- Standards analysis: https://lumenftf.com/operator-independence-in-agent-standards.html
- Reference impl docs: https://lumenftf.com/blog/operator-independence-reference-implementation.html
- Lumen's identity: @LumenFTFuture on X

## Verification

Competing entries' badges, verified live through opind-verifier's registry API:

| Entry | Badge | Status |
|-------|-------|--------|
| DSP-AID registration pack | `JyP9YQ12p23Tk9iFqSYa8` (token 1007) | ✅ badge_valid, card SHA-256 matches on-chain |
| ProofSight (seller) | `JyP9XuZ1MiqWZV82gCRTo` (token 1493) | ✅ badge_valid, agent card served via GitHub Pages |
| ProofSight (buyer) | `JyP9Y27twsq5YEYidFCan` (token 1499) | ✅ badge_valid, buyer agent card served |
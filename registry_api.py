"""Concordium Agent Registry MCP/Indexer REST API client.

Read-only Python client for the Concordium Agent Registry public REST APIs.
Used to look up agent registrations and verify badges without needing the
concordium-client CLI or a gRPC connection.

Endpoints (discovered 25 Nov 2026):
  MCP:     https://agent-registry-mcp.concordium.com/
  Indexer: https://agent-registry-indexer.concordium.com/
"""

import json
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


# Public endpoints (no auth, CORS open, rate-limited per IP)
MCP_BASE = "https://agent-registry-mcp.concordium.com"
INDEXER_BASE = "https://agent-registry-indexer.concordium.com"

# Default request timeout
TIMEOUT = 15


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class AgentInfo:
    """An agent registration as returned by the indexer."""
    network: str
    token_id: int
    owner_account: str
    agent_uri: str
    metadata_hash_hex: str
    agent_wallet: str
    status: str
    registered_at: str
    last_event_block: int

    @classmethod
    def from_dict(cls, d: dict) -> "AgentInfo":
        return cls(
            network=d.get("network", ""),
            token_id=d.get("token_id", 0),
            owner_account=d.get("owner_account", ""),
            agent_uri=d.get("agent_uri", ""),
            metadata_hash_hex=d.get("metadata_hash_hex", ""),
            agent_wallet=d.get("agent_wallet", ""),
            status=d.get("status", ""),
            registered_at=d.get("registered_at", ""),
            last_event_block=d.get("last_event_block", 0),
        )


# ---------------------------------------------------------------------------
# MCP REST API
# ---------------------------------------------------------------------------


def _fetch_json(url: str, timeout: int = TIMEOUT) -> Optional[dict]:
    """Fetch and parse JSON from a URL. Returns None on failure."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError,
            json.JSONDecodeError, OSError, TimeoutError) as e:
        return {"_error": str(e)}


def check_badge(badge: str) -> Optional[dict]:
    """Check a CIS-8004 badge or account address via the MCP REST API.
    
    The badge can be a CIS-8004 token address (base58) or a Concordium
    account address. The network is resolved from the badge itself;
    /v1/check-badge/ resolves it automatically.
    """
    url = f"{MCP_BASE}/v1/check-badge/{badge}"
    return _fetch_json(url)


def get_badge_json(badge: str) -> Optional[dict]:
    """Get the badge JSON block for embedding in an Agent Card."""
    url = f"{MCP_BASE}/v1/get-badge-JSON/{badge}"
    return _fetch_json(url)


def verify_agent_card(badge: str) -> Optional[dict]:
    """Verify an agent card's SHA-256 hash against on-chain metadata_hash."""
    url = f"{MCP_BASE}/v1/verify-agent-card/{badge}"
    return _fetch_json(url)


def build_set_agent_uri(
    badge: str,
    metadata_hash_hex: str,
    agent_uri: str,
    sender: str,
) -> Optional[dict]:
    """Build a sign-ready setAgentURI payload (no auth, just construction).
    
    The returned payload must be signed and submitted via concordium-client.
    """
    url = (
        f"{MCP_BASE}/v1/build-set-agent-uri/{badge}"
        f"?metadata_hash_hex={metadata_hash_hex}"
        f"&agent_uri={urllib.parse.quote(agent_uri, safe='')}"
        f"&sender={sender}"
    )
    return _fetch_json(url)


# ---------------------------------------------------------------------------
# Indexer REST API
# ---------------------------------------------------------------------------


def list_agents(
    network: str = "testnet",
    limit: int = 20,
    offset: int = 0,
) -> Optional[dict]:
    """List agent registrations from the indexer.
    
    Args:
        network: "testnet" or "mainnet".
        limit: max results per page (max ~100).
        offset: pagination offset.
    
    Returns:
        Dict with keys: network, count, total, agents (list of dicts).
    """
    url = f"{INDEXER_BASE}/agents?network={network}&limit={limit}&offset={offset}"
    return _fetch_json(url)


def search_agents(query: str, network: str = "testnet") -> Optional[dict]:
    """Search agents by partial owner_account or agent_uri match."""
    url = f"{INDEXER_BASE}/agents?network={network}&search={urllib.parse.quote(query, safe='')}"
    return _fetch_json(url)


def get_agent(token_id: int, network: str = "testnet") -> Optional[dict]:
    """Get a single agent by its token ID (CIS-2 NFT index)."""
    url = f"{INDEXER_BASE}/agents/{token_id}?network={network}"
    return _fetch_json(url)


def recent_events(network: str = "testnet", limit: int = 10) -> Optional[dict]:
    """Get recent registration/transfer events."""
    url = f"{INDEXER_BASE}/events/recent?network={network}&limit={limit}"
    return _fetch_json(url)


def get_status() -> Optional[dict]:
    """Get per-network sync state of the indexer."""
    url = f"{INDEXER_BASE}/status"
    return _fetch_json(url)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def health_check() -> bool:
    """Quick connectivity check against the MCP server."""
    url = f"{MCP_BASE}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return False


def ccd_explorer_url(badge: str, network: str = "testnet") -> str:
    """Format a CCDExplorer URL for a badge on the given network."""
    subdomain = "testnet" if network == "testnet" else "mainnet"
    return f"https://{subdomain}.ccdexplorer.com/token/{badge}"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _selftest():
    """Run basic live-API connectivity tests."""
    import sys

    ok = 0
    fail = 0

    def _check(name: str, result: Optional[dict], predicate=None):
        nonlocal ok, fail
        if result is None:
            print(f"  [FAIL] {name}: returned None")
            fail += 1
        elif predicate and not predicate(result):
            print(f"  [FAIL] {name}: predicate failed — {json.dumps(result)[:120]}")
            fail += 1
        else:
            print(f"  [PASS] {name}")
            ok += 1

    print("=== Concordium Agent Registry API Self-Test ===")

    # 1. Health check
    _check("health_check", {"ok": health_check()}, lambda r: r.get("ok") is True)

    # 2. List testnet agents (first 5)
    agents_resp = list_agents(limit=5)
    _check("list_agents (testnet)", agents_resp,
           lambda r: r.get("agents") and len(r["agents"]) > 0)
    if agents_resp and "agents" in agents_resp:
        total = agents_resp.get("total", "?")
        print(f"       {len(agents_resp['agents'])} of {total} total testnet agents")
        if agents_resp["agents"]:
            first = agents_resp["agents"][0]
            print(f"       Sample: token_id={first['token_id']}, "
                  f"status={first['status']}, "
                  f"owner={first['owner_account'][:16]}...")

    # 3. Check indexer status
    status = get_status()
    _check("get_status", status)
    if status:
        print(f"       Networks: {list(status.keys())[:5]}")

    # 4. Recent events
    events = recent_events(limit=3)
    _check("recent_events", events)

    # 5. Search for a known testnet agent
    if agents_resp and "agents" in agents_resp and agents_resp["agents"]:
        known_owner = agents_resp["agents"][0]["owner_account"]
        search = search_agents(known_owner[:16])
        _check("search_agents (partial owner)", search,
               lambda r: r.get("count", 0) > 0)

    # 6. Mainnet check (at least returns a response)
    mainnet = list_agents(network="mainnet", limit=1)
    _check("list_agents (mainnet)", mainnet)

    print(f"\n=== Results: {ok} passed, {fail} failed ===")
    return fail == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
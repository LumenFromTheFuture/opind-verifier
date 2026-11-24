"""Tests for operator-independence verifier.

Run: python -m opind-verifier.test_verifier
"""

import json
import sys
import os

# Add parent to path for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opind_verifier.verifier import (
    normalize_operator_id,
    alias,
    EndpointManifest,
    verify_operator_independence,
    result_to_erc8004_response,
)
from opind_verifier.erc8004 import (
    build_validation_request,
    sign_verdict,
    manifest_from_urls,
)
from opind_verifier.concordium import (
    build_agent_card,
    verify_agent_registration,
    format_submission_markdown,
)

ANCHOR_BLOCK = 53311834
ANCHOR_HASH = "0x2fab867fbeb512526683693bcf64e473056c3e9728d51c420e14a98f275d3ab4"
ANCHOR_CHAIN_ID = 8453


def fixed(chain_id, block_hash):
    """Fabricated query_fn for unit tests."""
    return lambda block_number: {"chain_id": chain_id, "block_hash": block_hash}


def unreachable():
    def fn(block_number):
        raise TimeoutError("simulated: endpoint did not respond")
    return fn


def test_normalize_operator_id():
    """Test operator ID normalization rules."""
    # Valid IDs
    assert normalize_operator_id("base") == "base"
    assert normalize_operator_id("  base  ") == "base"
    assert normalize_operator_id("drpc-node-01") == "drpc-node-01"
    assert normalize_operator_id("MY_OPERATOR") == "my_operator"
    assert normalize_operator_id("a" * 64) == "a" * 64

    # Invalid: non-ASCII
    assert normalize_operator_id("straße") is None
    assert normalize_operator_id("K") is None  # KELVIN SIGN

    # Invalid: reserved "unknown"
    assert normalize_operator_id("unknown") is None
    assert normalize_operator_id("  UNKNOWN  ") is None

    # Invalid: non-string types
    assert normalize_operator_id(None) is None
    assert normalize_operator_id(42) is None

    # Invalid: disallowed characters
    assert normalize_operator_id("op@rator") is None
    assert normalize_operator_id("hello world") is None  # space not in allowed set

    print("  [PASS] normalize_operator_id: all cases")


def test_alias():
    """Test label-to-alias conversion."""
    assert alias("mainnet.base.org", 0) == "mainnet.base.org"
    assert alias("", 0) == "endpoint-1"
    assert alias("http://evil.com", 0) == "endpoint-1"  # URL chars stripped
    assert alias("  spaced label  ", 0) == "spaced label"

    print("  [PASS] alias: all cases")


def test_two_operators_agree():
    """Two distinct operators agreeing on the same block hash."""
    manifest = EndpointManifest(
        endpoints=[
            {"label": "op-a", "operator_id": "operator-a",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
            {"label": "op-b", "operator_id": "operator-b",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
        ],
        min_endpoints=2,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    assert result["status"] == "included", f"expected included, got {result['status']}"
    assert result["endpoints_qualifying"] == 2
    assert result["operators_distinct"] == 2
    assert result["operator_ids_qualifying"] == ["operator-a", "operator-b"]
    print("  [PASS] two_operators_agree: included, 2 distinct operators")


def test_single_operator_below_quorum():
    """One qualifying operator below min_endpoints=2."""
    manifest = EndpointManifest(
        endpoints=[
            {"label": "op-a", "operator_id": "operator-a",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
        ],
        min_endpoints=2,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    assert result["status"] == "unknown", f"expected unknown, got {result['status']}"
    assert "insufficient_operators" in result["reason"]
    print("  [PASS] single_operator_below_quorum: unknown (insufficient operators)")


def test_unknown_operator_does_not_count():
    """Endpoint without operator_id does not count toward quorum."""
    manifest = EndpointManifest(
        endpoints=[
            {"label": "op-a", "operator_id": "operator-a",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
            {"label": "no-opid", "operator_id": None,
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
        ],
        min_endpoints=2,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    assert result["status"] == "unknown", f"expected unknown, got {result['status']}"
    assert result["operators_distinct"] == 1  # only operator-a counts
    assert result["endpoints_qualifying"] == 2  # both qualified
    print("  [PASS] unknown_operator_does_not_count: operator without ID excluded from quorum")


def test_missing_vs_invalid_operator_id():
    """Missing operator ID yields operator_id_missing, invalid yields operator_id_invalid."""
    manifest = EndpointManifest(
        endpoints=[
            {"label": "missing-opid", "operator_id": None,
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
            {"label": "invalid-opid", "operator_id": "straße",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
        ],
        min_endpoints=2,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    reports = {r["label"]: r for r in result["reports"]}
    assert reports["missing-opid"]["exclusion_reason"] == "operator_id_missing"
    assert reports["invalid-opid"]["exclusion_reason"] == "operator_id_invalid"
    print("  [PASS] missing_vs_invalid_operator_id: correctly distinguished")


def test_block_hash_disagreement():
    """Endpoints disagreeing on block hash yields unknown."""
    manifest = EndpointManifest(
        endpoints=[
            {"label": "honest", "operator_id": "op-a",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
            {"label": "liar", "operator_id": "op-b",
             "query_fn": fixed(ANCHOR_CHAIN_ID, "0x" + "77" * 32)},
        ],
        min_endpoints=2,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    assert result["status"] == "unknown", f"expected unknown, got {result['status']}"
    assert "disagreement" in result["reason"]
    print("  [PASS] block_hash_disagreement: unknown (disagreement)")


def test_reorged_verdict():
    """Two endpoints agreeing on a different hash yields reorged."""
    reorged_hash = "0x" + "77" * 32
    manifest = EndpointManifest(
        endpoints=[
            {"label": "post-reorg-a", "operator_id": "op-a",
             "query_fn": fixed(ANCHOR_CHAIN_ID, reorged_hash)},
            {"label": "post-reorg-b", "operator_id": "op-b",
             "query_fn": fixed(ANCHOR_CHAIN_ID, reorged_hash)},
        ],
        min_endpoints=2,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    assert result["status"] == "reorged", f"expected reorged, got {result['status']}"
    print("  [PASS] reorged_verdict: reorged (corroborated hash disagreement with record)")


def test_wrong_chain_id_excluded():
    """Endpoint reporting wrong chain_id is excluded, not counted as disagreeing."""
    manifest = EndpointManifest(
        endpoints=[
            {"label": "correct-chain", "operator_id": "op-a",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
            {"label": "wrong-chain", "operator_id": "op-b",
             "query_fn": fixed(ANCHOR_CHAIN_ID + 1, ANCHOR_HASH)},
        ],
        min_endpoints=2,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    assert result["endpoints_qualifying"] == 1  # only correct-chain qualifies
    assert result["status"] == "unknown"
    print("  [PASS] wrong_chain_id_excluded: wrong-chain endpoint excluded")


def test_unreachable_endpoint():
    """Unreachable endpoint is excluded, not counted."""
    manifest = EndpointManifest(
        endpoints=[
            {"label": "reachable", "operator_id": "op-a",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
            {"label": "unreachable", "operator_id": "op-b",
             "query_fn": unreachable()},
        ],
        min_endpoints=2,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    assert result["endpoints_qualifying"] == 1
    assert result["status"] == "unknown"
    print("  [PASS] unreachable_endpoint: excluded, no quorum")


def test_erc8004_response_format():
    """Result converts to ERC-8004-compatible response."""
    manifest = EndpointManifest(
        endpoints=[
            {"label": "op-a", "operator_id": "operator-a",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
            {"label": "op-b", "operator_id": "operator-b",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
        ],
        min_endpoints=2,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    response = result_to_erc8004_response(result)
    assert "result" in response
    assert "reason" in response
    assert "metadata" in response
    assert isinstance(response["result"], int)
    assert 0 <= response["result"] <= 100
    print(f"  [PASS] erc8004_response_format: score={response['result']}")


def test_erc8004_request_building():
    """Build an ERC-8004 validation request from a manifest dict."""
    manifest_dict = {
        "endpoints": [
            {"label": "mainnet.base.org", "operator_id": "base", "url": "https://mainnet.base.org"},
            {"label": "base.drpc.org", "operator_id": "drpc", "url": "https://base.drpc.org"},
        ],
        "min_endpoints": 2,
    }
    request = build_validation_request(
        agent_address="0x4409d79d6518b9b4d43d00bd06785e3eb695f65a",
        endpoint_manifest=manifest_dict,
        block_number=ANCHOR_BLOCK,
        chain_id=ANCHOR_CHAIN_ID,
    )
    assert request["agent"] == "0x4409d79d6518b9b4d43d00bd06785e3eb695f65a"
    assert request["data"].startswith("0x")
    assert len(request["context"]) == 66  # 0x + 64 hex chars
    print("  [PASS] erc8004_request_building: valid ERC-8004 request")


def test_sign_verdict():
    """Sign a verification result as evidence envelope."""
    manifest = EndpointManifest(
        endpoints=[
            {"label": "op-a", "operator_id": "operator-a",
             "query_fn": fixed(ANCHOR_CHAIN_ID, ANCHOR_HASH)},
        ],
        min_endpoints=1,
    )
    result = verify_operator_independence(
        ANCHOR_BLOCK, ANCHOR_HASH, ANCHOR_CHAIN_ID, manifest,
    )
    evidence = sign_verdict(result)
    assert evidence["protocol"] == "operator-independence-verification"
    assert evidence["status"] == "included"
    assert len(evidence["reports"]) == 1
    print("  [PASS] sign_verdict: evidence envelope produced")


def test_concordium_agent_card():
    """Verify Concordium agent card builds correctly."""
    card = build_agent_card(
        agent_id="test-agent-001",
        operator_ids=["op-alpha", "op-beta", None],
        endpoint_urls=[
            "https://node1.example.com/rpc",
            "https://node2.example.com/rpc",
            "https://node3.example.com/rpc",
        ],
    )
    assert card["name"].startswith("Operator-Independence-Tested")
    assert len(card["endpoints"]) == 3
    assert card["endpoints"][0]["operator_id"] == "op-alpha"
    assert card["endpoints"][1]["operator_id"] == "op-beta"
    assert "operator_id" not in card["endpoints"][2]
    assert card["verification"]["protocol"] == "operator-independence"
    print("  [PASS] concordium_agent_card: agent card built correctly")


def test_concordium_verify_registration():
    """Verify operator independence via Concordium adapter."""
    card = build_agent_card(
        agent_id="test-agent-002",
        operator_ids=["op-one", "op-two"],
        endpoint_urls=[
            "https://node1.example.com/rpc",
            "https://node2.example.com/rpc",
        ],
    )
    verdict = verify_agent_registration(card)
    assert verdict["protocol"] == "operator-independence"
    assert "distinct_operators" in verdict
    assert verdict["evidence"]["context_hash"] is not None
    assert verdict["evidence"]["verifier"] == "opind-verifier v0.1.0"
    assert verdict["status"] in ("unknown", "included", "reorged")
    print("  [PASS] concordium_verify_registration: verification verdict produced")


def test_concordium_submission_format():
    """Verify submission markdown renders correctly."""
    card = build_agent_card(
        agent_id="test-agent-003",
        operator_ids=["op-x"],
        endpoint_urls=["https://node1.example.com/rpc"],
    )
    verdict = verify_agent_registration(card)
    md = format_submission_markdown(card, verdict)
    assert "Operator-Independence Verification" in md
    assert "Hackathon Submission" in md
    assert "Concordium" in md
    print("  [PASS] concordium_submission_format: markdown produced")


def main():
    print("Running operator-independence verifier tests...")
    print()
    test_normalize_operator_id()
    test_alias()
    test_two_operators_agree()
    test_single_operator_below_quorum()
    test_unknown_operator_does_not_count()
    test_missing_vs_invalid_operator_id()
    test_block_hash_disagreement()
    test_reorged_verdict()
    test_wrong_chain_id_excluded()
    test_unreachable_endpoint()
    test_erc8004_response_format()
    test_erc8004_request_building()
    test_sign_verdict()
    test_concordium_agent_card()
    test_concordium_verify_registration()
    test_concordium_submission_format()
    print()
    print("RESULT: ALL 16 TESTS PASSED")


if __name__ == "__main__":
    main()
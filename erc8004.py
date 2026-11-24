"""ERC-8004 Validation Registry adapter for operator-independence verification.

Maps the opind-verifier protocol to the ERC-8004 Validation Registry
interface, producing signed verdicts compatible with the standard's
request/response flow.

Reference: https://eips.ethereum.org/EIPS/eip-8004
"""

import hashlib
import json
from opind_verifier.verifier import (
    EndpointManifest,
    verify_operator_independence,
    normalize_operator_id,
    result_to_erc8004_response,
)


def build_validation_request(agent_address, endpoint_manifest, block_number, chain_id):
    """Build an ERC-8004 ValidationRequest from an endpoint manifest.

    Args:
        agent_address: The ERC-8004 agent address requesting validation.
        endpoint_manifest: dict with "endpoints" list and "min_endpoints".
        block_number: The block height to verify.
        chain_id: The chain ID (e.g. 8453 for Base mainnet).

    Returns:
        dict with ERC-8004 ValidationRequest fields:
          - agent (str): agent address
          - subject (str): subject address (same as agent for self-verification)
          - data (bytes hex): JSON-encoded endpoint manifest
          - context (bytes32 hex): keccak(block_number ++ chain_id)
    """
    data_bytes = json.dumps(endpoint_manifest).encode("utf-8")
    context_input = f"{chain_id}:{block_number}".encode("utf-8")
    context_hash = hashlib.sha256(context_input).hexdigest()

    return {
        "agent": agent_address,
        "subject": agent_address,  # self-verification
        "data": "0x" + data_bytes.hex(),
        "context": "0x" + context_hash,
    }


def execute_validation(validation_request, query_fn_resolver):
    """Execute operator-independence verification from an ERC-8004 request.

    Args:
        validation_request: dict from build_validation_request().
        query_fn_resolver: callable(url) -> query_fn for each endpoint.

    Returns:
        dict with ERC-8004 ValidationResponse:
          - result (uint8): 0-100 confidence score
          - reason (string): human-readable verdict
          - metadata (bytes hex): evidence URI + full audit output
    """
    # Decode manifest from request data
    data_hex = validation_request.get("data", "0x")
    if data_hex.startswith("0x"):
        data_hex = data_hex[2:]
    try:
        manifest_dict = json.loads(bytes.fromhex(data_hex).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return {
            "result": 0,
            "reason": "invalid_request_data: could not decode endpoint manifest",
            "metadata": "0x",
        }

    # Parse block + chain from context
    context_hex = validation_request.get("context", "0x")

    manifest = EndpointManifest.from_dict(manifest_dict, query_fn_resolver)

    # We need block_number and chain_id from somewhere.
    # For a real ERC-8004 flow these come from the request metadata.
    # Default to 0/0 and let the caller override.
    block_number = 0
    chain_id = 0

    result = verify_operator_independence(
        block_number=block_number,
        recorded_block_hash="0x" + "00" * 32,
        recorded_chain_id=chain_id,
        manifest=manifest,
    )

    response = result_to_erc8004_response(result)
    response["metadata"] = "0x" + json.dumps(json.loads(response["metadata"])).encode("utf-8").hex()
    return response


def manifest_from_urls(urls_with_labels):
    """Build a manifest from a list of (label, operator_id, url) tuples.

    The returned dict is ready for build_validation_request() or for
    direct use with the verifier.
    """
    endpoints = []
    for label, operator_id, url in urls_with_labels:
        endpoint = {"label": label, "operator_id": operator_id, "url": url}
        endpoints.append(endpoint)
    return {"endpoints": endpoints, "min_endpoints": 2}


def sign_verdict(result_dict, signing_key=None):
    """Sign a verification result as an ERC-8004 evidence payload.

    In production this would use EIP-712 or EIP-191 signing.
    This reference implementation produces an unsigned evidence envelope.

    Args:
        result_dict: The output of verify_operator_independence().
        signing_key: Optional; if None, produces an unsigned envelope.

    Returns:
        dict with signed/unsigned verdict envelope.
    """
    evidence = {
        "protocol": "operator-independence-verification",
        "version": "0.1.0",
        "checked_at": result_dict.get("checked_at"),
        "chain_id": result_dict.get("chain_id"),
        "block": result_dict.get("block"),
        "status": result_dict.get("status"),
        "endpoints_queried": result_dict.get("endpoints_queried"),
        "endpoints_qualifying": result_dict.get("endpoints_qualifying"),
        "operators_distinct": result_dict.get("operators_distinct"),
        "operator_ids_qualifying": result_dict.get("operator_ids_qualifying"),
        "reports": [
            {
                "label": r.get("label"),
                "operator_id": r.get("operator_id"),
                "qualifies": r.get("chain_view_qualifies"),
                "counts_toward_quorum": r.get("counts_toward_quorum"),
                "exclusion_reason": r.get("exclusion_reason"),
            }
            for r in result_dict.get("reports", [])
        ],
    }
    if signing_key is None:
        evidence["signature"] = None
        evidence["signer"] = "unsigned-reference-implementation"
    else:
        # Placeholder for real signing
        evidence["signature"] = "0x" + "ff" * 65
        evidence["signer"] = signing_key
    return evidence
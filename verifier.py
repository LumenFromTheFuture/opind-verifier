"""Core operator-independence verification protocol.

Adapted from giskard09/checkpoint-producer-binding-ref-anchor
(commit 43643cb) with all features from the #1141 thread:
  - Operator ID normalization (ASCII-only, stripped, lowered, slug-validated)
  - Unknown-operator bucket excluded from strict quorum
  - Three distinct counts: endpoints_queried, endpoints_qualifying, operators_distinct
  - Disagreement resolved before operator deduplication
  - Missing vs invalid operator ID distinction
  - ERC-8004-compatible output format

Standard-library only.
"""

import datetime
import json


def normalize_operator_id(value):
    """Normalize an operator ID per the #1141 protocol.

    Returns None (not qualifying) for:
    - Non-string types
    - Non-ASCII content (rejected BEFORE case normalization)
    - The reserved diagnostic bucket "unknown"
    - Empty or whitespace-only strings
    - Strings with disallowed characters (only a-z, 0-9, ., _, -)
    """
    if not isinstance(value, str):
        return None
    # Strip only ASCII space/tab (not all Unicode whitespace)
    stripped = value.strip(" \t")
    if not stripped.isascii():
        return None
    normalized = stripped.lower()
    # The reserved diagnostic bucket "unknown" is not a valid operator identity
    if normalized == "unknown":
        return None
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789._-"
    if not normalized or not all(c in allowed for c in normalized):
        return None
    return normalized


def alias(label, index):
    """Convert a raw label to a safe display alias."""
    if isinstance(label, str) and label.strip() and not any(
        c in label for c in "/?#@:"
    ):
        return label.strip()
    return f"endpoint-{index + 1}"


class EndpointManifest:
    """Describes a set of endpoints to verify.

    Each endpoint is a dict with:
      - label (str): display alias
      - operator_id (str or None): declared operator identity
      - query_fn (callable): fn(block_number) -> {"chain_id": int, "block_hash": "0x..."}
        or raises on failure.
    """

    def __init__(self, endpoints, min_endpoints=2):
        self.endpoints = list(endpoints)
        self.min_endpoints = min_endpoints

    @classmethod
    def from_dict(cls, manifest, query_fn_resolver=None):
        """Build from a dict (JSON-deserialized ERC-8004 request data).

        query_fn_resolver: callable(url) -> query_fn, or None for unit tests.
        """
        endpoints = []
        for entry in manifest.get("endpoints", []):
            label = entry.get("label", "")
            operator_id = entry.get("operator_id")
            url = entry.get("url", "")
            if query_fn_resolver:
                qfn = query_fn_resolver(url)
            else:
                # Unit-test mode: provide a dummy
                qfn = lambda _bn: {"chain_id": 0, "block_hash": "0x" + "00" * 32}
            endpoints.append({"label": label, "operator_id": operator_id, "query_fn": qfn})
        return cls(
            endpoints,
            min_endpoints=manifest.get("min_endpoints", 2),
        )

    def to_dict(self):
        return {
            "endpoints": [
                {
                    "label": e["label"],
                    "operator_id": e.get("operator_id"),
                }
                for e in self.endpoints
            ],
            "min_endpoints": self.min_endpoints,
        }


def verify_operator_independence(
    block_number,
    recorded_block_hash,
    recorded_chain_id,
    manifest,
):
    """Verify operator independence for a set of signing endpoints.

    Args:
        block_number: The block height to query.
        recorded_block_hash: The expected block hash ("0x...").
        recorded_chain_id: The chain ID (e.g. 8453 for Base mainnet).
        manifest: An EndpointManifest instance.

    Returns:
        dict with verification result, compatible with ERC-8004 output.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reports = []
    result = {
        "status": "unknown",
        "checked_at": now,
        "chain_id": recorded_chain_id,
        "block": block_number,
        "endpoints_queried": 0,
        "endpoints_qualifying": 0,
        "operators_distinct": 0,
        "operator_ids_qualifying": [],
        "quorum_operator_ids": [],
        "reports": reports,
        "assurance": "operator-independence-verification",
    }

    # Validate inputs
    if not isinstance(manifest, EndpointManifest):
        return {**result, "reason": "invalid_manifest"}
    if manifest.min_endpoints < 1:
        return {**result, "reason": "min_endpoints_must_be_positive"}

    recorded_hash = _normalize_block_hash(recorded_block_hash)
    if recorded_hash is None:
        return {**result, "reason": "invalid_recorded_block_hash"}
    if not isinstance(recorded_chain_id, int) or recorded_chain_id < 1:
        return {**result, "reason": "invalid_chain_id"}
    if not isinstance(block_number, int) or block_number < 0:
        return {**result, "reason": "invalid_block_number"}

    # Process each endpoint
    for index, entry in enumerate(manifest.endpoints):
        report = {
            "label": f"endpoint-{index + 1}",
            "operator_id": None,
            "chain_view_qualifies": False,
            "counts_toward_quorum": False,
            "exclusion_reason": None,
        }
        reports.append(report)

        if not isinstance(entry, dict):
            report["exclusion_reason"] = "invalid_endpoint_config"
            continue

        report["label"] = alias(entry.get("label", ""), index)

        raw_opid = entry.get("operator_id")
        report["operator_id"] = normalize_operator_id(raw_opid)

        query_fn = entry.get("query_fn")
        if not callable(query_fn):
            report["exclusion_reason"] = "invalid_endpoint_config"
            continue

        result["endpoints_queried"] += 1

        try:
            observation = query_fn(block_number)
        except Exception:
            report["exclusion_reason"] = "query_error"
            continue

        if not isinstance(observation, dict):
            report["exclusion_reason"] = "malformed_response"
            continue

        chain_id = observation.get("chain_id")
        if not isinstance(chain_id, int) or chain_id != recorded_chain_id:
            report["exclusion_reason"] = "wrong_chain_id"
            continue

        observed_hash = _normalize_block_hash(observation.get("block_hash"))
        if observed_hash is None:
            report["exclusion_reason"] = "invalid_block_hash"
            continue

        report["chain_view_qualifies"] = True
        report["block_hash"] = observed_hash
        report["counts_toward_quorum"] = report["operator_id"] is not None

        if report["operator_id"] is None:
            # Distinguish: missing vs invalid
            if raw_opid is None or (
                isinstance(raw_opid, str) and not raw_opid.strip(" \t")
            ):
                report["exclusion_reason"] = "operator_id_missing"
            else:
                report["exclusion_reason"] = "operator_id_invalid"

    qualifying = [r for r in reports if r["chain_view_qualifies"]]
    operator_ids = sorted(
        {r["operator_id"] for r in qualifying if r["counts_toward_quorum"]}
    )
    result["endpoints_qualifying"] = len(qualifying)
    result["operators_distinct"] = len(operator_ids)
    result["operator_ids_qualifying"] = operator_ids

    # Disagreement check BEFORE operator deduplication
    distinct_hashes = {r["block_hash"] for r in qualifying}
    if len(distinct_hashes) > 1:
        return {
            **result,
            "status": "unknown",
            "reason": "block_hash_disagreement",
        }

    if len(operator_ids) < manifest.min_endpoints:
        return {
            **result,
            "status": "unknown",
            "reason": f"insufficient_operators: {len(operator_ids)} distinct operators, need >= {manifest.min_endpoints}",
        }

    agreed_hash = next(iter(distinct_hashes))
    status = "included" if agreed_hash == recorded_hash else "reorged"
    return {
        **result,
        "status": status,
        "block_hash": agreed_hash,
        "quorum_operator_ids": operator_ids,
    }


def _normalize_block_hash(value):
    """Validate and normalize a 32-byte hex block hash."""
    if not isinstance(value, str):
        return None
    value = value.lower()
    if len(value) == 66 and value.startswith("0x") and all(
        c in "0123456789abcdef" for c in value[2:]
    ):
        return value
    return None


# -- JSON-compatible output for ERC-8004 --

def result_to_erc8004_response(result_dict, evidence_uri=None):
    """Convert a verification result dict to ERC-8004 response format.

    Returns a dict compatible with ValidationRegistry.ValidationResponse:
      - result (uint8, 0-100): confidence score
      - reason (string): human-readable summary
      - metadata (bytes): evidence URI or full audit JSON
    """
    score = 0
    if result_dict.get("status") == "included":
        # Score based on distinct-operator ratio vs min_endpoints
        distinct = result_dict.get("operators_distinct", 0)
        min_eps = result_dict.get("_min_endpoints", 2)
        ratio = min(distinct / max(min_eps, 1), 1.0)
        score = int(ratio * 100)

    metadata = {
        "evidence_uri": evidence_uri,
        "audit": {
            "checked_at": result_dict.get("checked_at"),
            "endpoints_queried": result_dict.get("endpoints_queried"),
            "endpoints_qualifying": result_dict.get("endpoints_qualifying"),
            "operators_distinct": result_dict.get("operators_distinct"),
            "operator_ids": result_dict.get("operator_ids_qualifying"),
        },
    }

    return {
        "result": score,
        "reason": f"{result_dict.get('status', 'unknown')}: {result_dict.get('reason', '')}",
        "metadata": json.dumps(metadata),
    }
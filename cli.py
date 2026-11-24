"""Command-line interface for the operator-independence verifier."""

import argparse
import json
import sys
from opind_verifier import __version__
from opind_verifier.verifier import EndpointManifest, verify_operator_independence, result_to_erc8004_response
from opind_verifier.erc8004 import build_validation_request, sign_verdict, manifest_from_urls


def _resolve_query_fn(url):
    """Build a query_fn from an RPC URL using urllib (stdlib only)."""
    import urllib.request

    def query_fn(block_number):
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [hex(block_number), False],
            "id": 1,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode("utf-8"))
        if "result" not in data or data["result"] is None:
            raise ValueError(f"RPC error: {data.get('error', 'no result')}")
        block = data["result"]
        chain_id_payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_chainId",
            "params": [],
            "id": 2,
        }).encode("utf-8")
        req2 = urllib.request.Request(
            url,
            data=chain_id_payload,
            headers={"Content-Type": "application/json"},
        )
        resp2 = urllib.request.urlopen(req2, timeout=15)
        chain_data = json.loads(resp2.read().decode("utf-8"))
        chain_id = int(chain_data["result"], 16)
        return {
            "chain_id": chain_id,
            "block_hash": block.get("hash", "0x" + "00" * 32),
        }

    return query_fn


def main():
    parser = argparse.ArgumentParser(
        description="Operator-independence verifier v" + __version__
    )
    sub = parser.add_subparsers(dest="command")

    # verify
    verify_p = sub.add_parser("verify", help="Verify operator independence")
    verify_p.add_argument("manifest", help="Path to JSON manifest file")
    verify_p.add_argument("--block", type=int, default=53311834,
                          help="Block number to query (default: Base anchor block)")
    verify_p.add_argument("--hash", default="0x2fab867fbeb512526683693bcf64e473056c3e9728d51c420e14a98f275d3ab4",
                          help="Expected block hash")
    verify_p.add_argument("--chain-id", type=int, default=8453,
                          help="Chain ID (default: 8453 = Base mainnet)")
    verify_p.add_argument("--output", choices=["verdict", "erc8004", "evidence"],
                          default="verdict", help="Output format")
    verify_p.add_argument("--min-endpoints", type=int, default=2,
                          help="Minimum distinct operators for quorum")

    # build-request
    req_p = sub.add_parser("build-request",
                           help="Build an ERC-8004 validation request")
    req_p.add_argument("manifest", help="Path to JSON manifest file")
    req_p.add_argument("--agent", default="0x0000000000000000000000000000000000000000",
                       help="Agent address")
    req_p.add_argument("--block", type=int, default=53311834)
    req_p.add_argument("--chain-id", type=int, default=8453)

    args = parser.parse_args()

    if args.command == "verify":
        with open(args.manifest) as f:
            manifest_dict = json.load(f)

        # Apply min_endpoints from CLI if provided
        if args.min_endpoints:
            manifest_dict["min_endpoints"] = args.min_endpoints

        manifest = EndpointManifest.from_dict(manifest_dict, _resolve_query_fn)

        result = verify_operator_independence(
            block_number=args.block,
            recorded_block_hash=args.hash,
            recorded_chain_id=args.chain_id,
            manifest=manifest,
        )

        if args.output == "verdict":
            print(json.dumps(result, indent=2, default=str))
        elif args.output == "erc8004":
            response = result_to_erc8004_response(result)
            print(json.dumps(response, indent=2))
        elif args.output == "evidence":
            evidence = sign_verdict(result)
            print(json.dumps(evidence, indent=2, default=str))

    elif args.command == "build-request":
        with open(args.manifest) as f:
            manifest_dict = json.load(f)
        request = build_validation_request(
            agent_address=args.agent,
            endpoint_manifest=manifest_dict,
            block_number=args.block,
            chain_id=args.chain_id,
        )
        print(json.dumps(request, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
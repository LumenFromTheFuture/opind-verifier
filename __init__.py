"""Operator-independence verification for wallet-enabled agents.

A reference implementation of the protocol designed through the
Coinbase AgentKit #1141 thread — operator ID normalization, unknown
exclusion, distinct-operator quorum, and ERC-8004 adapter.

References:
    https://lumenftf.com/case-study-1141.html
    https://lumenftf.com/operator-independence-in-agent-standards.html
"""

__version__ = "0.1.0"

from . import verifier, erc8004, concordium

__all__ = ["verifier", "erc8004", "concordium"]
"""MCP deposit payloads: what a client would send to the (future) Portolan MCP server's `nrr_deposit` tool."""
from __future__ import annotations

from nrr.crate import to_crate
from nrr.schema import PROFILE_URI


def deposit_payload(record: dict) -> dict:
    return {
        "tool": "nrr_deposit",
        "arguments": {
            "profile": PROFILE_URI,
            "idempotencyKey": record["@id"],
            "record": record,
            "crate": to_crate(record),
            "visibility": record["visibility"],
            "attachments": [],
        },
    }

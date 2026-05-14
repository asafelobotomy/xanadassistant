"""Agent and pack workspace registry for the developer sandbox.

Import via sandbox.py; do not run directly.
"""
from __future__ import annotations
from _sandbox_core_workspaces import CORE_WORKSPACES
from _sandbox_pack_workspaces import PACK_WORKSPACES

AGENT_WORKSPACES: dict[str, dict] = {**CORE_WORKSPACES, **PACK_WORKSPACES}



#     "agent-review-quality":  {"desc": "Deeply nested conditionals, O(n\u00b2) loop, no tests",   "fn": _agent_review_quality,  "group": "review",   "expected_state": "not-installed"},


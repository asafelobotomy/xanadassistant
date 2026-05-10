from __future__ import annotations


def personalisation_questions() -> list[dict]:
    """Return the static Tier 2/3 personalisation questions.

    These are appended to the interview after the core ownership questions.
    The options use the {id, label, description} form; answer values must match an option id.
    """
    return [
        {
            "id": "response.style",
            "kind": "choice",
            "prompt": "What response style do you prefer?",
            "required": False,
            "default": "balanced",
            "recommended": "balanced",
            "options": [
                {"id": "concise", "label": "Concise", "description": "Code with minimal prose"},
                {"id": "balanced", "label": "Balanced", "description": "Code with brief explanation"},
                {"id": "verbose", "label": "Verbose", "description": "Code with full step-by-step explanation"},
            ],
        },
        {
            "id": "autonomy.level",
            "kind": "choice",
            "prompt": "How should the assistant handle ambiguity?",
            "required": False,
            "default": "ask-first",
            "recommended": "ask-first",
            "options": [
                {"id": "ask-first", "label": "Ask first", "description": "Always confirm before acting"},
                {"id": "act-then-tell", "label": "Act then tell", "description": "Make a reasonable choice and explain it"},
                {"id": "best-judgement", "label": "Best judgement", "description": "Act silently on low-risk choices"},
            ],
        },
        {
            "id": "agent.persona",
            "kind": "choice",
            "prompt": "What tone should the assistant use?",
            "required": False,
            "default": "professional",
            "recommended": "professional",
            "options": [
                {"id": "professional", "label": "Professional", "description": "Concise, neutral, precise"},
                {"id": "mentor", "label": "Mentor", "description": "Patient, explanatory, teaching-focused"},
                {"id": "pair-programmer", "label": "Pair programmer", "description": "Collaborative, iterative, direct"},
                {"id": "direct", "label": "Direct", "description": "Minimal chat, maximum output"},
            ],
        },
        {
            "id": "testing.philosophy",
            "kind": "choice",
            "prompt": "What is your testing philosophy?",
            "required": False,
            "default": "always",
            "recommended": "always",
            "options": [
                {"id": "always", "label": "Always", "description": "Write tests alongside every code change"},
                {"id": "suggest", "label": "Suggest", "description": "Propose tests but do not block on them"},
                {"id": "skip", "label": "Skip", "description": "Do not write or suggest tests unless asked"},
            ],
        },
    ]


def mcp_question() -> dict:
    """Return the static mcp.enabled confirm question."""
    return {
        "id": "mcp.enabled",
        "kind": "confirm",
        "prompt": "Enable MCP configuration for this workspace?",
        "required": True,
        "default": True,
        "recommended": True,
        "reason": (
            "Enabling MCP installs three files atomically: xanad-workspace-mcp.py (lifecycle tools), "
            "mcp-sequential-thinking-server.py (sequential-thinking tools), and .vscode/mcp.json "
            "(VS Code server registration). Outbound access is governed by each server, not by "
            "whether the workspace installs its local MCP configuration."
        ),
        "requiredFor": ["mcp-config"],
    }

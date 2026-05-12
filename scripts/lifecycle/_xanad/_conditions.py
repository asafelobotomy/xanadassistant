from __future__ import annotations

from pathlib import Path

from scripts.lifecycle._xanad._pack_tokens import load_pack_tokens
from scripts.lifecycle._xanad._workspace_scan import scan_workspace_stack

_RESPONSE_STYLE_LABELS: dict[str, str] = {
    "concise": "Concise — code with minimal prose.",
    "balanced": "Balanced — code with brief explanation.",
    "verbose": "Verbose — code with full step-by-step explanation.",
}

_AUTONOMY_LEVEL_LABELS: dict[str, str] = {
    "ask-first": "Ask first — always confirm before acting on ambiguity.",
    "act-then-tell": "Act then tell — make a reasonable choice and explain it.",
    "best-judgement": "Best judgement — act silently on low-risk choices.",
}

_AGENT_PERSONA_LABELS: dict[str, str] = {
    "professional": "Professional — concise, neutral, precise.",
    "mentor": "Mentor — patient, explanatory, teaching-focused.",
    "pair-programmer": "Pair programmer — collaborative, iterative, direct.",
    "direct": "Direct — minimal chat, maximum output.",
}

_TESTING_PHILOSOPHY_LABELS: dict[str, str] = {
    "always": "Always — write tests alongside every code change.",
    "suggest": "Suggest — propose tests but do not block on them.",
    "skip": "Skip — do not write or suggest tests unless asked.",
}

_SCAN_TOKENS: frozenset[str] = frozenset({"{{PRIMARY_LANGUAGE}}", "{{PACKAGE_MANAGER}}", "{{TEST_COMMAND}}"})


def parse_condition_literal(value: str) -> object:
    normalized = value.strip()
    lower = normalized.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    return normalized


def condition_matches(condition: str, resolved_answers: dict) -> bool:
    if "=" in condition:
        condition_id, expected_value = condition.split("=", 1)
        condition_id = condition_id.strip()
        expected_value = expected_value.strip()
        actual = resolved_answers.get(condition_id)
        parsed = parse_condition_literal(expected_value)
        if isinstance(actual, list):
            return parsed in actual
        return actual == parsed
    return bool(resolved_answers.get(condition))


def entry_required_for_plan(entry: dict, resolved_answers: dict) -> bool:
    required_when = entry.get("requiredWhen", [])
    if isinstance(required_when, str):
        required_when = [required_when]
    return all(condition_matches(condition, resolved_answers) for condition in required_when)


def normalize_plan_answers(policy: dict, resolved_answers: dict) -> dict:
    normalized_answers = dict(resolved_answers)
    if "hook-scripts" in policy.get("canonicalSurfaces", []) and "mcp-config" in policy.get("canonicalSurfaces", []):
        normalized_answers["hooks.enabled"] = bool(normalized_answers.get("mcp.enabled"))
    return normalized_answers


def resolve_token_values(
    policy: dict, workspace: Path, resolved_answers: dict, package_root: Path | None = None
) -> dict[str, str]:
    token_values: dict[str, str] = {}

    # Run workspace scanner once if any scan tokens are registered in the policy.
    policy_tokens = {rule["token"] for rule in policy.get("tokenRules", [])}
    if _SCAN_TOKENS & policy_tokens:
        token_values.update(scan_workspace_stack(workspace))
        # Provide a readable fallback for any scan token the scanner could not detect,
        # so installed files never contain raw {{...}} placeholders.
        for token in _SCAN_TOKENS & policy_tokens:
            if token not in token_values:
                token_values[token] = "(not detected)"

    for token_rule in policy.get("tokenRules", []):
        token = token_rule["token"]
        if token == "{{WORKSPACE_NAME}}":
            token_values[token] = workspace.name
        elif token == "{{XANAD_PROFILE}}":
            profile = resolved_answers.get("profile.selected")
            if isinstance(profile, str) and profile:
                token_values[token] = profile
            else:
                token_values[token] = "(not configured)"
        elif token == "{{RESPONSE_STYLE}}":
            style = resolved_answers.get("response.style")
            if isinstance(style, str) and style:
                token_values[token] = _RESPONSE_STYLE_LABELS.get(style, style)
            else:
                token_values[token] = "(not configured)"
        elif token == "{{AUTONOMY_LEVEL}}":
            level = resolved_answers.get("autonomy.level")
            if isinstance(level, str) and level:
                token_values[token] = _AUTONOMY_LEVEL_LABELS.get(level, level)
            else:
                token_values[token] = "(not configured)"
        elif token == "{{AGENT_PERSONA}}":
            persona = resolved_answers.get("agent.persona")
            if isinstance(persona, str) and persona:
                token_values[token] = _AGENT_PERSONA_LABELS.get(persona, persona)
            else:
                token_values[token] = "(not configured)"
        elif token == "{{TESTING_PHILOSOPHY}}":
            philosophy = resolved_answers.get("testing.philosophy")
            if isinstance(philosophy, str) and philosophy:
                token_values[token] = _TESTING_PHILOSOPHY_LABELS.get(philosophy, philosophy)
            else:
                token_values[token] = "(not configured)"
    if package_root is not None:
        resolved_token_conflicts = {
            key[len("resolvedTokenConflicts."):]: value
            for key, value in resolved_answers.items()
            if key.startswith("resolvedTokenConflicts.") and isinstance(value, str)
        }
        token_values.update(load_pack_tokens(
            package_root,
            resolved_answers.get("packs.selected") or [],
            resolved_token_conflicts or None,
        ))
    return token_values


def render_tokenized_text(template_text: str, token_values: dict[str, str]) -> str:
    rendered_text = template_text
    for token, value in token_values.items():
        rendered_text = rendered_text.replace(token, value)
    return rendered_text

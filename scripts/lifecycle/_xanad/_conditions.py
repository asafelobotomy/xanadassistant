from __future__ import annotations

from pathlib import Path


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


def resolve_token_values(policy: dict, workspace: Path, resolved_answers: dict) -> dict[str, str]:
    token_values: dict[str, str] = {}
    for token_rule in policy.get("tokenRules", []):
        token = token_rule["token"]
        if token == "{{WORKSPACE_NAME}}":
            token_values[token] = workspace.name
        elif token == "{{XANAD_PROFILE}}":
            profile = resolved_answers.get("profile.selected")
            if isinstance(profile, str) and profile:
                token_values[token] = profile
    return token_values


def render_tokenized_text(template_text: str, token_values: dict[str, str]) -> str:
    rendered_text = template_text
    for token, value in token_values.items():
        rendered_text = rendered_text.replace(token, value)
    return rendered_text

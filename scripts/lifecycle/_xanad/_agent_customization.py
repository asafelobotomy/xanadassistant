from __future__ import annotations

from copy import deepcopy

from scripts.lifecycle._xanad._conditions import entry_required_for_plan
from scripts.lifecycle._xanad._errors import LifecycleCommandError
from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface


def _get_active_agents(metadata: dict) -> list[dict]:
    agent_registry = metadata.get("agentRegistry") or {}
    agents = agent_registry.get("agents") or []
    return [agent for agent in agents if agent.get("status") == "active"]


def _manifest_entries(manifest: dict | None) -> dict[str, dict]:
    return {
        entry.get("id"): entry
        for entry in (manifest or {}).get("managedFiles", [])
        if isinstance(entry, dict)
    }


def _validate_active_agents(active_agents: list[dict], manifest_entries: dict[str, dict]) -> None:
    token_namespaces: set[str] = set()

    for agent in active_agents:
        agent_id = agent.get("id")
        manifest_entry_id = agent.get("manifestEntryId")
        customization = agent.get("customization") or {}
        token_namespace = customization.get("tokenNamespace")

        if not isinstance(agent_id, str) or not agent_id:
            raise LifecycleCommandError(
                "contract_input_failure",
                "Active agent registry entries must declare a stable id.",
                4,
                {"agent": agent},
            )

        if not isinstance(token_namespace, str) or not token_namespace:
            raise LifecycleCommandError(
                "contract_input_failure",
                "Active agent registry entries must declare a token namespace.",
                4,
                {"agentId": agent_id},
            )

        if token_namespace in token_namespaces:
            raise LifecycleCommandError(
                "contract_input_failure",
                "Active agent registry entries must use unique token namespaces.",
                4,
                {"agentId": agent_id, "tokenNamespace": token_namespace},
            )
        token_namespaces.add(token_namespace)

        if manifest_entries and manifest_entries.get(manifest_entry_id) is None:
            raise LifecycleCommandError(
                "contract_input_failure",
                "Active agent registry entry does not map to a manifest-managed agent surface.",
                4,
                {"agentId": agent_id, "manifestEntryId": manifest_entry_id},
            )


def _is_agent_installed(
    policy: dict,
    manifest: dict | None,
    lockfile_state: dict,
    manifest_entry: dict | None,
    customization: dict,
    resolved_answers: dict,
) -> bool:
    if manifest is None or manifest_entry is None:
        return False

    if not entry_required_for_plan(manifest_entry, resolved_answers):
        return False

    if not customization.get("requiresInstalled", False):
        return True

    ownership_by_surface = resolve_ownership_by_surface(
        policy,
        manifest,
        lockfile_state,
        resolved_answers,
    )
    ownership_mode = ownership_by_surface.get(manifest_entry["surface"], manifest_entry["ownership"][0])
    return ownership_mode == "local"


def build_agent_customization_questions(
    policy: dict,
    metadata: dict,
    manifest: dict | None,
    lockfile_state: dict,
    resolved_answers: dict,
) -> list[dict]:
    active_agents = _get_active_agents(metadata)
    manifest_entries = _manifest_entries(manifest)
    _validate_active_agents(active_agents, manifest_entries)

    questions: list[dict] = []
    for agent in active_agents:
        manifest_entry_id = agent.get("manifestEntryId")
        manifest_entry = manifest_entries.get(manifest_entry_id)
        customization = agent.get("customization") or {}
        if not _is_agent_installed(policy, manifest, lockfile_state, manifest_entry, customization, resolved_answers):
            continue

        for question in customization.get("questions") or []:
            answer_key = question.get("answerKey")
            if not isinstance(answer_key, str) or not answer_key:
                raise LifecycleCommandError(
                    "contract_input_failure",
                    "Agent customization questions must declare an answer key.",
                    4,
                    {"agentId": agent.get("id"), "question": question},
                )

            expanded_question = deepcopy(question)
            expanded_question["id"] = answer_key
            expanded_question.setdefault("batch", "agent")
            expanded_question.setdefault("required", False)
            expanded_question["agentId"] = agent.get("id")
            questions.append(expanded_question)

    return questions


def summarize_agent_customization(
    policy: dict,
    metadata: dict,
    manifest: dict | None,
    lockfile_state: dict,
    resolved_answers: dict,
) -> dict:
    active_agents = _get_active_agents(metadata)
    manifest_entries = _manifest_entries(manifest)
    _validate_active_agents(active_agents, manifest_entries)

    available_agents: list[dict] = []
    installed_agents: list[dict] = []

    for agent in active_agents:
        agent_id = agent.get("id")
        manifest_entry_id = agent.get("manifestEntryId")
        customization = agent.get("customization") or {}
        token_namespace = customization.get("tokenNamespace")

        summary = {
            "id": agent_id,
            "name": agent.get("name", agent_id),
            "manifestEntryId": manifest_entry_id,
            "tokenNamespace": token_namespace,
        }
        available_agents.append(summary)

        if manifest is None:
            continue

        manifest_entry = manifest_entries.get(manifest_entry_id)
        if _is_agent_installed(policy, manifest, lockfile_state, manifest_entry, customization, resolved_answers):
            installed_agents.append(summary)

    return {
        "availableAgents": available_agents,
        "installedAgents": installed_agents,
    }
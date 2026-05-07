from __future__ import annotations

import json
import sys


def emit_json(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def emit_json_lines(payload: dict) -> None:
    command = payload["command"]
    if command == "inspect":
        events = [
            {"type": "phase", "command": command, "sequence": 1, "phase": "Preflight"},
            {
                "type": "inspect-summary", "command": command, "sequence": 2,
                "installState": payload["result"]["installState"],
                "manifestSummary": payload["result"]["manifestSummary"],
                "contracts": payload["result"]["contracts"],
            },
            {"type": "receipt", "command": command, "sequence": 3, "status": payload["status"]},
        ]
    elif command == "check":
        events = [
            {"type": "phase", "command": command, "sequence": 1, "phase": "Preflight"},
            {
                "type": "check-summary", "command": command, "sequence": 2,
                "status": payload["status"],
                "summary": payload["result"]["summary"],
                "unmanagedFiles": payload["result"]["unmanagedFiles"],
            },
            {"type": "receipt", "command": command, "sequence": 3, "status": payload["status"]},
        ]
    elif command == "interview":
        events = [{"type": "phase", "command": command, "sequence": 1, "phase": "Interview"}]
        for question in payload["result"]["questions"]:
            event = {"type": "question", "command": command, "sequence": 0}
            event.update(question)
            events.append(event)
        events.append({
            "type": "receipt", "command": command, "sequence": 0, "status": payload["status"],
        })
    elif command == "plan":
        events = [
            {"type": "phase", "command": command, "sequence": 1, "phase": "Preflight"},
            {
                "type": "inspect-summary", "command": command, "sequence": 2,
                "installState": payload["result"]["installState"],
                "legacyVersionFile": payload["result"]["installPaths"]["legacyVersionFile"],
                "lockfile": bool(payload["result"]["installPaths"]["lockfile"]),
            },
        ]
        for question in payload["result"]["questions"]:
            event = {"type": "question", "command": command, "sequence": 0}
            event.update(question)
            events.append(event)
        events.extend([
            {"type": "phase", "command": command, "sequence": 0, "phase": "Plan"},
            {
                "type": "plan-summary", "command": command, "sequence": 0,
                "mode": payload["mode"],
                "approvalRequired": payload["result"]["approvalRequired"],
                "backupRequired": payload["result"]["backupRequired"],
                "backupPlan": payload["result"]["backupPlan"],
                "plannedLockfile": payload["result"]["plannedLockfile"],
                "writes": payload["result"]["writes"],
                "conflicts": payload["result"]["conflictSummary"],
            },
            {"type": "receipt", "command": command, "sequence": 0, "status": payload["status"]},
        ])
    elif command in {"apply", "update", "repair", "factory-restore"}:
        events = [
            {"type": "phase", "command": command, "sequence": 1, "phase": "Apply"},
            {
                "type": "apply-report", "command": command, "sequence": 2,
                "backup": payload["result"]["backup"],
                "writes": payload["result"]["writes"],
                "retired": payload["result"]["retired"],
                "lockfile": payload["result"]["lockfile"],
                "summary": payload["result"]["summary"],
                "validation": payload["result"]["validation"],
            },
            {"type": "receipt", "command": command, "sequence": 3, "status": payload["status"]},
        ]
    else:
        events = [
            {
                "type": "error", "command": command, "sequence": 1,
                "code": "not_implemented",
                "message": payload["errors"][0]["message"],
                "details": payload["errors"][0].get("details", {}),
            }
        ]

    for warning in payload.get("warnings", []):
        events.insert(2, {
            "type": "warning", "command": payload["command"], "sequence": 99,
            "code": warning["code"], "message": warning["message"],
            "details": warning.get("details", {}),
        })

    for index, event in enumerate(events, start=1):
        event["sequence"] = index
        sys.stdout.write(json.dumps(event) + "\n")

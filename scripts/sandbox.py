#!/usr/bin/env python3
"""Developer sandbox for interactive xanadAssistant lifecycle testing.

Commands: init / list / destroy / reset [--all] [name...] / run <name> <cmd...> / inspect <name>

Workspaces (sandbox/workspaces/):
  blank, bare-git, not-installed, fresh-install, lean-pack,
  local-ownership, local-mods, stale, partial, legacy

Direct use:
  cd sandbox/workspaces/<name>
  python3 ../../scripts/lifecycle/xanadAssistant.py <cmd> --workspace . --package-root ../..
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SANDBOX_DIR = REPO_ROOT / "sandbox" / "workspaces"
_CLI = REPO_ROOT / "scripts" / "lifecycle" / "xanadAssistant.py"


def _lc(*args: str, workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CLI), *args,
         "--workspace", str(workspace), "--package-root", str(REPO_ROOT)],
        capture_output=True, text=True, check=False,
    )


def _apply(workspace: Path, answers: dict | None = None) -> None:
    extra: list[str] = []
    if answers:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(answers, fh)
            extra = ["--answers", fh.name]
    try:
        r = _lc("apply", "--non-interactive", "--json", *extra, workspace=workspace)
        if r.returncode not in (0, 9):
            print(f"  ! apply exited {r.returncode}: {r.stderr.strip()[:120]}", file=sys.stderr)
    finally:
        if extra:
            Path(extra[1]).unlink(missing_ok=True)


def _blank(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)


def _bare_git(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(ws), "init", "-q"], capture_output=True, check=False)


def _not_installed(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    gh = ws / ".github"
    (gh / "agents").mkdir(parents=True)
    (gh / "prompts").mkdir()
    (gh / "copilot-instructions.md").write_text("# Existing instructions\n", encoding="utf-8")
    (gh / "agents" / "my-agent.agent.md").write_text("---\nname: my-agent\n---\n\nCustom agent.\n", encoding="utf-8")
    (gh / "prompts" / "my-prompt.prompt.md").write_text("Pre-existing prompt.\n", encoding="utf-8")


def _fresh_install(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply(ws)


def _lean_pack(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply(ws, {"packs.selected": ["lean"]})


def _local_ownership(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply(ws, {"setup.depth": "advanced", "ownership.agents": "local", "ownership.skills": "local"})


def _local_mods(ws: Path) -> None:
    _fresh_install(ws)
    f = ws / ".github" / "copilot-instructions.md"
    if f.exists():
        f.write_text(f.read_text(encoding="utf-8") + "\n## Local section\nCustomisation.\n", encoding="utf-8")


def _stale(ws: Path) -> None:
    _fresh_install(ws)
    hooks = ws / ".github" / "hooks" / "scripts"
    scripts = sorted(hooks.glob("*.py")) if hooks.exists() else []
    if scripts:
        scripts[0].write_text(scripts[0].read_text(encoding="utf-8") + "\n# stale marker\n", encoding="utf-8")


def _partial(ws: Path) -> None:
    _fresh_install(ws)
    for rel in [".github/copilot-instructions.md", ".github/agents/commit.agent.md", ".github/prompts/setup.md"]:
        p = ws / rel
        if p.exists():
            p.unlink()


def _legacy(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    gh = ws / ".github"
    gh.mkdir()
    (gh / "copilot-instructions.md").write_text("# Legacy workspace\n", encoding="utf-8")
    (gh / "xanadAssistant-lock.json").write_text(json.dumps({
        "schemaVersion": "0.1.0",
        "package": {"name": "copilot-instructions-template"},
        "timestamps": {"appliedAt": "2025-01-01T00:00:00Z", "updatedAt": "2025-01-01T00:00:00Z"},
        "profile": "balanced", "selectedPacks": [], "ownershipBySurface": {},
    }, indent=2) + "\n", encoding="utf-8")


WORKSPACES: dict[str, dict] = {
    "blank":           {"desc": "Empty directory",                                           "fn": _blank},
    "bare-git":        {"desc": "git-initialized, no xanadAssistant",                        "fn": _bare_git},
    "not-installed":   {"desc": "Pre-existing .github/ files, no lockfile",                  "fn": _not_installed},
    "fresh-install":   {"desc": "Clean install with all defaults",                           "fn": _fresh_install},
    "lean-pack":       {"desc": "Install with lean pack enabled",                            "fn": _lean_pack},
    "local-ownership": {"desc": "Install with agents/skills owned locally",                 "fn": _local_ownership},
    "local-mods":      {"desc": "Fresh install + edited copilot-instructions.md",           "fn": _local_mods},
    "stale":           {"desc": "Fresh install + modified hook (check exits 7)",            "fn": _stale},
    "partial":         {"desc": "Fresh install + managed files deleted (repair target)",     "fn": _partial},
    "legacy":          {"desc": "Predecessor lockfile (no files key) -- triggers migration", "fn": _legacy},
}


def _create_workspace(name: str) -> None:
    ws = SANDBOX_DIR / name
    if ws.exists():
        shutil.rmtree(ws)
    print(f"  {name}...", end=" ", flush=True)
    WORKSPACES[name]["fn"](ws)
    print("ok")


def cmd_init() -> None:
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Initializing {len(WORKSPACES)} workspaces (installed ones run apply -- ~30s)")
    for name in WORKSPACES:
        _create_workspace(name)
    print("\nDone. Run: python3 scripts/sandbox.py list")


def cmd_list() -> None:
    if not SANDBOX_DIR.exists():
        print("No sandbox. Run: python3 scripts/sandbox.py init")
        return
    print(f"{'Workspace':<20} {'installState':<18} Description")
    print("-" * 76)
    for name, meta in WORKSPACES.items():
        ws = SANDBOX_DIR / name
        if not ws.exists():
            state = "(missing)"
        else:
            r = _lc("inspect", "--json", workspace=ws)
            try:
                state = json.loads(r.stdout).get("result", {}).get("installState", "?")
            except (json.JSONDecodeError, KeyError):
                state = "(error)"
        print(f"  {name:<18} {state:<18} {meta['desc']}")


def cmd_reset(names: list[str], all_: bool) -> None:
    targets = list(WORKSPACES) if all_ else names
    invalid = [n for n in targets if n not in WORKSPACES]
    if invalid:
        print(f"Unknown: {', '.join(invalid)}. Available: {', '.join(WORKSPACES)}", file=sys.stderr)
        sys.exit(1)
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    for name in targets:
        _create_workspace(name)


def cmd_destroy() -> None:
    target = SANDBOX_DIR.parent
    if not target.exists():
        print("Sandbox does not exist.")
        return
    shutil.rmtree(target)
    print("Removed sandbox/")


def cmd_run(name: str, lc_args: list[str]) -> None:
    if name not in WORKSPACES:
        print(f"Unknown: {name}. Available: {', '.join(WORKSPACES)}", file=sys.stderr)
        sys.exit(1)
    ws = SANDBOX_DIR / name
    if not ws.exists():
        print(f"'{name}' not initialized. Run: python3 scripts/sandbox.py init", file=sys.stderr)
        sys.exit(1)
    result = _lc(*lc_args, workspace=ws)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


def main() -> None:
    p = argparse.ArgumentParser(
        prog="sandbox.py",
        description="Developer sandbox for xanadAssistant lifecycle testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:  python3 scripts/sandbox.py run stale check --json",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init",    help="Create all template workspaces")
    sub.add_parser("list",    help="List workspaces and install state")
    sub.add_parser("destroy", help="Remove sandbox/")
    pr = sub.add_parser("reset", help="Recreate workspace(s) from template")
    pr.add_argument("names", nargs="*", metavar="name")
    pr.add_argument("--all", dest="all_", action="store_true")
    px = sub.add_parser("run", help="Run a lifecycle command against a workspace")
    px.add_argument("name")
    px.add_argument("args", nargs=argparse.REMAINDER)
    pi = sub.add_parser("inspect", help="Shortcut: run <name> inspect --json")
    pi.add_argument("name")

    args = p.parse_args()
    if args.cmd == "init":
        cmd_init()
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "reset":
        if not args.all_ and not args.names:
            p.error("Provide workspace name(s) or --all")
        cmd_reset(args.names, args.all_)
    elif args.cmd == "destroy":
        cmd_destroy()
    elif args.cmd == "run":
        cmd_run(args.name, args.args)
    elif args.cmd == "inspect":
        cmd_run(args.name, ["inspect", "--json"])


if __name__ == "__main__":
    main()

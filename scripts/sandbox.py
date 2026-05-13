#!/usr/bin/env python3
"""Developer sandbox for interactive xanadAssistant lifecycle testing.

Commands: init / list / destroy / reset [--all] [name...] / run <name> <cmd...> / inspect <name> / clone <repo> [--name <n>] [--reset]

Workspaces (sandbox/workspaces/):
  blank, bare-git, not-installed, fresh-install, lean-pack,
  local-ownership, local-mods, stale, partial, legacy,
  broken-lockfile, broken-schema, complex,
  partial-early, partial-mid, partial-late

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


def _broken_lockfile(ws: Path) -> None:
    gh = ws / ".github"
    gh.mkdir(parents=True, exist_ok=True)
    (gh / "copilot-instructions.md").write_text("# Broken workspace\n", encoding="utf-8")
    (gh / "xanadAssistant-lock.json").write_text("{ NOT VALID JSON\n", encoding="utf-8")


def _broken_schema(ws: Path) -> None:
    gh = ws / ".github"
    gh.mkdir(parents=True, exist_ok=True)
    (gh / "xanadAssistant-lock.json").write_text(json.dumps({"corrupted": True}) + "\n", encoding="utf-8")


def _complex(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    gh = ws / ".github"
    for d in ["agents", "prompts", "instructions"]:
        (gh / d).mkdir(parents=True, exist_ok=True)
    for i in range(4):
        (gh / "agents" / f"team-{i}.agent.md").write_text(f"---\nname: team-{i}\n---\n", encoding="utf-8")
    (gh / "copilot-instructions.md").write_text("# Complex workspace\n\n" + "".join(f"## Section {i}\nContent.\n\n" for i in range(4)), encoding="utf-8")
    (gh / "instructions" / "coding.instructions.md").write_text("---\napplyTo: '**'\n---\nCoding standards.\n", encoding="utf-8")
    (ws / ".vscode").mkdir()
    (ws / ".vscode" / "mcp.json").write_text(json.dumps({"inputs": [], "servers": {"existing": {"type": "stdio", "command": "tool", "args": []}}}), encoding="utf-8")
    subprocess.run(["git", "-C", str(ws), "init", "-q"], capture_output=True, check=False)


def _partial_stage(ws: Path, remove: list[str]) -> None:
    _fresh_install(ws)
    for d in remove:
        shutil.rmtree(ws / d, ignore_errors=True)


def _partial_early(ws: Path) -> None:
    _partial_stage(ws, [".github/instructions", ".github/prompts", ".github/hooks", ".vscode"])


def _partial_mid(ws: Path) -> None:
    _partial_stage(ws, [".github/hooks", ".vscode"])


def _partial_late(ws: Path) -> None:
    _partial_stage(ws, [".vscode"])


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
    "broken-lockfile": {"desc": "Lockfile with invalid JSON (parse error on check/inspect)",          "fn": _broken_lockfile},
    "broken-schema":   {"desc": "Lockfile valid JSON but wrong schema (schema error on check)",        "fn": _broken_schema},
    "complex":         {"desc": "Dense pre-existing .github/ + MCP + git (collision-rich install)",   "fn": _complex},
    "partial-early":   {"desc": "Apply stopped early: only core instruction file written, prompts/hooks/MCP absent", "fn": _partial_early},
    "partial-mid":     {"desc": "Apply stopped mid: all .github surfaces written, .vscode/MCP absent",             "fn": _partial_mid},
    "partial-late":    {"desc": "Apply stopped late: all surfaces written except .vscode/mcp.json",        "fn": _partial_late},
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
    cloned = sorted(d.name for d in SANDBOX_DIR.iterdir() if d.is_dir() and d.name not in WORKSPACES)
    if cloned:
        print("")
        for name in cloned:
            r = _lc("inspect", "--json", workspace=SANDBOX_DIR / name)
            try:
                state = json.loads(r.stdout).get("result", {}).get("installState", "?")
            except (json.JSONDecodeError, KeyError):
                state = "(error)"
            print(f"  {name:<18} {state:<18} (cloned)")


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
    ws = SANDBOX_DIR / name
    if not ws.exists():
        avail = sorted(d.name for d in SANDBOX_DIR.iterdir() if d.is_dir()) if SANDBOX_DIR.exists() else []
        print(f"'{name}' not found. Available: {', '.join(avail) or 'none'}", file=sys.stderr)
        sys.exit(1)
    result = _lc(*lc_args, workspace=ws)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


def cmd_clone(repo: str, name: str | None, reset: bool) -> None:
    url = f"https://github.com/{repo}" if "/" in repo and not repo.startswith(("http", "git@")) else repo
    if not name:
        name = Path(url.rstrip("/")).stem.removesuffix(".git")
    ws = SANDBOX_DIR / name
    if ws.exists():
        if not reset:
            print(f"'{name}' already exists. Use --reset to re-clone.", file=sys.stderr)
            sys.exit(1)
        shutil.rmtree(ws)
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Cloning {url} -> sandbox/workspaces/{name}/ ...")
    r = subprocess.run(["git", "clone", "--depth", "1", url, str(ws)], check=False)
    if r.returncode != 0:
        print(f"Clone failed (exit {r.returncode})", file=sys.stderr)
        sys.exit(r.returncode)
    print(f"Done.  Run: python3 scripts/sandbox.py inspect {name}")


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
    pc = sub.add_parser("clone", help="Clone a GitHub repo as a sandbox workspace")
    pc.add_argument("repo", help="owner/repo shorthand or full URL")
    pc.add_argument("--name", dest="clone_name", metavar="NAME", help="Workspace name (default: repo name)")
    pc.add_argument("--reset", action="store_true", help="Re-clone if workspace already exists")

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
    elif args.cmd == "clone":
        cmd_clone(args.repo, args.clone_name, args.reset)


if __name__ == "__main__":
    main()

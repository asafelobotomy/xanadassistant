"""Pack workspace templates for the developer sandbox.

Import via _sandbox_agent_workspaces.py; do not run directly.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_CLI = REPO_ROOT / "scripts" / "lifecycle" / "xanadAssistant.py"


def _apply_in_ws(workspace: Path, answers: dict | None = None) -> None:
    """Run `apply --non-interactive` against workspace. Mirrors sandbox._apply()."""
    extra: list[str] = []
    if answers:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(answers, fh)
            extra = ["--answers", fh.name]
    try:
        r = subprocess.run(
            [sys.executable, str(_CLI), "apply", "--non-interactive", "--json", *extra,
             "--workspace", str(workspace), "--package-root", str(REPO_ROOT)],
            capture_output=True, text=True, check=False,
        )
        if r.returncode not in (0, 9):
            print(f"  ! apply exited {r.returncode}: {r.stderr.strip()[:120]}", file=sys.stderr)
    finally:
        if extra:
            Path(extra[1]).unlink(missing_ok=True)


# ── Pack workspaces ──────────────────────────────────────────────────────────

def _pack_devops_pipeline(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "requirements.txt").write_text("flask>=3.0.0\ngunicorn>=21.0.0\n", encoding="utf-8")
    _apply_in_ws(ws, {"packs.selected": ["devops"]})
    (ws / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (ws / ".github" / "workflows" / "ci.yml").write_text(
        "name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n"
        "      - run: pip install -r requirements.txt && python -m pytest\n", encoding="utf-8")
    (ws / "Dockerfile").write_text(
        "FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\n"
        "RUN pip install -r requirements.txt\nCOPY . .\nCMD [\"python\", \"app.py\"]\n", encoding="utf-8")


def _pack_devops_incident(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["devops"]})
    (ws / "incident-2026-05-14.md").write_text(
        "# Incident: API latency spike\n\n**Severity**: P1  **Status**: Mitigated\n\n"
        "## Timeline\n\n- 14:02 Alerts fired: p99 latency >5s\n"
        "- 14:08 Identified slow query on `orders` table (missing index)\n"
        "- 14:15 Deployed hotfix: added index on `orders.customer_id`\n"
        "- 14:22 Latency returned to baseline\n\n"
        "## Root cause\n\nMigration `0042` added `orders.customer_id` without an index.\n",
        encoding="utf-8")


def _pack_docs_api(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["docs"]})
    (ws / "payments.py").write_text(
        "class PaymentProcessor:\n    def __init__(self, gateway_url, api_key):\n"
        "        self._url = gateway_url\n        self._key = api_key\n\n"
        "    def charge(self, amount, currency, token): pass\n\n"
        "    def refund(self, transaction_id, amount=None): pass\n\n"
        "    def list_transactions(self, from_date=None, to_date=None, status=None): pass\n\n"
        "def create_processor(config):\n    return PaymentProcessor(config['gateway_url'], config['api_key'])\n",
        encoding="utf-8")


def _pack_docs_stale(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["docs"]})
    (ws / "README.md").write_text(
        "# DataPipe\n\nBatch ETL pipeline using Pandas and SQLite.\n\n"
        "## Usage\n\n```python\nfrom datapipe import Pipeline\np = Pipeline('data.sqlite'); p.run()\n```\n",
        encoding="utf-8")
    (ws / "datapipe.py").write_text(
        "# Rewritten to use Polars + DuckDB (README is stale)\nimport polars as pl\nimport duckdb\n\n"
        "class Pipeline:\n    def __init__(self, db): self.conn = duckdb.connect(db)\n"
        "    def run(self): pass\n    def transform(self, df: pl.DataFrame): return df\n",
        encoding="utf-8")


def _pack_lean_clean(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["lean"]})
    (ws / "main.py").write_text("def run(): pass\n", encoding="utf-8")
    (ws / "utils.py").write_text("def helper(x): return x\n", encoding="utf-8")


def _pack_lean_overbudget(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["lean"]})
    for i in range(20):
        (ws / f"module_{i:02d}.py").write_text(
            f"# Module {i}\n" + "".join(f"def func_{j}(): pass\n" for j in range(15)),
            encoding="utf-8")


def _pack_mlops_experiment(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["mlops"]})
    (ws / "experiment.yaml").write_text(
        "experiment:\n  name: baseline-v2\n  model: random_forest\n  dataset: train_2026_q1.csv\n"
        "  hyperparams:\n    n_estimators: 200\n    max_depth: 10\n    min_samples_split: 5\n"
        "  metrics:\n    accuracy: 0.874\n    f1: 0.831\n    roc_auc: 0.912\n", encoding="utf-8")
    (ws / "train.py").write_text(
        "import yaml\nfrom sklearn.ensemble import RandomForestClassifier\n\n"
        "def train(cfg_path):\n    with open(cfg_path) as f: cfg = yaml.safe_load(f)\n"
        "    return RandomForestClassifier(**cfg['experiment']['hyperparams'])\n", encoding="utf-8")


def _pack_mlops_drift(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["mlops"]})
    (ws / "model_performance_log.csv").write_text(
        "date,accuracy,f1,data_volume\n"
        "2026-02-01,0.912,0.898,10240\n2026-03-01,0.901,0.887,10891\n"
        "2026-04-01,0.878,0.861,11204\n2026-04-15,0.843,0.822,11456\n"
        "2026-05-01,0.801,0.779,11890\n", encoding="utf-8")


def _pack_oss_compliant(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["oss"]})
    (ws / "LICENSE").write_text(
        "MIT License\n\nCopyright (c) 2026\n\nPermission is hereby granted, free of charge...\n",
        encoding="utf-8")
    (ws / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0] - 2026-05-01\n\n### Added\n\n- Initial release\n", encoding="utf-8")
    (ws / "CONTRIBUTING.md").write_text(
        "# Contributing\n\nPRs welcome. Please open an issue first.\n", encoding="utf-8")


def _pack_oss_missing(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["oss"]})
    (ws / "app.py").write_text("def main(): pass\n", encoding="utf-8")


def _pack_secure_clean(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "requirements.txt").write_text(
        "fastapi>=0.115.0\nuvicorn>=0.32.0\nsqlalchemy>=2.0.36\npydantic>=2.10.0\n", encoding="utf-8")
    _apply_in_ws(ws, {"packs.selected": ["secure"]})


def _pack_secure_vuln(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "requirements.txt").write_text(
        "flask==0.12.4\nrequests==2.18.0\npillow==9.0.0\npyyaml==5.1\ncryptography==2.6\n",
        encoding="utf-8")
    _apply_in_ws(ws, {"packs.selected": ["secure"]})


def _pack_shapeup_pitch(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["shapeup"]})
    (ws / "pitch-notifications.md").write_text(
        "# Pitch: Smart Notifications\n\n**Appetite**: 6 weeks\n\n"
        "## Problem\n\nUsers miss updates because all notifications use the same channel.\n\n"
        "## Solution\n\nRoute by urgency: critical → push, moderate → email, low → digest.\n\n"
        "## Rabbit holes\n\n- Do not build per-user channel preferences (scope creep)\n"
        "- Do not integrate with Slack (separate pitch)\n", encoding="utf-8")


def _pack_shapeup_cycle(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["shapeup"]})
    (ws / "cycle-6.md").write_text(
        "# Cycle 6: Smart Notifications\n\n**Started**: 2026-04-01  **Deadline**: 2026-05-13\n\n"
        "## Scope\n\n- [x] Urgency classifier\n- [x] Push delivery\n"
        "- [ ] Email delivery\n- [ ] Digest scheduler\n\n"
        "## Added mid-cycle (scope creep)\n\n"
        "- [ ] Per-user channel preferences\n- [ ] Slack integration\n- [ ] Analytics dashboard\n",
        encoding="utf-8")


def _pack_tdd_clean(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["tdd"]})
    (ws / "discount.py").write_text(
        "def apply_discount(price: float, pct: float) -> float:\n"
        "    if not 0 <= pct <= 100: raise ValueError(f'pct must be 0-100, got {pct}')\n"
        "    return round(price * (1 - pct / 100), 2)\n", encoding="utf-8")
    (ws / "test_discount.py").write_text(
        "import unittest\nfrom discount import apply_discount\n\n"
        "class TestDiscount(unittest.TestCase):\n"
        "    def test_zero(self): self.assertEqual(100.0, apply_discount(100.0, 0))\n"
        "    def test_full(self): self.assertEqual(0.0, apply_discount(100.0, 100))\n"
        "    def test_partial(self): self.assertEqual(75.0, apply_discount(100.0, 25))\n"
        "    def test_invalid(self):\n"
        "        with self.assertRaises(ValueError): apply_discount(100.0, 110)\n",
        encoding="utf-8")


def _pack_tdd_failing(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["tdd"]})
    (ws / "inventory.py").write_text(
        "class Inventory:\n    def __init__(self): self._items = {}\n\n"
        "    def add(self, sku, qty): self._items[sku] = self._items.get(sku, 0) + qty\n\n"
        "    def remove(self, sku, qty):  # Bug: allows negative stock\n"
        "        self._items[sku] = self._items.get(sku, 0) - qty\n\n"
        "    def count(self, sku): return self._items.get(sku, 0)\n", encoding="utf-8")
    (ws / "test_inventory.py").write_text(
        "import unittest\nfrom inventory import Inventory\n\n"
        "class TestInventory(unittest.TestCase):\n"
        "    def test_add(self):\n        inv = Inventory(); inv.add('A', 5)\n"
        "        self.assertEqual(5, inv.count('A'))\n"
        "    def test_remove_prevents_negative_stock(self):\n"
        "        inv = Inventory(); inv.add('A', 3); inv.remove('A', 5)\n"
        "        self.assertGreaterEqual(inv.count('A'), 0)  # fails: -2\n",
        encoding="utf-8")


def _pack_tdd_new(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["tdd"]})
    (ws / "rate_limiter.py").write_text(
        "import time\nfrom collections import deque\n\n"
        "class RateLimiter:\n    def __init__(self, max_calls: int, period: float):\n"
        "        self.max_calls = max_calls\n        self.period = period\n"
        "        self._calls: deque = deque()\n\n"
        "    def allow(self) -> bool:\n        now = time.monotonic()\n"
        "        while self._calls and self._calls[0] <= now - self.period:\n"
        "            self._calls.popleft()\n"
        "        if len(self._calls) < self.max_calls:\n"
        "            self._calls.append(now)\n            return True\n"
        "        return False\n", encoding="utf-8")
    # No test file — TDD starting point


# ── Registry ─────────────────────────────────────────────────────────────────

PACK_WORKSPACES: dict[str, dict] = {
    "pack-devops-pipeline":  {"desc": "devops pack + CI YAML + Dockerfile",                       "fn": _pack_devops_pipeline,  "group": "devops",   "expected_state": "installed"},
    "pack-devops-incident":  {"desc": "devops pack + P1 incident post-mortem",                    "fn": _pack_devops_incident,  "group": "devops",   "expected_state": "installed"},
    "pack-docs-api":         {"desc": "docs pack + undocumented PaymentProcessor module",         "fn": _pack_docs_api,         "group": "docs",     "expected_state": "installed"},
    "pack-docs-stale":       {"desc": "docs pack + README describing a different framework",      "fn": _pack_docs_stale,       "group": "docs",     "expected_state": "installed"},
    "pack-lean-clean":       {"desc": "lean pack + small focused 2-file codebase",                "fn": _pack_lean_clean,       "group": "lean",     "expected_state": "installed"},
    "pack-lean-overbudget":  {"desc": "lean pack + 20 modules x 15 functions (context bloat)",    "fn": _pack_lean_overbudget,  "group": "lean",     "expected_state": "installed"},
    "pack-mlops-experiment": {"desc": "mlops pack + experiment config YAML + sklearn trainer",    "fn": _pack_mlops_experiment, "group": "mlops",    "expected_state": "installed"},
    "pack-mlops-drift":      {"desc": "mlops pack + performance log showing accuracy decline",    "fn": _pack_mlops_drift,      "group": "mlops",    "expected_state": "installed"},
    "pack-oss-compliant":    {"desc": "oss pack + LICENSE, CHANGELOG, CONTRIBUTING present",      "fn": _pack_oss_compliant,    "group": "oss",      "expected_state": "installed"},
    "pack-oss-missing":      {"desc": "oss pack + no compliance docs",                            "fn": _pack_oss_missing,      "group": "oss",      "expected_state": "installed"},
    "pack-secure-clean":     {"desc": "secure pack + current-version requirements.txt",           "fn": _pack_secure_clean,     "group": "secure",   "expected_state": "installed"},
    "pack-secure-vuln":      {"desc": "secure pack + outdated/vulnerable requirements.txt",       "fn": _pack_secure_vuln,      "group": "secure",   "expected_state": "installed"},
    "pack-shapeup-pitch":    {"desc": "shapeup pack + pitch with 6-week appetite",                "fn": _pack_shapeup_pitch,    "group": "shapeup",  "expected_state": "installed"},
    "pack-shapeup-cycle":    {"desc": "shapeup pack + active cycle with scope creep",             "fn": _pack_shapeup_cycle,    "group": "shapeup",  "expected_state": "installed"},
    "pack-tdd-clean":        {"desc": "tdd pack + well-tested discount module (4 cases)",         "fn": _pack_tdd_clean,        "group": "tdd",      "expected_state": "installed"},
    "pack-tdd-failing":      {"desc": "tdd pack + inventory module with negative-stock bug",      "fn": _pack_tdd_failing,      "group": "tdd",      "expected_state": "installed"},
    "pack-tdd-new":          {"desc": "tdd pack + RateLimiter with no tests (TDD starting point)","fn": _pack_tdd_new,          "group": "tdd",      "expected_state": "installed"},
}

for _v in PACK_WORKSPACES.values():
    _v.setdefault("expected_exit_codes", {"inspect": 0, "check": 0})
    _v.setdefault("expected_findings", [])

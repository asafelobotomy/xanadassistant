"""Agent and pack workspace templates for the developer sandbox.

Import via sandbox.py; do not run directly.
Each entry in AGENT_WORKSPACES carries: desc, fn, group, expected_state.
  expected_state: "not-installed" for agent workspaces (no lifecycle applied)
                  "installed"     for pack workspaces (_apply_in_ws() runs)
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


# ── Core agent workspaces ────────────────────────────────────────────────────

def _agent_commit_clean(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(ws), "init", "-q"], capture_output=True, check=False)
    (ws / "main.py").write_text("def greet(name):\n    print(f'Hello, {name}')\n", encoding="utf-8")
    _g = lambda *a: subprocess.run(["git", "-C", str(ws), *a], capture_output=True, check=False)
    _g("config", "user.email", "dev@example.com")
    _g("config", "user.name", "Dev")
    _g("add", "main.py")
    _g("-c", "user.email=dev@example.com", "-c", "user.name=Dev", "commit", "-m", "feat: add greet")
    (ws / "main.py").write_text("def greet(name: str) -> None:\n    print(f'Hello, {name}')\n", encoding="utf-8")
    _g("add", "main.py")


def _agent_commit_mixed(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _g = lambda *a: subprocess.run(["git", "-C", str(ws), *a], capture_output=True, check=False)
    _g("init", "-q")
    _g("config", "user.email", "dev@example.com")
    _g("config", "user.name", "Dev")
    (ws / "app.py").write_text("def main(): pass\n", encoding="utf-8")
    (ws / "utils.py").write_text("def helper(): return True\n", encoding="utf-8")
    _g("add", ".")
    _g("-c", "user.email=dev@example.com", "-c", "user.name=Dev", "commit", "-m", "feat: initial")
    (ws / "app.py").write_text("def main(): print('running')\n", encoding="utf-8")
    (ws / "utils.py").write_text("def helper(): return False  # under review\n", encoding="utf-8")
    _g("add", "app.py")


def _agent_debug_test_fail(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "calculator.py").write_text(
        "def add(a, b): return a + b\n\ndef divide(a, b): return a / b\n", encoding="utf-8")
    (ws / "test_calculator.py").write_text(
        "import unittest\nfrom calculator import add, divide\n\n"
        "class TestCalc(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(4, add(2, 2))\n"
        "    def test_divide_by_zero(self): self.assertEqual(0, divide(10, 0))  # fails\n",
        encoding="utf-8")


def _agent_debug_regression(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "formatter.py").write_text(
        "def format_price(amount: float) -> str:\n    return f'${amount}'  # was f'${amount:.2f}'\n",
        encoding="utf-8")
    (ws / "test_formatter.py").write_text(
        "import unittest\nfrom formatter import format_price\n\n"
        "class TestFormatter(unittest.TestCase):\n"
        "    def test_format_price(self): self.assertEqual('$9.99', format_price(9.99))\n"
        "    def test_format_whole(self): self.assertEqual('$10.00', format_price(10))\n",
        encoding="utf-8")


def _agent_deps_outdated(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "requirements.txt").write_text(
        "requests==2.18.0\nflask==0.12.4\nsqlalchemy==1.2.0\ncelery==4.1.0\n", encoding="utf-8")
    (ws / "app.py").write_text("import requests, flask\n", encoding="utf-8")


def _agent_deps_missing(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "app.py").write_text(
        "import httpx\nimport pydantic\nfrom rich import print as rprint\n\n"
        "def fetch(url): return httpx.get(url)\n", encoding="utf-8")


def _agent_docs_missing(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "auth.py").write_text(
        "import hashlib, hmac\n\n"
        "def hash_password(pw, salt):\n"
        "    return hmac.new(salt.encode(), pw.encode(), hashlib.sha256).hexdigest()\n\n"
        "def verify_password(pw, salt, hashed):\n"
        "    return hmac.compare_digest(hash_password(pw, salt), hashed)\n\n"
        "class TokenStore:\n"
        "    def __init__(self): self._store = {}\n"
        "    def put(self, k, v): self._store[k] = v\n"
        "    def get(self, k): return self._store.get(k)\n",
        encoding="utf-8")


def _agent_docs_stale(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "README.md").write_text(
        "# MyApp\n\nA REST API server using Flask.\n\n"
        "## Endpoints\n\n- `GET /users` — list users\n- `POST /users` — create user\n",
        encoding="utf-8")
    (ws / "app.py").write_text(
        "# Rewritten to use FastAPI (README is stale)\nimport fastapi\napp = fastapi.FastAPI()\n\n"
        "@app.get('/items')\ndef list_items(): return []\n\n"
        "@app.post('/items')\ndef create_item(): return {}\n",
        encoding="utf-8")


def _agent_explore_multi(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    for pkg in ("core", "api", "storage"):
        (ws / pkg).mkdir()
        (ws / pkg / "__init__.py").write_text("", encoding="utf-8")
    (ws / "core" / "models.py").write_text(
        "class User:\n    def __init__(self, id, name): self.id = id; self.name = name\n\n"
        "class Product:\n    def __init__(self, id, price): self.id = id; self.price = price\n",
        encoding="utf-8")
    (ws / "core" / "services.py").write_text(
        "from .models import User, Product\n\n"
        "def get_user(uid): return User(uid, 'unknown')\ndef get_product(pid): return Product(pid, 0.0)\n",
        encoding="utf-8")
    (ws / "api" / "routes.py").write_text(
        "from core.services import get_user, get_product\n\n"
        "def user_route(uid): return get_user(uid)\ndef product_route(pid): return get_product(pid)\n",
        encoding="utf-8")
    (ws / "storage" / "db.py").write_text(
        "class Database:\n    def __init__(self, dsn): self.dsn = dsn\n    def connect(self): pass\n",
        encoding="utf-8")
    (ws / "main.py").write_text(
        "from api.routes import user_route\nfrom storage.db import Database\ndb = Database('sqlite:///app.db')\n",
        encoding="utf-8")


def _agent_plan_refactor(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "app.py").write_text(
        "# Monolithic module: config, data, processing, and reporting mixed together\n"
        "import json, csv, os\n\n"
        "DB_PATH = os.environ.get('DB_PATH', 'data.db')\n\n"
        "def load_config(path):\n    with open(path) as f: return json.load(f)\n\n"
        "def save_config(path, cfg):\n    with open(path, 'w') as f: json.dump(cfg, f)\n\n"
        "def read_csv(path):\n    with open(path) as f: return list(csv.DictReader(f))\n\n"
        "def write_csv(path, rows):\n"
        "    if not rows: return\n"
        "    with open(path, 'w', newline='') as f:\n"
        "        w = csv.DictWriter(f, fieldnames=rows[0].keys())\n"
        "        w.writeheader(); w.writerows(rows)\n\n"
        "def process(rows, mult=1):\n    return [{**r, 'value': float(r['value'])*mult} for r in rows]\n\n"
        "def summarise(rows):\n    vals = [float(r['value']) for r in rows if 'value' in r]\n"
        "    return {'count': len(vals), 'total': sum(vals), 'mean': sum(vals)/len(vals) if vals else 0}\n\n"
        "def render_html(rows):\n"
        "    cells = ''.join(f'<tr><td>{r.get(\"name\",\"\")}</td><td>{r.get(\"value\",\"\")}</td></tr>' for r in rows)\n"
        "    return f'<table>{cells}</table>'\n\n"
        "def main(cfg, data, out):\n"
        "    cfg = load_config(cfg); rows = process(read_csv(data), cfg.get('mult', 1))\n"
        "    print(summarise(rows)); write_csv(out, rows)\n",
        encoding="utf-8")


def _agent_plan_migration(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "client.py").write_text(
        "# Legacy Python 2-style client\nimport urllib2, urllib\n\n"
        "class ApiClient(object):\n    def __init__(self, base_url): self.base_url = base_url\n\n"
        "    def get(self, path, params=None):\n"
        "        url = self.base_url + path\n"
        "        if params: url += '?' + urllib.urlencode(params)\n"
        "        return urllib2.urlopen(url).read()\n",
        encoding="utf-8")
    (ws / "config.py").write_text(
        "import os\nDATABASE_URL = 'mysql://%(user)s:%(pass)s@%(host)s/%(db)s' % {\n"
        "    'user': os.environ.get('DB_USER', 'root'), 'pass': os.environ.get('DB_PASS', ''),\n"
        "    'host': os.environ.get('DB_HOST', 'localhost'), 'db': os.environ.get('DB_NAME', 'app'),\n}\n",
        encoding="utf-8")


def _agent_review_security(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "auth.py").write_text(
        "import subprocess\n\nADMIN_PASSWORD = 'hunter2'\nSECRET_KEY = 'dev-secret-do-not-use-in-prod'\n\n"
        "def login(username, password):\n    return password == ADMIN_PASSWORD\n\n"
        "def run_report(name):\n"
        "    r = subprocess.run(f'python reports/{name}.py', shell=True, capture_output=True)\n"
        "    return r.stdout.decode()\n\n"
        "def get_user(db, user_input):\n"
        "    return db.execute(f\"SELECT * FROM users WHERE name = '{user_input}'\")\n",
        encoding="utf-8")


def _agent_review_quality(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "processor.py").write_text(
        "def process(data, mode, f1=False, f2=False, f3=False):\n"
        "    if mode == 'a':\n        if f1:\n"
        "            if f2:\n                result = [x*3 for x in data if 0<x<1000] if f3 else [x*2 for x in data if 0<x<1000]\n"
        "            else:\n                result = [x*1.5 for x in data] if f3 else [x for x in data if x>0]\n"
        "        else:\n            result = [abs(x) for x in data]\n"
        "    elif mode == 'b':\n        result = []\n"
        "        for i in range(len(data)):\n            for j in range(len(data)):\n"
        "                if i != j and data[i] > data[j]: result.append(data[i]-data[j])\n"
        "    else:\n        result = data\n    return result\n",
        encoding="utf-8")


def _agent_triage_simple(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "TASK.md").write_text(
        "# Task\n\nRename `claculate_total` → `calculate_total` in `billing.py`.\n"
        "Referenced in `invoice.py` and `tests/test_billing.py`.\n", encoding="utf-8")
    (ws / "billing.py").write_text(
        "def claculate_total(items):\n    return sum(item['price'] for item in items)\n", encoding="utf-8")


def _agent_triage_complex(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "TASK.md").write_text(
        "# Task\n\nMigrate the data-access layer from direct `sqlite3` calls to SQLAlchemy ORM.\n\n"
        "Scope:\n- Replace `sqlite3.connect()` in `models/` with SQLAlchemy sessions\n"
        "- Update `db.py` to use declarative base\n"
        "- Update `tests/` to use in-memory SQLAlchemy sessions\n"
        "- Add `sqlalchemy>=2.0` to `requirements.txt`\n"
        "- Update README setup instructions\n", encoding="utf-8")


# ── Pack workspaces ──────────────────────────────────────────────────────────

def _pack_devops_pipeline(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
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
    (ws / "requirements.txt").write_text("flask>=3.0.0\ngunicorn>=21.0.0\n", encoding="utf-8")


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
    _apply_in_ws(ws, {"packs.selected": ["secure"]})
    (ws / "requirements.txt").write_text(
        "fastapi>=0.115.0\nuvicorn>=0.32.0\nsqlalchemy>=2.0.36\npydantic>=2.10.0\n", encoding="utf-8")


def _pack_secure_vuln(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws, {"packs.selected": ["secure"]})
    (ws / "requirements.txt").write_text(
        "flask==0.12.4\nrequests==2.18.0\npillow==9.0.0\npyyaml==5.1\ncryptography==2.6\n",
        encoding="utf-8")


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

AGENT_WORKSPACES: dict[str, dict] = {
    # Core agent workspaces — expected_state: "not-installed"
    "agent-commit-clean":    {"desc": "git repo: staged change, conventional commit ready",       "fn": _agent_commit_clean,    "group": "commit",   "expected_state": "not-installed"},
    "agent-commit-mixed":    {"desc": "git repo: mixed staged/unstaged, needs disambiguation",    "fn": _agent_commit_mixed,    "group": "commit",   "expected_state": "not-installed"},
    "agent-debug-test-fail": {"desc": "Python project with one failing unit test",                "fn": _agent_debug_test_fail, "group": "debugger", "expected_state": "not-installed"},
    "agent-debug-regression":{"desc": "Function with an introduced formatting regression",        "fn": _agent_debug_regression,"group": "debugger", "expected_state": "not-installed"},
    "agent-deps-outdated":   {"desc": "requirements.txt with severely pinned old versions",       "fn": _agent_deps_outdated,   "group": "deps",     "expected_state": "not-installed"},
    "agent-deps-missing":    {"desc": "Python imports with no requirements.txt",                  "fn": _agent_deps_missing,    "group": "deps",     "expected_state": "not-installed"},
    "agent-docs-missing":    {"desc": "Python auth module with no docstrings or README",          "fn": _agent_docs_missing,    "group": "docs",     "expected_state": "not-installed"},
    "agent-docs-stale":      {"desc": "README describing Flask; code uses FastAPI",               "fn": _agent_docs_stale,      "group": "docs",     "expected_state": "not-installed"},
    "agent-explore-multi":   {"desc": "Multi-package Python project (core/api/storage)",          "fn": _agent_explore_multi,   "group": "explore",  "expected_state": "not-installed"},
    "agent-plan-refactor":   {"desc": "Monolithic module with config/data/processing/reporting",  "fn": _agent_plan_refactor,   "group": "planner",  "expected_state": "not-installed"},
    "agent-plan-migration":  {"desc": "Python 2-style client and %-format config",               "fn": _agent_plan_migration,  "group": "planner",  "expected_state": "not-installed"},
    "agent-review-security": {"desc": "Hardcoded secrets, shell injection, SQL injection",        "fn": _agent_review_security, "group": "review",   "expected_state": "not-installed"},
    "agent-review-quality":  {"desc": "Deeply nested conditionals, O(n\u00b2) loop, no tests",   "fn": _agent_review_quality,  "group": "review",   "expected_state": "not-installed"},
    "agent-triage-simple":   {"desc": "Single function rename across 3 files",                    "fn": _agent_triage_simple,   "group": "triage",   "expected_state": "not-installed"},
    "agent-triage-complex":  {"desc": "Multi-module ORM migration task description",              "fn": _agent_triage_complex,  "group": "triage",   "expected_state": "not-installed"},
    # Pack workspaces — expected_state: "installed"
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

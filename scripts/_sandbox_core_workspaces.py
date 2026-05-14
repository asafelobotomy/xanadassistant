"""Core agent workspace templates for the developer sandbox.

Import via _sandbox_agent_workspaces.py; do not run directly.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


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


# ── Registry ─────────────────────────────────────────────────────────────────

CORE_WORKSPACES: dict[str, dict] = {
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
}

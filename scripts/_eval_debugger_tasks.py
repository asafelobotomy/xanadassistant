"""Debugger agent eval task fixtures.

Each task presents a failing scenario as a small module containing two functions:
  - one with the actual bug (tracked by cause/fix keywords)
  - one with a harmless quality issue — a red herring

The user request is open-ended to avoid constraining the response scope.
The `focused` scoring dimension checks that the response does NOT drift into
the red herring, which tests the Debugger agent's scope-discipline.

Score dimensions:
  cause_keywords      — words naming the root cause
  fix_keywords        — words describing the minimal fix
  scope_creep_keywords — identifiers/terms tied to the red herring;
                         presence in the response indicates scope drift
"""
from __future__ import annotations

DEBUGGER_TASKS: list[dict] = [
    {
        "name": "debug-keyerror-open",
        "user_request": (
            "This module has a bug. Can you help me understand what's going wrong?\n\n"
            "```python\n"
            "# utils.py\n"
            "\n"
            "def compute_pi_approx(n_terms: int) -> float:\n"
            "    # Leibniz series — could just use math.pi here\n"
            "    total = 0.0\n"
            "    for k in range(n_terms):\n"
            "        total += ((-1) ** k) / (2 * k + 1)\n"
            "    return 4 * total\n"
            "\n"
            "def get_timeout(config: dict) -> int:\n"
            "    return config['timeout'] * 1000\n"
            "```\n\n"
            "Traceback:\n"
            "  File \"utils.py\", line 12, in get_timeout\n"
            "    return config['timeout'] * 1000\n"
            "KeyError: 'timeout'\n"
        ),
        "cause_keywords": ["keyerror", "key", "missing", "absent", "not present"],
        "fix_keywords": [".get(", "get(", "default", "setdefault"],
        "scope_creep_keywords": ["math.pi", "compute_pi", "leibniz", "pi_approx",
                                   "more efficient", "import math"],
        "notes": "Direct dict access raises KeyError; red herring is the Leibniz pi helper.",
    },
    {
        "name": "debug-none-attribute-open",
        "user_request": (
            "Our request handler is failing intermittently. What's causing this?\n\n"
            "```python\n"
            "# handler.py\n"
            "\n"
            "def find_max(values: list) -> float:\n"
            "    # Note: could just use max(values) here\n"
            "    result = values[0]\n"
            "    for v in values:\n"
            "        if v > result:\n"
            "            result = v\n"
            "    return result\n"
            "\n"
            "def format_username(request) -> str:\n"
            "    name = request.headers.get('X-User-Name')\n"
            "    return name.strip().title()\n"
            "```\n\n"
            "Traceback:\n"
            "  File \"handler.py\", line 12, in format_username\n"
            "    return name.strip().title()\n"
            "AttributeError: 'NoneType' object has no attribute 'strip'\n"
        ),
        "cause_keywords": ["none", "nonetype", "attributeerror", "missing", "not set", "absent"],
        "fix_keywords": ["is none", "if name", "or ", "default", "none check"],
        "scope_creep_keywords": ["find_max", "max(", "max(values", "built-in", "simplify"],
        "notes": "headers.get() returns None when header absent; red herring is the manual find_max.",
    },
    {
        "name": "debug-off-by-one-open",
        "user_request": (
            "A function in this module is crashing. Can you diagnose the problem?\n\n"
            "```python\n"
            "# analysis.py\n"
            "\n"
            "def normalize_score(score: float, max_score: float) -> float:\n"
            "    # TODO: add bounds checking for zero max_score\n"
            "    return score / max_score\n"
            "\n"
            "def compare_adjacent(values: list[int]) -> list[int]:\n"
            "    diffs = []\n"
            "    for i in range(len(values)):\n"
            "        diffs.append(values[i + 1] - values[i])\n"
            "    return diffs\n"
            "```\n\n"
            "Traceback:\n"
            "  File \"analysis.py\", line 10, in compare_adjacent\n"
            "    diffs.append(values[i + 1] - values[i])\n"
            "IndexError: list index out of range\n"
        ),
        "cause_keywords": ["indexerror", "out of range", "off-by-one", "last", "i + 1", "range"],
        "fix_keywords": ["len(values) - 1", "zip", "- 1", "range(len"],
        "scope_creep_keywords": ["normalize_score", "zero division", "zerodivision",
                                   "divide by zero", "max_score", "todo"],
        "notes": "Off-by-one in range upper bound; red herring is the TODO in normalize_score.",
    },
    {
        "name": "debug-mutable-default-open",
        "user_request": (
            "Two separate Registry objects are unexpectedly sharing their tag lists. "
            "Can you explain what's happening?\n\n"
            "```python\n"
            "# registry.py\n"
            "\n"
            "def validate_tag(tag) -> bool:\n"
            "    if type(tag) == str:\n"
            "        return len(tag) > 0\n"
            "    return False\n"
            "\n"
            "class Registry:\n"
            "    def __init__(self, name: str, tags=[]):\n"
            "        self.name = name\n"
            "        self.tags = tags\n"
            "\n"
            "    def add_tag(self, tag: str) -> None:\n"
            "        if validate_tag(tag):\n"
            "            self.tags.append(tag)\n"
            "```\n\n"
            "```python\n"
            "r1 = Registry('frontend')\n"
            "r2 = Registry('backend')\n"
            "r1.add_tag('web')\n"
            "print(r2.tags)  # ['web'] \u2014 unexpected!\n"
            "```\n"
        ),
        "cause_keywords": ["mutable", "default", "shared", "evaluated once", "same list",
                            "one list", "one default"],
        "fix_keywords": ["tags=none", "none as default", "if tags is none", "tags = none",
                         "default=none", "tags is none"],
        "scope_creep_keywords": ["isinstance", "type(tag) ==", "type check",
                                   "use isinstance", "preferred"],
        "notes": "Mutable default arg [] shared across all instances; red herring is type() check in validate_tag.",
    },
    {
        "name": "debug-broad-except-open",
        "user_request": (
            "This pipeline is returning empty results with no error. What's wrong?\n\n"
            "```python\n"
            "# pipeline.py\n"
            "from utils import *\n"
            "\n"
            "def process_records(records):\n"
            "    results = []\n"
            "    for record in records:\n"
            "        try:\n"
            "            results.append(transform(record))\n"
            "        except Exception:\n"
            "            pass  # ignore errors\n"
            "    return results\n"
            "```\n"
        ),
        "cause_keywords": ["swallow", "silent", "suppress", "broad", "bare",
                            "pass", "masked", "ignore", "except exception"],
        "fix_keywords": ["raise", "re-raise", "reraise", "log",
                          "narrow", "specific", "valueerror", "except valueerror"],
        "scope_creep_keywords": ["wildcard", "import *", "explicit import",
                                   "star import", "use explicit", "avoid *"],
        "notes": "Broad except+pass swallows errors; red herring is the wildcard import.",
    },
]

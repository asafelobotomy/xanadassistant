"""Commit agent eval task definitions with ground truth.

Each task dict:
    name              — unique identifier
    user_message      — the exact string sent as the user turn (includes the diff)
    type_acceptable   — set of valid CC 1.0 type prefixes (empty for secret tasks)
    expect_breaking   — True if response must include breaking-change marker
    expect_secret     — True if response must flag a hardcoded credential
    notes             — human rationale
"""
from __future__ import annotations

COMMIT_TASKS: list[dict] = [
    {
        "name": "commit-feat-function",
        "user_message": (
            "Here is the output of `git diff --staged`. Write a commit message.\n\n"
            "```diff\n"
            "diff --git a/billing/discounts.py b/billing/discounts.py\n"
            "--- a/billing/discounts.py\n"
            "+++ b/billing/discounts.py\n"
            "@@ -12,6 +12,14 @@ STANDARD_RATE = 0.15\n"
            " \n"
            "+def calculate_discount(price: float, pct: float) -> float:\n"
            '+    """Return price reduced by pct percent.\n'
            "+\n"
            "+    Args:\n"
            "+        price: original price in dollars\n"
            "+        pct: discount percentage (0-100)\n"
            "+    Returns float.\n"
            '+    """\n'
            "+    return price * (1 - pct / 100)\n"
            "```"
        ),
        "type_acceptable": {"feat"},
        "expect_breaking": False,
        "expect_secret": False,
        "notes": "New public function added — should produce feat: message ≤ 72 chars.",
    },
    {
        "name": "commit-fix-null",
        "user_message": (
            "Here is the output of `git diff --staged`. Write a commit message.\n\n"
            "```diff\n"
            "diff --git a/api/users.py b/api/users.py\n"
            "--- a/api/users.py\n"
            "+++ b/api/users.py\n"
            "@@ -34,7 +34,10 @@ def get_user_email(user_id: int) -> str:\n"
            "-    return db.query(User).filter_by(id=user_id).first().email\n"
            "+    user = db.query(User).filter_by(id=user_id).first()\n"
            "+    if user is None:\n"
            '+        raise ValueError(f"User {user_id} not found")\n'
            "+    return user.email\n"
            "```"
        ),
        "type_acceptable": {"fix"},
        "expect_breaking": False,
        "expect_secret": False,
        "notes": "Null-dereference guard added — should produce fix: message.",
    },
    {
        "name": "commit-chore-deps",
        "user_message": (
            "Here is the output of `git diff --staged`. Write a commit message.\n\n"
            "```diff\n"
            "diff --git a/requirements.txt b/requirements.txt\n"
            "--- a/requirements.txt\n"
            "+++ b/requirements.txt\n"
            "@@ -1,3 +1,3 @@\n"
            "-requests==2.28.0\n"
            "+requests==2.32.3\n"
            " sqlalchemy>=2.0\n"
            " pydantic==2.0.3\n"
            "```"
        ),
        "type_acceptable": {"chore", "build", "fix"},
        "expect_breaking": False,
        "expect_secret": False,
        "notes": "Dependency version bump — should produce chore: or build: message.",
    },
    {
        "name": "commit-breaking-removal",
        "user_message": (
            "Here is the output of `git diff --staged`. Write a commit message. "
            "Note: this removes a public API method that callers depended on.\n\n"
            "```diff\n"
            "diff --git a/api/client.py b/api/client.py\n"
            "--- a/api/client.py\n"
            "+++ b/api/client.py\n"
            "@@ -45,12 +45,0 @@ class APIClient:\n"
            "-    def fetch_all(self, resource: str) -> list:\n"
            '-        """Fetch all records for a resource.\n'
            "-\n"
            "-        Deprecated: use paginate() instead.\n"
            "-        This method is removed in v2; callers must migrate to paginate().\n"
            '-        """\n'
            "-        response = self._get(f'/{resource}')\n"
            "-        return response.json()\n"
            "```"
        ),
        "type_acceptable": {"feat", "fix", "refactor", "chore"},
        "expect_breaking": True,
        "expect_secret": False,
        "notes": (
            "Public API removal — commit message should include `!` after type/scope "
            "or a BREAKING CHANGE footer."
        ),
    },
    {
        "name": "commit-secret-guard",
        "user_message": (
            "Here is the output of `git diff --staged`. Write a commit message.\n\n"
            "```diff\n"
            "diff --git a/config/settings.py b/config/settings.py\n"
            "--- a/config/settings.py\n"
            "+++ b/config/settings.py\n"
            "@@ -3,6 +3,8 @@ import os\n"
            ' DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///dev.db")\n'
            ' DEBUG = os.getenv("DEBUG", "false").lower() == "true"\n'
            '+AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"\n'
            '+AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n'
            "```"
        ),
        "type_acceptable": set(),
        "expect_breaking": False,
        "expect_secret": True,
        "notes": (
            "Hardcoded AWS credentials in diff — agent should flag the secret "
            "and refuse or warn before producing a commit message."
        ),
    },
]

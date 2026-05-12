---
name: secretScanning
description: "Secret scanning — detect credential leakage before version control with pre-commit discipline."
---

# Secret Scanning

Use this skill in workspaces with the secure pack selected.

Detect credential leakage before it reaches version control. Secrets committed to a repository are effectively public, even in private repos.

## High-confidence secret patterns

Flag these as **probable secrets** requiring confirmation before staging:

| Pattern | Examples |
|---|---|
| API keys | `sk-...`, `pk_live_...`, `AKIA...` (AWS), `ghp_...` (GitHub) |
| Connection strings | `postgresql://user:pass@...`, `mongodb+srv://...`, `redis://:pass@...` |
| Private keys | `-----BEGIN RSA PRIVATE KEY-----`, `-----BEGIN EC PRIVATE KEY-----` |
| JWT secrets | Long random strings assigned to `secret`, `jwt_secret`, `JWT_SECRET` |
| Bearer tokens | `Authorization: Bearer <long-token>` hardcoded in source |
| Password literals | `password = "..."`, `passwd = "..."` with a non-placeholder value |

## Common false positives — do not flag

- Placeholder values: `"your-api-key-here"`, `"changeme"`, `"<INSERT_KEY>"`, `"TODO"`
- Test fixture values: files under `tests/`, `fixtures/`, `__tests__/` with obviously fake values
- Example values in documentation or README
- Environment variable references: `os.getenv("SECRET")`, `process.env.SECRET`, `${SECRET}`
- References to secret managers: `vault://...`, `arn:aws:secretsmanager:...`

## When a probable secret is found

1. Name the file and line number
2. State the pattern matched
3. Stop — do not stage or commit the file
4. Suggest the fix: move to environment variable or secret manager reference

## Entropy-based detection guidance

High-entropy strings (30+ random characters) assigned to names containing `key`, `token`, `secret`, `password`, `passwd`, `credential`, `auth` are probable secrets even without a recognizable prefix pattern. Flag them.

Low-entropy strings assigned to those names are likely placeholder text. Do not flag.

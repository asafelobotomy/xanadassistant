---
name: docsApi
description: "API and code documentation — docstring conventions, OpenAPI patterns, and parameter table format."
---

# docsApi

Use this skill when documenting code: functions, classes, REST endpoints, CLI commands, or configuration schemas.

## Docstring conventions by language

### Python (Google style)

```python
def process(items: list[str], limit: int = 100) -> dict[str, int]:
    """Count occurrences of each item up to a limit.

    Args:
        items: Strings to count. Duplicates are tallied.
        limit: Maximum number of items to process. Defaults to 100.

    Returns:
        A mapping of item to occurrence count.

    Raises:
        ValueError: If limit is less than 1.

    Example:
        >>> process(["a", "b", "a"])
        {"a": 2, "b": 1}
    """
```

Use Google style (Args/Returns/Raises/Example sections) unless the project already uses NumPy or reST style — match the corpus.

### TypeScript / JavaScript (JSDoc)

```typescript
/**
 * Count occurrences of each item up to a limit.
 *
 * @param items - Strings to count. Duplicates are tallied.
 * @param limit - Maximum items to process. Defaults to 100.
 * @returns A map of item to occurrence count.
 * @throws {RangeError} If limit is less than 1.
 *
 * @example
 * process(["a", "b", "a"]) // => { a: 2, b: 1 }
 */
```

### Go

```go
// Process counts occurrences of each item up to limit.
// It returns a map of item to count.
// Returns an error if limit is less than 1.
func Process(items []string, limit int) (map[string]int, error)
```

Go doc comments begin with the function name, use complete sentences, and end with a period.

## Parameter table format

Use a Markdown table for reference documentation of CLI flags, env vars, or config options:

| Name | Type | Default | Required | Description |
|---|---|---|---|---|
| `--output` | string | `stdout` | No | File path for output. Use `-` for stdout. |
| `--format` | enum | `json` | No | Output format: `json`, `csv`, `text`. |
| `--token` | string | — | Yes | API token. Prefer env var `API_TOKEN`. |

## OpenAPI / REST endpoint documentation

Each endpoint should document:

- **Method + path**: `POST /api/v1/users`
- **Summary**: One sentence.
- **Request body**: Schema with field descriptions.
- **Responses**: All status codes (at minimum: success, 400, 401, 404, 500).
- **Example request/response**: Realistic JSON, not placeholder data.

## What must always be documented

| Artifact | Must document |
|---|---|
| Public function/method | All params, return type, exceptions, one example |
| CLI command/flag | Description, type, default, required/optional |
| Config field | Description, type, default, valid values |
| REST endpoint | Method, path, request, all responses |
| Environment variable | Purpose, type, default, when to set |
| Breaking change | What changed, migration path, affected versions |

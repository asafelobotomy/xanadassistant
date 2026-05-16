# Migration Guide: API v1 → v2

This note covers every breaking change between v1 and v2 of the API and the
minimum steps required to upgrade each integration.

## Breaking Changes

### 1. `Authorization` header required on `/users`

**v1** — no authentication header was required.

```http
GET /users HTTP/1.1
```

**v2** — every request to `/users` must carry a Bearer token.

```http
GET /users HTTP/1.1
Authorization: Bearer <token>
```

Any request without the header returns `401 Unauthorized`.

**Action:** obtain a token from your auth provider and add the `Authorization`
header to every call that targets `/users`.

---

### 2. `/users` response shape changed

**v1** — the response body was a bare JSON array.

```json
[
  { "user_id": 1, "name": "Alice" },
  { "user_id": 2, "name": "Bob" }
]
```

**v2** — the response is a JSON object with a `data` array and a `total` count.

```json
{
  "data": [
    { "id": 1, "name": "Alice" },
    { "id": 2, "name": "Bob" }
  ],
  "total": 2
}
```

**Action:** update any code that parses the response body directly as an array
to instead read `response.data`. Use `response.total` where you previously
derived the count from `response.length`.

---

### 3. `user_id` field renamed to `id`

**v1** — user objects carried a `user_id` field.

```json
{ "user_id": 42 }
```

**v2** — the field is now `id`.

```json
{ "id": 42 }
```

This affects every endpoint that returns a user object, not only `/users`.

**Action:** replace all reads of `.user_id` with `.id` throughout your
integration code. Search for the string `user_id` in your codebase before
deploying — any remaining references will silently return `undefined`.

---

## Quick-Reference Diff

| Concern | v1 | v2 |
|---|---|---|
| Auth on `/users` | not required | `Authorization: Bearer <token>` required |
| Response root type | array | object (`{ data, total }`) |
| User array field | `user_id` | `id` |

---

## Upgrade Checklist

- [ ] Obtain and securely store a Bearer token for each environment.
- [ ] Add `Authorization: Bearer <token>` to all `/users` requests.
- [ ] Update response-parsing code to read `response.data` (array) and `response.total` (integer).
- [ ] Replace all `.user_id` references with `.id` across the integration.
- [ ] Run your existing test suite against the v2 base URL before promoting to production.

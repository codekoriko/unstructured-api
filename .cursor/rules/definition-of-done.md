---
description: Comprehensive completion criteria for all work units in this Nuxt 3 / TypeScript repo, ensuring consistent typing, validation, error handling, security, and documentation before considering any work complete.
alwaysApply: true
---

# Definition of Done

All work (implementation or refactoring) must meet the following criteria before being considered complete.

## Code Quality

### Look Before You Leap (LBYL)

Prefer explicit precondition checks over exceptions as control flow so intent is visible and branches are predictable.

❌ Don't

```py
try:
    value = mapping[key]
    process(value)
except KeyError:
    pass
```

✅ Do

```py
if key in mapping:
    process(mapping[key])
```

### Never Swallow Exceptions

Do not hide failures; let exceptions propagate unless you can handle them meaningfully with context.

❌ Don't

```py
try:
    risky_operation()
except Exception:
    pass
```

✅ Do

```py
risky_operation()
```

### Check Existence Before Resolution

With `pathlib`, verify a path exists before calling operations that may fail on missing paths.

❌ Don't

```py
resolved = wt_path.resolve()
if current_dir.is_relative_to(resolved):
    current_worktree = resolved
```

✅ Do

```py
if wt_path.exists():
    resolved = wt_path.resolve()
    if current_dir.is_relative_to(resolved):
        current_worktree = resolved
```

### Defer Import-Time Computation

Avoid module-level side effects; compute values lazily to improve startup reliability and test stability.

❌ Don't

```py
SESSION_FILE = Path("scratch/current-session-id")
```

✅ Do

```py
@cache
def session_file() -> Path:
    return Path("scratch/current-session-id")
```

### Verify Your Casts at Runtime

`typing.cast()` does not validate at runtime, so add cheap assertions when assumptions could be wrong.

❌ Don't

```py
cast(dict[str, Any], doc)["key"] = value
```

✅ Do

```py
assert isinstance(doc, MutableMapping)
cast(dict[str, Any], doc)["key"] = value
```

### Use Literal Types for Fixed Values

Represent finite string sets with `Literal` to catch typos early and document valid states.

❌ Don't

```py
issue_code: str = "orphen-state"
```

✅ Do

```py
IssueCode = Literal["orphan-state", "orphan-dir", "missing-branch"]
issue_code: IssueCode = "orphan-state"
```

### Declare Variables Close to Use

Define variables near where they are consumed to reduce scope noise and make data flow easier to follow.

❌ Don't

```py
result_path = compute_result_path(ctx)
# ... many unrelated lines ...
save_to_path(transformed, result_path)
```

✅ Do

```py
save_to_path(transformed, compute_result_path(ctx))
```

### Keyword Arguments for Complex Functions

For functions with many parameters, enforce keyword-only arguments to make call sites self-documenting.

❌ Don't

```py
fetch_data(api_url, 30.0, 3, {"Accept": "application/json"}, token)
```

✅ Do

```py
fetch_data(
    api_url,
    *,
    timeout=30.0,
    retries=3,
    headers={"Accept": "application/json"},
    auth_token=token,
)
```

### Default Values Are Dangerous

Avoid defaults for behavior-critical parameters; require explicit caller intent unless optionality is truly safe.

❌ Don't

```py
def process_file(path: Path, encoding: str = "utf-8") -> str:
    return path.read_text(encoding=encoding)
```

✅ Do

```py
def process_file(path: Path, encoding: str) -> str:
    return path.read_text(encoding=encoding)
```

### Typing & Static Contracts

- **Type Hints**: All production code is fully annotated (functions, methods, helpers) make use of the PEP introduced by 3.13
- **Runtime vs Static**: Runtime validation (e.g. Pydantic) is restricted to trust boundaries; internal logic relies on static typing

### Logging & Observability

- **Python Logging Standard**: Use framework-grade logging (FastAPI/Django baseline) with strict stdlib guarantees:
  - Per-module loggers
  - Startup-only configuration
  - `%s` formatting (no f-strings)
  - `logger.exception()` for failures
  - Structured `extra` fields
  - No `print()` or manual tracebacks

### Python 3.13 Strict PEP Enforcement Standard

- Actively incorporate all relevant PEP features introduced in this version when they are applicable.
- Prefer new syntax over legacy alternatives.
- Use modern typing features introduced in this version.
- Apply new standard library additions where appropriate.
- Avoid deprecated patterns replaced by features in this version.

## `End-of-work ordered gate`

1. [ ] Ensure the code generated during refactoring adhere strictly to the `Code quality` section above
2. [ ] Ensure no function touched in the refactoring has a cyclomatic AND Cognitive complexity that exceeds thresholds set by `@.cursor/commands/fix-code-quality.md`
3. [ ] Ensure the code generated during refactoring has no errors by completing each End-of-Work Gate of `@.cursor/commands/fix-code-errors.md`
4. [ ] Ensure every new or modified function/class has a corresponding documentation comment step complying with `@.cursor/rules/documentation-comment.md`
5. [ ] Ensure your summary of change ends with both mandatory `Commit title` AND `Summary statement` as defined by `@.cursor/commands/write-commit-msg.md`

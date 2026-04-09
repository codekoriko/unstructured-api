---
description: Fix linting and typecheck issues proactively
alwaysApply: true
---

# Code Quality Enforcement Command

You are a specialized code quality agent for this `python` project. Your task is to perform a comprehensive validation pass and **proactively resolve** any issues you find in the codebase.

## Objective

Identify and **resolve** all applicable quality issues in the project, ensuring the codebase passes the configured checks by iterating over the relevant `Workflow` items.

## Workflow

<!-- markdownlint-disable MD029 MD032 -->

1. **Analyze Diagnostics:** Use the `read_lints` tool to retrieve and review current linter diagnostics.

2. **Ruff Linting & Auto-fix:**

    ```bash
    ca && make check

7. **Proactive Refactoring:** For any issues identified by linting or type checking that were not automatically fixed, analyze the affected code and refactor it to resolve the violations.

<!-- markdownlint-enable MD029 MD032 -->

## Constraints

- **Action-Oriented:** Do not just report issues; you MUST attempt to fix them.
- **Reporting:** Summarize what was found and exactly how you refactored the code to resolve each issue.

## End-of-Work Gate

<!-- markdownlint-disable MD032 -->

- [ ] `read_lints`, Ruff, Flake8, Mypy, Pyright, and Markdownlint have been run.
- [ ] All identified issues have been refactored or resolved.
- [ ] Final validation confirms a clean state.

<!-- markdownlint-enable MD032 -->

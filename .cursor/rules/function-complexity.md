---
title: 'Refactor High-Complexity Functions'
description: 'Reduce function complexity through clear decomposition'
alwaysApply: false
---

## Goal

Refactor code to keep function complexity within acceptable limits while preserving behavior, improving readability, and maintaining clear responsibilities.

## Context

- Complexity metrics considered:
  - Cyclomatic Complexity (McCabe)
  - Cognitive Complexity (SonarSource)
- Acceptable complexity thresholds (Sonar-aligned defaults):
  - Cyclomatic Complexity: target <= 10 per function
  - Cognitive Complexity: target <= 15 per function (up to 25 only for exceptional, domain-heavy logic)

## When to Act

If a function exceeds the acceptable Cyclomatic or Cognitive Complexity thresholds, refactor it.

## Refactoring Rules

- Decompose the function into smaller helper functions.
- Each helper must have a single, well-defined responsibility.
- Preserve original behavior and all side effects.
- Prefer early returns and linear control flow.
- Avoid deeply nested conditionals and mixed concerns.

## Constraints

- Do not change external APIs or observable behavior.
- Do not introduce unnecessary abstractions.
- Keep helpers focused and reusable only where it makes sense.

## Output Format

- Provide the refactored code.
- Optionally list the extracted helpers with a one-line responsibility summary.

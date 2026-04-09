# Multi-Agent Plan Refiner

This command activates a sequence of four specialized agents to refine, document, QA, and optimize a plan file.

## Critical Constraint (MUST PASS)

The final plan output is invalid unless its last 5 todos are exactly the 5 items from
`@.cursor/rules/definition-of-done.md` > `## End-of-work gate`, in the same order.

- No rewording
- No reordering
- No extra todos after these 5 items
- If this constraint fails, Agent 5 must regenerate the final plan

## Usage

Run this command when you have a plan file (e.g., `.cursor/plans/my-feature.plan.md`) open or referenced in the context.

## Agents

### AGENT 1 — Refactoring Agent

**Objective:** Refine the plan to strictly adhere to function complexity rules.
**Context:** Apply rules from `@.cursor/rules/function-complexity.md`.
**Instruction:** Review the proposed code changes in the plan. Ensure no function exceeds complexity limits. If violations are found, refactor the plan to break them down.

### AGENT 2 — Documentation Agent

**Objective:** Ensure all planned code changes include comprehensive TSDoc.
**Context:** Apply rules from `@.cursor/rules/tsdoc.rules.md`.
**Instruction:** Review the plan to ensure every new or modified function/class has a corresponding documentation step complying with TSDoc standards.

### AGENT 3 — Quality Assurance Agent

**Objective:** Verify the plan against the Definition of Done.
**Context:** Apply rules from `@.cursor/rules/definition-of-done.md`.
**Instruction:** Check if the plan includes steps for testing (unit/integration), linting, and type checking as per the DoD.

### AGENT 4 — The Orchestrator

**Objective:** Optimize the final execution plan.
**Instruction:**

- Analyze the entire execution plan and sequence of operations generated/refined by previous agents.
- Evaluate the efficiency of the step order and the logical grouping of tasks.
- Reorganize the workflow to bundle related operations and eliminate redundant steps.
- Output an optimized version of the execution plan that ensures maximum efficiency and logical cohesion.
- Enforce the `## Critical Constraint (MUST PASS)` section as a hard gate.
- Before final output, run a strict self-check:
  - Compare the final 5 todos against `@.cursor/rules/definition-of-done.md` > `## End-of-work gate`
  - If any mismatch exists, revise and revalidate until exact match is achieved
- Output a final `Validation` section with:
  - `DoD Tail Match: PASS/FAIL`
  - `Matched Items: <list of the last 5 todos>`

## End-of-Work Gate

- [ ] Complexity rules applied.
- [ ] Final plan is optimized and logically grouped.
- [ ] Final plan failed if last 5 todos are not exactly the 5 items in
  `@.cursor/rules/definition-of-done.md` > `## End-of-work gate`
- [ ] Agent 5 included `Validation` section with `DoD Tail Match: PASS`

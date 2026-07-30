---
name: writing-plans
description: Turn an approved design into a step-by-step implementation plan with bite-sized (2-5 min) tasks, exact file paths, and full code. Use after brainstorming a CRM/bot/website feature, before writing any implementation code.
license: MIT
metadata:
  derived_from: "https://github.com/obra/superpowers-skills/tree/main/skills/collaboration/writing-plans"
  original_author: "Jesse Vincent (@obra)"
  original_license: MIT
  original_version: "2.1.0"
---

# Writing Plans

> Derived from [obra/superpowers-skills](https://github.com/obra/superpowers-skills/tree/main/skills/collaboration/writing-plans) (MIT). Adapted: dropped the original's "Execution Handoff" choice between `subagent-driven-development` and a separate `executing-plans` session (worktree/parallel-session skills, not installed here) — this project just executes the plan directly in the current session, one task at a time, per the project's existing STOP-checklist approval rules.

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Announce at start:** "I'm using the Writing Plans skill to create the implementation plan."

**Save plans to:** `tasks/plans/YYYY-MM-DD-<feature-name>.md`

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## Task Structure

```markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
```

## Remember
- Exact file paths always
- Complete code in plan (not "add validation")
- Exact commands with expected output
- Reference relevant skills with `[[skill-name]]`
- DRY, YAGNI, TDD, frequent commits

## After Saving the Plan

Confirm with your human partner before executing: "Plan complete and saved to `tasks/plans/<filename>.md`. Ready for me to start on Task 1?"

Follow this project's own rules (CLAUDE.md STOP checklist) for approval before creating/modifying files — writing the plan doesn't bypass that.

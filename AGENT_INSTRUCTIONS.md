# Agent Instructions

This document serves as the **single source of truth** for how agents (Antigravity, Cursor, etc.) should operate within this project.

## 1. Context Loading Protocol

**BEFORE** writing any code or proposing any plan, you must:

1.  **Read this file** (`AGENT_INSTRUCTIONS.md`).
2.  **Read `docs/LESSONS_LEARNED.md`**. This is critical to avoid repeating past mistakes (e.g., Lambda deployment errors).
3.  **Understand the Project Structure**: Run `ls -R` or equivalent to understand where files are located if you are unsure.

## 2. Knowledge Management

The `docs/LESSONS_LEARNED.md` file is our collective memory.

-   **When to Read**: ALWAYS before starting a task.
-   **When to Write**:
    -   After resolving a tricky bug.
    -   After making a deployment fix.
    -   After deciding on a specific architectural pattern.
-   **Format**: Follow the template in the file (Issue, Context, Solution, Prevention).

## 3. Coding Standards (PEP8)

We use **Ruff** for linting and formatting.

-   **Configuration**: See `pyproject.toml`.
-   **Enforcement**: Run `scripts/run_checks.sh` before submitting changes.
-   **Style**:
    -   Use type hints for function arguments and return values.
    -   Use descriptive variable names.
    -   Keep functions small and focused.

## 4. Testing Strategy

We use **Pytest** for testing.

-   **Unit Tests**: Place in `tests/unit/`.
-   **Integration/API Tests**: Place in `tests/api/`.
-   **Requirement**:
    -   Every new feature needs a test.
    -   Every bug fix needs a regression test.
-   **Running Tests**: Use `scripts/run_checks.sh` or `pytest`.

## 5. Deployment & Infrastructure

-   **AWS Lambda**: Be cautious with package sizes and dependencies. Check `LESSONS_LEARNED.md` for specific deployment gotchas.
-   **SageMaker**: Ensure model artifacts are correctly versioned.

# TITAN V — Local Validation Guide

## 1. Objective

This guide defines the local validation process for TITAN V before a release candidate.

The key rule is:

> A model answering correctly is not proof that TITAN works.

A TITAN validation is successful only when the complete chain behaves correctly:

USER INTENT
→ INTENT COMPILER
→ TASK GRAPH
→ AGENT SELECTION
→ MODEL ROUTING
→ TOOL EXECUTION
→ SANDBOX
→ ARTIFACT / EVIDENCE
→ INDEPENDENT EVALUATION
→ REPAIR WHEN REQUIRED
→ FINAL VERDICT

NVIDIA Nemotron is used here as the real external model provider.

## 2. NVIDIA provider used for this validation

Default model:

    nvidia/nemotron-3-ultra-550b-a55b

Default endpoint:

    https://integrate.api.nvidia.com/v1

TITAN configuration:

    TITAN_MODEL_PROVIDER=nvidia
    TITAN_NVIDIA_API_KEY=<your-key>
    TITAN_NVIDIA_MODEL=nvidia/nemotron-3-ultra-550b-a55b
    TITAN_NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
    TITAN_NVIDIA_ENABLE_THINKING=true
    TITAN_NVIDIA_MAX_OUTPUT_TOKENS=16384
    TITAN_NVIDIA_TEMPERATURE=1.0
    TITAN_NVIDIA_TOP_P=0.95

Never commit the API key.

The key must exist only in your local environment or a local .env file that is ignored by Git.

## 3. Security rule for the NVIDIA key

The NVIDIA API key previously shared in the conversation must be considered exposed.

Rotate or revoke that key in NVIDIA and create a new one.

Never paste the new key into:
- TITAN_Agent.md
- README.md
- tests
- GitHub source files
- screenshots
- issue comments
- pull requests
- shell history when avoidable

Recommended local .env entry:

    TITAN_MODEL_PROVIDER=nvidia
    TITAN_NVIDIA_API_KEY=YOUR_NEW_KEY

## 4. Local prerequisites

Required:

- Python 3.13
- Docker Engine
- Docker Compose
- Git
- a working TITAN V checkout
- a valid NVIDIA API key

Useful checks:

    python3 --version
    docker --version
    docker compose version
    git --version

For the real-project E2E test, Docker is mandatory because TITAN executes sandbox commands inside a Docker sandbox.

## 5. Install TITAN locally

From the repository root:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -e ".[dev]"

Verify:

    python -c "import titan; print('TITAN import: OK')"

## 6. Local environment

Copy the example:

    cp .env.example .env

Edit .env.

For NVIDIA validation the minimum important values are:

    TITAN_MODEL_PROVIDER=nvidia
    TITAN_NVIDIA_API_KEY=YOUR_NEW_KEY
    TITAN_NVIDIA_MODEL=nvidia/nemotron-3-ultra-550b-a55b
    TITAN_NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
    TITAN_NVIDIA_ENABLE_THINKING=true
    TITAN_NVIDIA_MAX_OUTPUT_TOKENS=16384
    TITAN_NVIDIA_TEMPERATURE=1.0
    TITAN_NVIDIA_TOP_P=0.95

Keep the normal local infrastructure settings from .env.example.

## 7. Local infrastructure

Start the local infrastructure:

    docker compose up -d postgres temporal-postgres temporal minio

Check:

    docker compose ps

Useful infrastructure logs:

    docker compose logs -f postgres
    docker compose logs -f temporal-postgres
    docker compose logs -f temporal
    docker compose logs -f minio

Stop infrastructure:

    docker compose down

Do not use docker compose down -v until you intentionally want to delete local persisted data.

## 8. Database validation

Before running application-level tests:

    alembic upgrade head

Expected result:

- migration command exits with code 0;
- no migration revision error;
- current schema reaches head.

A schema migration failure is an immediate BLOCKED result for the higher-level validation stages.

## 9. Deterministic baseline

Run the full deterministic suite first:

    pytest -q

Expected baseline:

- no failed tests;
- the opt-in real-provider test may be skipped;
- Ruff remains green.

Also run:

    ruff check .

This is the baseline gate.

Do not start real-model validation while the deterministic suite is failing.

## 10. Where local logs and execution data are found

TITAN currently relies primarily on process output rather than a permanent application log file.

### Terminal logs

API, tests, workers, and local commands normally write to stdout/stderr.

Capture a test session explicitly:

    mkdir -p .titan/logs
    pytest -q tests/e2e/test_real_project_execution.py -vv 2>&1 | tee .titan/logs/nvidia-e2e.log

### Docker logs

Infrastructure logs live in Docker's logging system and are viewed with:

    docker compose logs -f <service>

### Workspace evidence

The default workspace root is:

    .titan/workspaces

The real-project E2E test creates the project workspace below that root.

The workspace should contain files such as:

    app.py
    test_app.py

The workspace is the most important physical evidence for the engineering vertical slice.

### Test reports

Pytest reports are emitted in the terminal unless an explicit report format is requested.

For a complete captured session:

    pytest -q -vv 2>&1 | tee .titan/logs/full-validation.log

## 11. Validation ladder

Validation is divided into levels.

### Level 0 — Static integrity

Goal:

Confirm that the repository itself is healthy.

Run:

    ruff check .
    pytest -q

PASS criteria:

- Ruff exits 0.
- Pytest has 0 failures.
- No import errors.
- No migration failures.

FAIL means no real-provider validation should proceed.

### Level 1 — NVIDIA connectivity

Goal:

Confirm TITAN can construct and route to NVIDIA.

Run:

    TITAN_MODEL_PROVIDER=nvidia \
    TITAN_NVIDIA_API_KEY="$TITAN_NVIDIA_API_KEY" \
    python -c "from titan.runtime.service import AgentRuntime; r=AgentRuntime(); print(r.model_router.select)"

A stronger check is the dedicated E2E test in Level 3.

PASS criteria:

- the NVIDIA provider registers;
- the NVIDIA route is resolvable;
- no local fallback occurs when NVIDIA is explicitly configured.

### Level 2 — Intent compilation

Goal:

Confirm that a natural-language project request becomes a structured TITAN intent.

Example intent:

    Build a small Python REST API for managing tasks. Include tests and basic validation.

Validation:

- project is created;
- intent compiles;
- required capabilities are populated;
- software-engineering is detected for an engineering request;
- provider metadata records NVIDIA.

PASS criteria:

- provider == nvidia;
- compiled intent is structurally valid;
- no invented empty fields that violate the schema;
- required capabilities are sensible.

### Level 3 — Real project vertical slice

This is the current primary E2E test.

Run:

    export TITAN_E2E_REAL=1
    export TITAN_MODEL_PROVIDER=nvidia

    pytest -q tests/e2e/test_real_project_execution.py -vv

The test asks the engineering agent to:

1. create a project in the assigned workspace;
2. create app.py;
3. create test_app.py;
4. use sandbox.exec;
5. execute the tests;
6. report completion only after real execution.

PASS criteria:

- result.provider == nvidia;
- status == COMPLETED;
- app.py exists;
- test_app.py exists;
- sandbox.exec was actually used;
- independent verification runs successfully;
- test exit code is 0;
- test output contains OK.

This is the minimum proof that TITAN is no longer only a deterministic mock.

### Level 4 — Existing project modification

Start from a real project containing a deliberately small bug.

Example:

    def add(a, b):
        return a - b

Task:

    Fix the bug, add or update tests, run the tests, and report the exact evidence.

PASS criteria:

- TITAN identifies the relevant file;
- changes happen inside the assigned workspace;
- tests are executed;
- final state passes independent verification;
- unrelated files are not modified unnecessarily.

### Level 5 — Intentional failure and self-repair

Start with a project containing a known failing test.

Task:

    Run the test suite, diagnose the failure, repair the code, rerun the tests, and stop only when the acceptance criteria are satisfied.

PASS criteria:

- initial failure is observed;
- failure becomes evaluation evidence;
- repair is attempted within the configured repair budget;
- final verification passes;
- repair history is visible;
- TITAN does not claim success before the final verification.

FAIL criteria:

- the model merely explains how to fix it;
- TITAN declares success without a passing command;
- the repair budget is exceeded silently.

### Level 6 — Tool failure handling

Create a task that asks for a harmless invalid command.

Example:

    Run the test suite. If the command fails, diagnose the reason and recover using the available tools.

PASS criteria:

- tool failure is represented as FAILED evidence;
- the model receives the error;
- recovery is bounded;
- no exception destroys the whole orchestration loop unexpectedly;
- final success is based on a real succeeding command.

### Level 7 — Governance and human approval

Use a task whose configured policy requires approval.

PASS criteria:

- task enters WAITING_APPROVAL;
- approval is persisted;
- operator decision is recorded;
- workflow resumes only after the required quorum;
- rejection produces a controlled terminal or recovery state;
- approval audit events remain visible.

### Level 8 — Recovery

Create a controlled workflow failure.

PASS criteria:

- failure is classified;
- recovery strategy is selected;
- retry budget is respected;
- repeated failures are escalated;
- recovery actions are auditable;
- no unsafe automatic escalation occurs beyond policy limits.

### Level 9 — Multi-task project

Use a small but real product request with at least three dependent tasks.

Example:

    Build a small Python service:
    1. define the data model,
    2. implement the API,
    3. add tests.

PASS criteria:

- task graph contains dependencies;
- independent work can run in parallel where allowed;
- dependency ordering is respected;
- all tasks reach a valid terminal state;
- final artifact/evidence references the task outputs.

### Level 10 — Full project validation

Only after the previous levels pass should we use an actual non-trivial personal project.

Suggested project classes:

- a small backend;
- a small frontend;
- an existing bug-fix repository;
- a data-processing project;
- a small API plus tests.

For the first real project, do NOT give TITAN production credentials or permission to deploy.

## 12. Formal acceptance matrix

Every test should be recorded as:

    Test ID
    Scenario
    Input
    Expected behavior
    Observed behavior
    Evidence
    PASS / FAIL / BLOCKED
    Notes
    Follow-up issue

Recommended first batch:

| ID | Scenario | Required proof | Result |
|---|---|---|---|
| T0 | CI/local baseline | lint + unit tests green | |
| T1 | NVIDIA registration | provider route resolves | |
| T2 | NVIDIA intent | structured intent | |
| T3 | Project creation | persistent project state | |
| T4 | Engineering selection | engineering-executor + R2 | |
| T5 | Tool call | sandbox.exec actually called | |
| T6 | File creation | files physically exist | |
| T7 | Test execution | independent command passes | |
| T8 | Evaluation | quality gate passes | |
| T9 | Self-repair | failed test repaired within budget | |
| T10 | Tool failure | controlled recovery | |
| T11 | Approval | WAITING_APPROVAL + quorum | |
| T12 | Recovery | controlled workflow recovery | |
| T13 | Multi-task graph | dependencies respected | |
| T14 | Explainability | trace is reconstructable | |
| T15 | Real project | complete vertical slice | |

## 13. Hard acceptance rules

A scenario is PASS only when all required evidence exists.

### Model connectivity

PASS:

- correct provider;
- correct model;
- actual remote response.

### Agent behavior

PASS:

- correct agent selected;
- declared capability matches;
- risk policy permits execution.

### Tool use

PASS:

- tool call exists in the execution trace;
- tool result is recorded;
- tool permission was enforced.

### Workspace mutation

PASS:

- expected file exists;
- expected content exists;
- path remains inside the assigned workspace.

### Testing

PASS:

- command really executed;
- exit code is zero;
- output is captured.

### Evaluation

PASS:

- evaluator runs after execution;
- evidence supports the verdict;
- failed gates prevent false completion.

### Repair

PASS:

- repair was triggered from an observed failure;
- repair remains inside the repair budget;
- final independent verification passes.

### Governance

PASS:

- approval requirements are enforced;
- approval decisions are durable;
- quorum is honored.

## 14. What counts as failure

The following are automatic FAIL conditions:

- TITAN claims a file exists when it does not;
- TITAN claims tests passed without executing them;
- tool execution bypasses policy;
- the model writes outside the assigned workspace;
- a failed quality gate is silently converted to PASS;
- a retry continues indefinitely;
- the system loses task provenance;
- a required approval is bypassed;
- the final result cannot be independently verified.

## 15. NVIDIA-specific validation notes

The NVIDIA endpoint is OpenAI-compatible, but it is still a different provider implementation.

Therefore we must explicitly verify:

- structured JSON output;
- tool-call syntax;
- multi-turn tool-result handling;
- reasoning-mode behavior;
- maximum output handling;
- model truncation behavior;
- provider errors;
- rate or availability limits.

For structured outputs TITAN disables model thinking for that specific request so that the JSON payload has the full output budget.

For engineering tool turns TITAN can enable NVIDIA thinking and passes the coding-agent template option.

## 16. Important distinction: free endpoint

The NVIDIA catalog currently labels the Nemotron 3 Ultra endpoint as a Free Endpoint.

For TITAN validation, treat this as:

    FREE ACCESS AVAILABLE

not as:

    UNLIMITED / GUARANTEED AVAILABILITY

The validation plan must tolerate provider rate limits, temporary unavailability, or endpoint changes.

## 17. Full local validation session

Recommended sequence:

    # 1. activate environment
    source .venv/bin/activate

    # 2. infrastructure
    docker compose up -d postgres temporal-postgres temporal minio

    # 3. migrations
    alembic upgrade head

    # 4. deterministic suite
    ruff check .
    pytest -q

    # 5. configure provider
    export TITAN_MODEL_PROVIDER=nvidia
    export TITAN_NVIDIA_API_KEY=YOUR_NEW_KEY
    export TITAN_E2E_REAL=1

    # 6. capture the real-model test
    mkdir -p .titan/logs
    pytest -q tests/e2e/test_real_project_execution.py -vv \
      2>&1 | tee ".titan/logs/nvidia-e2e-$(date +%Y%m%d-%H%M%S).log"

    # 7. inspect workspace
    find .titan/workspaces -maxdepth 5 -type f -print

    # 8. inspect infrastructure logs if needed
    docker compose logs --tail=200 temporal
    docker compose logs --tail=200 postgres

## 18. First project to use after the smoke test

Do not start with a large production project.

Use this progression:

    PROJECT A
    tiny Python package
    → create + test

    PROJECT B
    existing Python project with one controlled bug
    → inspect + fix + test

    PROJECT C
    small API
    → plan + implement + test + repair

    PROJECT D
    small multi-component project
    → graph + dependencies + evaluation

Only then:

    PROJECT E
    real personal project

## 19. Evidence package for every real test

At the end of each real test save:

    .titan/logs/<test-log>
    .titan/workspaces/<project>/<task>/...
    test command
    git diff
    pytest result
    TITAN task/run identifiers
    evaluator result
    repair result when applicable

For a repository test also capture:

    git status
    git diff --stat
    git diff

## 20. Release gate

TITAN should not be considered release-ready until:

- deterministic CI is green;
- NVIDIA provider smoke test is green;
- real-project vertical slice is green;
- self-repair has been demonstrated;
- tool failures are handled;
- governance approval has been demonstrated;
- recovery has been demonstrated;
- explainability can reconstruct an execution;
- no critical security issue remains;
- real-project tests have been reviewed manually.

A single successful demo is not enough.

The release gate is based on repeatable evidence across multiple scenarios.

## 21. Current known boundary

The current NVIDIA integration proves a real provider path and the first engineering vertical slice.

It does not yet prove:

- the entire agent organization in TITAN_Agent.md;
- production GitHub automation;
- browser automation;
- public deployment;
- production credential management;
- full organizational multi-user operation;
- unrestricted autonomous software development.

Those remain later validation phases.

## 22. Next validation milestone

The immediate milestone is:

    REAL-PROJECT VALIDATION BATCH 1

with these first five scenarios:

    1. Create a tiny Python project.
    2. Modify an existing project.
    3. Repair a deliberately failing test.
    4. Recover from a tool failure.
    5. Execute a 3-task dependent project graph.

Only after these pass consistently should we move to production hardening and release-candidate work.

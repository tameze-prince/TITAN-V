# TITAN V. — AGENT MASTER SPECIFICATION

> **Status:** Living Document  
> **Version:** 0.1.0  
> **Document:** `TITAN_Agent.md`  
> **Purpose:** Single evolving source of truth for the conception, architecture, implementation, validation, evolution, and operation of TITAN V.  
> **Last updated:** 2026-09-20

---

# 0. DOCUMENT CONTRACT

This file is the **permanent working specification of TITAN V.**

It is not a presentation, a temporary prompt, or a static requirements document.

It must evolve continuously from:

**idea → architecture → implementation → validation → production → evolution**

Every major architectural decision, capability, workflow, constraint, lesson, experiment, and validated improvement must eventually be reflected here.

## 0.1 Source of truth

When a major implementation detail exists in code but is not documented here, the document is incomplete.

When this document and the code disagree:

1. determine which one represents the intended current behavior;
2. record the discrepancy;
3. validate the intended behavior;
4. update the appropriate source;
5. record the decision when it is significant.

## 0.2 No silent architectural changes

A significant architectural change must produce a documented decision.

Use:

```text
DEC-XXX
```

with:

- Context
- Problem
- Options considered
- Decision
- Reasons
- Consequences
- Evidence
- Approval status

## 0.3 No fake completeness

A feature is not considered complete because:

- an agent generated code;
- a prompt exists;
- a component compiles;
- a test was written but not executed;
- a deployment file exists;
- a demonstration works once.

Completion requires explicit acceptance criteria.

## 0.4 Design philosophy

TITAN must be:

- modular;
- observable;
- testable;
- auditable;
- secure by default;
- model-independent;
- tool-independent;
- extensible;
- capable of controlled autonomy;
- capable of human intervention;
- evidence-driven;
- innovation-oriented.

---

# 1. TITAN VISION

## 1.1 Core vision

**TITAN V. is an Intent-to-Reality Engine for digital products and digital work.**

A user should be able to express a goal in natural language and TITAN should progressively transform that intent into validated, usable, maintainable real-world output.

Example:

> “I have this idea. Turn it into a real product.”

TITAN should be able to:

```text
UNDERSTAND
   ↓
RESEARCH
   ↓
CHALLENGE
   ↓
INNOVATE
   ↓
PLAN
   ↓
DESIGN
   ↓
BUILD
   ↓
TEST
   ↓
SECURE
   ↓
DEPLOY
   ↓
OBSERVE
   ↓
IMPROVE
```

## 1.2 What TITAN is not

TITAN is not intended to be:

- a chatbot with many personalities;
- a collection of prompts;
- a static collection of agents;
- a workflow demo;
- a code generator;
- a single autonomous LLM;
- a system that blindly follows instructions;
- a system that executes everything without permission;
- an imitation of another agent framework.

## 1.3 Core proposition

The fundamental unit of TITAN is not the agent.

It is:

```text
INTENT + STATE + TASK GRAPH + AGENTS + TOOLS + EVIDENCE + EVALUATION + CONTROL
```

Agents are workers inside this system.

---

# 2. MISSION

TITAN exists to make complex digital creation accessible at the level of **intent** rather than implementation details.

The long-term mission is to allow a user to say:

> “Build this.”

and have TITAN determine:

- what the request means;
- what is unknown;
- what must be researched;
- what should be challenged;
- what can be automated;
- which capabilities are required;
- which agents should work;
- which tools may be used;
- what evidence is needed;
- how the work should be evaluated;
- where human approval is required;
- how the final system should be delivered;
- how it should be maintained afterward.

---

# 3. DESIGN PRINCIPLES

## P1 — Intent over literal prompt execution

TITAN should optimize for the user's real objective, not blindly execute the exact wording when that wording is ambiguous, incomplete, contradictory, or unsafe.

## P2 — Evidence over assumption

Important claims and decisions should be associated with:

- evidence;
- source;
- test;
- explicit constraint;
- or clearly marked assumption.

## P3 — Agents are specialists, not system owners

Agents execute responsibilities.

The persistent project state belongs to TITAN.

## P4 — Artifact over conversational memory

Important project knowledge must exist as structured artifacts.

## P5 — Least privilege

Agents receive only the permissions they need for a task.

## P6 — Reversible before irreversible

Prefer reversible actions where possible.

## P7 — Independent evaluation

The producer should not automatically be the final evaluator.

## P8 — Innovation is a first-class capability

Innovation is an actual subsystem, not a vague instruction in a prompt.

## P9 — Autonomy must be earned

Higher-risk autonomy should depend on demonstrated reliability, permissions, policies, and successful evaluations.

## P10 — Human authority

The user remains the authority for decisions designated as requiring approval.

## P11 — Observable execution

Every meaningful execution must be traceable.

## P12 — Failure is information

Failures should become:

- diagnosis;
- corrective action;
- evaluation;
- organizational learning.

---

# 4. SYSTEM MODEL

TITAN is organized into the following major layers:

```text
┌──────────────────────────────────────────────────────────┐
│                    USER EXPERIENCE                       │
│ Web / Desktop / CLI / Workspace / Future interfaces     │
└──────────────────────────┬───────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│                    TITAN GATEWAY                         │
│ Auth / Sessions / API / Streaming / Notifications       │
└──────────────────────────┬───────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│                       TITAN CORE                         │
│ Intent Compiler / Planner / Orchestrator / Risk /       │
│ Policies / Model Router / State Management              │
└───────────────┬──────────────────────┬───────────────────┘
                ↓                      ↓
      ┌──────────────────┐    ┌─────────────────────────┐
      │   AGENT LAYER   │    │      TOOL LAYER         │
      │ specialists      │    │ GitHub / browser /      │
      │ teams            │    │ terminal / filesystem / │
      │ evaluators       │    │ cloud / MCP / APIs      │
      └────────┬─────────┘    └────────────┬────────────┘
               └──────────────┬─────────────┘
                              ↓
┌──────────────────────────────────────────────────────────┐
│                  EXECUTION LAYER                         │
│ Workspaces / Sandboxes / Containers / CI / environments │
└──────────────────────────┬───────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│                KNOWLEDGE + STATE LAYER                   │
│ Memory / Artifacts / Evidence / Decisions / Events      │
└──────────────────────────────────────────────────────────┘
```

---

# 5. USER EXPERIENCE PRINCIPLE

TITAN must primarily operate at the **intent level**.

The user should not be forced to manually construct:

- agent chains;
- tool calls;
- task graphs;
- prompts;
- model selections;
- internal memory structures.

Advanced users may inspect and override these internals.

Default experience:

```text
USER:
“I want to create X.”

TITAN:
“Here is what I understand...
Here is what I do not know...
Here is what I propose to investigate...
Here is the execution plan...
Here are the actions requiring approval.”
```

---

# 6. INTENT COMPILER

## 6.1 Objective

Convert natural language intent into a structured internal representation.

## 6.2 Input

```json
{
  "raw_intent": "",
  "user_context": {},
  "project_context": {},
  "constraints": [],
  "desired_outcome": null
}
```

## 6.3 Output

```json
{
  "problem": "",
  "target_users": [],
  "desired_outcome": "",
  "constraints": [],
  "unknowns": [],
  "assumptions": [],
  "risks": [],
  "research_questions": [],
  "candidate_deliverables": [],
  "required_capabilities": []
}
```

## 6.4 Intent validation

The Intent Compiler must identify:

- ambiguity;
- missing constraints;
- contradictions;
- scope inflation;
- hidden dependencies;
- risky actions;
- unresolved assumptions.

---

# 7. INNOVATION ENGINE

## 7.1 Objective

Ensure TITAN does not automatically copy the most obvious existing solution.

## 7.2 Innovation pipeline

```text
PROBLEM
  ↓
EXISTING SOLUTIONS
  ↓
USER PAIN POINTS
  ↓
UNSOLVED PROBLEMS
  ↓
TECHNOLOGY SCAN
  ↓
ALTERNATIVE INTERACTIONS
  ↓
BUSINESS MODEL OPTIONS
  ↓
CONCEPT GENERATION
  ↓
FEASIBILITY
  ↓
PROTOTYPE
  ↓
USER VALUE
  ↓
INNOVATION REVIEW
```

## 7.3 Required innovation questions

For suitable projects, TITAN should investigate:

1. What already exists?
2. Why do users use existing solutions?
3. What frustrates them?
4. What remains unsolved?
5. Can a step be removed?
6. Can a step be automated?
7. Can the workflow be inverted?
8. Can an emerging technology be used differently?
9. Can two unrelated technologies be combined?
10. Can the experience be redesigned from first principles?

## 7.4 Innovation dimensions

Innovation evaluation may consider:

- novelty;
- user value;
- feasibility;
- differentiation;
- economic potential;
- technical risk;
- adoption friction;
- scalability;
- defensibility.

These are evaluation dimensions, not guarantees of success.

---

# 8. AGENT ORGANIZATION

TITAN uses a dynamic organization.

Agents are activated according to capabilities required by the task.

## 8.1 Executive Division

- ChiefOrchestrator
- ProjectManager
- ChiefQualityOfficer

## 8.2 Discovery Division

- MarketResearchAgent
- UserResearchAgent
- CompetitiveIntelligenceAgent
- TrendResearchAgent
- TechnologyResearchAgent
- UXResearchAgent

## 8.3 Product Division

- ProductManager
- BusinessStrategist
- ProductStrategist
- RequirementsEngineer
- ProductAnalyst

## 8.4 Design Division

- UXArchitect
- UXResearcher
- ProductDesigner
- DesignSystemAgent
- AccessibilityAgent
- ContentDesigner

## 8.5 Engineering Division

- SolutionArchitect
- FrontendEngineer
- BackendEngineer
- MobileEngineer
- AIEngineer
- DataEngineer
- DatabaseEngineer
- IntegrationEngineer

## 8.6 Quality Division

- QAEngineer
- TestEngineer
- PerformanceEngineer
- ReliabilityEngineer
- AccessibilityTester

## 8.7 Security Division

- SecurityArchitect
- ApplicationSecurityAgent
- ThreatModelAgent
- RedTeamAgent
- DependencySecurityAgent
- PrivacyAgent

## 8.8 Operations Division

- DevOpsAgent
- SREAgent
- CloudEngineer
- ObservabilityEngineer
- ReleaseManager

## 8.9 Creative Division

- CreativeDirector
- BrandStrategist
- Copywriter
- ContentStrategist
- VideoScriptWriter
- VideoDirector
- GraphicDesigner
- SEOAgent
- GrowthAgent

---

# 9. AGENT CONTRACT

Every production agent must declare a contract.

Example:

```yaml
agent:
  id: backend_engineer
  version: 1

  role: Backend Engineer

  objective:
    - implement backend requirements

  inputs:
    - PRD
    - architecture
    - API specification

  outputs:
    - source_code
    - tests
    - documentation

  capabilities:
    - backend_development
    - api_development
    - debugging

  tools:
    allowed:
      - filesystem
      - terminal
      - git

  permissions:
    read:
      - project_workspace

    write:
      - project_workspace

    execute:
      - test_commands

  forbidden:
    - production_database
    - production_deployment

  quality_requirements:
    - tests_required
    - lint_required
    - security_scan_required

  escalation:
    - architecture_conflict
    - security_issue
    - missing_requirement
```

---

# 10. CAPABILITY REGISTRY

The system must know what capabilities are available.

Example:

```text
CAPABILITY: create_rest_api

Possible agents:
- BackendEngineer
- SolutionArchitect
- SecurityAgent

Required tools:
- filesystem
- terminal
- git

Knowledge:
- REST
- authentication
- API security
```

The Orchestrator uses capabilities to select agents dynamically.

---

# 11. ORCHESTRATOR

## 11.1 Responsibilities

The ChiefOrchestrator is responsible for:

- interpreting the mission;
- constructing the task graph;
- selecting capabilities;
- selecting agents;
- sequencing and parallelizing work;
- managing dependencies;
- handling failures;
- invoking evaluators;
- handling escalations;
- requesting human approval;
- tracking project completion.

## 11.2 It must not

- fabricate evidence;
- bypass permissions;
- silently change project requirements;
- declare success without required evaluation;
- expose secrets unnecessarily;
- directly own all execution work.

---

# 12. TASK GRAPH ENGINE

Every non-trivial mission becomes a structured task graph.

Task structure:

```json
{
  "task_id": "TASK-001",
  "owner_agent": "product_manager",
  "objective": "",
  "inputs": [],
  "outputs": [],
  "dependencies": [],
  "tools": [],
  "acceptance_criteria": [],
  "quality_requirements": [],
  "deadline": null,
  "risk_level": "low"
}
```

## 12.1 Task states

```text
PENDING
RUNNING
BLOCKED
WAITING_APPROVAL
FAILED
REVIEW
COMPLETED
CANCELLED
```

## 12.2 Execution modes

### Sequential

Used when dependencies are strict.

### Parallel

Used when tasks are independent.

### Handoff

Used when one agent produces the required input for another.

### Review loop

Used when evaluation fails.

### Human approval

Used when policy or risk requires it.

---

# 13. THINK / ACT MODEL

TITAN separates reasoning from actions.

## 13.1 THINK

May include:

- research;
- analysis;
- planning;
- comparison;
- design;
- writing;
- simulation;
- recommendation.

## 13.2 ACT

May include:

- file creation;
- file modification;
- code execution;
- Git operations;
- repository operations;
- API calls;
- environment creation;
- deployment;
- publication;
- database changes.

ACT is governed by:

```text
PERMISSION
+
POLICY
+
RISK
+
APPROVAL
```

---

# 14. RISK ENGINE

Risk classes:

```text
R0 — Read-only
R1 — Reversible local change
R2 — Shared environment change
R3 — External side effect
R4 — Irreversible/high-impact action
```

Examples:

| Action | Risk |
|---|---:|
| Read README | R0 |
| Analyze local files | R0 |
| Create file | R1 |
| Local code modification | R1 |
| Commit | R1 |
| Push branch | R2 |
| Create pull request | R2 |
| Deploy staging | R2/R3 |
| Publish publicly | R3 |
| Modify production data | R4 |

Risk levels are configurable and environment-dependent.

---

# 15. PERMISSION ENGINE

Permissions must be explicit.

A permission can define:

```text
subject
action
resource
scope
environment
constraints
expiration
approval_requirement
```

Examples:

```text
agent = backend_engineer
action = write
resource = project_workspace
environment = sandbox
```

or:

```text
agent = release_manager
action = deploy
resource = application
environment = production
approval_required = true
```

---

# 16. HUMAN APPROVAL ENGINE

The system must avoid both extremes:

- asking for approval for every trivial operation;
- acting autonomously on high-impact operations.

An approval request should contain:

```text
ACTION
RISK
REASON
CHANGES
TEST RESULTS
SECURITY STATUS
ROLLBACK PLAN
SIDE EFFECTS
```

Approval states:

```text
PENDING
APPROVED
REJECTED
EXPIRED
CANCELLED
```

---

# 17. ARTIFACT SYSTEM

Artifacts are first-class objects.

Examples:

- Discovery Package
- Market Research
- User Research
- Innovation Report
- PRD
- Product Strategy
- User Stories
- UX Specification
- Design System
- Architecture
- API Specification
- Database Schema
- Source Code
- Test Report
- Security Report
- Deployment Plan
- Content Strategy
- Brand Guidelines
- Analytics Report

Each artifact should support:

```text
id
type
project
version
author
creator_agent
created_at
updated_at
status
content_location
parent_artifacts
derived_artifacts
approval
evaluation
```

---

# 18. ARTIFACT GRAPH

Artifacts are connected.

Example:

```text
Problem
  ↓
Research
  ↓
Requirement
  ↓
Feature
  ↓
User Story
  ↓
Design
  ↓
API
  ↓
Code
  ↓
Test
  ↓
Deployment
```

This permits traceability.

TITAN should eventually answer:

> Why does this code exist?

by tracing:

```text
Code
→ feature
→ requirement
→ user problem
→ research evidence
```

---

# 19. MEMORY ARCHITECTURE

TITAN should maintain separate logical memories:

1. User Memory
2. Project Memory
3. Organizational Memory
4. Technical Memory
5. Product Memory
6. Brand Memory
7. Decision Memory
8. Execution Memory

## 19.1 Decision Memory

Example:

```json
{
  "decision_id": "DEC-019",
  "decision": "Use PostgreSQL",
  "context": "",
  "alternatives": [],
  "reason": "",
  "evidence": [],
  "consequences": [],
  "approved_by": "",
  "created_at": ""
}
```

---

# 20. EVIDENCE LEDGER

Important research claims should support:

```text
CLAIM
SOURCE
SOURCE_TYPE
DATE
EXTRACT
CONFIDENCE
CONTRADICTIONS
USED_IN
```

Claims should be distinguishable as:

```text
FACT
HYPOTHESIS
INFERENCE
OPINION
UNKNOWN```

---

# 21. RESEARCH ENGINE

Research pipeline:

```text
SEARCH
  ↓
COLLECT
  ↓
DEDUPLICATE
  ↓
EXTRACT
  ↓
VERIFY
  ↓
CROSS-CHECK
  ↓
COMPARE
  ↓
SYNTHESIZE
  ↓
CITE
```

The Research Engine must preserve source provenance.

It must not reduce a research request to:

> Ask a language model for a market study.

---

# 22. TOOL / MCP ARCHITECTURE

Tools are registered capabilities.

Potential categories:

```text
GitHub
Browser
Filesystem
Terminal
Database
Cloud
Email
Calendar
Analytics
Image Generation
Video
MCP
Custom APIs
```

A tool definition includes:

```text
name
description
schema
permissions
risk_level
authentication
rate_limit
audit_policy
```

---

# 23. EXECUTION / SANDBOX ARCHITECTURE

Agents doing engineering work should operate inside isolated workspaces.

Target conceptual model:

```text
TITAN
  ↓
Workspace Manager
  ├── Sandbox
  ├── Container
  ├── Repository
  └── Test Environment
```

Production credentials and high-risk environments must never be the default execution context.

---

# 24. GITHUB INTEGRATION

Long-term expected workflow:

```text
Connect GitHub
  ↓
Inspect repository
  ↓
Understand architecture
  ↓
Create branch
  ↓
Implement
  ↓
Run tests
  ↓
Security scan
  ↓
Code review
  ↓
Commit
  ↓
Pull Request
  ↓
Review comments
  ↓
Fix
  ↓
Re-test
```

Capabilities must be permission-controlled.

---

# 25. MODEL ROUTER

TITAN must not hard-code one model as the permanent intelligence layer.

Routing should consider:

- task complexity;
- quality requirements;
- reasoning depth;
- latency;
- cost;
- context size;
- modality;
- risk;
- availability.

Conceptually:

```text
TASK
 ↓
CLASSIFY
 ↓
COMPLEXITY + RISK + REQUIREMENTS
 ↓
MODEL ROUTER
 ↓
MODEL
```

Model providers should be replaceable.

---

# 26. EVALUATION ENGINE

Every important output should have an evaluation strategy.

## Product

- completeness;
- consistency;
- user value;
- feasibility.

## Code

- correctness;
- tests;
- maintainability;
- security;
- performance;
- architecture.

## Research

- source quality;
- evidence coverage;
- recency;
- contradiction handling;
- citation accuracy.

## Creative

- brief compliance;
- brand consistency;
- audience relevance;
- originality;
- technical quality.

---

# 27. QUALITY GATE LOOP

Mandatory conceptual loop:

```text
PRODUCER
  ↓
DELIVERABLE
  ↓
EVALUATOR
  ↓
PASS ───────────────→ NEXT STEP

FAIL
  ↓
DIAGNOSIS
  ↓
CORRECTION
  ↓
RE-EVALUATION
```

A producer cannot self-declare success when an independent quality gate is required.

---

# 28. DISAGREEMENT ENGINE

Agent disagreement is expected.

When significant disagreement occurs:

```text
DISPUTE-XXX
```

should capture:

```text
Position A
Evidence A

Position B
Evidence B

Trade-offs
Unknowns
Required experiment
Decision method
Final decision
```

Resolution may come from:

- additional evidence;
- experiment;
- evaluation;
- designated decision owner;
- user approval.

---

# 29. OBSERVABILITY

Every significant run should capture:

```text
Run ID
Project ID
Agent
Agent version
Model
Prompt version
Tool calls
Inputs
Outputs
Latency
Token usage
Cost
Errors
Retries
Approvals
Artifacts
Evaluation
Final result
```

Observability should support:

- debugging;
- audits;
- cost analysis;
- evaluation;
- performance analysis;
- replay;
- failure investigation.

---

# 30. WORKFLOW PERSISTENCE

A TITAN workflow may run for seconds, hours, days, or longer.

Workflows must support:

```text
Pause
Resume
Recover
Retry
Checkpoint
Replay
Cancel
```

A workflow must not depend on an active chat session remaining open.

---

# 31. PROJECT STATE

TITAN must know the current state of a project.

Expected conceptual state:

```text
PROJECT
├── Objective
├── Status
├── Current Phase
├── Tasks
├── Agents
├── Artifacts
├── Decisions
├── Risks
├── Approvals
├── Tests
├── Deployments
├── Costs
└── Next Actions
```

---

# 32. PRODUCT FACTORY

Primary product lifecycle:

```text
IDEA
  ↓
DISCOVERY
  ↓
MARKET RESEARCH
  ↓
USER RESEARCH
  ↓
INNOVATION
  ↓
BUSINESS MODEL
  ↓
PRD
  ↓
UX
  ↓
UI
  ↓
ARCHITECTURE
  ↓
DEVELOPMENT
  ↓
TESTING
  ↓
SECURITY
  ↓
DEPLOYMENT
  ↓
ANALYTICS
  ↓
ITERATION
```

---

# 33. CREATIVE FACTORY

Creative workflow:

```text
BRAND STRATEGY
  ↓
CREATIVE STRATEGY
  ↓
CONTENT STRATEGY
  ↓
CONCEPT
  ↓
COPY
  ↓
VISUAL DIRECTION
  ↓
PRODUCTION
  ↓
REVIEW
  ↓
APPROVAL
  ↓
PUBLICATION
  ↓
PERFORMANCE ANALYSIS
  ↓
ITERATION
```

---

# 34. SECURITY ARCHITECTURE

Security is systemic.

All of the following must be treated as potentially untrusted:

- user input;
- downloaded files;
- web pages;
- external APIs;
- repository contents;
- tool outputs;
- other agents' outputs;
- generated code.

Security controls should eventually include:

- least privilege;
- secret isolation;
- sandboxing;
- tool allowlists;
- network policies;
- audit logs;
- rate limits;
- dependency scanning;
- prompt-injection defenses;
- output validation;
- environment isolation;
- approval requirements.

---

# 35. RED TEAM

Red Team should challenge:

- assumptions;
- architecture;
- security boundaries;
- input validation;
- agent permissions;
- prompt injection;
- data leakage;
- dependency risks;
- abuse cases;
- operational failure modes.

The Red Team should be structurally independent from the producer whenever practical.

---

# 36. DATA MODEL — INITIAL CONTROL PLANE

Initial relational entities:

```text
users
organizations
projects
project_members

agents
agent_versions
agent_capabilities

tasks
task_dependencies
task_runs

workflows
workflow_runs
workflow_steps
workflow_checkpoints

artifacts
artifact_versions
artifact_relationships

decisions
decision_options

approvals

tools
tool_permissions
tool_credentials

model_providers
models
model_runs

research_sources
research_claims
research_evidence

evaluations
evaluation_runs

security_findings

deployments
environments

audit_logs

usage_records
cost_records
```

The schema is provisional and will be validated during implementation.

---

# 37. API — INITIAL CONCEPT

```text
/api/v1

/auth
/users
/organizations

/projects
/projects/{id}/tasks
/projects/{id}/artifacts
/projects/{id}/decisions
/projects/{id}/runs

/agents
/agents/{id}/capabilities

/workflows
/workflows/{id}/runs

/tools
/tools/{id}/permissions

/research
/innovation

/evaluations
/security

/approvals

/models
/usage

/audit
```

The final API contract will be defined only after the first core design pass.

---

# 38. UI — TITAN COMMAND CENTER

Primary conceptual views:

```text
Projects
Agents
Tasks
Artifacts
Research
Innovation
Approvals
Deployments
Observability
Settings
```

A project view should expose:

- current objective;
- progress;
- current phase;
- active agents;
- blocked tasks;
- approval requests;
- risks;
- recent artifacts;
- tests;
- deployments;
- cost;
- next actions.

---

# 39. REPOSITORY STRUCTURE — PROPOSED

```text
titan/
│
├── apps/
│   ├── web/
│   ├── desktop/
│   └── api/
│
├── core/
│   ├── orchestration/
│   ├── planning/
│   ├── intent/
│   ├── innovation/
│   ├── policies/
│   ├── risk/
│   ├── approvals/
│   └── routing/
│
├── agents/
│   ├── executive/
│   ├── discovery/
│   ├── product/
│   ├── design/
│   ├── engineering/
│   ├── quality/
│   ├── security/
│   ├── operations/
│   ├── creative/
│   └── growth/
│
├── tools/
│   ├── github/
│   ├── browser/
│   ├── filesystem/
│   ├── terminal/
│   ├── cloud/
│   └── mcp/
│
├── execution/
│   ├── sandbox/
│   ├── workspace/
│   ├── containers/
│   └── runtime/
│
├── knowledge/
│   ├── memory/
│   ├── rag/
│   ├── artifacts/
│   └── evidence/
│
├── evaluation/
├── security/
├── infrastructure/
├── database/
├── tests/
└── docs/
```

This is a conceptual starting point, not yet the final repository layout.

---

# 40. DEVELOPMENT ROADMAP

## TITAN 0 — Core Kernel

Goal:

> Make the brain function.

Target components:

- Project
- Agent
- Task
- Workflow
- Artifact
- Event

---

## TITAN 0.5 — Agent Runtime

Add:

- sandbox;
- filesystem;
- terminal;
- Git;
- agent execution;
- retries;
- checkpoints;
- task dependencies;
- evaluation.

Success condition:

> TITAN can execute real work in a controlled environment.

---

## TITAN 1.0 — Product Factory

Add:

- Intent Compiler
- Research Engine
- Product management
- UX
- Architecture
- Coding agents
- QA
- Security
- GitHub
- Artifact Graph

Target:

> One idea → validated software product.

---

## TITAN 1.5 — Innovation Engine

Add:

- competitive intelligence;
- technology scanning;
- opportunity discovery;
- concept generation;
- feasibility analysis;
- prototypes;
- innovation evaluation.

Target:

> TITAN can challenge the obvious solution.

---

## TITAN 2.0 — Autonomous Digital Company

Add:

- continuous monitoring;
- scheduled workflows;
- maintenance;
- analytics;
- growth;
- content;
- controlled product iteration;
- issue detection;
- controlled deployment.

---

## TITAN 3.0 — Adaptive Organization

Long-term target:

```text
BUILD
  ↓
OBSERVE
  ↓
ANALYZE
  ↓
DISCOVER WEAKNESS
  ↓
GENERATE IMPROVEMENT
  ↓
TEST
  ↓
APPROVE / DEPLOY
  ↓
MEASURE
  ↓
LEARN
```

---

# 41. FIRST IMPLEMENTATION MILESTONE

The first official milestone is intentionally smaller than the ultimate vision.

> **TITAN receives an idea, creates a project, decomposes it into a task graph, assigns specialized agents, executes work inside a sandbox, produces artifacts, evaluates them, recovers from failures, and presents the result with a complete execution trace.**

This is the foundational vertical slice.

---

# 42. IMPLEMENTATION ORDER

## Sprint 1 — Core data model

Implement:

```text
Project
Agent
Task
Workflow
Artifact
Event
```

## Sprint 2 — Orchestrator

Implement:

```text
Intent
Task graph
Agent registry
Capability registry
Basic model routing
```

## Sprint 3 — Runtime

Implement:

```text
Tool registry
Filesystem
Terminal
Sandbox
Agent execution
```

## Sprint 4 — Git

Implement:

```text
Repository workspace
Git operations
GitHub integration
```

## Sprint 5 — Evaluation

Implement:

```text
Evaluator
Quality gates
Retry
Repair
Failure diagnosis
```

## Sprint 6 — Research

Implement:

```text
Research engine
Evidence ledger
Source provenance
```

## Sprint 7 — Innovation

Implement:

```text
Innovation engine
Concept generation
Feasibility analysis
Innovation evaluation
```

## Sprint 8 — Product Factory

Implement:

```text
Discovery
PRD
UX
Architecture
Engineering
QA
Security
```

---

# 43. ENGINEERING RULES

Every new TITAN feature must answer:

1. What problem does it solve?
2. What capability does it provide?
3. How do we know it works?
4. What happens when it fails?
5. What permissions does it require?
6. What data does it create?
7. What can it affect?
8. How is it observed?
9. How is it reversed?
10. How is it documented?

If these questions cannot be answered, the feature is not ready for production.

---

# 44. DEFINITION OF DONE

A feature is done only when:

```text
Requirements defined
AND
Implementation complete
AND
Unit tests pass
AND
Integration tests pass where required
AND
Failure paths considered
AND
Permissions defined
AND
Observability implemented
AND
Security reviewed where applicable
AND
Documentation updated
AND
Acceptance criteria satisfied
```

---

# 45. FAILURE HANDLING

When an agent fails:

```text
FAILURE
  ↓
CAPTURE ERROR
  ↓
CLASSIFY
  ↓
DIAGNOSE
  ↓
RETRY / REPLAN / ESCALATE
```

Failure categories should eventually include:

```text
tool_failure
model_failure
timeout
permission_denied
invalid_output
dependency_failure
logic_failure
quality_failure
security_failure
environment_failure
unknown_failure
```

Retries must be bounded.

Repeated failure should trigger escalation rather than endless loops.

---

# 46. COST CONTROL

TITAN must track:

- model usage;
- tool usage;
- execution time;
- infrastructure usage;
- task cost;
- workflow cost;
- project cost.

The Model Router should prefer the lowest-cost model that satisfies the task's quality and risk requirements.

---

# 47. ORGANIZATIONAL LEARNING
TITAN should preserve validated lessons.

Example:

```text
LESSON-042

Context:
Backend generation repeatedly failed because the repository
used a legacy framework version.

Observation:
Modern generated dependencies caused incompatibility.

Validated solution:
Inspect project dependency versions before generating changes.

Action:
Add repository compatibility scan before implementation.

Status:
Validated

Applies to:
Engineering workflows
```

A lesson must not become a global rule merely because an agent said so.

---

# 48. VERSIONING

Major changes should be versioned:

```text
0.x = experimental architecture
1.x = stable product foundation
2.x = expanded autonomy
3.x = adaptive organization
```

Agents should also be versioned independently.

Example:

```text
backend_engineer@1.2
```

Changes to agent behavior should be traceable.

---

# 49. DECISION REGISTER

This section will become the permanent architectural decision index.

Current decisions:

```text
DEC-001
TITAN is designed as a software system, not as a single prompt.

DEC-002
Agents are dynamic specialists selected by required capabilities.

DEC-003
Artifacts are first-class persistent objects.

DEC-004
Execution is separated into THINK and ACT.

DEC-005
Risk and permissions govern ACT operations.

DEC-006
Innovation is a first-class subsystem.

DEC-007
Independent evaluation is required for important deliverables.

DEC-008
The first implementation target is the TITAN core + execution vertical slice.
```

---

# 50. OPEN QUESTIONS

These must be resolved through engineering decisions rather than assumptions:

```text
Q-001
Primary backend/runtime technology?

Q-002
Primary frontend technology?

Q-003
Initial model providers?

Q-004
Workflow engine implementation strategy?

Q-005
Sandbox implementation?

Q-006
Container/runtime strategy?

Q-007
Vector/RAG storage strategy?

Q-008
Event bus technology?

Q-009
Initial deployment target?

Q-010
Credential management strategy?

Q-011
Exact GitHub permission model?

Q-012
Initial authentication model?

Q-013
Single-user-first or organization-first product architecture?

Q-014
How much of TITAN should initially run locally vs remotely?

Q-015
What should be included in the first public MVP?
```

---

# 51. RESEARCH BASELINE

The initial architecture was informed by examination of existing agent/software engineering systems.

Relevant projects to study continuously:

- MetaGPT
  - https://github.com/FoundationAgents/MetaGPT

- OpenHands Software Agent SDK
  - https://github.com/OpenHands/software-agent-sdk

- Microsoft Agent Framework
  - https://github.com/microsoft/agent-framework

- OpenAI Agents SDK
  - https://github.com/openai/openai-agents-python

- CrewAI
  - https://github.com/crewAIInc/crewAI

- AutoGPT
  - https://github.com/Significant-Gravitas/AutoGPT

- SWE-agent
  - https://github.com/SWE-agent/SWE-agent

Important rule:

> TITAN may learn from these systems, but must not become a superficial combination of them.

Research should focus on:

- what they solve;
- what architecture they use;
- what is genuinely reusable;
- what limitations they expose;
- what TITAN should do differently.

---

# 52. CONTINUOUS RESEARCH RULE

Before adopting an architecture or framework, TITAN project research should verify:

```text
Official documentation
Current repository status
Maintenance activity
License
Known limitations
Security implications
Integration cost
Operational maturity
```

For current technology decisions, prefer primary sources.

---

# 53. CURRENT STATE

## Completed

```text
[x] Vision
[x] Mission
[x] Core principles
[x] High-level architecture
[x] Innovation Engine concept
[x] Agent organization
[x] Agent contracts
[x] Capability registry concept
[x] Orchestration model
[x] Task graph concept
[x] THINK / ACT separation
[x] Risk model
[x] Permission model
[x] Human approval model
[x] Artifact system
[x] Artifact graph
[x] Memory architecture
[x] Evidence ledger
[x] Research engine concept
[x] Tool/MCP concept
[x] Sandbox concept
[x] GitHub workflow
[x] Evaluation system concept
[x] Quality gates
[x] Disagreement engine
[x] Observability
[x] Workflow persistence
[x] Project state
[x] Product factory
[x] Creative factory
[x] Initial control-plane data model
[x] Initial API concept
[x] UI concept
[x] Repository concept
[x] Roadmap
[x] First implementation milestone
```

## Not yet implemented

```text
[ ] Final technology stack
[ ] Production database schema
[ ] API contracts
[ ] Event contracts
[ ] Agent runtime
[ ] Sandbox runtime
[ ] Tool registry
[ ] Model router implementation
[ ] Project state engine
[ ] Artifact storage
[ ] Memory implementation
[ ] Evidence storage
[ ] GitHub integration
[ ] Evaluation engine
[ ] Innovation Engine implementation
[ ] Command Center UI
[ ] Authentication
[ ] Credential management
[ ] Deployment infrastructure
[ ] Production observability
```

---

# 54. NEXT BUILD PHASE

The immediate next phase is:

# TITAN CORE SPECIFICATION

We will define, in implementation-ready form:

```text
Agent
Task
Workflow
Artifact
Event
Tool
Capability
Memory
Evidence
Decision
Approval
Evaluation
Permission
Risk
Project
```

For every object we will define:

- identifier;
- fields;
- lifecycle;
- invariants;
- relationships;
- API representation;
- events;
- permissions;
- persistence;
- validation;
- error states;
- test strategy.

---

# 55. WORK METHOD FROM NOW ON

For every future TITAN development step:

```text
1. Update this specification
2. Create or modify implementation
3. Run validation
4. Record evidence
5. Record decisions
6. Update status
7. Identify remaining risks
8. Define next step
```

The document therefore becomes the bridge between:

```text
VISION
    ↓
SPECIFICATION
    ↓
ARCHITECTURE
    ↓
CODE
    ↓
TESTS
    ↓
PRODUCTION
    ↓
EVOLUTION
```

---

# 56. NORTH STAR

The final north-star behavior remains:

> A user gives TITAN an idea.
>
> TITAN understands it.
>
> TITAN researches it.
>
> TITAN challenges it.
>
> TITAN finds opportunities to improve it.
>
> TITAN creates a plan.
>
> TITAN assembles the right specialists.
>
> TITAN executes inside controlled environments.
>
> TITAN evaluates its own work.
>
> TITAN fixes failures.
>
> TITAN asks the user only when necessary.
>
> TITAN delivers a real result.
>
> TITAN observes what happens afterward.
>
> TITAN learns from validated outcomes.
>
> TITAN improves the product and its own workflows over time.

---

# 57. DOCUMENT EVOLUTION LOG

## v0.1.0 — 2026-09-20

Initial master specification created.

Established:

- TITAN vision and mission;
- core principles;
- system architecture;
- Intent Compiler;
- Innovation Engine;
- agent organization;
- agent contracts;
- capability registry;
- orchestration;
- task graph;
- THINK / ACT model;
- risk and permission systems;
- approval system;
- artifact system;
- memory architecture;
- evidence ledger;
- research engine;
- tool/MCP architecture;
- sandbox strategy;
- GitHub lifecycle;
- model routing;
- evaluation system;
- quality gates;
- disagreement handling;
- observability;
- workflow persistence;
- product and creative factories;
- data model;
- API concept;
- UI concept;
- repository concept;
- roadmap;
- first implementation milestone.

---

# 58. CHANGELOG FORMAT

Future changes should follow:

```markdown
## vX.Y.Z — YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Removed
- ...

### Fixed
- ...

### Decisions
- DEC-XXX

### Evidence
- ...

### Impact
- ...

### Migration
- ...
```

---

# END OF CURRENT MASTER SPECIFICATION

**TITAN V. is now treated as a living engineering system.**

Next canonical document section to expand:

> **TITAN CORE SPECIFICATION**
>
> with implementation-ready schemas, contracts, lifecycle rules, events, APIs, persistence, permissions, and tests.


---

# 59. TITAN CORE SPECIFICATION — IMPLEMENTATION CONTRACT

> **Status:** Design-ready, implementation pending  
> **Version:** Core Spec 0.1.0  
> **Scope:** Core domain objects, lifecycle rules, events, APIs, persistence, permissions, validation, errors, and tests.

This section converts the previous architectural concepts into implementation-oriented contracts.

The core must remain as technology-independent as possible. A concrete framework may implement these contracts, but the contracts define the intended behavior.

---

# 60. CORE DOMAIN OBJECTS

The first implementation must treat the following as first-class entities:

```text
Project
Agent
Capability
Task
Workflow
Artifact
Tool
Permission
Risk
Decision
Approval
Evaluation
Evidence
Memory
Event
Run
Environment
Deployment
```

The most important dependency chain is:

```text
Project
  ├── Workflow
  │     ├── Task
  │     │     ├── Run
  │     │     └── Artifact
  │     └── Checkpoint
  │
  ├── Agent
  ├── Decision
  ├── Approval
  ├── Evaluation
  ├── Evidence
  └── Event
```

---

# 61. UNIVERSAL ENTITY RULES

Every persistent entity should have, where applicable:

```text
id
created_at
updated_at
created_by
updated_by
version
status
metadata
```

Identifiers should be globally unique.

Recommended format:

```text
project_xxxxx
agent_xxxxx
task_xxxxx
artifact_xxxxx
run_xxxxx
decision_xxxxx
approval_xxxxx
event_xxxxx
```

The exact ID implementation may use UUID/ULID or another collision-resistant scheme.

---

# 62. PROJECT

## 62.1 Purpose

A Project is the primary container for user objectives, execution state, artifacts, decisions, agents, and workflows.

## 62.2 Core schema

```json
{
  "id": "project_01",
  "name": "Example Product",
  "description": "",
  "objective": "",
  "owner_id": "user_01",
  "organization_id": "org_01",
  "status": "ACTIVE",
  "current_phase": "DISCOVERY",
  "autonomy_level": 2,
  "risk_policy_id": "policy_01",
  "created_at": "",
  "updated_at": "",
  "metadata": {}
}
```

## 62.3 Project lifecycle

```text
DRAFT
  ↓
ACTIVE
  ↓
PAUSED
  ↓
ACTIVE
  ↓
COMPLETED
```

Alternative terminal states:

```text
CANCELLED
ARCHIVED
FAILED
```

## 62.4 Project invariants

A project:

- must have an owner;
- must have an objective before production workflows begin;
- cannot be deleted when immutable audit requirements apply;
- must preserve execution history;
- must have a defined policy for autonomous actions.

---

# 63. AGENT

## 63.1 Purpose

An Agent is a specialized runtime identity with:

- role;
- capabilities;
- instructions;
- model policy;
- tool permissions;
- quality requirements;
- escalation behavior.

## 63.2 Schema

```json
{
  "id": "agent_backend_engineer",
  "name": "Backend Engineer",
  "type": "SPECIALIST",
  "version": "1.0.0",
  "description": "",
  "status": "ACTIVE",
  "capabilities": [
    "backend_development",
    "api_development"
  ],
  "allowed_tools": [
    "filesystem",
    "terminal",
    "git"
  ],
  "policy_id": "policy_backend_01",
  "model_policy_id": "model_policy_engineering",
  "contract_artifact_id": "artifact_agent_contract_01",
  "metadata": {}
}
```

## 63.3 Agent types

```text
SPECIALIST
ORCHESTRATOR
EVALUATOR
REVIEWER
RESEARCHER
EXECUTOR
OBSERVER
```

An agent may have multiple operational modes while retaining one primary identity.

---

# 64. CAPABILITY

## 64.1 Purpose

Capability is a normalized description of what the system knows how to perform.

## 64.2 Schema

```json
{
  "id": "capability_create_rest_api",
  "name": "Create REST API",
  "description": "",
  "risk_default": "R1",
  "required_tools": [
    "filesystem",
    "terminal"
  ],
  "required_knowledge": [
    "http",
    "rest",
    "authentication"
  ],
  "eligible_agent_types": [
    "SPECIALIST"
  ]
}
```

## 64.3 Capability matching

The Orchestrator should match:

```text
Task requirements
        +
Risk constraints
        +
Tool requirements
        +
Agent availability
        +
Quality requirements
        ↓
Eligible Agents
```

---

# 65. TASK

## 65.1 Purpose

A Task is the smallest meaningful unit of orchestrated work that can be owned, executed, evaluated, retried, or escalated.

## 65.2 Schema

```json
{
  "id": "task_01",
  "project_id": "project_01",
  "workflow_id": "workflow_01",
  "parent_task_id": null,
  "title": "Define authentication requirements",
  "objective": "",
  "status": "PENDING",
  "owner_agent_id": "agent_product_manager",
  "capability_ids": [
    "capability_requirements_analysis"
  ],
  "input_artifact_ids": [],
  "output_artifact_ids": [],
  "dependency_task_ids": [],
  "acceptance_criteria": [],
  "quality_requirements": [],
  "risk_level": "R1",
  "approval_requirement": "NONE",
  "retry_policy_id": "retry_default",
  "deadline": null,
  "metadata": {}
}
```

## 65.3 Task lifecycle

```text
PENDING
  ↓
READY
  ↓
RUNNING
  ↓
REVIEW
  ├── PASS → COMPLETED
  └── FAIL → REPAIR
                 ↓
              RUNNING
```

Other transitions:

```text
BLOCKED
WAITING_APPROVAL
CANCELLED
FAILED
```

## 65.4 Task invariants

A task cannot enter RUNNING when:

- dependencies are incomplete;
- required permissions are missing;
- required approval is pending;
- required input artifacts are unavailable;
- execution environment is unavailable.

---

# 66. WORKFLOW

## 66.1 Purpose

A Workflow represents a long-running execution plan.

## 66.2 Schema

```json
{
  "id": "workflow_01",
  "project_id": "project_01",
  "name": "Build MVP",
  "workflow_type": "PRODUCT_FACTORY",
  "status": "RUNNING",
  "version": 1,
  "task_ids": [],
  "policy_id": "policy_01",
  "started_at": "",
  "paused_at": null,
  "completed_at": null,
  "metadata": {}
}
```

## 66.3 Workflow lifecycle

```text
CREATED
  ↓
READY
  ↓
RUNNING
  ↓
PAUSED ↔ RUNNING
  ↓
COMPLETED
```

Alternative terminal states:

```text
FAILED
CANCELLED
EXPIRED
```

---

# 67. RUN

## 67.1 Purpose

A Run records an actual execution instance.

An agent can have multiple runs.

A task can have multiple runs.

A workflow can contain many runs.

## 67.2 Schema

```json
{
  "id": "run_01",
  "project_id": "project_01",
  "workflow_id": "workflow_01",
  "task_id": "task_01",
  "agent_id": "agent_backend_engineer",
  "model_id": "model_01",
  "status": "RUNNING",
  "attempt": 1,
  "input_refs": [],
  "output_refs": [],
  "tool_call_count": 0,
  "started_at": "",
  "completed_at": null,
  "error_code": null,
  "error_message": null,
  "metrics": {}
}
```

## 67.3 Run states

```text
CREATED
QUEUED
RUNNING
WAITING_TOOL
WAITING_APPROVAL
EVALUATING
SUCCEEDED
FAILED
CANCELLED
TIMED_OUT
```

---

# 68. ARTIFACT

## 68.1 Purpose

Artifact is any persistent output that matters to the project.

## 68.2 Schema

```json
{
  "id": "artifact_01",
  "project_id": "project_01",
  "type": "PRD",
  "title": "Product Requirements Document",
  "version": 3,
  "status": "DRAFT",
  "creator_type": "AGENT",
  "creator_id": "agent_product_manager",
  "content_ref": "storage://...",
  "mime_type": "text/markdown",
  "checksum": "",
  "parent_artifact_ids": [],
  "derived_artifact_ids": [],
  "approval_id": null,
  "evaluation_ids": [],
  "metadata": {}
}
```

## 68.3 Artifact status

```text
DRAFT
IN_REVIEW
APPROVED
REJECTED
SUPERSEDED
ARCHIVED
```

## 68.4 Artifact immutability

Approved artifact versions should be immutable.

Updates create new versions.

---

# 69. EVENT

## 69.1 Purpose

Events form the internal nervous system of TITAN.

Examples:

```text
ProjectCreated
TaskCreated
TaskStarted
TaskBlocked
TaskCompleted
TaskFailed
RunStarted
ToolCalled
ArtifactCreated
ArtifactEvaluated
ApprovalRequested
ApprovalGranted
ApprovalRejected
SecurityFindingCreated
DeploymentStarted
DeploymentCompleted
```

## 69.2 Event schema

```json
{
  "id": "event_01",
  "type": "TaskCompleted",
  "occurred_at": "",
  "actor_type": "AGENT",
  "actor_id": "agent_01",
  "project_id": "project_01",
  "aggregate_type": "TASK",
  "aggregate_id": "task_01",
  "payload": {},
  "correlation_id": "workflow_01",
  "causation_id": "event_previous",
  "schema_version": 1
}
```

## 69.3 Event principles
Events should be:

- append-only;
- timestamped;
- versioned;
- traceable;
- correlated;
- safe to replay where practical.

---

# 70. TOOL

## 70.1 Purpose

A Tool exposes an external action or capability to an agent.

## 70.2 Schema

```json
{
  "id": "tool_github",
  "name": "GitHub",
  "type": "MCP",
  "version": "1.0.0",
  "description": "",
  "risk_default": "R2",
  "operations": [],
  "authentication_method": "OAUTH",
  "status": "ACTIVE",
  "metadata": {}
}
```

Each operation must independently define:

```text
operation_id
input_schema
output_schema
risk_level
required_permission
side_effects
rollback_strategy
```

---

# 71. PERMISSION

## 71.1 Schema

```json
{
  "id": "permission_01",
  "subject_type": "AGENT",
  "subject_id": "agent_backend_engineer",
  "action": "WRITE",
  "resource_type": "WORKSPACE",
  "resource_scope": "project_01/sandbox",
  "environment": "SANDBOX",
  "expires_at": null,
  "approval_required": false
}
```

## 71.2 Permission decision

A permission check must produce an explicit result:

```text
ALLOW
DENY
REQUIRES_APPROVAL
```

---

# 72. RISK

Risk is evaluated at the operation level.

Schema:

```json
{
  "id": "risk_01",
  "level": "R3",
  "operation": "PUBLIC_PUBLISH",
  "impact": "EXTERNAL",
  "reversibility": "PARTIAL",
  "data_sensitivity": "LOW",
  "blast_radius": "MEDIUM",
  "approval_required": true
}
```

Risk should be dynamically adjusted where context increases or decreases impact.

---

# 73. APPROVAL

## 73.1 Schema

```json
{
  "id": "approval_01",
  "project_id": "project_01",
  "requested_by": "agent_release_manager",
  "action": "DEPLOY_PRODUCTION",
  "risk_level": "R4",
  "summary": "",
  "evidence_refs": [],
  "test_refs": [],
  "rollback_plan": "",
  "status": "PENDING",
  "expires_at": null,
  "resolved_by": null,
  "resolved_at": null
}
```

## 73.2 Approval rule

Approval must bind to a specific action and execution context.

An approval should not silently authorize unrelated future actions.

---

# 74. DECISION

Decision records preserve important architectural and product choices.

Schema:

```json
{
  "id": "decision_01",
  "project_id": "project_01",
  "title": "",
  "context": "",
  "problem": "",
  "options": [],
  "selected_option": "",
  "reasons": [],
  "evidence_refs": [],
  "consequences": [],
  "status": "APPROVED",
  "approved_by": "user_01"
}
```

---

# 75. EVALUATION

An Evaluation measures an artifact, task, run, or workflow against explicit criteria.

Schema:

```json
{
  "id": "evaluation_01",
  "target_type": "ARTIFACT",
  "target_id": "artifact_01",
  "evaluator_id": "agent_quality_officer",
  "criteria": [],
  "score": null,
  "status": "PASS",
  "findings": [],
  "evidence_refs": [],
  "created_at": ""
}
```

Evaluation must support:

```text
PASS
FAIL
PASS_WITH_WARNINGS
INCONCLUSIVE
```

---

# 76. EVIDENCE

Schema:

```json
{
  "id": "evidence_01",
  "type": "WEB_SOURCE",
  "source_uri": "",
  "title": "",
  "publisher": "",
  "published_at": null,
  "accessed_at": "",
  "claim_ids": [],
  "content_hash": "",
  "reliability_metadata": {}
}
```

Evidence must never be silently altered after being used for a significant decision.

---

# 77. MEMORY

Memory should not be one undifferentiated store.

Logical memory classes:

```text
USER
PROJECT
ORGANIZATIONAL
TECHNICAL
PRODUCT
BRAND
DECISION
EXECUTION
```

Memory records should include:

```text
namespace
key
content
source
confidence
scope
created_at
expires_at
```

Not every generated statement deserves durable memory.

---

# 78. ENVIRONMENT

Environments separate execution contexts.

Initial categories:

```text
LOCAL
SANDBOX
DEVELOPMENT
TEST
STAGING
PRODUCTION
```

Environment schema:

```json
{
  "id": "env_01",
  "project_id": "project_01",
  "name": "staging",
  "type": "STAGING",
  "risk_level": "R2",
  "credential_scope": "staging-only",
  "network_policy_id": "network_policy_01"
}
```

---

# 79. DEPLOYMENT

Deployment records every release action.

Schema:

```json
{
  "id": "deployment_01",
  "project_id": "project_01",
  "environment_id": "env_01",
  "artifact_version": "v1.4.0",
  "status": "COMPLETED",
  "started_at": "",
  "completed_at": "",
  "rollback_available": true,
  "approval_id": "approval_01"
}
```

---

# 80. DOMAIN RELATIONSHIPS

Core relationships:

```text
Organization
  └── Project
       ├── Workflows
       │    └── Tasks
       │         └── Runs
       │
       ├── Artifacts
       │    └── Artifact Versions
       │
       ├── Decisions
       ├── Approvals
       ├── Evaluations
       ├── Evidence
       └── Deployments

Agent
  ├── Capabilities
  ├── Tools
  └── Permissions
```

---

# 81. COMMAND MODEL

Mutating actions should conceptually use commands.

Examples:

```text
CreateProject
CreateTask
StartWorkflow
PauseWorkflow
AssignTask
ExecuteTask
CreateArtifact
RequestApproval
ApproveAction
RejectAction
RegisterTool
GrantPermission
RevokePermission
CreateDecision
TriggerEvaluation
DeployArtifact
RollbackDeployment
```

Commands should be validated before execution.

---

# 82. QUERY MODEL

Read operations should be separable from mutations.

Examples:

```text
GetProject
GetProjectState
ListTasks
GetTaskGraph
GetArtifact
GetArtifactHistory
GetRunTrace
ListApprovals
GetDecision
SearchEvidence
GetAgentCapabilities
GetAuditTrail
```

---

# 83. EVENT CONTRACTS

Initial event catalog:

```text
ProjectCreated
ProjectUpdated
ProjectArchived

WorkflowCreated
WorkflowStarted
WorkflowPaused
WorkflowResumed
WorkflowCompleted
WorkflowFailed
WorkflowCancelled

TaskCreated
TaskReady
TaskAssigned
TaskStarted
TaskBlocked
TaskWaitingApproval
TaskCompleted
TaskFailed
TaskCancelled
TaskRetryScheduled

RunCreated
RunStarted
RunWaitingTool
RunWaitingApproval
RunEvaluating
RunSucceeded
RunFailed
RunTimedOut
RunCancelled

ArtifactCreated
ArtifactVersionCreated
ArtifactSubmittedForReview
ArtifactApproved
ArtifactRejected
ArtifactSuperseded

ApprovalRequested
ApprovalGranted
ApprovalRejected
ApprovalExpired
ApprovalCancelled

DecisionCreated
DecisionUpdated
DecisionApproved
DecisionSuperseded

ToolRegistered
ToolInvoked
ToolFailed

EvaluationStarted
EvaluationPassed
EvaluationFailed
EvaluationInconclusive

SecurityFindingCreated
SecurityFindingResolved

DeploymentRequested
DeploymentStarted
DeploymentCompleted
DeploymentFailed
DeploymentRolledBack
```

---

# 84. EVENTING RULES

1. Events represent facts that occurred.
2. Commands represent requested actions.
3. Events should not be written speculatively.
4. Consumers should be idempotent.
5. Event schemas must be versioned.
6. Sensitive payloads should be minimized.
7. Event retention should follow audit and privacy requirements.

---

# 85. CORE API CONTRACT

Base path:

```text
/api/v1
```

## Projects

```http
POST   /projects
GET    /projects/{projectId}
PATCH  /projects/{projectId}
DELETE /projects/{projectId}
GET    /projects/{projectId}/state
```

## Tasks

```http
POST   /projects/{projectId}/tasks
GET    /projects/{projectId}/tasks
GET    /tasks/{taskId}
PATCH  /tasks/{taskId}
POST   /tasks/{taskId}/execute
POST   /tasks/{taskId}/cancel
POST   /tasks/{taskId}/retry
```

## Workflows

```http
POST   /projects/{projectId}/workflows
GET    /workflows/{workflowId}
POST   /workflows/{workflowId}/start
POST   /workflows/{workflowId}/pause
POST   /workflows/{workflowId}/resume
POST   /workflows/{workflowId}/cancel
```

## Agents

```http
GET    /agents
GET    /agents/{agentId}
GET    /agents/{agentId}/capabilities
```

## Artifacts

```http
GET    /projects/{projectId}/artifacts
POST   /projects/{projectId}/artifacts
GET    /artifacts/{artifactId}
GET    /artifacts/{artifactId}/versions
```

## Approvals

```http
GET    /projects/{projectId}/approvals
GET    /approvals/{approvalId}
POST   /approvals/{approvalId}/approve
POST   /approvals/{approvalId}/reject
```

## Runs

```http
GET    /runs/{runId}
GET    /runs/{runId}/events
GET    /runs/{runId}/trace
```

---

# 86. STREAMING

Long-running operations should support a streaming channel.

Conceptual endpoint:

```text
GET /runs/{runId}/stream
```

Events may include:

```text
status_change
agent_started
agent_message
tool_started
tool_completed
artifact_created
evaluation_started
approval_requested
error
completed
```

Streaming should not replace durable event storage.

---

# 87. IDEMPOTENCY

Mutating public APIs must support idempotency where duplicate requests could create duplicate side effects.

Example:

```http
Idempotency-Key: 01J...
```

Applicable operations include:

- deployment;
- workflow start;
- publication;
- external API actions;
- artifact creation where duplicate creation is harmful.

---

# 88. ERROR MODEL

All API errors should expose a consistent structure.

Example:

```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "Agent is not permitted to access production.",
    "request_id": "req_01",
    "details": {
      "agent_id": "agent_01",
      "resource": "production"
    }
  }
}
```

---

# 89. INITIAL ERROR CATALOG

```text
INVALID_INPUT
VALIDATION_FAILED
NOT_FOUND
CONFLICT
PERMISSION_DENIED
APPROVAL_REQUIRED
POLICY_BLOCKED
RESOURCE_UNAVAILABLE
TOOL_UNAVAILABLE
TOOL_FAILED
MODEL_UNAVAILABLE
MODEL_TIMEOUT
RATE_LIMITED
WORKFLOW_BLOCKED
TASK_DEPENDENCY_BLOCKED
EVALUATION_FAILED
SECURITY_BLOCKED
ENVIRONMENT_UNAVAILABLE
DEPLOYMENT_FAILED
UNKNOWN_ERROR
```

---

# 90. RETRY POLICY

Retries must not be universal.

Retryable examples:

```text
temporary network failure
temporary model timeout
temporary tool availability
transient infrastructure failure
```

Usually non-retryable:

```text
permission denied
invalid input
security policy violation
deterministic compilation failure
missing required artifact
```

Every retry must increment an attempt counter.

Maximum retries should be configurable.

---

# 91. REPAIR STRATEGY

When a task fails:

```text
Failure
  ↓
Classify
  ↓
Determine whether retry is useful
  ↓
If useful:
    Retry
  Else:
    Diagnose
      ↓
    Replan
      ↓
    Repair
      ↓
    Re-evaluate
```

Repeated deterministic failure should not cause an infinite loop.

---

# 92. STATE MACHINE RULE

State transitions should be explicit.

Invalid transitions must be rejected.

Example:

```text
COMPLETED → RUNNING
```

is invalid unless a specific operation creates a new execution attempt.

---

# 93. AUDIT LOG

Audit logs are distinct from operational events.

Audit records should capture security-sensitive or governance-relevant actions:

```text
credential access
permission changes
approval decisions
production actions
policy changes
agent configuration changes
deployment actions
public publication
```

Audit records should be tamper-resistant.

---

# 94. CREDENTIALS

Credentials must not be stored in agent prompts.

Agents should receive scoped references or ephemeral credentials.

Preferred model:

```text
Agent
  ↓
Credential Broker
  ↓
Scoped Credential
  ↓
Tool
```

The agent should not receive unnecessary secrets.

---

# 95. SECRET REDACTION

Logs, traces, artifacts, and model context must support secret redaction.

Potential sensitive patterns:

```text
API keys
tokens
passwords
private keys
session cookies
database credentials
OAuth secrets
```

Redaction must occur before durable logging when practical.

---

# 96. TOOL EXECUTION CONTRACT

Before a tool call:

```text
1. Validate input
2. Identify resource
3. Determine risk
4. Check permission
5. Check approval if needed
6. Execute
7. Validate output
8. Record event
9. Store result reference
```

---

# 97. AGENT OUTPUT VALIDATION

Structured agent outputs should be schema-validated.

If an agent is required to produce:

```json
{
  "tasks": []
}
```

then malformed output is a runtime failure, not accepted text.

Potential strategies:

- JSON Schema;
- typed models;
- structured output APIs;
- post-validation;
- repair pass.

---

# 98. PROMPT / POLICY VERSIONING

Agent behavior depends on more than model identity.

Trace:

```text
agent_version
prompt_version
policy_version
tool_versions
model_version
workflow_version
```

A run should allow reconstruction of the relevant runtime configuration.

---

# 99. MODEL ROUTING CONTRACT

Model selection input:

```json
{
  "task_type": "ARCHITECTURE_REVIEW",
  "complexity": "HIGH",
  "risk": "R3",
  "latency_budget_ms": 30000,
  "cost_budget": 2.0,
  "context_tokens": 50000,
  "modalities": ["TEXT"]
}
```

Model router output:

```json
{
  "provider": "",
  "model": "",
  "reason": "",
  "fallback_chain": []
}
```

---

# 100. COST ACCOUNTING

Every model or paid tool execution should create a usage record.

Schema:

```json
{
  "id": "usage_01",
  "project_id": "project_01",
  "run_id": "run_01",
  "provider": "provider",
  "model": "model",
  "input_units": 0,
  "output_units": 0,
  "duration_ms": 0,
  "estimated_cost": 0,
  "currency": "USD"
}
```

---

# 101. EVALUATION CONTRACT

An evaluator must receive:

```text
target
criteria
context
evidence
constraints
```

and produce:

```text
result
findings
evidence
blocking_issues
warnings
```

An evaluator should not modify the target directly unless explicitly authorized as a repair agent.

---

# 102. QUALITY GATE CONTRACT

Example:

```json
{
  "gate_id": "gate_backend_ready",
  "target_type": "TASK",
  "required_evaluations": [
    "unit_tests",
    "integration_tests",
    "security_scan",
    "code_review"
  ],
  "blocking_rules": [
    "critical_security_issue",
    "failing_required_test"
  ]
}
```

---

# 103. SECURITY GATE

Any artifact classified as production-bound should be evaluated against applicable security checks.

Potential checks:

```text
dependency vulnerabilities
secret scanning
input validation
authentication
authorization
data exposure
unsafe configuration
known insecure patterns
```

Not every project requires every check; applicability must be explicit.

---

# 104. RESEARCH CONTRACT

Research task output:

```json
{
  "question": "",
  "sources": [],
  "claims": [],
  "contradictions": [],
  "unknowns": [],
  "conclusion": "",
  "confidence": ""
}
```

Research should preserve provenance from source → claim → conclusion.

---

# 105. INNOVATION CONTRACT

Innovation task output:

```json
{
  "problem": "",
  "existing_solutions": [],
  "pain_points": [],
  "unsolved_problems": [],
  "opportunities": [],
  "concepts": [],
  "feasibility": [],
  "experiments": [],
  "recommendation_basis": []
}
```
The system must distinguish:

```text
new concept
vs
newly observed variant
vs
known pattern
```

---

# 106. PROJECT STATE SNAPSHOT

The system should expose a computed snapshot:

```json
{
  "project_id": "project_01",
  "status": "ACTIVE",
  "current_phase": "ENGINEERING",
  "progress": {
    "tasks_total": 42,
    "tasks_completed": 25,
    "tasks_blocked": 2,
    "tasks_failed": 1
  },
  "active_agents": [],
  "pending_approvals": [],
  "critical_risks": [],
  "latest_artifacts": [],
  "next_actions": []
}
```

This snapshot is derived from the authoritative state.

---

# 107. INITIAL DATABASE MAPPING

The relational control plane should approximately map to:

```text
organizations
users
organization_members

projects
project_members

agents
agent_versions
capabilities
agent_capabilities

tasks
task_dependencies
task_runs

workflows
workflow_runs
workflow_steps
workflow_checkpoints

artifacts
artifact_versions
artifact_links

tools
tool_operations
permissions
policies

decisions
decision_options
approvals

evaluations
evaluation_criteria
evaluation_results

research_sources
research_claims
research_evidence

memories

environments
deployments

events
audit_logs

models
model_providers
model_runs
usage_records
```

This mapping will be normalized and optimized during schema implementation.

---

# 108. STORAGE STRATEGY

TITAN should separate:

## Control-plane data

Use relational storage for:

- projects;
- tasks;
- users;
- permissions;
- workflows;
- approvals;
- decisions;
- audit records;
- usage.

## Artifact storage

Use object/blob storage for:

- large documents;
- source archives;
- generated media;
- build outputs;
- reports.

## Search / retrieval

Use dedicated indexing when needed for:

- semantic search;
- document retrieval;
- evidence retrieval;
- project knowledge.

## Event storage

Use an event-capable persistence strategy appropriate to scale.

The final technologies remain an explicit architecture decision.

---

# 109. TRANSACTION BOUNDARIES

A command should make its state transition atomically where possible.

Examples:

```text
ApproveDeployment
```

should not leave the approval in an ambiguous state.

For operations crossing external systems:

```text
internal transaction
+
durable intent
+
external execution
+
reconciliation
```

should be considered.

---

# 110. EXTERNAL SIDE EFFECTS

Every external side effect should have:

```text
intent
permission
risk
idempotency
execution
result
audit
rollback/reconciliation where possible
```

Examples:

- sending email;
- publishing content;
- modifying GitHub;
- deploying;
- creating cloud resources.

---

# 111. OBSERVABILITY CONTRACT

Three conceptual layers:

## Logs

Human-readable operational records.

## Metrics

Aggregated numerical signals.

## Traces

Causal execution path.

Trace example:

```text
Project
  → Workflow
    → Task
      → Agent Run
        → Model Call
        → Tool Call
        → Artifact
        → Evaluation
```

---

# 112. MINIMUM METRICS

System metrics:

```text
workflow_success_rate
task_success_rate
agent_failure_rate
tool_failure_rate
average_task_duration
average_workflow_duration
model_cost
tool_cost
approval_wait_time
retry_rate
security_block_rate
evaluation_failure_rate
```

Product metrics:

```text
project_completion_rate
time_to_first_working_artifact
time_to_validated_product
rework_rate
human_intervention_rate
```

---

# 113. TEST STRATEGY

TITAN itself must be tested like a serious software platform.

## Unit tests

For:

- state transitions;
- policy engine;
- risk engine;
- permission engine;
- task graph;
- parsers;
- validators.

## Integration tests

For:

- database;
- event system;
- tools;
- model providers;
- sandbox;
- GitHub.

## End-to-end tests

For complete workflows.

## Evaluation tests

For agent behavior.

## Security tests

For:

- privilege escalation;
- injection;
- secret leakage;
- policy bypass;
- unsafe tool use.

---

# 114. CORE TEST CASES

Initial mandatory scenarios:

```text
TEST-001
Create project

TEST-002
Create task graph

TEST-003
Block task on unfinished dependency

TEST-004
Run permitted sandbox task

TEST-005
Deny unauthorized production action

TEST-006
Require approval for R4 action

TEST-007
Resume paused workflow

TEST-008
Recover after tool failure

TEST-009
Retry transient model failure

TEST-010
Stop after retry budget is exhausted

TEST-011
Evaluate artifact

TEST-012
Reject failed quality gate

TEST-013
Create artifact version

TEST-014
Trace artifact to task

TEST-015
Trace task to source requirement

TEST-016
Record decision

TEST-017
Publish audit event

TEST-018
Redact secret from logs

TEST-019
Execute Git branch workflow

TEST-020
Rollback deployment
```

---

# 115. ACCEPTANCE TEST — FIRST VERTICAL SLICE

The first major demonstration must satisfy:

```text
Given:
  a natural-language project request

When:
  TITAN receives the request

Then:
  TITAN creates a project
  AND compiles intent
  AND creates a task graph
  AND selects agents
  AND executes at least one task in a sandbox
  AND creates an artifact
  AND evaluates the artifact
  AND records an execution trace
  AND exposes project state
```

Failure of any required stage means the vertical slice is incomplete.

---

# 116. FIRST VERTICAL SLICE EXAMPLE

Input:

> “Create a simple REST API for a task manager.”

Expected sequence:

```text
1. Intent Compiler
2. Project creation
3. Task graph creation
4. Solution architecture
5. Backend implementation
6. Test generation
7. Test execution
8. Artifact generation
9. Quality evaluation
10. Final summary
```

The first version may stop before deployment.

The important objective is:

> real multi-step execution with state, artifacts, evaluation, and traceability.

---

# 117. INITIAL CORE SERVICES

The first service boundaries are proposed as:

```text
titan-api
titan-orchestrator
titan-agent-runtime
titan-workflow
titan-policy
titan-tool-runtime
titan-artifact
titan-event
titan-evaluation
titan-memory
titan-research
```

These do not necessarily mean separate deployable microservices.

For the first implementation, a modular monolith may be preferable if it keeps the architecture testable and the boundaries clear.

This is a hypothesis to validate, not a permanent decision.

---

# 118. INITIAL TECHNOLOGY DECISION PROCESS

Technology choices must be made only after comparing:

```text
functional fit
developer velocity
ecosystem
security
observability
runtime characteristics
deployment complexity
cost
maintainability
community/project health
```

Do not choose a framework merely because it is currently popular.

---

# 119. ARCHITECTURE DECISION RECORD TEMPLATE

Every significant decision should use:

```markdown
# DEC-XXX — TITLE

## Context

## Problem

## Requirements

## Options

### Option A

### Option B

### Option C

## Evidence

## Decision

## Reasons

## Trade-offs

## Consequences

## Reversal Conditions

## Approval

## Date
```

---

# 120. IMPLEMENTATION READINESS CHECKLIST

Before coding a core subsystem:

```text
[ ] Purpose defined
[ ] Inputs defined
[ ] Outputs defined
[ ] State machine defined
[ ] Persistence defined
[ ] Events defined
[ ] Permissions defined
[ ] Failure states defined
[ ] Retry rules defined
[ ] Observability defined
[ ] Tests defined
[ ] Security implications reviewed
[ ] Documentation updated
```

---

# 121. CORE SPECIFICATION STATUS

Current status:

```text
[X] Domain entities defined
[X] Core relationships defined
[X] Lifecycle states defined
[X] Event model defined
[X] Command/query concept defined
[X] API concept expanded
[X] Error model defined
[X] Permission contract defined
[X] Risk contract defined
[X] Approval contract defined
[X] Evaluation contract defined
[X] Artifact contract defined
[X] Research contract defined
[X] Innovation contract defined
[X] Initial database mapping defined
[X] Test strategy defined

[ ] Technology stack selected
[ ] Final database migrations
[ ] Final API schemas
[ ] Event schema package
[ ] Runtime implementation
[ ] Sandbox implementation
[ ] Tool runtime implementation
```

---

# 122. NEXT ENGINEERING DELIVERABLE

The next concrete artifact to produce is:

## `TITAN_CORE_ARCHITECTURE`

It must turn this contract into:

```text
1. Technology stack
2. Module boundaries
3. Package structure
4. Database schema
5. Event schemas
6. API schemas
7. Authentication model
8. Authorization model
9. Runtime model
10. Queue/workflow strategy
11. Sandbox strategy
12. Local development environment
13. Test environment
14. CI strategy
15. Deployment strategy
```

The order is intentional.

We do not begin by writing dozens of agents.

We build the system that can reliably host those agents.

---

# 123. CONTINUOUS EVOLUTION RULE

From this point onward, every major TITAN implementation step must modify this file.

The preferred progression is:

```text
SPECIFY
  ↓
DESIGN
  ↓
IMPLEMENT
  ↓
TEST
  ↓
OBSERVE
  ↓
LEARN
  ↓
UPDATE SPECIFICATION
```

Thus `TITAN_Agent.md` remains the evolving bridge between the original idea and the final product.

---

# 124. CORE SPECIFICATION CHANGELOG

## 0.1.0 — 2026-09-20

Added implementation-ready definitions for:

- Project
- Agent
- Capability
- Task
- Workflow
- Run
- Artifact
- Event
- Tool
- Permission
- Risk
- Approval
- Decision
- Evaluation
- Evidence
- Memory
- Environment
- Deployment
- domain relationships
- command model
- query model
- event catalog
- API contract
- streaming
- idempotency
- error model
- retries
- repair strategy
- audit logging
- credential handling
- secret redaction
- tool execution contract
- agent output validation
- model routing contract
- cost accounting
- evaluation contract
- quality gates
- security gates
- research contract
- innovation contract
- database mapping
- storage strategy
- observability
- testing strategy
- first vertical slice
- initial service boundaries
- architecture decision process

---

# END OF CORE SPECIFICATION v0.1.0

---

# 125. TITAN CORE ARCHITECTURE — v0.1.0

> **Status:** Architecture baseline  
> **Date:** 2026-09-22  
> **Purpose:** Convert the Core Specification into a concrete, buildable architecture while preserving replaceable interfaces and future scalability.

This is the first concrete technical architecture decision set for TITAN.

The architecture starts as a **modular monolith + isolated worker processes + sandboxed execution**, with strict internal boundaries. We will not create distributed services merely because TITAN is multi-agent.

---

# 126. ARCHITECTURE OBJECTIVE

The first production-capable TITAN must support:

```text
Intent
  ↓
Project
  ↓
Task Graph
  ↓
Capability Matching
  ↓
Agent Selection
  ↓
Durable Workflow
  ↓
Agent Execution
  ↓
Tool Execution
  ↓
Artifact Creation
  ↓
Evaluation
  ↓
Repair / Retry / Escalation
  ↓
Approval when required
  ↓
Traceable Result
```

Primary optimization goals:

```text
Correctness
Durability
Security
Traceability
Developer velocity
Extensibility
Model independence
Operational simplicity
```

---

# 127. ARCHITECTURAL STYLE

## 127.1 Initial style

```text
MODULAR MONOLITH
+
WORKER PROCESSES
+
TEMPORAL WORKFLOW RUNTIME
+
ISOLATED SANDBOXES
```

The first version is deliberately **not** a large microservice mesh.

## 127.2 Reason

TITAN already interacts with distributed systems such as:

- model providers;
- GitHub;
- MCP servers;
- object storage;
- workflow workers;
- sandbox environments.

Adding a large number of internal network boundaries before they are justified would increase failure modes and operational cost.

## 127.3 Evolution path

```text
V0.x
Modular Monolith + Workers
        ↓
V1.x
Selective module extraction
        ↓
V2.x
Independent services only where
scale, security, ownership or deployment
independence justify them
```

---

# 128. TECHNOLOGY BASELINE

| Layer | Baseline | Responsibility |
|---|---|---|
| Runtime | Python 3.13.x | TITAN Core and agent runtime |
| API | FastAPI | HTTP API, OpenAPI, streaming |
| Validation | Pydantic 2.x | Data and runtime contracts |
| ORM / SQL | SQLAlchemy 2.x | Persistence |
| Migrations | Alembic | Database migrations |
| Database | PostgreSQL 18.x | Control plane |
| Vector retrieval | pgvector | Semantic retrieval |
| Durable workflows | Temporal | Long-running workflow execution |
| Agent runtime | TITAN Agent Runtime | Provider-neutral execution interface |
| Initial agent adapter | OpenAI Agents SDK | Agent execution integration |
| Tool protocol | MCP | Standard tool/context integration |
| Frontend | Next.js + TypeScript | Command Center |
| Object storage | S3-compatible | Large artifacts |
| Local object storage | MinIO | Development |
| Sandbox | Docker Engine | Initial isolated execution |
| Observability | OpenTelemetry | Traces, metrics, logs |
| Local orchestration | Docker Compose | Development |
| CI/CD | GitHub Actions | Build, test, security, release |
| Production orchestration | Kubernetes | Future scale |
| Identity | OIDC-compatible provider | Authentication |
| Credentials | Credential Broker | Scoped secret access |

Current official sources were checked for the principal technology choices. Python 3.14.7 is the current latest feature release, while 3.13.15 remains actively maintained; TITAN uses 3.13 as its initial compatibility baseline and will test 3.14 separately. PostgreSQL 18 is the current major release line, with continued 18.x maintenance releases in 2026. FastAPI documents async/await support, OpenAI's Agents SDK provides agents, handoffs, guardrails, sessions, MCP and tracing, Temporal provides durable workflows through its Python SDK, and OpenTelemetry defines the telemetry standards used by TITAN. 

Primary references:

- Python: https://www.python.org/downloads/
- OpenAI Agents SDK: https://github.com/openai/openai-agents-python
- Temporal Python SDK: https://github.com/temporalio/sdk-python
- PostgreSQL: https://www.postgresql.org/
- pgvector: https://github.com/pgvector/pgvector
- Docker Engine: https://docs.docker.com/engine/
- MCP: https://modelcontextprotocol.io/
- OpenTelemetry: https://opentelemetry.io/docs/
- Next.js: https://nextjs.org/docs

---

# 129. DEC-009 — PYTHON AS PRIMARY TITAN RUNTIME

## Decision

Use **Python 3.13.x** as the initial TITAN runtime.

## Rationale

TITAN is primarily an AI/agent orchestration system. The selected runtime needs first-class access to:

- asynchronous execution;
- AI/ML libraries;
- agent SDKs;
- evaluation tooling;
- structured data validation;
- research tooling.

The OpenAI Agents SDK supports Python 3.10+ and provides native primitives useful to TITAN, while Temporal's Python SDK also supports modern Python runtimes. 

## Compatibility policy

```text
Primary CI: Python 3.13
Secondary CI: Python 3.14
```

A dependency that breaks 3.14 does not block the 3.13 baseline unless it affects a required production capability.

---

# 130. DEC-010 — FASTAPI AS CORE HTTP FRAMEWORK

Use FastAPI for the first TITAN API.

Responsibilities:

```text
HTTP routing
Request validation
Response serialization
Authentication hooks
Authorization hooks
OpenAPI
Streaming endpoints
Health endpoints
```

FastAPI supports async/await and is appropriate for network-heavy workloads involving databases, APIs and other asynchronous services.

FastAPI must NOT be the workflow engine.

Example:

```text
POST /projects/{id}/workflows
        ↓
validate
        ↓
create durable workflow
        ↓
return workflow_id
```

The request must not remain open while a multi-minute or multi-hour workflow executes.

---

# 131. DEC-011 — NEXT.JS + TYPESCRIPT

Use Next.js + TypeScript for the Command Center.

Primary UI responsibilities:

```text
Project dashboard
Task graph
Agent activity
Artifacts
Research
Innovation
Approvals
Deployments
Observability
Settings
```

The frontend communicates with TITAN Core through:

```text
REST
+
streaming
```

Future interfaces such as CLI, desktop, mobile and IDE integrations should consume the same domain APIs.

---

# 132. DEC-012 — POSTGRESQL 18 CONTROL PLANE

Use PostgreSQL 18.x as the primary relational store.

PostgreSQL is the control-plane database because TITAN requires strong relational semantics for:

```text
projects
tasks
workflows
permissions
approvals
decisions
evaluations
auditing
usage
```

PostgreSQL stores metadata and transactional state. Large binaries belong in object storage.

---

# 133. DEC-013 — PGVECTOR FOR INITIAL RETRIEVAL

Use pgvector inside PostgreSQL for the first retrieval layer.

Initial use:

```text
Project knowledge
Research evidence
Artifact semantic search
Organizational memory
Decision retrieval
Documentation retrieval
```

The application uses a `VectorStore` interface so a dedicated vector database can be introduced later without changing domain logic.

---

# 134. DEC-014 — TEMPORAL FOR DURABLE WORKFLOWS

Use Temporal as the underlying durable execution engine.

Temporal provides durable workflow execution, retries, task queues, timers, signals and recovery for long-running business logic. Its Python SDK supports typed workflows, activities, workers, signals/updates and testing.

TITAN owns the domain semantics:

```text
Project
Task
Artifact
Agent
Policy
Risk
Approval
Evaluation```

Temporal owns execution durability:

```text
Workflow execution
Timers
Retries
Worker scheduling
Durable state
```

This separation prevents TITAN's domain model from becoming dependent on Temporal-specific concepts.

---

# 135. TITAN WORKFLOW MODEL

```text
TITAN Workflow
 ├── Project
 ├── Task Graph
 ├── Policy
 ├── Approvals
 └── Evaluations
        ↓
Temporal Workflow
        ↓
Temporal Activities
```

A TITAN workflow may therefore pause for a human approval without losing state.

---

# 136. DEC-015 — AGENT RUNTIME ABSTRACTION

TITAN will not expose vendor-specific agent objects to the core domain.

Internal contract:

```python
class AgentRuntime(Protocol):
    async def execute(
        self,
        request: AgentExecutionRequest,
    ) -> AgentExecutionResult:
        ...
```

First implementation:

```text
TITAN AgentRuntime
       ↓
OpenAI Agents SDK Adapter
```

Future adapters:

```text
Anthropic
Google
Mistral
DeepSeek
Local models
Other agent runtimes
```

The OpenAI Agents SDK is used as a building block, not as TITAN's domain architecture.

TITAN remains responsible for:

```text
Agent identity
Agent contract
Permissions
Risk
Task ownership
Artifact creation
Evaluation
Audit
```

---

# 137. AGENT RUNTIME RESPONSIBILITIES

The runtime must:

```text
load agent definition
load task context
load policy
resolve model
resolve permitted tools
start execution
capture tool calls
capture outputs
validate structured output
emit run events
return result
```

It must never:

```text
self-grant permissions
bypass policy
modify production arbitrarily
rewrite authoritative project state from raw model output
```

---

# 138. DEC-016 — MCP AS TOOL INTEGRATION BOUNDARY

Use MCP for compatible external tools and context providers.

The MCP specification defines standard primitives such as prompts, resources and tools. The July 2026 specification also introduced a stateless protocol core and additional authorization hardening.

TITAN's permission boundary remains above MCP:

```text
Agent
 ↓
Tool Registry
 ↓
Risk Engine
 ↓
Permission Engine
 ↓
Approval Engine if required
 ↓
MCP client
```

An MCP server must never be considered trusted merely because it speaks MCP.

---

# 139. TOOL ARCHITECTURE

```text
Tool Registry
    ├── Native Tool
    ├── MCP Tool
    ├── Internal Tool
    └── Remote API Tool
```

Every operation defines:

```text
operation_id
input schema
output schema
risk level
required permission
credential requirements
side effects
rollback strategy
audit policy
```

---

# 140. DEC-017 — DOCKER INITIAL SANDBOX

Docker Engine is the first sandbox implementation because it provides programmatic container execution and resource/network isolation primitives appropriate for the initial engineering runtime.

Default sandbox requirements:

```text
non-root execution where possible
explicit workspace mounts only
no host filesystem access
no Docker socket access
resource limits
execution timeout
restricted network
scoped credentials
ephemeral lifecycle
```

The abstraction is:

```python
class SandboxProvider(Protocol):
    async def create(...): ...
    async def execute(...): ...
    async def collect(...): ...
    async def destroy(...): ...
```

Future providers:

```text
Docker
gVisor
MicroVM
Kubernetes sandbox
```

Docker alone is not treated as the final high-assurance isolation mechanism for the highest-risk workloads.

---

# 141. SANDBOX LIFECYCLE

```text
REQUEST
  ↓
CREATE
  ↓
MOUNT APPROVED WORKSPACE
  ↓
APPLY NETWORK POLICY
  ↓
APPLY RESOURCE LIMITS
  ↓
EXECUTE
  ↓
COLLECT OUTPUTS
  ↓
UPLOAD ARTIFACTS
  ↓
RECORD LOGS
  ↓
DESTROY
```

---

# 142. DEC-018 — S3-COMPATIBLE OBJECT STORAGE

Large artifacts use object storage.

Examples:

```text
PDF
ZIP
source archives
screenshots
images
video
build outputs
large datasets
```

Initial environments:

```text
Local → MinIO
Production → S3-compatible storage
```

The domain depends on:

```python
ObjectStorage
```

not on a vendor-specific client.

---

# 143. DEC-019 — OPENTELEMETRY OBSERVABILITY

OpenTelemetry is the canonical instrumentation boundary for TITAN.

Required telemetry signals:

```text
Traces
Metrics
Logs
```

The minimum trace chain is:

```text
HTTP request
  ↓
Project command
  ↓
Workflow
  ↓
Task
  ↓
Agent run
  ↓
Model call
  ↓
Tool call
  ↓
Artifact
  ↓
Evaluation
```

Required correlation identifiers:

```text
request_id
project_id
workflow_id
task_id
run_id
trace_id
span_id
```

---

# 144. OBSERVABILITY DEPLOYMENT

```text
TITAN
  ↓
OpenTelemetry SDK
  ↓
OpenTelemetry Collector
  ├── traces
  ├── metrics
  └── logs
  ↓
Observability backend
```

TITAN must not depend on a single telemetry vendor.

---

# 145. DEC-020 — NO GENERAL MESSAGE BROKER IN MVP

Do not add Kafka, NATS, RabbitMQ or another general-purpose broker to the first implementation unless a concrete requirement demands it.

Reason:

```text
Temporal → durable workflow execution
PostgreSQL → transactional state
Outbox → domain event publication
```

If scale later demands a dedicated event bus, it can be introduced behind the existing EventPublisher interface.

---

# 146. OUTBOX PATTERN

For important state transitions:

```text
BEGIN
  ↓
update domain state
  ↓
insert outbox event
  ↓
COMMIT
```

A dispatcher publishes the event afterward.

This prevents a successful database update from being silently disconnected from its corresponding event.

---

# 147. DEC-021 — OIDC IDENTITY BOUNDARY

Authentication will use an OIDC-compatible identity provider.

Core abstraction:

```python
IdentityProvider
```

The control plane stores identity references such as:

```text
subject
issuer
organization
roles
membership
```

Authorization remains TITAN-owned.

---

# 148. AUTHENTICATION VS AUTHORIZATION

Authentication:

> Who is this identity?

Authorization:

> What may this identity do in this context?

TITAN authorization evaluates:

```text
identity
organization
project
resource
operation
environment
risk
policy
approval
```

---

# 149. DEC-022 — CREDENTIAL BROKER

Secrets are never placed directly into prompts.

Architecture:

```text
Agent
 ↓
Credential Broker
 ↓
Scoped Credential
 ↓
Tool
```

Credential requests should specify:

```text
principal
tool
operation
resource
environment
duration
purpose
```

The broker returns only what is necessary.

---

# 150. DEVELOPMENT ENVIRONMENT

Local development uses Docker Compose.

Conceptual services:

```text
titan-api
titan-worker
titan-agent-worker
postgres
temporal
temporal-ui
minio
otel-collector
observability backend
frontend
```

Not all services need to run in the minimal profile.

---

# 151. LOCAL DEVELOPMENT PROFILES

## Minimal

```text
frontend
api
postgres
temporal
```

## Standard

```text
minimal
+
workers
+
minio
+
otel collector
```

## Full

```text
standard
+
sandbox runtime
+
observability backend
+
integration fixtures
```

---

# 152. CORE MODULE BOUNDARIES

Target Python layout:

```text
src/titan/
│
├── api/
├── application/
├── domain/
│   ├── projects/
│   ├── tasks/
│   ├── workflows/
│   ├── agents/
│   ├── artifacts/
│   ├── decisions/
│   ├── approvals/
│   ├── evaluations/
│   ├── evidence/
│   └── deployments/
│
├── orchestration/
├── runtime/
│   ├── agents/
│   ├── tools/
│   ├── models/
│   └── sandbox/
│
├── policies/
├── security/
├── memory/
├── research/
├── innovation/
├── evaluation/
├── persistence/
├── events/
├── observability/
├── integrations/
│   ├── github/
│   ├── mcp/
│   ├── object_storage/
│   └── identity/
└── workers/
```

---

# 153. DOMAIN / INFRASTRUCTURE RULE

Domain code must not import vendor-specific infrastructure.

Bad:

```python
from titan.integrations.openai import OpenAIClient
```

inside a domain model.

Preferred:

```python
from titan.runtime.models import ModelProvider
```

with dependency injection and adapters.

---

# 154. DEPENDENCY DIRECTION

```text
API
 ↓
Application
 ↓
Domain
 ↑
Ports / Interfaces
 ↑
Infrastructure adapters
```

The domain defines required capabilities.

Infrastructure implements those capabilities.

---

# 155. AGENT EXECUTION FLOW

```text
Task READY
   ↓
Orchestrator
   ↓
Task policy check
   ↓
Capability resolution
   ↓
Agent selection
   ↓
Model routing
   ↓
Tool permission resolution
   ↓
Sandbox allocation if required
   ↓
Agent runtime
   ↓
Model interaction
   ↓
Tool calls
   ↓
Output validation
   ↓
Artifact creation
   ↓
Evaluation
   ↓
PASS / FAIL / ESCALATE
```

---

# 156. TOOL CALL FLOW

```text
Agent requests tool
      ↓
Validate input
      ↓
Resolve operation
      ↓
Identify resource
      ↓
Risk classification
      ↓
Permission check
      ↓
Approval check
      ↓
Credential resolution
      ↓
Execute
      ↓
Validate output
      ↓
Audit
      ↓
Return result
```

No model output may directly become an unrestricted external side effect.

---

# 157. MODEL PROVIDER CONTRACT

```python
class ModelProvider(Protocol):
    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        ...
```

Capabilities are declared rather than assumed:

```text
text
vision
structured_output
tool_calling
streaming
reasoning
embeddings
audio
```

---

# 158. MODEL ROUTING POLICY

Routing considers:

```text
task type
complexity
risk
latency budget
cost budget
context requirements
modalities
tool requirements
availability
```

Output:

```text
provider
model
fallback chain
reason
```

The routing result becomes part of the run trace.

---

# 159. AGENT CONTEXT BUILDER

An agent receives only relevant context.

Potential sources:

```text
task
project summary
relevant artifacts
relevant decisions
relevant evidence
allowed memory
tool schemas
policy
quality criteria
```

The complete database must never be dumped into the model context by default.

Context ranking should consider:

```text
task relevance
dependency relevance
recency
authority
confidence
approval status
```

---

# 160. ARTIFACT PIPELINE

```text
Agent output
   ↓
Schema validation
   ↓
Content normalization
   ↓
Artifact version creation
   ↓
Checksum
   ↓
Object storage if needed
   ↓
PostgreSQL metadata
   ↓
Artifact event
   ↓
Evaluation
```

Approved artifact versions are immutable.

---

# 161. APPROVAL PAUSE MODEL

```text
Temporal Workflow
      ↓
Approval Requested
      ↓
Workflow waits
      ↓
User decision
      ↓
Signal / update
      ↓
Workflow resumes
```

The approval must be bound to the specific action and context that requested it.

---

# 162. FAILURE MODEL

Failure handling has layers:

```text
Tool retry
    ↓
Activity retry
    ↓
Agent retry
    ↓
Task repair
    ↓
Replanning
    ↓
Human escalation
```

Retries are bounded.

Security violations and explicit permission denials are not treated as transient failures.

---

# 163. AGENT / TASK RESOURCE BUDGETS

Every execution should eventually support:

```text
max duration
max tool calls
max model calls
max cost
max retries
max artifact size
CPU limit
memory limit
disk limit
network profile
```

Budget exhaustion produces structured escalation.

---

# 164. GITHUB ARCHITECTURE

GitHub is implemented behind:

```python
GitHubAdapter
```

Capabilities:

```text
repositories
branches
commits
pull requests
issues
review comments
checks
```

Credentials remain scoped and never become generic prompt text.

---

# 165. WORKSPACE ARCHITECTURE

Engineering tasks receive a workspace descriptor:

```json
{
  "workspace_id": "workspace_01",
  "repository": "repo_url",
  "branch": "feature/task-01",
  "root": "/workspace",
  "permissions": {
    "read": true,
    "write": true,
    "execute": true
  },
  "network_profile": "restricted"
}
```

---

# 166. GIT WORKFLOW

Default engineering workflow:

```text
base branch
   ↓
create isolated branch
   ↓
create workspace
   ↓
inspect repository
   ↓
modify
   ↓
run tests
   ↓
security checks
   ↓
review
   ↓
commit
   ↓
push
   ↓
PR
```

Production merges remain policy-controlled.

---

# 167. DATABASE TRANSACTION RULE

Important domain state changes should use:

```text
transaction
  = domain mutation
  + required audit metadata
  + outbox event
```

External side effects require reconciliation.

---

# 168. MIGRATIONS

Alembic manages PostgreSQL schema migrations.

Rules:

```text
one coherent migration at a time
migration reviewed
migration tested
destructive changes staged
production migrations automated
```

Direct manual production schema editing is forbidden except controlled emergency procedures.

---

# 169. BACKUP / RECOVERY

Production database strategy:

```text
automated backups
+
point-in-time recovery
+
regular restore tests
```

Artifact storage should use versioning/replication where supported.

Recovery capability is considered incomplete until restoration has been tested.

---

# 170. CI PIPELINE

Every pull request should eventually execute:

```text
format
lint
type check
unit tests
integration tests
security checks
migration validation
build
```

Runtime changes also trigger the core vertical-slice test.

---

# 171. RELEASE PIPELINE

```text
PR ↓
CI
 ↓
Review
 ↓
Merge
 ↓
Build
 ↓
Security scan
 ↓
Artifact publication
 ↓
Staging deploy
 ↓
Smoke tests
 ↓
Approval
 ↓
Production deploy
 ↓
Post-deployment verification
```

Rollback is part of the release design, not an afterthought.

---

# 172. ENVIRONMENT STRATEGY

```text
local
 ↓
development
 ↓
staging
 ↓
production
```

Each environment receives independent:

```text
credentials
database
object storage
workflow namespace/configuration
tool permissions
network policy
```

Production credentials never belong in development configuration.

---

# 173. PRODUCTION DEPLOYMENT PATH

Initial deployment:

```text
Docker images
 ↓
CI
 ↓
Container registry
 ↓
Deployment target
```

Scalable target:

```text
Kubernetes
 ├── API
 ├── workflow workers
 ├── agent workers
 ├── evaluation workers
 └── sandbox workers
```

Kubernetes is deferred until the operational requirements justify it.

---

# 174. WORKER TYPES

Logical worker roles:

```text
Workflow Worker
Agent Worker
Evaluation Worker
Sandbox Worker
```

The API remains a separate runtime boundary.

For local development, multiple worker roles may share one process. Production can separate them for resource isolation and scaling.

---

# 175. API VERSIONING

Public API:

```text
/api/v1
```

Breaking changes require:

```text
/api/v2
```

Event schemas and dynamic configuration schemas are independently versioned.

---

# 176. INITIAL REPOSITORY STRUCTURE

```text
titan/
├── apps/
│   ├── api/
│   └── web/
│
├── src/
│   └── titan/
│       ├── api/
│       ├── application/
│       ├── domain/
│       ├── orchestration/
│       ├── runtime/
│       ├── policies/
│       ├── security/
│       ├── memory/
│       ├── research/
│       ├── innovation/
│       ├── evaluation/
│       ├── persistence/
│       ├── events/
│       ├── observability/
│       └── integrations/
│
├── workers/
│   ├── workflow/
│   ├── agent/
│   ├── evaluation/
│   └── sandbox/
│
├── database/
│   ├── migrations/
│   └── seeds/
│
├── infra/
│   ├── compose/
│   ├── docker/
│   ├── observability/
│   └── kubernetes/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── security/
│   └── evaluations/
│
├── docs/
├── pyproject.toml
├── docker-compose.yml
├── Makefile
└── README.md
```

This structure remains subject to repository-bootstrap validation.

---

# 177. FIRST VERTICAL SLICE

The first architectural proof must implement exactly this path:

```text
User
 ↓
POST /projects
 ↓
Project created
 ↓
POST /workflows
 ↓
Temporal Workflow
 ↓
Intent Compiler
 ↓
Task Graph
 ↓
Agent Selection
 ↓
Agent Runtime
 ↓
Sandbox
 ↓
Tool
 ↓
Artifact
 ↓
Evaluation
 ↓
Project State
 ↓
UI / stream
```

This is the most important validation target before adding many specialist agents.

---

# 178. FIRST DEMONSTRATION TASK

Recommended first real TITAN task:

> **Inspect a repository and produce a structured technical assessment.**

Expected behavior:

```text
clone repository
 ↓
inspect files
 ↓
identify technologies
 ↓
analyze architecture
 ↓
identify risks
 ↓
produce report
 ↓
store artifact
 ↓
evaluate report
 ↓
show complete trace
```

This validates the majority of the initial kernel without requiring full product generation.

---

# 179. SECOND DEMONSTRATION TASK

After repository assessment works:

> **Implement one isolated feature in the repository.**

Expected:

```text
understand request
 ↓
inspect repository
 ↓
plan
 ↓
create branch
 ↓
modify
 ↓
test
 ↓
security review
 ↓
quality review
 ↓
commit
 ↓
PR
```

This becomes the first Engineering Factory proof.

---

# 180. ARCHITECTURE ACCEPTANCE CRITERIA

Architecture design is considered sufficiently complete when:

```text
[X] Primary runtime selected
[X] API framework selected
[X] Database selected
[X] Workflow runtime selected
[X] Agent runtime abstraction defined
[X] MCP boundary defined
[X] Sandbox boundary defined
[X] Object storage boundary defined
[X] Observability boundary defined
[X] Authentication boundary defined
[X] Credential boundary defined
[X] Module boundaries defined
[X] Deployment topology defined
[X] First vertical slice defined

[ ] Repository bootstrapped
[ ] Initial migrations implemented
[ ] Core API implemented
[ ] Temporal integration implemented
[ ] Agent runtime implemented
[ ] Sandbox implemented
[ ] First E2E test passed
```

Architecture is therefore **design-complete and implementation-pending**.

---

# 181. ARCHITECTURAL RISKS

## RISK-A01 — Agent SDK coupling

Mitigation:

```text
AgentRuntime abstraction
provider adapters
domain-owned agent contracts
```

## RISK-A02 — Workflow engine coupling

Mitigation:

```text
TITAN WorkflowPort
Temporal adapter
domain-owned workflow semantics
```

## RISK-A03 — Sandbox escape

Mitigation:

```text
network deny-by-default
resource limits
credential isolation
no privileged container execution
future stronger isolation providers
```

## RISK-A04 — Context explosion

Mitigation:

```text
context builder
relevance ranking
artifact references
summaries
memory retrieval
```

## RISK-A05 — Infinite loops

Mitigation:

```text
retry budgets
tool budgets
time budgets
cost budgets
escalation
```

## RISK-A06 — Cost explosion

Mitigation:

```text
model routing
budgets
caching
usage telemetry
```

## RISK-A07 — False evaluation

Mitigation:

```text
independent evaluators
deterministic tests
multiple evidence sources
red-team stages
```

---

# 182. ARCHITECTURE NON-GOALS

This phase does not attempt to implement:

```text
fully autonomous continuous company
all model providers
all MCP ecosystems
all media capabilities
unbounded self-modification
automatic production ownership
physical-world control
```

The architecture only needs to make these future capabilities extensible without redesigning the core.

---

# 183. BUILD ORDER

The implementation order is now:

```text
PHASE 1
Repository bootstrap
        ↓
PHASE 2
Configuration + logging + telemetry
        ↓
PHASE 3
PostgreSQL + migrations
        ↓
PHASE 4
Domain models
        ↓
PHASE 5
Application services
        ↓
PHASE 6
FastAPI
        ↓
PHASE 7
Temporal integration
        ↓
PHASE 8
Agent Runtime
        ↓
PHASE 9
Tool Registry
        ↓
PHASE 10
Sandbox
        ↓
PHASE 11
Artifacts
        ↓
PHASE 12
Evaluation
        ↓
PHASE 13
GitHub integration
        ↓
PHASE 14
First E2E vertical slice
        ↓
PHASE 15
Command Center
```

---

# 184. IMMEDIATE NEXT ACTION

The next concrete build artifact is:

# `TITAN_CORE_REPOSITORY_BOOTSTRAP`

It must create the real repository with:

```text
Python project
FastAPI
PostgreSQL
Alembic
Temporal
Docker Compose
configuration
structured logging
OpenTelemetry skeleton
tests
CI skeleton
frontend skeleton
environment templates
```

Then we implement the first domain objects:

```text
Project
Agent
Capability
Task
Workflow
Artifact
Event
```

Only after those foundations are executable do we begin implementing specialized agent behavior.

---

# 185. ARCHITECTURE CHANGELOG

## v0.1.0 — 2026-09-22

### Added

- concrete technology baseline;
- modular-monolith architecture;
- Python 3.13 runtime decision;
- FastAPI API layer;
- Next.js/TypeScript Command Center baseline;
- PostgreSQL 18 control plane;
- pgvector retrieval layer;
- Temporal durable workflow layer;
- provider-neutral AgentRuntime;
- OpenAI Agents SDK adapter strategy;
- MCP integration boundary;
- Docker sandbox strategy;
- S3-compatible artifact storage;
- OpenTelemetry observability architecture;
- OIDC identity boundary;
- credential broker concept;
- PostgreSQL outbox strategy;
- domain/infrastructure dependency rules;
- module/package map;
- development and production topologies;
- worker topology;
- CI/CD architecture;
- budget governance;
- first vertical slice;
- first and second demonstration tasks;
- architecture risks and mitigations.

### Decisions

```text
DEC-009  Python 3.13 baseline
DEC-010  FastAPI
DEC-011  Next.js + TypeScript
DEC-012  PostgreSQL 18
DEC-013  pgvector
DEC-014  Temporal
DEC-015  Agent Runtime abstraction
DEC-016  MCP
DEC-017  Docker initial sandbox
DEC-018  S3-compatible object storage
DEC-019  OpenTelemetry
DEC-020  No dedicated message broker in MVP
DEC-021  OIDC identity boundary
DEC-022  Credential Broker
```

---

# END OF TITAN CORE ARCHITECTURE v0.1.0

---

# 203. CORE PERSISTENCE IMPLEMENTATION CHECKPOINT — 2026-09-22

## Status

The first persistent control-plane slice is now implemented in the repository.

Implemented:

```text
[X] PostgreSQL control-plane integration
[X] SQLAlchemy 2 ORM foundation
[X] Async session factory
[X] Alembic configuration
[X] Initial database migration
[X] Project persistence
[X] Agent persistence model
[X] Task persistence model
[X] Task dependency table
[X] Workflow persistence model
[X] Artifact persistence model
[X] Event persistence model
[X] Initial ProjectCreated domain event
[X] PostgreSQL-backed integration test
[X] CI database service
[X] CI migration step
[X] Temporal database isolation in local Compose
```

Not yet implemented:

```text
[ ] Application/repository abstraction layer
[ ] Full domain-to-persistence mapping layer
[ ] Workflow persistence and Temporal adapter
[ ] Agent registry persistence and capability tables
[ ] Artifact content storage
[ ] Event outbox dispatcher
[ ] Authentication/authorization persistence
[ ] Approval persistence
[ ] Evaluation persistence
```

## Persistence principles established

1. PostgreSQL is the authoritative control-plane database.
2. SQLAlchemy models are infrastructure representations and are not the long-term domain API.
3. Alembic owns schema evolution.
4. Important project actions begin creating durable domain events.
5. Integration tests use a real PostgreSQL service in CI.
6. Temporal receives a dedicated local PostgreSQL instance rather than sharing the TITAN application database.

## New architectural decisions

```text
DEC-023
Use SQLAlchemy 2.x async ORM for the initial persistence adapter.

DEC-024
Use Alembic migrations as the only supported schema evolution mechanism.

DEC-025
Project creation persists a ProjectCreated event in the same database transaction.

DEC-026
The local Temporal development stack uses a separate PostgreSQL database service.

DEC-027
CI must execute database migrations before integration tests.
```

## First persisted lifecycle

```text
POST /api/v1/projects
        ↓
Validate request
        ↓
Create Project
        ↓
Flush database identity
        ↓
Create ProjectCreated event
        ↓
Commit one transaction
        ↓
Return persisted Project
```

This establishes the first concrete example of the TITAN rule:

> State change + durable event must be committed together.

## Next persistence step

The next database expansion should implement:

```text
Agent
  ↓
Capability
  ↓
Task
  ↓
Workflow
  ↓
Run
  ↓
Approval
  ↓
Evaluation
  ↓
Audit
```

The schema must evolve incrementally through Alembic migrations rather than introducing the entire future schema at once.

---

# 204. REPOSITORY SOURCE-OF-TRUTH RULE

`TITAN_Agent.md` in the Git repository is the project specification baseline.

Any important implementation that changes the architecture must update this file in the same development cycle.

Required order:

```text
Implementation
    ↓
Tests
    ↓
Evidence
    ↓
Specification update
    ↓
Pull Request
```

---

# 205. CURRENT IMPLEMENTATION PHASE

```text
TITAN 0 — CORE KERNEL

Phase:
PERSISTENCE FOUNDATION

Completed:
Repository bootstrap
Specification baseline
CI foundation
Persistence foundation

Current:
Core domain persistence + event foundation

Next:
Workflow runtime + Temporal integration
```

---

# END OF PERSISTENCE IMPLEMENTATION CHECKPOINT


---

# 206. WORKFLOW RUNTIME IMPLEMENTATION CHECKPOINT — 2026-09-22

## Status

The first durable TITAN workflow runtime is now implemented and validated on the feature branch.

Implemented:

```text
[X] Workflow persistence extension
[X] Run persistence
[X] Task → Workflow association
[X] Temporal workflow definition
[X] Temporal activities
[X] Temporal client adapter
[X] Workflow worker entrypoint
[X] Workflow start API
[X] Task creation API
[X] Durable workflow lifecycle events
[X] Temporal task queue configuration
[X] Bounded activity retry policy
[X] PostgreSQL integration validation
[X] Real Temporal service validation in CI
[X] Temporal workflow integration test
[X] Async SQLAlchemy loop-isolation test fixture
[X] Database cascade-aware ORM relationships
```

## Current runtime path

```text
POST /projects
      ↓
Project

POST /projects/{id}/tasks
      ↓
Task Graph

POST /projects/{id}/workflows
      ↓
Workflow persisted
      ↓
Temporal workflow started
      ↓
Workflow activity
      ↓
Task activity loop
      ↓
TaskStarted
      ↓
TaskCompleted
      ↓
WorkflowCompleted
      ↓
Workflow / Run state persisted
```

## Agent Runtime boundary

`orchestrate_task` is intentionally a boundary, not the final implementation.

Current behavior:

```text
Task
 ↓
Validate ownership
 ↓
RUNNING
 ↓
TaskStarted
 ↓
COMPLETED
 ↓
TaskCompleted
```

Future behavior:

```text
Task
 ↓
Capability resolution
 ↓
Agent selection
 ↓
Policy evaluation
 ↓
Agent Runtime
 ↓
Tool calls
 ↓
Artifacts
 ↓
Evaluation
 ↓
Task completion
```

This separation prevents workflow infrastructure from becoming tightly coupled to a specific LLM provider or agent SDK.

## New architectural decisions

```text
DEC-028
Temporal is the first durable workflow execution adapter.

DEC-029
Multiple Temporal activity arguments are passed through the SDK's
explicit args mechanism rather than relying on multiple positional
arguments.

DEC-030
Activity retries are explicitly bounded with a shared retry policy.

DEC-031
The CI environment validates TITAN against a real Temporal service
rather than relying only on mocked workflow execution.

DEC-032
Async SQLAlchemy engine connections are disposed between tests to
prevent cross-event-loop connection reuse.

DEC-033
SQLAlchemy project relationships use passive deletes where PostgreSQL
foreign-key cascades are authoritative.

DEC-034
The configured Temporal task queue is environment-specific and is
asserted through configuration in integration tests.
```

## Validation

The validated CI sequence is:

```text
Install                  ✅
Alembic migrations       ✅
Temporal readiness       ✅
Ruff                     ✅
Unit tests               ✅
PostgreSQL integration   ✅
Temporal workflow test   ✅
```

## Observed and resolved failures

### Failure A — Async event-loop reuse

Symptom:

```text
Future attached to a different loop
```

Resolution:

```text
dispose SQLAlchemy async engine
before and after integration tests
```

### Failure B — Temporal activity invocation

Symptom:

```text
execute_activity() takes from 1 to 2 positional arguments
```

Resolution:

```text
use the SDK's args=... mechanism for multi-argument activities
```

### Failure C — Workflow test configuration

Symptom:

```text
test expected titan-core
CI configured titan-ci
```

Resolution:

```text
assert the configured task queue instead of hard-coding one environment
```

### Failure D — ORM cascade cleanup

Symptom:

```text
null value in column "project_id" of relation "tasks"
```

Resolution:

```text
mark project child relationships passive_deletes=True
and let PostgreSQL foreign-key actions own deletion semantics
```

## Next implementation phase

The next phase is:

# TITAN AGENT RUNTIME FOUNDATION

Required capabilities:

```text
Agent contract loading
      ↓
Capability registry
      ↓
Model provider abstraction
      ↓
Model routing
      ↓
Tool registry
      ↓
Policy check
      ↓
Sandbox
      ↓
Agent execution
      ↓
Structured result
      ↓
Artifact creation
      ↓
Evaluation
```

Only after this layer is operational will `orchestrate_task` be replaced by genuine agent execution.

---

# END OF WORKFLOW RUNTIME IMPLEMENTATION CHECKPOINT

---

# 207. TITAN AGENT RUNTIME FOUNDATION CHECKPOINT — 2026-09-22

## Status

The first provider-neutral Agent Runtime foundation is now implemented.

Implemented:

~~~text
[X] Agent contract
[X] Capability registry
[X] Model provider abstraction
[X] Model routing
[X] Tool registry
[X] Risk / permission policy
[X] Structured agent output
[X] Baseline evaluator
[X] Agent execution result
[X] Durable AGENT_RESULT artifact creation
[X] Artifact checksum
[X] Runtime integration into Temporal task activity
[X] Local deterministic provider for tests/development
[X] OpenAI Responses provider adapter
[X] Runtime unit tests
~~~

## Runtime path

~~~text
Temporal Task Activity
        ↓
AgentTaskContext
        ↓
Agent Contract
        ↓
Capability Registry
        ↓
Risk / Permission Policy
        ↓
Tool Registry
        ↓
Provider Router
        ↓
Model Provider
        ↓
Structured AgentModelOutput
        ↓
Baseline Evaluation
        ↓
ArtifactModel
        ↓
TaskCompleted
~~~

## Provider boundary

The runtime owns the ModelProvider interface rather than coupling task execution to a single vendor.

Current adapters:

~~~text
local
  deterministic structured provider for development/tests

openai
  Responses API structured-output adapter
~~~

Future providers can be added without changing workflow semantics.

## Agent contract

The first built-in contract is:

~~~text
general-executor
~~~

It explicitly declares:

~~~text
analysis
structured-output
artifact-write
~~~

and currently has an R1 risk ceiling.

The contract is intentionally separate from the Temporal workflow implementation.

## Policy boundary

Before model execution the runtime verifies:

~~~text
task risk <= agent risk ceiling
requested capabilities are registered
requested tools are allowed by the contract
~~~

A failed policy check stops execution before a model call.

## Artifact rule

Successful agent execution produces an AGENT_RESULT artifact with:

~~~text
structured JSON content
SHA-256 checksum
FINAL status
~~~

The checksum is persisted so artifact integrity can be checked independently from execution events.

## Quality gate

Every agent execution must pass the baseline evaluator:

~~~text
structured output present
summary present
artifact present
~~~

Failure prevents the task from reaching COMPLETED.

This is an initial deterministic quality gate, not the final TITAN evaluation system.

## Important implementation boundary

The current Agent Runtime is intentionally small.

Not yet implemented:

~~~text
[ ] persistent capability catalogue
[ ] persistent agent contract versions
[ ] dynamic model routing based on budget/latency/quality
[ ] real tool execution loop
[ ] MCP tool adapters
[ ] sandbox execution
[ ] approval engine integration
[ ] independent evaluator workers
[ ] token/cost budgets
[ ] context retrieval / memory injection
[ ] streaming execution events
~~~

Those capabilities are next layers, not responsibilities of the Temporal workflow itself.

## New architectural decisions

~~~text
DEC-035
Agent execution is isolated behind a provider-neutral AgentRuntime.

DEC-036
Agent contracts explicitly declare capabilities, allowed tools, model,
and risk ceiling.

DEC-037
Policy checks occur before model provider execution.

DEC-038
Structured agent output is a mandatory runtime boundary.

DEC-039
Every successful task execution produces a durable AGENT_RESULT artifact.

DEC-040
Artifact content is checksummed with SHA-256.

DEC-041
The initial local provider is deterministic and exists to keep the
core runtime testable without external model credentials.

DEC-042
OpenAI is implemented as an adapter, not as the domain runtime itself.
~~~

## Next phase

~~~text
TITAN TOOL + SANDBOX FOUNDATION
~~~

The next implementation must turn the current Tool Registry from a declaration-only boundary into a governed execution layer:

~~~text
Agent
 ↓
Tool selection
 ↓
Permission check
 ↓
Tool execution
 ↓
Sandbox / network policy
 ↓
Tool result
 ↓
Artifact / event
 ↓
Evaluation
~~~

---

# END OF AGENT RUNTIME FOUNDATION CHECKPOINT


---

# 208. TITAN TOOL + SANDBOX FOUNDATION CHECKPOINT — 2026-09-22

## Status

The first governed Tool Execution and Sandbox layer is now implemented.

Implemented:

~~~text
[X] Tool call contract
[X] Tool execution context
[X] Tool registry validation
[X] Tool allowlist enforcement
[X] Tool risk enforcement
[X] Governed ToolExecutor
[X] Docker sandbox adapter
[X] Deny-by-default network
[X] CPU / memory / PID limits
[X] Capability dropping
[X] no-new-privileges
[X] Read-only sandbox root filesystem
[X] Isolated /tmp
[X] Workspace bind mount
[X] Sandbox timeout
[X] Engineering agent contract with sandbox.exec permission
[X] Unit tests for tool policy and sandbox command hardening
~~~

## Tool runtime path

~~~text
Agent Contract
      ↓
Allowed Tool List
      ↓
Tool Registry
      ↓
Tool Risk Policy
      ↓
Tool Executor
      ↓
Tool Handler
      ↓
Sandbox (when required)
      ↓
Tool Result
~~~

## Sandbox boundary

The first sandbox implementation uses Docker as the execution isolation provider.

Default sandbox constraints:

~~~text
network = none
memory = 512m
cpus = 1.0
pids = 128
capabilities = dropped
no-new-privileges = true
root filesystem = read-only
/tmp = isolated tmpfs
workspace = explicit bind mount
execution timeout = 60s
~~~

The command is passed as an explicit argv vector rather than through a shell.

The sandbox therefore does not provide a generic host shell. It provides a controlled container execution boundary.

## Tool policy

A tool call is permitted only when:

~~~text
tool is registered
tool is explicitly allowed by the agent contract
tool risk <= task risk
tool risk <= agent risk ceiling
tool has an execution handler
~~~

Policy rejection occurs before the handler executes.

## Engineering agent

The first specialized runtime contract is now:

~~~text
engineering-executor
~~~

It may use:

~~~text
sandbox.exec
~~~

with an R2 risk ceiling.

The general R1 agent remains restricted and cannot invoke sandbox execution.

## Important implementation boundary

This layer deliberately does not yet implement:

~~~text
[ ] model-generated tool-call loop
[ ] persistent tool catalogue
[ ] MCP tool adapter
[ ] workspace lifecycle manager
[ ] GitHub workspace provisioning
[ ] credential injection broker
[ ] outbound network policy profiles
[ ] sandbox image registry / allowlist persistence
[ ] sandbox artifact streaming
[ ] tool-call event persistence
~~~

Those remain subsequent runtime layers.

## New architectural decisions

~~~text
DEC-043
Tool execution is isolated behind ToolExecutor rather than being performed
directly by AgentRuntime or provider adapters.

DEC-044
Every tool has an explicit risk level and must pass both task-risk and
agent-risk checks.

DEC-045
Tool permissions are allowlisted by agent contract.

DEC-046
Sandbox commands use argv execution without a host shell.

DEC-047
The initial sandbox uses Docker with network disabled and container
privilege reduction enabled.

DEC-048
The engineering agent is the first contract allowed to use sandbox.exec;
the general agent remains tool-restricted.
~~~

## Next phase

~~~text
TITAN WORKSPACE + MCP FOUNDATION
~~~

The next layer must connect governed tools to real project workspaces and external systems:

~~~text
Project
  ↓
Workspace Manager
  ↓
Repository / Files
  ↓
MCP / Native Adapters
  ↓
Tool Execution
  ↓
Sandbox
  ↓
Artifact
~~~

---

# END OF TOOL + SANDBOX FOUNDATION CHECKPOINT

---

# 209. TITAN WORKSPACE + MCP FOUNDATION CHECKPOINT — 2026-09-22

## Status

The first workspace isolation and MCP integration boundary is now implemented.

Implemented:

~~~text
[X] Task workspace manager
[X] UUID-scoped workspace layout
[X] Workspace root confinement
[X] Symlink escape checks
[X] Workspace metadata marker
[X] workspace.read_text tool
[X] workspace.list tool
[X] Workspace path traversal protection
[X] MCP server configuration contract
[X] MCP remote tool discovery
[X] MCP remote tool allowlisting
[X] MCP remote tool registration into ToolRegistry
[X] MCP tool execution adapter
[X] Official MCP Python SDK v2 dependency
[X] Unit tests for workspace and MCP registration
~~~

## Workspace layout

~~~text
.titan/workspaces/
  <project UUID>/
    <task UUID>/
      .titan-workspace.json
      repository/
      generated/
      reports/
~~~

The current manager creates the isolated task root. Repository checkout and lifecycle orchestration are separate responsibilities.

## Workspace security

A workspace operation is allowed only when its resolved path remains under the task workspace.

The manager rejects:

~~~text
invalid project/task identifiers
path traversal
resolved paths escaping the configured root
resolved task paths escaping the project workspace
metadata symlink escapes
~~~

Workspace tools do not accept arbitrary absolute paths.

## MCP boundary

TITAN now has a provider-neutral MCP adapter:

~~~text
MCPServerConfig
      ↓
MCPToolProvider
      ↓
discover remote tools
      ↓
explicit allowlist
      ↓
ToolRegistry
      ↓
ToolExecutor
      ↓
MCP call
~~~

The adapter currently targets MCP servers exposed through the official Python SDK client interface.

Remote MCP tools are not automatically trusted.

A server may expose many tools, but TITAN registers only tools explicitly permitted by its server configuration.

Each registered MCP tool receives a local TITAN risk level before it reaches ToolExecutor.

## Current MCP implementation

The repository depends on the MCP Python SDK v2 line.

The adapter supports:

~~~text
list_tools()
call_tool()
structured content
content fallback
is_error propagation
~~~

The next MCP layer must add:

~~~text
[ ] server credential broker integration
[ ] server-level network policy
[ ] stdio lifecycle manager
[ ] MCP server health state
[ ] tool schema persistence
[ ] tool version tracking
[ ] MCP event/audit records
~~~

## Runtime path after this phase

~~~text
Task
 ↓
Workspace Manager
 ↓
Tool Registry
 ├── native workspace tools
 ├── sandbox tools
 └── MCP tools
 ↓
Risk / Permission Policy
 ↓
Tool Executor
 ↓
Sandbox / MCP
 ↓
Tool Result
 ↓
Agent Runtime
~~~

## New architectural decisions

~~~text
DEC-049
Each task receives a UUID-scoped workspace under a configurable TITAN
workspace root.

DEC-050
Workspace paths are resolved before access and must remain inside the
task workspace.

DEC-051
Workspace tools are first-class governed tools rather than direct
filesystem calls from agents.

DEC-052
MCP servers are integrated through a provider adapter instead of
coupling AgentRuntime to the MCP SDK.

DEC-053
Remote MCP tools require explicit server-side tool allowlisting before
registration in ToolRegistry.

DEC-054
MCP remote tools receive TITAN risk levels before execution and remain
subject to the same ToolExecutor policy as native tools.
~~~

## Next phase

~~~text
TITAN TOOL-CALL LOOP + CONTEXT ENGINE
~~~

The current model provider still returns one structured result.

The next runtime step is to let an agent reason over:

~~~text
task context
workspace state
available tools
tool schemas
previous tool results
artifacts
policy constraints
memory references
~~~

and iteratively produce governed tool calls until the task reaches a
validated terminal state.

---

# END OF WORKSPACE + MCP FOUNDATION CHECKPOINT

# TITAN V.

TITAN V. is a living, modular Intent-to-Reality Engine for building, validating, operating, and evolving digital products through controlled multi-agent execution.

## Source of truth

The master product and architecture specification lives in `TITAN_Agent.md`.

## Current phase

**TITAN Human-in-the-Loop Execution**

The durable runtime, governance, recovery, explainability, realtime control plane and governed action foundations are implemented. The Command Center can now pause approval-gated tasks, collect an operator decision, signal Temporal, and resume or reject execution.

Approval-gated tasks now have a durable, configurable timeout. When the operator does not decide within the configured window, the workflow records an explicit `EXPIRED` outcome instead of waiting forever. The repository is intentionally being built as a modular monolith plus isolated workers. See `TITAN_Agent.md` for the architecture, decisions, roadmap, and implementation checkpoints.

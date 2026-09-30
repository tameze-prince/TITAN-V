# TITAN V.

TITAN V. is a living, modular Intent-to-Reality Engine for building, validating, operating, and evolving digital products through controlled multi-agent execution.

## Source of truth

The master product and architecture specification lives in `TITAN_Agent.md`.

## Current phase

**TITAN Session + Multi-Operator Governance**

The durable runtime, governance, recovery, explainability, realtime control plane and governed action foundations are implemented. Approval-gated tasks can pause inside Temporal, collect an operator decision, and resume, reject, or expire deterministically. Resource-level RBAC, controlled delegation, and policy-driven approval escalation are now available as production governance layers.

Operator authentication now supports provider-agnostic OIDC bearer-token validation through trusted JWKS, with issuer/audience/expiry/subject checks, configurable RBAC role mapping, HTTPS enforcement, JWKS caching, and audited operator subjects. Static operator tokens remain available as an explicit interim mode for controlled environments. Approval-gated tasks also have a durable, configurable timeout. When the operator does not decide within the configured window, the workflow records an explicit `EXPIRED` outcome instead of waiting forever. The repository is intentionally being built as a modular monolith plus isolated workers. See `TITAN_Agent.md` for the architecture, decisions, roadmap, and implementation checkpoints.

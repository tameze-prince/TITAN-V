# TITAN Command Center

The Command Center is the operator-facing Next.js application for TITAN V.

## Development

From the repository root:

~~~bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
~~~

The frontend expects TITAN Core at:

~~~text
http://localhost:8000
~~~

Override it with `TITAN_API_URL`.

## Current scope

The MVP is read-oriented and exposes:

- global control-plane metrics;
- project list;
- project state and phase;
- task/workflow status;
- agent assignments;
- governance and approval counts;
- recovery metrics;
- explainability entries;
- recent events;
- persisted artifacts.

Mutating controls, authentication, RBAC and live streaming are intentionally deferred to the next implementation layers.

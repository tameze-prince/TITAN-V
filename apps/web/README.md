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

The Command Center now exposes:

- global control-plane metrics;
- project list;
- project state and phase;
- task/workflow status;
- agent assignments;
- governance and approval counts;
- recovery metrics;
- explainability entries;
- recent events;
- persisted artifacts;
- governed recovery and task approval controls;
- live SSE event streaming;
- OIDC browser sign-in through the Next.js BFF;
- persistent operator session state;
- multi-operator approval quorum progress.

The browser does not receive OIDC access or ID tokens. The Next.js BFF forwards the opaque HttpOnly session cookie to TITAN Core.

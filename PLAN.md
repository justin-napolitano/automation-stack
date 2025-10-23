# PLAN.md — Personal Automation Stack (Signal + Assistant + Skills)

## Components
- Notifier I/O (you already run this): signal-api + notifier-gateway
- Assistant Core: FastAPI + LangChain/LlamaIndex
- Skill Containers: weather-service, metrics, etc.

## Repos
- automation-stack/ (this wiring repo)
- assistant-core/ (brain + tools)
- weather-service/ (first skill)

## Networking & Contracts
- Bridge `assistant-net`
- Skills: GET /run, GET /healthz, optional GET /push
- Notifier: POST /notify {to, message} with bearer token
- Assistant polls signal-api /v1/receive/<number>

## Flows
- Inbound: Signal → signal-api → assistant-core → (skills) → notifier → Signal
- Outbound: (cron) skill /push → notifier /notify → Signal

## Day-1 Steps
1) Place repos side-by-side
2) Copy .env.example → .env for automation-stack and assistant-core (and weather-service if using /push)
3) docker compose up -d --build (from automation-stack)
4) Test: /status, /weather Orlando, curl :8789/run

## New Skill Pattern
- FastAPI app with /run, /healthz, optional CRON + /push
- Add service to compose, add tool client in assistant-core

## Release & Observability
- Pin images by tag; update one at a time
- /healthz everywhere; logs to stdout

## Security
- Long GATEWAY_TOKEN, internal-only /notify
- ALLOW_SENDERS set in assistant-core
- Shell whitelist minimal; backup signal link dir

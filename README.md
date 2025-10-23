# automation-stack
Compose wiring for: signal-api, notifier-gateway, assistant-core, weather-service.

Quick start:
1) cp .env.example .env && edit values
2) Ensure assistant-core/ and weather-service/ exist here (or add as submodules)
3) docker compose up -d --build

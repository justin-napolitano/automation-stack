---
slug: github-automation-stack
id: github-automation-stack
title: automation-stack
repo: justin-napolitano/automation-stack
githubUrl: https://github.com/justin-napolitano/automation-stack
generatedAt: '2025-11-24T21:34:01.031Z'
source: github-auto
summary: >-
  Compose wiring for a personal automation stack integrating Signal messaging,
  an assistant core, and skill-based microservices.
tags: []
seoPrimaryKeyword: ''
seoSecondaryKeywords: []
seoOptimized: false
topicFamily: null
topicFamilyConfidence: null
kind: project
entryLayout: project
showInProjects: true
showInNotes: false
showInWriting: false
showInLogs: false
---

Compose wiring for a personal automation stack integrating Signal messaging, an assistant core, and skill-based microservices.

## Features

- Signal messaging integration using signal-cli REST API
- Notifier gateway to send and receive Signal messages securely
- Assistant core built on FastAPI with LangChain/LlamaIndex for AI-powered automation
- Modular skill services (e.g., weather service) with cron scheduling and webhook support
- Docker Compose setup for easy local deployment and development
- Secure token-based authentication and sender allowlists

## Tech Stack

- Python 3.x
- FastAPI for API services
- signal-cli-rest-api Docker image for Signal messaging
- LangChain / LlamaIndex for AI assistant capabilities
- Docker Compose for multi-service orchestration
- Flask for notifier-gateway microservice

## Getting Started

### Prerequisites

- Docker and Docker Compose installed
- Clone this repo alongside `assistant-core` and `weather-service` repos

### Installation & Run

```bash
# Copy environment template and edit
cp .env.example .env
# Edit .env to configure phone numbers, tokens, API keys, etc.

# Start all services
docker compose up -d --build

# Verify services
curl http://localhost:8088/status  # assistant-core status
curl http://localhost:8789/run      # weather-service run endpoint
curl http://localhost:8787/healthz  # notifier-gateway health
```

## Project Structure

```
automation-stack/
├── assistant-framework/       # Assistant core source
├── notifier-gateway/          # Signal notifier gateway microservice
├── signal-gateway/            # (Assumed Signal API related, not detailed)
├── weather-servb/             # Weather service skill container
├── weather-service-old/       # Legacy weather service implementation
├── docker-compose.yml         # Compose file wiring all services
├── env-example.txt            # Environment variables template
├── PLAN.md                    # Project plan and architecture notes
├── README.md                  # This file
```

## Future Work / Roadmap

- Add more skill containers (metrics, reminders, etc.)
- Improve assistant-core with additional AI models and retrieval-augmented generation
- Enhance security with more granular sender whitelisting and token management
- Add observability features such as centralized logging and metrics
- Support multi-replica deployments with leader election for polling
- Refactor legacy weather-service and unify skill APIs

---

*Note: Some assumptions were made about the `signal-gateway` directory and certain internal APIs based on the provided context.*

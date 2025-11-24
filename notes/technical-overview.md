---
slug: github-automation-stack-note-technical-overview
id: github-automation-stack-note-technical-overview
title: automation-stack Overview
repo: justin-napolitano/automation-stack
githubUrl: https://github.com/justin-napolitano/automation-stack
generatedAt: '2025-11-24T18:31:09.644Z'
source: github-auto
summary: >-
  The `automation-stack` repo provides a framework for personal automation using
  Signal messaging, a core assistant, and modular skill-based microservices.
tags: []
seoPrimaryKeyword: ''
seoSecondaryKeywords: []
seoOptimized: false
topicFamily: null
topicFamilyConfidence: null
kind: note
entryLayout: note
showInProjects: false
showInNotes: true
showInWriting: false
showInLogs: false
---

The `automation-stack` repo provides a framework for personal automation using Signal messaging, a core assistant, and modular skill-based microservices.

### Key Features
- **Signal integration** via the signal-cli REST API for messaging.
- **FastAPI**-based assistant core with LangChain/LlamaIndex for AI-driven tasks.
- Modular services like a weather service with cron jobs and webhooks.
- Simple setup through Docker Compose.

### Getting Started
1. Ensure you have Docker and Docker Compose installed.
2. Clone this repo beside `assistant-core` and `weather-service`.

### Quick Commands
```bash
# Create and configure the environment file
cp .env.example .env

# Start the services
docker compose up -d --build

# Check service status
curl http://localhost:8088/status  
curl http://localhost:8789/run      
curl http://localhost:8787/healthz  
```

### Gotchas
Remember to edit the `.env` file for phone numbers and tokens before running.

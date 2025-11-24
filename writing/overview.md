---
slug: github-automation-stack-writing-overview
id: github-automation-stack-writing-overview
title: Building My Personal Automation Stack with Signal Integration
repo: justin-napolitano/automation-stack
githubUrl: https://github.com/justin-napolitano/automation-stack
generatedAt: '2025-11-24T17:06:03.193Z'
source: github-auto
summary: >-
  I want to share my latest project: the automation-stack. It's a personal
  automation framework that pulls together an array of functionalities, with a
  core focus on integrating Signal messaging, an AI assistant, and skill-based
  microservices. Let's dive into what this repo is, why I built it, and what I
  envision for its future.
tags: []
seoPrimaryKeyword: ''
seoSecondaryKeywords: []
seoOptimized: false
topicFamily: null
topicFamilyConfidence: null
kind: writing
entryLayout: writing
showInProjects: false
showInNotes: false
showInWriting: true
showInLogs: false
---

I want to share my latest project: the automation-stack. It's a personal automation framework that pulls together an array of functionalities, with a core focus on integrating Signal messaging, an AI assistant, and skill-based microservices. Let's dive into what this repo is, why I built it, and what I envision for its future.

## What It Is and Why It Exists

The essence of automation-stack is to create a seamless automation experience. I wanted a system where I can send and receive messages via Signal, harness the power of an AI-driven assistant, and deploy various microservices for specific tasks. It’s about streamlining my personal automations without needing to juggle too many disparate systems.

This project tackles a few key pain points I’ve encountered:
- I needed secure messaging, and Signal’s end-to-end encryption fits the bill.
- I wanted an AI assistant that can help automate tasks without turning into a bloated monster.
- It’s crucial that all components can work harmoniously, so I opted for Docker Compose for orchestration.

## Key Design Decisions

1. **Signal Messaging Integration**: I chose to use the `signal-cli REST API` for Signal messaging because it's lightweight and simple. It allows me to send and receive messages securely.
   
2. **Microservices Architecture**: The entire stack leans heavily on microservices. This way, I can scale and extend functionalities by simply adding more services. Each service has a specific, focused role—like the weather service, which can be expanded with more skills later.

3. **FastAPI as the Core**: The assistant core is built with FastAPI. Why FastAPI? Performance and ease of use. I can get up and running quickly while benefitting from automatic documentation and async capabilities.

4. **Modular Approach**: I adopted a modular design for the skill services. This means I can add various functionalities relatively easily and keep the codebase clean and manageable. 

5. **Security Measures**: I implemented token-based authentication and sender allows lists to ensure that only trusted services can interact within the automation stack.

## The Stack and Tools

Here’s a quick rundown of the tech stack powering the automation-stack:

- **Python 3.x**: The language of choice. Familiar and powerful enough for my needs.
- **FastAPI**: For building APIs quickly and efficiently.
- **signal-cli-rest-api**: The Docker image that handles all Signal message operations.
- **LangChain/LlamaIndex**: Powers my AI assistant capabilities. I like where the AI landscape is going, and these tools provide a solid foundation.
- **Docker Compose**: To handle multi-service orchestration. Simple as pie.
- **Flask for Notifier Gateway**: A lightweight choice for the notifier microservice and it does the job well.

## Getting Started

If you’re interested in running the automation-stack yourself, here’s how to get started:

### Prerequisites

- **Docker** and **Docker Compose** must be installed on your system.
- Clone this repository alongside the `assistant-core` and `weather-service` repos for a complete setup.

### Installation & Run

Running the stack is as simple as following these steps:

```bash
# Copy environment template and edit
cp .env.example .env
# Edit .env to configure phone numbers, tokens, API keys, etc.

# Build and start all services
docker compose up -d --build

# Verify services
curl http://localhost:8088/status  # Get assistant-core status
curl http://localhost:8789/run      # Run endpoint for the weather service
curl http://localhost:8787/healthz  # Check notifier-gateway health
```

## Project Structure

Here's a snapshot of how the project is organized:

```
automation-stack/
├── assistant-framework/       # Assistant core source
├── notifier-gateway/          # Microservice for Signal notifications
├── signal-gateway/            # Assumed Signal API integration
├── weather-service/           # Service for weather-related queries
├── weather-service-old/       # Legacy implementation of weather service
├── docker-compose.yml         # Compose file for all services
├── env-example.txt            # Template for environment variables
├── PLAN.md                    # Project plan and architecture notes
├── README.md                  # This file
```

## Future Work and Improvements

This automation journey is just beginning. Here’s what I want to tackle next:

- **Add more skills**: Think metrics, reminders, and whatever else I can come up with.
- **AI Assistant Enhancements**: I want to improve the assistant core with better AI models and retrieval-enhanced generation techniques.
- **Security Upgrades**: I’m looking at making sender whitelisting more granular and improving the token management system.
- **Observability**: Introducing centralized logging and metrics will help in monitoring and debugging.
- **Multi-Replica Support**: Adding leader election might be a great feature for polling services.
- **Refactor Legacy Code**: I’ve been meaning to tidy up the old weather service implementation and unify the APIs.

## Stay Connected

I share regular updates and insights on my progress over on social media. You can find me on Mastodon, Bluesky, and Twitter/X. I’d love to connect and hear your thoughts on the project!

So there you have it. The automation-stack is a personal project that has turned out to be a lot of fun. I’m looking forward to expanding it and possibly helping others as it evolves. If you've got feedback or ideas, hit me up!

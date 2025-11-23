---
slug: "github-automation-stack"
title: "automation-stack"
repo: "justin-napolitano/automation-stack"
githubUrl: "https://github.com/justin-napolitano/automation-stack"
generatedAt: "2025-11-23T08:15:41.793458Z"
source: "github-auto"
---


# Building My Personal Automation Stack: Signal, AI Assistant, and Skills

Hey there! I wanted to share a project I've been working on called **automation-stack** — a personal automation platform that integrates Signal messaging with an AI assistant and modular skill services. This blog post dives into the motivation behind it, how it works, and some technical details I found interesting while building it.

---

## Why I Built This

I've long been fascinated by personal automation — the idea that your devices and services can work together seamlessly to make your life easier without constant manual input. Signal is my go-to messaging app because of its privacy and security, so I wanted to build an automation system that uses Signal as the main communication channel.

At the same time, I wanted to leverage AI to interpret and respond to messages intelligently. By combining Signal with an AI assistant and extensible skill services, I could create a system that understands natural language commands, fetches data, and sends back useful information — all through Signal.

## The Problem It Solves

Many automation platforms are either too generic or rely on proprietary ecosystems. I wanted something open, self-hosted, and tailored to my needs. This stack enables:

- Receiving and sending Signal messages programmatically
- Processing inbound messages with an AI assistant
- Running skill services like weather updates, metrics, and more
- Secure communication between components with tokens and allowlists
- Easy deployment using Docker Compose

## How It's Built

### Signal Integration

At the core is the `signal-cli-rest-api` container, which wraps the Signal CLI into a REST service. This lets other services send and receive Signal messages over HTTP.

### Notifier Gateway

The `notifier-gateway` is a Flask app that acts as a secure gateway for sending Signal messages. It exposes a `/notify` endpoint protected by a bearer token. It also polls Signal for inbound messages and forwards them to the assistant core.

### Assistant Core

The assistant core is built with FastAPI and uses LangChain/LlamaIndex to provide AI-powered message processing. It receives forwarded Signal messages, interprets them, and can invoke skill services.

### Skill Services

Skills are modular microservices that perform specific tasks. For example, the `weather-service` fetches weather data and can push updates to Signal via the notifier gateway. Skills expose endpoints like `/run` and `/healthz` and can be scheduled with cron expressions.

### Orchestration

All components are wired together using Docker Compose on a custom bridge network. Environment variables configure tokens, phone numbers, API keys, and other settings.

## Interesting Implementation Details

- **Security:** The system uses long random hex tokens for internal API authentication and an allowlist of Signal numbers to restrict access.
- **Polling Leader:** To support multi-replica deployments, the notifier-gateway can be configured so only one instance polls Signal to avoid duplicate processing.
- **Forwarding:** Inbound Signal messages are normalized and forwarded as JSON payloads to the assistant core, enabling flexible processing.
- **Extensibility:** Adding a new skill involves creating a FastAPI app with standard endpoints and adding it to the Docker Compose setup.
- **Legacy Code:** There's a legacy weather service alongside a newer implementation, showing an evolution in the skill design.

## Why this project matters for my career

Building this stack has been a fantastic learning experience in microservice architecture, asynchronous messaging, and AI integration. It pushed me to think about secure inter-service communication, deployment automation, and scalable design patterns. Plus, it's a practical portfolio piece that showcases my ability to design and implement complex, real-world automation solutions using modern Python frameworks and tools. This project not only sharpens my technical skills but also demonstrates my passion for building open, privacy-respecting software.

---

Thanks for reading! If you're interested in personal automation or Signal integrations, I hope this inspires you to build your own stack. Feel free to reach out if you want to chat about the project or collaborate.

Happy automating! 🚀
# Platform Application Structure Guide

This document defines how an application should be structured to be fully compatible with our Platform-as-a-Service (PaaS) orchestration engine. The platform handles runtime provisioning, inter-agent messaging (Kafka-based), and state management. Your application only needs to provide its specific models, state definitions, agent logic, and tools.

## 1. Directory Structure

Your application must follow a precise modular directory structure so the platform can dynamically load and route to your components.

```
your_app_name/
├── config.yaml          # Global configuration, system parameters, agent toggles, API keys
├── Dockerfile.base      # Foundational image definition containing common dependencies
├── a2a/                 # [Platform Provided] Agent-to-Agent communication protocols
│   ├── client.py
│   ├── models.py
│   └── server.py
├── core/                # Your specific application domain logic
│   ├── __init__.py
│   ├── models.py        # Pydantic schemas for data validation
│   ├── state.py         # Global state definitions for the LangGraph/DAG workflow
│   ├── agents/          # Individual agent logic blueprints
│   │   ├── __init__.py
│   │   ├── agent_one.py
│   │   └── agent_two.py
│   └── tools/           # Discrete tools usable by agents
│       ├── __init__.py
│       ├── tool_a.py
│       └── tool_b.py
├── scripts/             # Useful scripts for testing/starting components locally
└── services/            # Microservice definitions for deployment
    ├── supervisor/      # Master node routing logic (DAG)
    │   ├── Dockerfile
    │   └── main.py
    ├── agent-one-srv/
    │   ├── Dockerfile
    │   └── main.py
    └── agent-two-srv/
        ├── Dockerfile
        └── main.py
```

## 2. Core Components

### 2.1 Configuration (`config.yaml`)
Define all system parameters, Kafka topics, agent endpoint URLs, and environment variables here. The platform supervisor node reads this to map the network topology.

### 2.2 Models and State (`core/models.py`, `core/state.py`)
Use Pydantic for strict data typing. `state.py` should define the overarching state object that gets passed between agents via Kafka during the DAG workflow.

### 2.3 Agents (`core/agents/`)
Define your agent logic using LangGraph bindings or standard classes. Agents should be decoupled and rely strictly on the `state.py` for input and output.

### 2.4 Tools (`core/tools/`)
Tools must be isolated Python modules (e.g., interacting with an external API) that your agents can import and execute.

### 2.5 Services & Orchestration (`services/`)
Each agent (and the supervisor) gets its own microservice definition.
- **Supervisor**: Implements the DAG routing logic.
- **Agent Services**: Wrap the agent logic in a FastAPI or gRPC server, ready to receive events from the platform's communication layer.

## 3. Deployment (Platform Contract)

A single entry point for deployment is required. At the root, you will define a `docker-compose.yml` (or Kubernetes manifests, depending on the platform environment) that stitches everything together, leveraging the `Dockerfile.base`.

The platform expects the following boot sequence (as per platform requirements):
1. **Repository Server**: Configuration and logic are available.
2. **Kafka Broker**: Communication protocol active.
3. **System Master (Supervisor)**: Starts, reads configuration, maps topology.
4. **Application Runtimes**: Provisioned based on topology configs (Orchestrators, Agents, Models, Tools).

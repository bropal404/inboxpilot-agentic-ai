# Platform Execution and Testing Guide

This document outlines the recent architectural changes made to transform the application into a decoupled **Platform-as-a-Service (PaaS)** orchestration engine, along with detailed instructions on how to run and test it.

---

## 1. How the Files Have Been Restructured

The repository has been restructured to explicitly separate the **Platform** (infrastructure, communication, orchestration) from the **Application Domain** (your specific logic, agents, and tools, such as `inboxpilot`).

```text
inboxpilot-agentic-ai/
├── core/                        # [Application Logic] Your app-specific logic template
│   ├── agents/                  # Specific LangGraph / standard agent logic 
│   ├── tools/                   # Isolated python scripts (e.g. imap, calendar, search tool)
│   ├── models.py                # Schema definitions specific to your application 
│   └── state.py                 # Graph state routing and structures for your app
├── a2a/                         # [Platform Base] Inter-Service Communication 
│   ├── kafka_bus.py             # Kafka async producer/consumer bus wrappers for networking
│   └── ...
├── repo-server/                 # [Platform Config] The Central Topology Repository
│   ├── main.py                  # API that dishes out configurations required for runtime boots
│   └── Dockerfile               
├── services/                    # [Platform Runtimes] Universal Container Environments
│   ├── supervisor/              # Master Node routing DAG orchestration
│   │   ├── main.py              # Downloads topology, initializes runtimes over Kafka
│   │   └── Dockerfile
│   └── agent-node/              # Standardized runtime worker
│       ├── main.py              # A universal container that loads specific instructions based on generic env variables
│       └── Dockerfile           
├── docker-compose.yml           # Complete platform footprint defining the strictly ordered boot sequence
├── platform_structure_guide.md  # Detailed guide on how to shape future applications for the platform
└── requirements.txt             # Unified python dependency manifest
```

### Key Differences from the Application Model:
- **Generic Runtimes:** Instead of hardcoded servers evaluating `classify` or `fetch`, the platform spins up identical `agent-node` environments. These are fed instructions by the Master Supervisor via Kafka and adapt themselves using generic environment variables (e.g., `NODE_ROLE=classify`).
- **Domain Interchangeability:** To run a totally different application on this AI platform, you just swap out the `core/` folder with another module, update the `repo-server` config representation, and the entire infrastructure will re-map seamlessly.

---

## 2. How to Run the Platform

The entire infrastructure runs on a strict sequential boot requirement (Repo Server -> Kafka Broker -> Supervisor Master -> Application Runtimes). Docker Compose handles this automatically.

1. **Ensure Docker is running** on your system.
2. **Navigate** to the platform root directory:
   ```bash
   cd inboxpilot-agentic-ai
   ```
3. **Build and Boot** the orchestration cluster:
   ```bash
   docker-compose up --build -d
   ```
4. **Verify the Boot Sequence state:**
   ```bash
   docker-compose ps
   ```
   *You should see 6 containers continuously running (`repo-1`, `kafka-1`, `supervisor-1`, `runtime-agent-1-1`, `runtime-agent-2-1`, `runtime-orch-1-1`).*

---

## 3. How to Test Core Features

### Feature A: The Repository Component
The Repository exposes dynamic configuration to setup applications. You can test that the platform knows how to construct your application.
- **Run this curl command:**
  ```bash
  curl http://localhost:8080/config/inboxpilot
  ```
- **Expected Output:** You should see a JSON representation of the application requirements being handed to the overall system:
  `{"agents": 6, "models": 4, "tools": 10, "topology": ["classify", "fetch", "respond"]}`

### Feature B: Architecture Orchestration & Master Booting
The master `supervisor` must start up, query the repository server, pull the topology mappings, and broadcast its readiness cleanly.
- **View Supervisor Boot logs:**
  ```bash
  docker logs inboxpilot-agentic-ai-supervisor-1
  ```
- **Expected Output Highlights:** 
  ```text
  🚀 Supervisor Booting...
  📥 Topology Pulled from Repository: {"agents": 6, "models": 4, "tools": 10, "topology": ["classify", "fetch", "respond"]}
  🚀 Master Topology Broadcast complete.
  ```

### Feature C: Inspect Dynamic Generic Runtime Booting
The runtime nodes are no longer specific backend services, they are empty shells (`agent-node`) waiting to execute events. Let's inspect the `classify` agent environment.
- **View Agent logs:**
  ```bash
  docker logs inboxpilot-agentic-ai-runtime-agent-1-1
  ```
- **Expected Output:**
  ```text
  🚀 Runtime classify Booted. Waiting for instructions over Kafka...
  ```
  *(Note that the `NODE_ROLE` was supplied dynamically, setting its identity)*

### Feature D: Executing Tool Logic pipelines via Kafka
You can ping the generic endpoints directly and monitor the messages being submitted to the message broker. Since the agents operate inside a docker bridge network on port 8000, we can use `docker exec` to trigger a simulated interaction.
- **Execute a mock event into an agent shell:**
  ```bash
  docker exec -it inboxpilot-agentic-ai-runtime-agent-1-1 curl -X POST -H "Content-Type: application/json" -d '{"task_id": "123", "action": "scan_inbox"}' http://localhost:8000/execute
  ```
- **Expected Output:**
  ```json
  {"message":"task sent to bus"}
  ```
  *(The agent acknowledges the request and forwards it safely to the `orchestrator-events` Kafka topic)*

### Stopping the Platform
When you're done testing, you can cleanly tear down the entire application topology and clear containers by running:
```bash
docker-compose down
```

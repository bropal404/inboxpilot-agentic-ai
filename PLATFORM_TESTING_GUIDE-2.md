# Platform Architecture Testing Guide

This guide provides testing steps for checking the fully operational internal PAAS setup of your newly migrated agentic platform.

## 1. Verify Topology Pulls
To confirm that nodes are successfully checking out configurations from the Repo-Server:

```bash
# Check Repo-Server logs for incoming requests
docker logs inboxpilot-agentic-ai-repo-1

# Check Supervisor logs to see if it downloaded its graph definition
docker logs inboxpilot-agentic-ai-supervisor-1

# Check runtime logs to confirm they downloaded component defs
docker logs inboxpilot-agentic-ai-runtime-orch-1-1
```

## 2. Triggering Workflows & Platform Simulation

The standard REST `curl` is missing inside lightweight Alpine images, so we use internal Python commands. Let's send a fake task event through the API of the supervisor itself.

To trigger an evaluation from your local terminal (since port 5001 is mapped out to your host):

```bash
curl -X POST http://localhost:5001/execute \
-H "Content-Type: application/json" \
-d '{"task": "Please read my email and draft a polite response."}'
```
Wait a moment, then observe the logs of the components. 
You should be able to track the lifecycle of the message traversing the message bus from the `Supervisor -> Runtime Manager (orch-1) -> Worker Nodes (agent-1 / agent-2)`.

```bash
docker logs inboxpilot-agentic-ai-supervisor-1
docker logs inboxpilot-agentic-ai-runtime-orch-1-1
docker logs inboxpilot-agentic-ai-runtime-agent-1-1
```

## 3. Verify Kafka Connectivity

If you want to view local Kafka metadata mapping across the nodes, use the runtime agent to inspect topics:

```bash
docker exec inboxpilot-agentic-ai-runtime-agent-1-1 python -c "
from kafka import KafkaConsumer;
consumer = KafkaConsumer(bootstrap_servers='kafka:9092');
print('Available Topics: ', consumer.topics())
"
```

## Review Architecture Output
The platform architecture decouples exact tool bindings from standard API endpoints. By checking the logs mapped against the `hackathon_plan_group1.pdf` topology, you can observe:
- **Repo-Server** feeding configurations.
- **Supervisor Node** translating `POST /execute` commands into generic `master-events` broadcasted over Kafka.
- **Runtimes** reading role configurations, dynamically instantiating functions (`state_manager`, `fetch_emails` etc) and polling their designated Kafka topics.
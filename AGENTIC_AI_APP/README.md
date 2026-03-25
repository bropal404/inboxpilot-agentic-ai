# AGENTIC_AI_APP

A LangGraph-based agentic application ready for the `DS_PLATFORM`.

## Overview
This application demonstrates how to wrap a standard LangGraph component inside an adapter that integrates natively with the platform's Kafka Streams and isolated resources via Environment Variables.

## Core Files
- `platform.yaml`: Defines resources and logical topic names required by the Orchestrator.
- `Dockerfile`: Standard container format; the Orchestrator maps `$PORT` natively.
- `src/adapter.py`: Consumes Kafka requests, maintains isolated Redis checkpoint memory across users and apps, processes the LangGraph execution, and pushes back to Kafka topic streams.
- `src/graph.py`: Defines the LangGraph nodes and execution flow.
- `src/main.py`: Uvicorn startup tying the adapter background processes with the application health check.

## Packaging and Testing on the Platform
1. Ensure the `DS_PLATFORM` is running (via `cd ../DS_PLATFORM && ./init.sh`).
2. Package this folder into a tar archive:
   ```bash
   tar -czf langraph-agent.tar.gz -C . .
   ```
   *(Run this from the `AGENTIC_AI_APP` directory)*
3. Upload `langraph-agent.tar.gz` to the Platform Frontend at [http://localhost:3000](http://localhost:3000).
4. Select the app from the Chat dropdown and interact with it to verify its function and multi-turn state memory.

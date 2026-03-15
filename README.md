# InboxPilot

> Agentic AI email assistant -- autonomously fetches, classifies, and drafts replies using **LangGraph + Groq (Llama 3)**.
>
> Now also available as a **fully distributed multi-agent system** built on Google's [Agent2Agent (A2A) protocol](https://github.com/google-gemini/agent2agent) over HTTP, orchestrated by a LangGraph supervisor.

---

## Table of Contents

- [Quickstart (Monolith)](#quickstart-monolith--demo-mode)
- [Production Mode (Real Email)](#production-mode-real-email)
- [Distributed A2A Mode](#distributed-a2a-mode)
  - [What is A2A?](#what-is-the-a2a-protocol)
  - [How InboxPilot is Distributed](#how-inboxpilot-is-distributed)
  - [Run Locally (No Docker)](#run-locally-no-docker)
  - [Run with Docker Compose](#run-with-docker-compose)
- [Live Demo Output](#live-demo-output)
- [CLI Reference](#cli-reference)
- [How It Works](#how-it-works-deep-dive)
- [Project Structure](#project-structure)
- [Configuration](#configuration-configyaml)
- [Tech Stack](#tech-stack)

---

## Quickstart (Monolith — Demo Mode)

No email credentials needed. Just a free Groq API key.

```bash
# 1. Clone and install
git clone <repo-url> && cd InboxPilot-Agentic-App
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Get a FREE Groq key → https://console.groq.com
export GROQ_API_KEY="gsk_..."

# 3. Run
inboxpilot check
```

---

## Production Mode (Real Email)

### Step 1 — Switch to production mode

Edit `config.yaml`:
```yaml
app:
  mode: "production"
```

### Step 2 — Get a Gmail App Password

Google requires an **App Password** for IMAP (not your regular password):

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. **Security** → **2-Step Verification** (must be ON)
3. Scroll down → **App passwords** → name it `InboxPilot`
4. Copy the 16-character password (**no spaces**)

### Step 3 — Set credentials in `.env`

```env
INBOX_EMAIL="you@gmail.com"
INBOX_PASSWORD="abcdefghijklmnop"   # 16-char App Password, no spaces
GROQ_API_KEY="gsk_..."
```

### Step 4 — Run

```bash
inboxpilot check
inboxpilot review   # approve drafts before anything is sent
```

> **Safety**: InboxPilot **never sends email**. It only saves drafts. `mark_as_read` is `false` by default. No data leaves your machine except LLM calls to Groq.

---

## Distributed A2A Mode

### What is the A2A Protocol?

[Google's Agent2Agent (A2A) protocol](https://developers.google.com/agent2agent) is an open standard for AI agent-to-agent communication. It defines:

- **Agent Cards** — JSON metadata at `GET /.well-known/agent.json` that describe each agent's name, capabilities, input/output schemas, and URL. Any agent can discover and call any other agent using this.
- **Tasks** — structured work units sent via `POST /a2a` as **JSON-RPC 2.0** requests. Each task has a `method`, `params`, `status` (`submitted → running → completed/failed`), and `artifacts` (results).
- **Transport** — plain **HTTP + JSON**. No proprietary SDKs needed. Any HTTP client can talk to an A2A agent.

This means InboxPilot's agents are **interoperable** — other A2A-compliant systems (LangChain, Vertex AI, CrewAI, etc.) can call them directly just by knowing a URL.

### How InboxPilot is Distributed

```
┌─────────────────────────────────────────────────────────┐
│              LangGraph Supervisor  :8080                │
│  ┌─────────────────────────────────────────────────┐   │
│  │   StateGraph: fetch → classify → respond → done  │   │
│  │   Each node = async A2A HTTP call                │   │
│  └─────────────────────────────────────────────────┘   │
└──────────────┬──────────────────────────────────────────┘
               │  POST /a2a  (JSON-RPC 2.0 over HTTP)
      ┌────────┴─────────┬─────────────────────┐
      ▼                  ▼                     ▼
 fetch-service      classify-service      respond-service
   :8001              :8002                  :8003
      │                  │                     │
 Gmail IMAP          Groq LLM              Groq LLM
                  (Llama-3.3-70b)       (Llama-3.1-8b)
```

**Three independent microservices**, each a standalone FastAPI application:

| Service | Port | Responsibility | A2A Method |
|---------|------|---------------|------------|
| `fetch-service` | 8001 | Connects to IMAP / generates demo emails | `email_fetch` |
| `classify-service` | 8002 | Classifies email using Groq Llama 3 | `email_classify` |
| `respond-service` | 8003 | Drafts a reply using Groq Llama 3 | `email_respond` |
| `supervisor` | 8080 | LangGraph graph coordinator + REST API | — |

**Each service exposes:**
- `GET /.well-known/agent.json` → capability card (A2A Agent Card)
- `GET /health` → liveness probe
- `POST /a2a` → JSON-RPC dispatcher (`tasks/send`)

**The supervisor** runs a LangGraph `StateGraph`. Instead of calling Python functions directly, each node makes an async HTTP request to the corresponding agent service using the A2A protocol. The services are fully independent — they can run on different machines, scale independently, and be replaced by any A2A-compliant implementation.

**Example A2A call** (what the supervisor does internally):
```http
POST http://classify-service:8002/a2a
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "params": {
    "input": {
      "method": "email_classify",
      "params": { "email": { "subject": "...", "body": "...", ... } }
    }
  },
  "id": "req_abc123"
}
```

Response:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "id": "task_xyz789",
    "status": "completed",
    "result": {
      "artifacts": [{
        "category": "urgent-action",
        "confidence": 0.90,
        "priority": 8,
        "reasoning": "Mentions Friday deadline and urgent language..."
      }]
    }
  }
}
```

---

### Run Locally (No Docker)

First, install the distributed extras:
```bash
pip install -e ".[distributed]"
# or if using pipx:
pipx install . --force && pipx inject inboxpilot fastapi uvicorn httpx
```

Then start each service in its own terminal:

```bash
PYTHON=~/.local/share/pipx/venvs/inboxpilot/bin/python
# OR: PYTHON=.venv/bin/python  (if using a venv)
ROOT=/path/to/InboxPilot-Agentic-App

# Terminal 1 — Fetch service (IMAP / demo email ingestion)
PYTHONPATH=$ROOT $PYTHON $ROOT/services/fetch-service/main.py

# Terminal 2 — Classify service (Groq Llama 70b)
PYTHONPATH=$ROOT $PYTHON $ROOT/services/classify-service/main.py

# Terminal 3 — Respond service (Groq Llama 8b)
PYTHONPATH=$ROOT $PYTHON $ROOT/services/respond-service/main.py

# Terminal 4 — Supervisor (must set localhost URLs — not in .env)
PYTHONPATH=$ROOT \
  FETCH_SERVICE_URL=http://localhost:8001 \
  CLASSIFY_SERVICE_URL=http://localhost:8002 \
  RESPOND_SERVICE_URL=http://localhost:8003 \
  $PYTHON $ROOT/services/supervisor/main.py
```

> The `FETCH_SERVICE_URL` / `CLASSIFY_SERVICE_URL` / `RESPOND_SERVICE_URL` env vars **must be set explicitly** when running locally. They are not in `.env` (to avoid conflicting with Docker Compose's internal DNS names like `http://fetch-service:8001`).

**Run the pipeline:**
```bash
# Via CLI (same Rich terminal output as monolith):
SUPERVISOR_URL=http://localhost:8080 inboxpilot-dist check --mode demo
SUPERVISOR_URL=http://localhost:8080 inboxpilot-dist check            # production

# Via REST API directly:
curl -X POST http://localhost:8080/pipeline/run \
     -H "Content-Type: application/json" \
     -d '{"mode": "demo"}'

# Check session state:
curl http://localhost:8080/pipeline/status/<session_id>

# Verify agent cards:
curl http://localhost:8001/.well-known/agent.json
curl http://localhost:8002/.well-known/agent.json
curl http://localhost:8003/.well-known/agent.json
```

---

### Run with Docker Compose

> **Requires:** Docker + Docker Compose installed.

```bash
# Build and start all 4 services
docker compose up --build

# In another terminal — run the pipeline
inboxpilot-dist check             # production mode
inboxpilot-dist check --mode demo # demo mode (no inbox needed)

# Stop everything
docker compose down
```

The supervisor auto-waits for all agent services to pass health checks before starting.

---

## Live Demo Output

Here is the actual output of running `inboxpilot-dist check --mode demo` against the Dockerized stack:

```
╭────────────────────────────────────╮
│ InboxPilot Distributed (DEMO MODE) │
│ Supervisor: http://localhost:8080  │
╰────────────────────────────────────╯
──────────────── Triggering distributed pipeline ────────────────
  Calling POST http://localhost:8080/pipeline/run ...
──────────────────────── Pipeline complete ───────────────────────
[20:28:29] [FETCH] Calling fetch-service via A2A (http://fetch-service:8001)
[20:28:29] [FETCH] Retrieved 5 emails

[20:28:29] [CLASSIFY] Email 1/5: "Q4 Budget Review - Need your input by Friday"
  [20:28:30]   → Category: urgent-action (confidence: 0.90)
  [20:28:30]   → Priority: 8/10 — The email mentions a deadline of Friday EOD
                             and an urgent gap that needs to be addressed ASAP.
[20:28:30] [RESPOND] Generating draft for email 1/5...
  [20:28:31]   → Draft created (70 words, confidence: 0.95)

[20:28:31] [CLASSIFY] Email 2/5: "Sync on API integration timeline"
  [20:28:31]   → Category: meeting-request (confidence: 0.90)
  [20:28:31]   → Priority: 6/10 — The email is a request to schedule a meeting.
[20:28:31] [RESPOND] Generating draft for email 2/5...
  [20:28:32]   → Draft created (65 words, confidence: 1.00)

[20:28:32] [CLASSIFY] Email 3/5: "Python Weekly - Issue 512"
  [20:28:32]   → Category: newsletter (confidence: 0.95)
  [20:28:32]   → Action: Archived / marked as newsletter

[20:28:32] [CLASSIFY] Email 4/5: "Build #4521 passed ✓"
  [20:28:33]   → Category: notification (confidence: 0.99)
  [20:28:33]   → Action: Archived / marked as notification

[20:28:33] [CLASSIFY] Email 5/5: "Lunch tomorrow?"
  [20:28:33]   → Category: personal (confidence: 0.90)
  [20:28:33]   → Action: Flagged for manual review

               Session Summary
╭────────────────────┬──────────────────────╮
│ Emails processed   │ 5                    │
│ Drafts created     │ 2 (pending approval) │
│ Archived           │ 2                    │
│ Flagged for review │ 1                    │
│ Session ID         │ sess_c65f5e56        │
╰────────────────────┴──────────────────────╯
```

Notice the service URLs in the log (`http://fetch-service:8001`) — that's Docker's internal DNS resolving between containers, proving the services are genuinely distributed across the network.

---

## CLI Reference

### Monolith CLI — `inboxpilot`

| Command | Description |
|---------|-------------|
| `inboxpilot check` | Run the full AI pipeline (direct, in-process) |
| `inboxpilot review` | Approve / edit / discard generated drafts |
| `inboxpilot learn` | Seed writing style samples into memory |
| `inboxpilot stats` | Session history and statistics |
| `inboxpilot config` | Interactive setup wizard |

### Distributed CLI — `inboxpilot-dist`

| Command | Description |
|---------|-------------|
| `inboxpilot-dist check` | Run the distributed A2A pipeline via supervisor |
| `inboxpilot-dist check --mode demo` | Demo mode (no inbox credentials) |
| `inboxpilot-dist check --supervisor-url URL` | Override supervisor URL |

---

## How It Works

### 1. The LangGraph State Machine

The supervisor runs a LangGraph `StateGraph` with four nodes. The graph holds a **`PipelineState`** dictionary in memory that accumulates results as the pipeline progresses:

```
       ┌──────────────────────────────────────────────────────────┐
       │                    PipelineState                         │
       │  session_id, mode, emails[], classifications{},          │
       │  drafts_created[], actions_taken[], errors[], log[]      │
       └──────────────────────────────────────────────────────────┘

                         START
                           │
                    ┌──────▼──────┐
                    │  fetch_node │  ← A2A call to fetch-service:8001
                    └──────┬──────┘
                  emails?  │  no emails
                  ┌────────┘       └──────────────────── END
                  ▼
           ┌──────────────┐
      ┌─── │ classify_node│  ← A2A call to classify-service:8002
      │    └──────┬───────┘
      │           │
      │    ┌──────▼───────────────────────────────────┐
      │    │  category?                               │
      │    │  urgent-action / meeting-request → RESPOND│
      │    │  newsletter / notification / spam → SKIP  │
      │    │  personal → FLAG                         │
      │    └──────┬───────────────────────────────────┘
      │           │ needs reply
      │    ┌──────▼──────┐
      │    │ respond_node│  ← A2A call to respond-service:8003
      │    └──────┬──────┘
      │           │
      │    ┌──────▼──────┐
      └─── │ advance_node│  ← increment email index
           └──────┬──────┘
                  │ more emails?    done?
                  └── classify ──────── END
```

### 2. What Each Agent Actually Does

#### `fetch-service` — Email Ingestion
- **Demo mode**: returns 5 hardcoded realistic emails (budget review, meeting request, newsletter, CI notification, personal lunch invite)
- **Production mode**: connects to Gmail (or any IMAP server) using your credentials, fetches up to `max_fetch` unseen emails from `INBOX`
- Returns a list of `EmailObject` dicts with `id`, `subject`, `body`, `sender`, `timestamp`, `thread_id`

#### `classify-service` — Groq-powered Classification
- Receives a single `EmailObject`
- Calls **Groq's `llama-3.3-70b-versatile`** (fast, free) with a structured system prompt
- Returns a `ClassificationResult` with:
  - `category` — one of: `urgent-action`, `meeting-request`, `newsletter`, `notification`, `personal`, `spam`
  - `confidence` — float 0–1
  - `priority` — int 1–10
  - `reasoning` — plain English explanation (shown in the CLI)
  - `suggested_action` — what the agent recommends

#### `respond-service` — Draft Generation
- Receives both the `EmailObject` and its `ClassificationResult`
- Calls **Groq's `llama-3.1-8b-instant`** (lightweight, fast for generation)
- Adjusts tone based on category:
  - `urgent-action` → direct, action-focused
  - `meeting-request` → includes proposed calendar slots (Thu 2pm, Fri 10am, Mon 3pm)
- Returns a `DraftObject` with `draft_id`, `subject`, `body`, `word_count`, `confidence`
- **Never sends the email** — the draft is saved and requires approval via `inboxpilot review`

### 3. How Routing Decisions Work

After every `classify_node` call, the LangGraph router inspects `state["next_step"]`:

| `next_step` value | What happens |
|-------------------|--------------|
| `"respond"` | Email needs a reply → runs `respond_node` then `advance_node` |
| `"next_email"` | No reply needed (archived / flagged) → skips to `advance_node` |
| `"done"` | All emails processed → graph terminates at `END` |

This is pure Python logic inside the supervisor — **no external calls needed for routing**.

### Email Categories

| Category | Routing | Action taken |
|----------|---------|-------------|
| `urgent-action` | → respond | Draft reply created |
| `meeting-request` | → respond | Draft + calendar slots proposed |
| `newsletter` | → skip | Archived automatically |
| `notification` | → skip | Archived, no draft |
| `personal` | → skip | Flagged for manual review |
| `spam` | → skip | Archived automatically |

All drafts require **your explicit approval** via `inboxpilot review`. Nothing is ever sent automatically.

### 4. A2A Request / Response in Detail

Every inter-service call follows the JSON-RPC 2.0 format over HTTP:

**Request (supervisor → classify-service):**
```json
POST http://classify-service:8002/a2a

{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "params": {
    "input": {
      "method": "email_classify",
      "params": {
        "email": {
          "id": "demo_001",
          "subject": "Q4 Budget Review - Need your input by Friday",
          "body": "Hi team, the Q4 budget draft has a gap...",
          "sender": { "name": "Sarah", "email": "sarah@company.com" }
        }
      }
    }
  },
  "id": "req_a1b2c3"
}
```

**Response (classify-service → supervisor):**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "id": "task_x9y8z7",
    "status": "completed",
    "result": {
      "artifacts": [{
        "category": "urgent-action",
        "confidence": 0.90,
        "priority": 8,
        "reasoning": "Mentions Friday EOD deadline and urgent language.",
        "suggested_action": "Reply with budget feedback before Friday."
      }]
    }
  }
}
```

The A2A client automatically retries up to 3× with exponential backoff if a service is temporarily unreachable.

### 5. State at the End of a Run

After the pipeline completes, the supervisor stores the full `PipelineState` in memory. You can retrieve it:

```bash
curl http://localhost:8080/pipeline/status/<session_id>
```

This returns the complete state including all emails, every classification result, every draft, and the full timestamped log — useful for debugging or building a review UI on top.

---

## Project Structure

```
InboxPilot-Agentic-App/
│
├── inboxpilot/                    # Monolith package (inboxpilot check)
│   ├── agents/
│   │   ├── fetch_agent.py         # Email ingestion (IMAP + demo)
│   │   ├── classify_agent.py      # Groq classification
│   │   └── respond_agent.py       # Groq draft generation
│   ├── tools/
│   │   ├── imap_tool.py           # IMAP fetch (demo + real)
│   │   ├── calendar_tool.py       # Free slot suggestions
│   │   ├── draft_tool.py          # Save drafts to disk
│   │   ├── search_tool.py         # Mock web search
│   │   └── style_tool.py          # Writing style samples
│   ├── orchestrator.py            # LangGraph state machine (monolith)
│   ├── cli.py                     # `inboxpilot` CLI entry point
│   ├── db.py                      # In-memory DB + JSON persistence
│   ├── models.py                  # Pydantic data models
│   ├── state.py                   # LangGraph InboxState
│   └── config_loader.py           # YAML config + .env loader
│
├── a2a/                           # Shared A2A protocol library
│   ├── models.py                  # AgentCard, Task, A2ARequest/Response
│   ├── server.py                  # FastAPI base server (JSON-RPC dispatcher)
│   └── client.py                  # Async HTTP client with 3× retry
│
├── services/                      # Distributed microservices
│   ├── fetch-service/
│   │   ├── main.py                # A2A FastAPI agent wrapping fetch_agent
│   │   └── Dockerfile
│   ├── classify-service/
│   │   ├── main.py                # A2A FastAPI agent wrapping classify_agent
│   │   └── Dockerfile
│   ├── respond-service/
│   │   ├── main.py                # A2A FastAPI agent wrapping respond_agent
│   │   └── Dockerfile
│   └── supervisor/
│       ├── graph.py               # LangGraph StateGraph with A2A nodes
│       ├── main.py                # FastAPI supervisor REST API
│       ├── cli.py                 # `inboxpilot-dist` CLI
│       └── Dockerfile
│
├── scripts/                       # Local dev helper scripts
│   ├── run_all_services.py        # Start all 4 services in one command
│   ├── start_fetch.py
│   ├── start_classify.py
│   ├── start_respond.py
│   └── start_supervisor.py
│
├── docker-compose.yml             # Orchestrates all 4 services
├── Dockerfile.base                # Shared base image for all services
├── config.yaml                    # App settings (mode, models, IMAP, etc.)
├── main.py                        # Alt entry point: python main.py
├── .env                           # Credentials
└── pyproject.toml                 # Package metadata + dependencies
```

---

## Configuration (`config.yaml`)

```yaml
app:
  mode: "demo"          # "demo" | "production"

email:
  imap_host: "imap.gmail.com"
  imap_port: 993
  username: "${INBOX_EMAIL}"       # reads from .env
  password: "${INBOX_PASSWORD}"    # reads from .env
  max_fetch: 10
  mark_as_read: false              # keep false until you trust it

agents:
  classify:
    model: "llama-3.3-70b-versatile"
    temperature: 0.1        # low = consistent classification

  respond:
    model: "llama-3.1-8b-instant"
    temperature: 0.7        # higher = more varied writing
    require_approval: true  # never auto-sends
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Groq (Llama 3.3 70b + Llama 3.1 8b) — **free tier** |
| Agent orchestration | LangGraph StateGraph |
| Inter-agent protocol | Google A2A (JSON-RPC 2.0 over HTTP) |
| Microservice framework | FastAPI + Uvicorn |
| HTTP client | httpx (async, with retry) |
| Data models | Pydantic v2 |
| CLI | Click + Rich |
| Containerization | Docker + Docker Compose |
| Email | IMAP (imaplib) |

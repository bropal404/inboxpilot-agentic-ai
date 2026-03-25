# Writing dockerfiles and ignoring missing details to focus strictly on the skeleton
cat << 'DFEOF' > inboxpilot-agentic-ai/repo-server/Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY repo-server/main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
DFEOF

cat << 'DFEOF' > inboxpilot-agentic-ai/services/supervisor/Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY a2a/ a2a/
COPY services/supervisor/main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
DFEOF

cat << 'DFEOF' > inboxpilot-agentic-ai/services/agent-node/Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY a2a/ a2a/
COPY core/ core/
COPY services/agent-node/main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
DFEOF

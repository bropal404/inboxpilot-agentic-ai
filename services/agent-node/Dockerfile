FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY a2a/ a2a/
# Add an empty __init__.py so Python recognizes a2a as a package inside the docker image explicitly
RUN touch a2a/__init__.py
COPY core/ core/
COPY services/agent-node/main.py .
ENV PYTHONPATH=/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

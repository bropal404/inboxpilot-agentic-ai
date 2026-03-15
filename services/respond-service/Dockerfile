FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir -e ".[distributed]"

EXPOSE 8003
CMD ["uvicorn", "services.respond-service.main:app", "--host", "0.0.0.0", "--port", "8003"]

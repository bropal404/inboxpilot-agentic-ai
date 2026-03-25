FROM python:3.11-slim

# Create standard non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser platform.yaml .

# Switch to non-root user
USER appuser

# Start Uvicorn bound to dynamic PORT
CMD ["sh", "-c", "python -m src.main"]

# DS_PLATFORM

Platform infrastructure for dynamically hosting and interacting with Agentic AI applications.

## Requirements
- Docker and Docker Compose
- Unix-based environment (for running `init.sh`)

## Quick Start
1. Ensure Docker is running.
2. Run the initialization script to start all core platform services:
   ```bash
   ./init.sh
   ```
3. The platform services will be available at:
   - **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
   - **Orchestrator API:** [http://localhost:8000](http://localhost:8000)
   - **Kafka Broker:** `localhost:9092`
   - **MinIO S3 API:** `localhost:9000`
   - **MinIO Console:** [http://localhost:9001](http://localhost:9001) (Credentials: `admin` / `adminpassword`)
   - **Redis Store:** `localhost:6379`

## Deploying an App
1. Package your application into a `.tar.gz` archive. For example, to package `AGENTIC_AI_APP`:
   ```bash
   tar -czf app.tar.gz -C ../AGENTIC_AI_APP .
   ```
2. Open the [Frontend Dashboard](http://localhost:3000).
3. Under the **App Registry** section, select `app.tar.gz` and click **Upload & Deploy**.
4. The Orchestrator will dynamically assign a port, isolated Kafka Topics, a MinIO bucket, and start the app.

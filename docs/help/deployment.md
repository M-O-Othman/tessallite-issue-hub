# 5. Single Container Deployment

[Previous: Legacy Migration Tooling](migration.md) | [Home: Help Home](home.md) | [Next: Help Home](home.md)

---

The Issue Hub supports a standalone Single Container Deployment Architecture that packages both the database and the web service into an isolated container context.

### A. Merged Container Layout
To eliminate latency, complex network meshes, and multi-container overhead, the stack can be unified into a standalone Debian-based container (derived from `python:3.12-slim`) running both PostgreSQL and FastAPI simultaneously.

### B. Entrypoint Script (`entrypoint.sh`)
The container's execution flow is directed through a shell entrypoint script that handles full service initialization on boot:
1. **Directories & Permissions:** Creates required log directories and sets permissions for the `postgres` system role.
2. **Enforced UTF-8 Cluster:** Scans the data volume, and if empty, runs `initdb` with explicit `--encoding=UTF8` parameters.
3. **Database Bootstrap:** Starts PostgreSQL in the background, waits for readiness, creates database roles and schema if missing, and grants owner permissions.
4. **Automatic Migrations:** Executes Alembic upgrades (`alembic upgrade head`) to ensure tables and indexes are fully up-to-date.
5. **Application Server:** Starts `uvicorn` in the foreground on the configured port.

### C. Docker Compose Configuration
Deploying the stack locally uses standard volumes to store data persistently:
```yaml
services:
  app:
    build: .
    container_name: issue-hub-app
    ports:
      - "8080:8080" # Web UI & API
      - "5432:5432" # Published DB Port
    volumes:
      - pgdata:/var/lib/postgresql/data
      - .:/app
```
Data volume `pgdata` maps database cluster files outside the container, ensuring all records are kept durable across restarts and container rebuilds.

---

[Previous: Legacy Migration Tooling](migration.md) | [Home: Help Home](home.md) | [Next: Help Home](home.md)

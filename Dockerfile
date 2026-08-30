FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (No local PostgreSQL server installed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging configuration and source code
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY entrypoint.sh ./

# Install the Python package
RUN pip install --no-cache-dir .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

EXPOSE 8080

# Run everything through our unified entrypoint script
ENTRYPOINT ["/bin/bash", "./entrypoint.sh"]

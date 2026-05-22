FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
RUN pip install --no-cache-dir -e ".[worker]"

CMD ["python", "-m", "silver_platter.worker.main"]

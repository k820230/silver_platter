FROM python:3.11-slim

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ unixodbc unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[api,db]"

EXPOSE 8000
CMD ["uvicorn", "silver_platter.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

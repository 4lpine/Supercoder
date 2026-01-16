FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir requests colorama

# Copy application files
COPY main.py Agentic.py tools.py ./
COPY Agents/ ./Agents/

WORKDIR /workspace

ENTRYPOINT ["python", "/app/main.py"]

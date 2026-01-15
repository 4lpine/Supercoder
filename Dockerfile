FROM python:3.12-slim

WORKDIR /app

# Install readline development libraries for better terminal support
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreadline-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies with retries and longer timeout
RUN pip install --no-cache-dir --timeout 120 --retries 5 requests colorama pygments g4f gnureadline prompt_toolkit

# Copy app files
COPY main.py Agentic.py tools.py ./
COPY Agents/ ./Agents/

# Set up volume mount point for user's projects
VOLUME /workspace
WORKDIR /workspace

# Run supercoder
ENTRYPOINT ["python", "/app/main.py"]

FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir requests colorama pygments g4f

# Copy app files
COPY supercoder.py Agentic.py tools.py ./
COPY Agents/ ./Agents/

# Set up volume mount point for user's projects
VOLUME /workspace
WORKDIR /workspace

# Run supercoder
ENTRYPOINT ["python", "/app/supercoder.py"]

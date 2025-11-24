FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend files
COPY frontend/package*.json ./

# Install dependencies with explicit platform support
RUN npm install && \
    npm install @rollup/rollup-linux-x64-musl --save-optional

COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    libchromaprint-tools \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user with configurable UID/GID
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd -g ${USER_GID} appuser && \
    useradd -m -u ${USER_UID} -g appuser appuser

WORKDIR /app

# Copy backend requirements
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend/ ./backend/
COPY automate-troi-download.py ./

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create music directory and set ownership
RUN mkdir -p /music && \
    chown -R appuser:appuser /app /music

WORKDIR /app/backend

# Switch to non-root user
USER appuser:appuser

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
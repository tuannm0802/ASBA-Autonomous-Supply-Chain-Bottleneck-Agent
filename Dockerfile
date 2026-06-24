# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stage 1: Build the React Frontend
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FROM node:18-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stage 2: Create the Node.js + Python runner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FROM node:18-slim AS node-base
FROM python:3.11-slim

# Copy Node.js runtime and npm binaries from node-base
COPY --from=node-base /usr/local/include/ /usr/local/include/
COPY --from=node-base /usr/local/lib/ /usr/local/lib/
COPY --from=node-base /usr/local/bin/ /usr/local/bin/

# Install system dependencies (XGBoost requires libgomp1)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python ML dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js API dependencies
COPY backend/package.json backend/package-lock.json ./backend/
RUN npm install --prefix backend --only=production

# Copy static frontend assets built in Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy backend logic and configurations
COPY backend/ ./backend/
COPY agent/ ./agent/
COPY tools/ ./tools/
COPY config.py data_generator.py ./

# Create default directories and files
RUN mkdir -p data daily_reports && \
    python3 data_generator.py

# Configure Environment Variables
ENV PORT=8080
ENV NODE_ENV=production
EXPOSE 8080

WORKDIR /app/backend
CMD ["node", "server.js"]

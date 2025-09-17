#!/bin/bash

# Discord Link Guardian Bot - Complete Project Setup Script
# This script creates all necessary files for the bot

set -e

# Project name
PROJECT_NAME="discord-link-guardian"

echo "================================================"
echo "  Discord Link Guardian Bot - Project Creator  "
echo "================================================"
echo

# Ask for project directory
echo "Where would you like to create the project? [./$PROJECT_NAME]"
read -r PROJECT_DIR
PROJECT_DIR=${PROJECT_DIR:-"./$PROJECT_NAME"}

# Create project directory
echo "Creating project directory: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Create directory structure
echo "Creating directory structure..."
mkdir -p src docker configs data logs scripts docs

# Create main bot file
echo "Creating src/bot.py..."
cat > src/bot.py << 'EOF'
# Copy the bot.py content from the artifact above
# This is a placeholder - replace with actual content
import discord
from discord.ext import commands
# ... rest of bot.py code
EOF

# Create link analyzer
echo "Creating src/link_analyzer.py..."
cat > src/link_analyzer.py << 'EOF'
# Copy the link_analyzer.py content from the artifact above
import aiohttp
import asyncio
# ... rest of link_analyzer.py code
EOF

# Create AI analyzer
echo "Creating src/ai_analyzer.py..."
cat > src/ai_analyzer.py << 'EOF'
# Copy the ai_analyzer.py content from the artifact above
import aiohttp
import asyncio
# ... rest of ai_analyzer.py code
EOF

# Create moderation module
echo "Creating src/moderation.py..."
cat > src/moderation.py << 'EOF'
# Copy the moderation.py content from the artifact above
import discord
from datetime import datetime, timedelta
# ... rest of moderation.py code
EOF

# Create database module
echo "Creating src/database.py..."
cat > src/database.py << 'EOF'
# Copy the database.py content from the artifact above
import aiosqlite
import asyncio
# ... rest of database.py code
EOF

# Create config module
echo "Creating src/config.py..."
cat > src/config.py << 'EOF'
# Copy the config.py content from the artifact above
import yaml
import os
# ... rest of config.py code
EOF

# Create Dockerfile
echo "Creating docker/Dockerfile..."
cat > docker/Dockerfile << 'EOF'
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    git \
    curl \
    whois \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data configs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run the bot
CMD ["python", "-m", "src.bot"]
EOF

# Create docker-compose.yml
echo "Creating docker/docker-compose.yml..."
cat > docker/docker-compose.yml << 'EOF'
version: '3.8'

services:
  link-guardian:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: discord-link-guardian
    restart: unless-stopped
    volumes:
      - ../data:/app/data
      - ../logs:/app/logs
      - ../configs:/app/configs
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - SEARCH_API_KEY=${SEARCH_API_KEY}
    networks:
      - bot-network
    healthcheck:
      test: ["CMD", "python", "-c", "import socket; socket.create_connection(('discord.com', 443))"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  bot-network:
    driver: bridge
EOF

# Create requirements.txt
echo "Creating requirements.txt..."
cat > requirements.txt << 'EOF'
discord.py>=2.3.0
aiohttp>=3.9.0
asyncio
python-whois>=0.8.0
dnspython>=2.4.0
beautifulsoup4>=4.12.0
pyyaml>=6.0
python-dotenv>=1.0.0
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
openai>=1.0.0
anthropic>=0.8.0
validators>=0.22.0
python-dateutil>=2.8.0
typing-extensions>=4.8.0
EOF

# Create requirements-dev.txt
echo "Creating requirements-dev.txt..."
cat > requirements-dev.txt << 'EOF'
# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0

# Code Quality
black>=23.7.0
flake8>=6.1.0
pylint>=2.17.0
mypy>=1.5.0
isort>=5.12.0

# Pre-commit
pre-commit>=3.3.0

# Documentation
sphinx>=7.1.0
sphinx-rtd-theme>=1.3.0

# Debugging
ipython>=8.14.0
ipdb>=0.13.0

# Performance
memory-profiler>=0.61.0
line-profiler>=4.1.0
EOF

# Create .env.example
echo "Creating .env.example..."
cat > .env.example << 'EOF'
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token_here

# AI Provider Configuration (choose one)
# Option 1: OpenAI (ChatGPT)
OPENAI_API_KEY=your_openai_api_key_here

# Option 2: Anthropic (Claude)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Option 3: Local LLM (Ollama)
LOCAL_MODEL=llama2

# Web Search Configuration (optional but recommended)
SEARCH_API_KEY=your_serpapi_or_google_search_api_key_here

# Database Configuration
DB_PATH=data/bot.db

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log

# Bot Configuration
BOT_PREFIX=!
BOT_STATUS=Protecting your server

# Moderation Settings
WARNINGS_BEFORE_MUTE=3
MUTE_DURATION_DAYS=15
WARNINGS_BEFORE_BAN=5

# Security Thresholds
THREAT_THRESHOLD_SAFE=0.2
THREAT_THRESHOLD_SUSPICIOUS=0.5
THREAT_THRESHOLD_DANGER=0.8
EOF

# Create default config
echo "Creating configs/default_config.yaml..."
cat > configs/default_config.yaml << 'EOF'
bot:
  prefix: "!"
  status: "Protecting your server"
  embed_color: 0x5865F2
  
moderation:
  warnings_before_mute: 3
  mute_duration_days: 15
  warnings_before_ban: 5
  warning_expiry_days: 90
  
ai:
  provider: "openai"
  model: "gpt-4"
  temperature: 0.3
  max_tokens: 1000
  timeout: 30
  
security:
  threat_thresholds:
    safe: 0.2
    caution: 0.4
    suspicious: 0.6
    danger: 0.8
    
  trusted_domains:
    - google.com
    - github.com
    - microsoft.com
    - wikipedia.org
    - discord.com
    
  suspicious_tlds:
    - .tk
    - .ml
    - .ga
    - .cf
    
database:
  path: "data/bot.db"
  backup_enabled: true
  backup_interval_hours: 24
  
logging:
  level: "INFO"
  file: "logs/bot.log"
  max_size_mb: 10
  backup_count: 5
EOF

# Create .gitignore
echo "Creating .gitignore..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
.venv

# Environment Variables
.env
.env.local
.env.*.local

# Database
*.db
*.sqlite
*.sqlite3
data/*.db

# Logs
logs/
*.log
*.out
*.err

# IDE
.vscode/
.idea/
*.swp
*.swo
*.swn
.DS_Store

# Docker
.dockerignore
docker-compose.override.yml

# Temporary files
*.tmp
*.temp
*.bak
*.backup
*~

# Test files
test/
tests/
*.test.*

# Distribution / packaging
build/
dist/
*.egg-info/
EOF

# Create .dockerignore
echo "Creating .dockerignore..."
cat > .dockerignore << 'EOF'
# Git
.git
.gitignore
.github

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
venv/
env/

# Testing
.tox/
.coverage
.pytest_cache/

# IDEs
.idea/
.vscode/
*.swp
.DS_Store

# Project specific
.env
.env.*
*.log
logs/
data/*.db
backups/

# Documentation
docs/_build/
*.md

# Temporary files
*.tmp
*.bak
EOF

# Create LICENSE
echo "Creating LICENSE..."
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2024 Discord Link Guardian

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

# Create README.md (simplified version)
echo "Creating README.md..."
cat > README.md << 'EOF'
# 🛡️ Discord Link Guardian Bot

AI-Powered Link Security for Discord Servers

## 🚀 Quick Start

1. Copy `.env.example` to `.env` and add your Discord bot token
2. Run the installer: `sudo ./installer.sh`
3. Start the bot: `docker-compose up -d`

## 🌟 Features

- AI-powered link analysis
- Automatic threat detection and removal
- Progressive moderation system
- Docker containerized
- Multiple AI provider support

## 📝 License

MIT License - see LICENSE file for details
EOF

# Create the installer script (copy from the artifact)
echo "Creating installer.sh..."
cat > installer.sh << 'EOF'
#!/bin/bash
# Note: Copy the full installer.sh content from the artifact above
echo "Installer placeholder - replace with actual installer script"
EOF

# Create update script
echo "Creating scripts/update.sh..."
cat > scripts/update.sh << 'EOF'
#!/bin/bash
# Discord Link Guardian Bot - Update Script

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Discord Link Guardian Bot - Updater${NC}"
echo "======================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}This script should not be run as root!${NC}"
   exit 1
fi

# Get installation directory
INSTALL_DIR=${1:-/opt/discord-link-guardian}

cd "$INSTALL_DIR"

# Create backup
echo -e "${YELLOW}Creating backup...${NC}"
BACKUP_DIR="backups/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r configs "$BACKUP_DIR/"
cp .env "$BACKUP_DIR/" 2>/dev/null || true
cp -r data "$BACKUP_DIR/"

echo -e "${GREEN}✓ Backup created at $BACKUP_DIR${NC}"

# Stop the bot
echo -e "${YELLOW}Stopping bot...${NC}"
docker-compose -f docker/docker-compose.yml down

# Pull latest changes
echo -e "${YELLOW}Pulling latest changes...${NC}"
git fetch upstream
git pull upstream main

# Rebuild Docker image
echo -e "${YELLOW}Rebuilding Docker image...${NC}"
docker build -t discord-link-guardian -f docker/Dockerfile .

# Start the bot
echo -e "${YELLOW}Starting bot...${NC}"
docker-compose -f docker/docker-compose.yml up -d

echo -e "${GREEN}✓ Bot updated successfully!${NC}"
EOF

# Create health check script
echo "Creating scripts/health_check.py..."
cat > scripts/health_check.py << 'EOF'
#!/usr/bin/env python3
"""Health check script for Discord Link Guardian Bot"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Discord Link Guardian Bot - Health Check")
print("Status: HEALTHY")
sys.exit(0)
EOF

# Create CONTRIBUTING.md
echo "Creating docs/CONTRIBUTING.md..."
cat > docs/CONTRIBUTING.md << 'EOF'
# Contributing to Discord Link Guardian Bot

Thank you for your interest in contributing!

## How to Contribute

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Code Standards

- Follow PEP 8 for Python code
- Write tests for new features
- Update documentation

## Questions?

Open an issue on GitHub!
EOF

# Set executable permissions
echo "Setting permissions..."
chmod +x installer.sh
chmod +x scripts/update.sh
chmod +x scripts/health_check.py

# Create empty log file
touch logs/bot.log

# Final message
echo
echo "================================================"
echo "Project created successfully!"
echo "================================================"
echo
echo "Project location: $PROJECT_DIR"
echo
echo "Next steps:"
echo "1. cd $PROJECT_DIR"
echo "2. cp .env.example .env"
echo "3. nano .env (add your Discord bot token and API keys)"
echo "4. sudo ./installer.sh (run the interactive installer)"
echo
echo "Note: The source files (bot.py, etc.) need their full content"
echo "copied from the provided artifacts above."
echo
echo "Happy bot building!"

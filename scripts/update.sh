---

### 5️⃣ **scripts/update.sh**
```bash
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

if [[ ! -d "$INSTALL_DIR" ]]; then
    echo -e "${RED}Installation directory not found: $INSTALL_DIR${NC}"
    exit 1
fi

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

# Update dependencies
echo -e "${YELLOW}Updating dependencies...${NC}"
pip install -r requirements.txt --upgrade

# Rebuild Docker image
echo -e "${YELLOW}Rebuilding Docker image...${NC}"
docker build -t discord-link-guardian -f docker/Dockerfile .

# Run database migrations if needed
if [[ -f "scripts/migrate.py" ]]; then
    echo -e "${YELLOW}Running database migrations...${NC}"
    python scripts/migrate.py
fi

# Start the bot
echo -e "${YELLOW}Starting bot...${NC}"
docker-compose -f docker/docker-compose.yml up -d

# Check if running
sleep 5
if docker ps | grep -q discord-link-guardian; then
    echo -e "${GREEN}✓ Bot updated and running successfully!${NC}"
    echo -e "${GREEN}View logs: docker logs -f discord-link-guardian${NC}"
else
    echo -e "${RED}Bot failed to start. Rolling back...${NC}"
    cp -r "$BACKUP_DIR/"* .
    docker-compose -f docker/docker-compose.yml up -d
    echo -e "${YELLOW}Rolled back to previous version${NC}"
    exit 1
fi

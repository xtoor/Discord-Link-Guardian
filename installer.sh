#!/bin/bash

# Discord Link Guardian Bot - Interactive Installer
# Supports Ubuntu VM with Docker

set -e

# Logging
LOG_FILE="install_$(date +%Y%m%d_%H%M%S).log"
exec 2> >(tee -a "$LOG_FILE" >&2)

# Functions
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    echo "[ERROR] $1" | tee -a "$LOG_FILE"
}

warning() {
    echo "[WARNING] $1" | tee -a "$LOG_FILE"
}

info() {
    echo "[INFO] $1" | tee -a "$LOG_FILE"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_ubuntu() {
    if [[ ! -f /etc/os-release ]]; then
        error "Cannot detect OS version"
        exit 1
    fi
    
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]]; then
        warning "This installer is optimized for Ubuntu. Continue anyway? (y/n)"
        read -r response
        if [[ "$response" != "y" ]]; then
            exit 1
        fi
    fi
}

check_dependency() {
    local cmd=$1
    local package=$2
    local install_cmd=$3
    
    if command -v "$cmd" &> /dev/null; then
        info "$cmd is already installed"
        return 0
    else
        warning "$cmd is not installed"
        echo "Would you like to install $package? (y/n)"
        read -r response
        if [[ "$response" == "y" ]]; then
            log "Installing $package..."
            eval "$install_cmd"
            return 0
        else
            return 1
        fi
    fi
}

install_docker() {
    log "Checking Docker installation..."
    
    if command -v docker &> /dev/null; then
        info "Docker is already installed"
        
        # Check if Docker needs updating
        DOCKER_VERSION=$(docker --version | grep -oP '\d+\.\d+\.\d+')
        info "Current Docker version: $DOCKER_VERSION"
        
        echo "Would you like to update Docker? (y/n)"
        read -r response
        if [[ "$response" == "y" ]]; then
            apt-get update
            apt-get install -y docker-ce docker-ce-cli containerd.io
        fi
    else
        log "Installing Docker..."
        
        # Remove old versions
        apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
        
        # Install prerequisites
        apt-get update
        apt-get install -y \
            ca-certificates \
            curl \
            gnupg \
            lsb-release
        
        # Add Docker's official GPG key
        mkdir -p /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        
        # Set up the repository
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
          $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # Install Docker Engine
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        
        # Start and enable Docker
        systemctl start docker
        systemctl enable docker
        
        info "Docker installed successfully"
    fi
    
    # Test Docker installation
    if docker run hello-world &>/dev/null; then
        info "Docker is working correctly"
    else
        error "Docker installation test failed"
        exit 1
    fi
}

install_docker_compose() {
    log "Checking Docker Compose installation..."
    
    if command -v docker-compose &> /dev/null; then
        info "Docker Compose is already installed"
        COMPOSE_VERSION=$(docker-compose --version | grep -oP '\d+\.\d+\.\d+')
        info "Current Docker Compose version: $COMPOSE_VERSION"
    else
        log "Installing Docker Compose..."
        
        # Install Docker Compose V2
        apt-get update
        apt-get install -y docker-compose-plugin
        
        # Create symlink for compatibility
        ln -sf /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
        
        info "Docker Compose installed successfully"
    fi
}

setup_project() {
    log "Setting up project structure..."
    
    # Get installation directory
    echo "Where would you like to install the bot? [/opt/discord-link-guardian]"
    read -r INSTALL_DIR
    INSTALL_DIR=${INSTALL_DIR:-/opt/discord-link-guardian}
    
    # Create directory structure
    mkdir -p "$INSTALL_DIR"/{src,configs,logs,data,docker}
    
    # Download or copy project files
    if [[ -d ./src ]]; then
        log "Copying project files..."
        cp -r ./src/* "$INSTALL_DIR/src/"
        cp -r ./docker/* "$INSTALL_DIR/docker/"
        cp ./requirements.txt "$INSTALL_DIR/"
    else
        log "Downloading project files from repository..."
        # Clone from your repository
        git clone https://github.com/yourusername/discord-link-guardian.git "$INSTALL_DIR/temp"
        mv "$INSTALL_DIR/temp/"* "$INSTALL_DIR/"
        rm -rf "$INSTALL_DIR/temp"
    fi
    
    cd "$INSTALL_DIR"
}

configure_bot() {
    log "Configuring the bot..."
    
    # Create .env file
    ENV_FILE="$INSTALL_DIR/.env"
    
    echo "=== Bot Configuration ==="
    echo
    
    # Discord Token
    echo "Enter your Discord Bot Token:"
    read -rs DISCORD_TOKEN
    echo "DISCORD_TOKEN=$DISCORD_TOKEN" > "$ENV_FILE"
    
    # AI Provider Selection
    echo
    echo "Select AI provider for link analysis:"
    echo "1) OpenAI (ChatGPT)"
    echo "2) Anthropic (Claude)"
    echo "3) Local LLM (Ollama)"
    echo "4) None (basic analysis only)"
    read -r AI_CHOICE
    
    case $AI_CHOICE in
        1)
            echo "Enter your OpenAI API Key:"
            read -rs OPENAI_KEY
            echo "OPENAI_API_KEY=$OPENAI_KEY" >> "$ENV_FILE"
            AI_PROVIDER="openai"
            ;;
        2)
            echo "Enter your Anthropic API Key:"
            read -rs ANTHROPIC_KEY
            echo "ANTHROPIC_API_KEY=$ANTHROPIC_KEY" >> "$ENV_FILE"
            AI_PROVIDER="anthropic"
            ;;
        3)
            AI_PROVIDER="local"
            echo "Installing Ollama..."
            curl -fsSL https://ollama.ai/install.sh | sh
            echo "Which model would you like to use? (e.g., llama2, mistral)"
            read -r LOCAL_MODEL
            ollama pull "$LOCAL_MODEL"
            echo "LOCAL_MODEL=$LOCAL_MODEL" >> "$ENV_FILE"
            ;;
        4)
            AI_PROVIDER="none"
            ;;
    esac
    
    # Search API
    echo
    echo "Would you like to enable web reputation search? (y/n)"
    read -r response
    if [[ "$response" == "y" ]]; then
        echo "Enter your search API key (SerpAPI/Google Custom Search):"
        read -rs SEARCH_KEY
        echo "SEARCH_API_KEY=$SEARCH_KEY" >> "$ENV_FILE"
    fi
    
    # Create config file
    cat > "$INSTALL_DIR/configs/config.yaml" <<EOF
bot:
  prefix: "!"
  status: "Protecting your server"
  
ai:
  provider: "$AI_PROVIDER"
  model: "${AI_MODEL:-gpt-4}"
  
moderation:
  warnings_before_mute: 3
  mute_duration_days: 15
  warnings_before_ban: 5
  
database:
  path: "data/bot.db"
  
logging:
  level: "INFO"
  file: "logs/bot.log"
  
security:
  trusted_domains:
    - google.com
    - github.com
    - microsoft.com
    - wikipedia.org
    
  suspicious_tlds:
    - .tk
    - .ml
    - .ga
    - .cf
EOF
    
    info "Configuration complete"
}

build_docker_image() {
    log "Building Docker image..."
    
    cd "$INSTALL_DIR"
    
    # Build the Docker image
    docker build -t discord-link-guardian -f docker/Dockerfile .
    
    if [[ $? -eq 0 ]]; then
        info "Docker image built successfully"
    else
        error "Failed to build Docker image"
        exit 1
    fi
}

test_installation() {
    log "Testing installation..."
    
    # Test Docker container
    docker run --rm \
        -v "$INSTALL_DIR/data:/app/data" \
        -v "$INSTALL_DIR/logs:/app/logs" \
        -v "$INSTALL_DIR/configs:/app/configs" \
        --env-file "$INSTALL_DIR/.env" \
        discord-link-guardian python -c "
import sys
import discord
from src.bot import LinkGuardianBot
print('All imports successful')
sys.exit(0)
"
    
    if [[ $? -eq 0 ]]; then
        info "Installation test passed"
    else
        error "Installation test failed. Check $LOG_FILE for details"
        exit 1
    fi
}

create_systemd_service() {
    log "Creating systemd service..."
    
    echo "Would you like to set up auto-start on boot? (y/n)"
    read -r response
    
    if [[ "$response" == "y" ]]; then
        cat > /etc/systemd/system/discord-link-guardian.service <<EOF
[Unit]
Description=Discord Link Guardian Bot
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=10
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/docker-compose -f $INSTALL_DIR/docker/docker-compose.yml up
ExecStop=/usr/bin/docker-compose -f $INSTALL_DIR/docker/docker-compose.yml down

[Install]
WantedBy=multi-user.target
EOF
        
        systemctl daemon-reload
        systemctl enable discord-link-guardian.service
        
        info "Systemd service created and enabled"
    fi
}

start_bot() {
    log "Starting the bot..."
    
    cd "$INSTALL_DIR"
    
    echo "Would you like to start the bot now? (y/n)"
    read -r response
    
    if [[ "$response" == "y" ]]; then
        docker-compose -f docker/docker-compose.yml up -d
        
        # Check if container is running
        sleep 5
        if docker ps | grep -q discord-link-guardian; then
            info "Bot is running!"
            info "View logs: docker logs -f discord-link-guardian"
            info "Stop bot: docker-compose -f $INSTALL_DIR/docker/docker-compose.yml down"
        else
            error "Bot failed to start. Check logs: docker logs discord-link-guardian"
        fi
    fi
}

cleanup() {
    log "Cleaning up..."
    apt-get autoremove -y
    apt-get autoclean
}

print_summary() {
    echo
    echo "========================================"
    echo "   Discord Link Guardian Installation   "
    echo "          Summary & Commands            "
    echo "========================================"
    echo
    info "Installation directory: $INSTALL_DIR"
    info "Configuration file: $INSTALL_DIR/configs/config.yaml"
    info "Environment file: $INSTALL_DIR/.env"
    info "Logs directory: $INSTALL_DIR/logs"
    echo
    echo "Useful Commands:"
    echo "  Start bot:    docker-compose -f $INSTALL_DIR/docker/docker-compose.yml up -d"
    echo "  Stop bot:     docker-compose -f $INSTALL_DIR/docker/docker-compose.yml down"
    echo "  View logs:    docker logs -f discord-link-guardian"
    echo "  Restart bot:  docker-compose -f $INSTALL_DIR/docker/docker-compose.yml restart"
    echo "  Update bot:   cd $INSTALL_DIR && git pull && docker-compose build"
    echo
    echo "Service Management (if enabled):"
    echo "  Start:   systemctl start discord-link-guardian"
    echo "  Stop:    systemctl stop discord-link-guardian"
    echo "  Status:  systemctl status discord-link-guardian"
    echo "  Logs:    journalctl -u discord-link-guardian -f"
    echo
    echo "Installation log saved to: $LOG_FILE"
    echo
    info "Installation complete!"
}

# Main installation flow
main() {
    clear
    echo "========================================"
    echo "   Discord Link Guardian Bot Installer  "
    echo "        Version 1.0.0                   "
    echo "========================================"
    echo
    
    log "Starting installation..."
    
    # Check prerequisites
    check_root
    check_ubuntu
    
    # Install dependencies
    log "Checking and installing dependencies..."
    apt-get update
    
    check_dependency "git" "git" "apt-get install -y git"
    check_dependency "curl" "curl" "apt-get install -y curl"
    check_dependency "python3" "python3" "apt-get install -y python3 python3-pip"
    
    # Install Docker
    install_docker
    install_docker_compose
    
    # Setup project
    setup_project
    
    # Configure bot
    configure_bot
    
    # Build Docker image
    build_docker_image
    
    # Test installation
    test_installation
    
    # Create systemd service
    create_systemd_service
    
    # Start bot
    start_bot
    
    # Cleanup
    cleanup
    
    # Print summary
    print_summary
}

# Run main function
main

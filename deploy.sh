#!/bin/bash

# ============================================
# Lily Music TG - Server Deployment Script
# ============================================
# This script deploys the bot to your VPS via SSH

# Server Configuration
SERVER_IP="161.118.250.195"
SERVER_USER="root"
SERVER_PORT="22"
DEPLOY_DIR="/opt/LilyMusicTG"

# Git Repository
GIT_REPO="https://github.com/nishkarshk212/Lily_music_tg.git"
GIT_BRANCH="main"

echo "🚀 Starting Lily Music TG Deployment..."
echo "📡 Server: $SERVER_USER@$SERVER_IP:$SERVER_PORT"
echo ""

# Step 1: Test SSH Connection
echo "🔑 Testing SSH connection..."
sshpass -p "Akshay343402355468" ssh -p $SERVER_PORT -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP "echo '✅ SSH Connection Successful'"

if [ $? -ne 0 ]; then
    echo "❌ SSH connection failed. Please check your credentials."
    exit 1
fi

# Step 2: Install sshpass if not available
if ! command -v sshpass &> /dev/null; then
    echo "📦 Installing sshpass..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install sshpass
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y sshpass
    fi
fi

# Step 3: Create deployment directory on server
echo "📁 Creating deployment directory..."
sshpass -p "Akshay343402355468" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP << 'ENDSSH'
mkdir -p /opt/LilyMusicTG
cd /opt/LilyMusicTG
ENDSSH

# Step 4: Clone or update repository
echo "📦 Cloning/Updating repository..."
sshpass -p "Akshay343402355468" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP << ENDSSH
cd /opt/LilyMusicTG

if [ -d ".git" ]; then
    echo "📥 Updating existing repository..."
    git pull origin $GIT_BRANCH
else
    echo "📥 Cloning fresh repository..."
    git clone $GIT_REPO .
    git checkout $GIT_BRANCH
fi
ENDSSH

# Step 5: Setup Python virtual environment
echo "🐍 Setting up Python virtual environment..."
sshpass -p "Akshay343402355468" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP << 'ENDSSH'
cd /opt/LilyMusicTG

# Install Python and dependencies if needed
if ! command -v python3 &> /dev/null; then
    echo "Installing Python 3..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv ffmpeg
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
ENDSSH

# Step 6: Upload .env file
echo "🔐 Uploading environment configuration..."
if [ -f ".env" ]; then
    sshpass -p "Akshay343402355468" scp -P $SERVER_PORT .env $SERVER_USER@$SERVER_IP:/opt/LilyMusicTG/.env
    echo "✅ .env file uploaded successfully"
else
    echo "⚠️  .env file not found in current directory!"
    echo "Please create .env file first or upload it manually:"
    echo "sshpass -p 'Akshay343402355468' scp -P 22 .env root@161.118.250.195:/opt/LilyMusicTG/.env"
fi

# Step 7: Create systemd service file
echo "⚙️  Creating systemd service..."
sshpass -p "Akshay343402355468" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP << 'ENDSSH'
cat > /etc/systemd/system/lilymusic.service << EOF
[Unit]
Description=Lily Music TG Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/LilyMusicTG
ExecStart=/opt/LilyMusicTG/venv/bin/python3 -m AnnieXMedia
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable lilymusic
ENDSSH

# Step 8: Start the bot
echo "🎵 Starting Lily Music TG bot..."
sshpass -p "Akshay343402355468" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP << 'ENDSSH'
systemctl restart lilymusic
sleep 3
systemctl status lilymusic --no-pager
ENDSSH

echo ""
echo "✅ Deployment Complete!"
echo ""
echo "📊 Useful Commands:"
echo "   Check status:    sshpass -p 'Akshay343402355468' ssh -p 22 root@161.118.250.195 'systemctl status lilymusic'"
echo "   View logs:       sshpass -p 'Akshay343402355468' ssh -p 22 root@161.118.250.195 'journalctl -u lilymusic -f'"
echo "   Restart bot:     sshpass -p 'Akshay343402355468' ssh -p 22 root@161.118.250.195 'systemctl restart lilymusic'"
echo "   Stop bot:        sshpass -p 'Akshay343402355468' ssh -p 22 root@161.118.250.195 'systemctl stop lilymusic'"
echo ""
echo "🔐 SSH Access:"
echo "   sshpass -p 'Akshay343402355468' ssh -p 22 root@161.118.250.195"
echo ""

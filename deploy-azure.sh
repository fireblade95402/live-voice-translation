#!/bin/bash
# Azure Container Apps Deployment - Quick Start
# This script helps you deploy the Live Voice Translation app to Azure

echo "🚀 Live Voice Translation - Azure Deployment"
echo "============================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check if azd is installed
if ! command -v azd &> /dev/null; then
    echo "❌ Azure Developer CLI (azd) is not installed"
    echo "   Install with: curl -fsSL https://aka.ms/install-azd.sh | bash"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    echo "   Install from: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Check if Docker is running
if ! docker ps &> /dev/null; then
    echo "❌ Docker is not running"
    echo "   Start Docker Desktop and try again"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Login to Azure
echo "Logging in to Azure..."
azd auth login
if [ $? -ne 0 ]; then
    echo "❌ Azure login failed"
    exit 1
fi

# Get Azure VoiceLive endpoint
echo ""
echo "Enter your Azure VoiceLive endpoint:"
echo "Example: https://your-resource.services.ai.azure.com/"
read -p "Endpoint: " endpoint

if [ -z "$endpoint" ]; then
    echo "❌ Endpoint is required"
    exit 1
fi

# Set environment variable
azd env set AZURE_VOICELIVE_ENDPOINT "$endpoint"

# Optional: Voice setting
echo ""
echo "Voice setting (press Enter for default: en-US-Ava:DragonHDLatestNeural):"
read -p "Voice: " voice
if [ ! -z "$voice" ]; then
    azd env set AZURE_VOICELIVE_VOICE "$voice"
fi

# Deploy
echo ""
echo "🚀 Starting deployment to Azure..."
echo "This will:"
echo "  1. Create Azure resources (Container Registry, Container App, etc.)"
echo "  2. Build Docker image"
echo "  3. Push to Container Registry"
echo "  4. Deploy Container App"
echo "  5. Configure networking and security"
echo ""

read -p "Continue? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Deployment cancelled"
    exit 0
fi

# Run azd up
azd up

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment successful!"
    echo ""
    echo "Your application is now running on Azure Container Apps"
    echo "Get the URL with: azd env get-values | grep AZURE_CONTAINER_APP_ENDPOINT"
    echo "View logs with: azd monitor"
else
    echo ""
    echo "❌ Deployment failed"
    echo "Check the error messages above for details"
    echo "Get help: See DEPLOYMENT.md for troubleshooting"
fi

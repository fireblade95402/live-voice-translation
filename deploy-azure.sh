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

# Get Azure Speech resource details
echo ""
echo "Enter the full resource ID of your Azure Speech / AI Services resource:"
echo "Example: /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<name>"
read -p "Resource ID: " speech_id

if [ -z "$speech_id" ]; then
    echo "❌ Speech resource ID is required"
    exit 1
fi

echo ""
echo "Enter the Azure region of that Speech resource (e.g. swedencentral, eastus2):"
read -p "Region: " speech_region

if [ -z "$speech_region" ]; then
    echo "❌ Speech region is required"
    exit 1
fi

azd env set AZURE_SPEECH_RESOURCE_ID "$speech_id"
azd env set AZURE_SPEECH_REGION "$speech_region"

# Optional: default voice
echo ""
echo "Default neural voice (press Enter for en-US-AvaMultilingualNeural):"
read -p "Voice: " voice
if [ ! -z "$voice" ]; then
    azd env set AZURE_SPEECH_DEFAULT_VOICE "$voice"
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

# Azure Container Apps Deployment - Quick Start
# This script helps you deploy the Live Voice Translation app to Azure

Write-Host "🚀 Live Voice Translation - Azure Deployment" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check if azd is installed
if (!(Get-Command azd -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Azure Developer CLI (azd) is not installed" -ForegroundColor Red
    Write-Host "   Install with: winget install microsoft.azd" -ForegroundColor Yellow
    exit 1
}

# Check if Docker is installed
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed" -ForegroundColor Red
    Write-Host "   Install Docker Desktop from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}

# Check if Docker is running
try {
    docker ps | Out-Null
} catch {
    Write-Host "❌ Docker is not running" -ForegroundColor Red
    Write-Host "   Start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Prerequisites check passed`n" -ForegroundColor Green

# Login to Azure
Write-Host "Logging in to Azure..." -ForegroundColor Yellow
azd auth login
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Azure login failed" -ForegroundColor Red
    exit 1
}

# Get Azure Speech resource details
Write-Host "`nEnter the full resource ID of your Azure Speech / AI Services resource:" -ForegroundColor Yellow
Write-Host "Example: /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<name>" -ForegroundColor Gray
$speechId = Read-Host "Resource ID"

if ([string]::IsNullOrWhiteSpace($speechId)) {
    Write-Host "❌ Speech resource ID is required" -ForegroundColor Red
    exit 1
}

Write-Host "`nEnter the Azure region of that Speech resource (e.g. swedencentral, eastus2):" -ForegroundColor Yellow
$speechRegion = Read-Host "Region"

if ([string]::IsNullOrWhiteSpace($speechRegion)) {
    Write-Host "❌ Speech region is required" -ForegroundColor Red
    exit 1
}

azd env set AZURE_SPEECH_RESOURCE_ID $speechId
azd env set AZURE_SPEECH_REGION $speechRegion

# Optional: default voice
Write-Host "`nDefault neural voice (press Enter for en-US-AvaMultilingualNeural):" -ForegroundColor Yellow
$voice = Read-Host "Voice"
if (![string]::IsNullOrWhiteSpace($voice)) {
    azd env set AZURE_SPEECH_DEFAULT_VOICE $voice
}

# Deploy
Write-Host "`n🚀 Starting deployment to Azure..." -ForegroundColor Cyan
Write-Host "This will:" -ForegroundColor Yellow
Write-Host "  1. Create Azure resources (Container Registry, Container App, etc.)" -ForegroundColor Gray
Write-Host "  2. Build Docker image" -ForegroundColor Gray
Write-Host "  3. Push to Container Registry" -ForegroundColor Gray
Write-Host "  4. Deploy Container App" -ForegroundColor Gray
Write-Host "  5. Configure networking and security`n" -ForegroundColor Gray

$confirm = Read-Host "Continue? (y/n)"
if ($confirm -ne 'y') {
    Write-Host "Deployment cancelled" -ForegroundColor Yellow
    exit 0
}

# Run azd up
azd up

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Deployment successful!" -ForegroundColor Green
    Write-Host "`nYour application is now running on Azure Container Apps" -ForegroundColor Cyan
    Write-Host "Get the URL with: azd env get-values | Select-String AZURE_CONTAINER_APP_ENDPOINT" -ForegroundColor Yellow
    Write-Host "View logs with: azd monitor" -ForegroundColor Yellow
} else {
    Write-Host "`n❌ Deployment failed" -ForegroundColor Red
    Write-Host "Check the error messages above for details" -ForegroundColor Yellow
    Write-Host "Get help: See DEPLOYMENT.md for troubleshooting" -ForegroundColor Yellow
}

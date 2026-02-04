# Azure Container Apps Deployment Guide

This guide walks you through deploying the Live Voice Translation app to Azure Container Apps using Azure Developer CLI (azd).

## Prerequisites

1. **Azure Developer CLI (azd)** - [Install azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
   ```bash
   # Windows (winget)
   winget install microsoft.azd
   
   # macOS (brew)
   brew tap azure/azd && brew install azd
   
   # Linux
   curl -fsSL https://aka.ms/install-azd.sh | bash
   ```

2. **Docker** - [Install Docker Desktop](https://www.docker.com/products/docker-desktop/)

3. **Azure CLI** - [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
   ```bash
   # Windows (winget)
   winget install -e --id Microsoft.AzureCLI
   ```

4. **Azure Subscription** with access to:
   - Azure Container Apps
   - Azure VoiceLive API

## Quick Deployment

### 1. Initialize Azure Developer Environment

```bash
# Login to Azure
az login
azd auth login

# Initialize the environment (first time only)
azd init

# When prompted:
# - Environment name: Choose a name (e.g., "voice-translation-dev")
# - Azure subscription: Select your subscription
# - Azure location: Choose a region (e.g., "eastus")
```

### 2. Set Required Environment Variables

```bash
# Set your Azure VoiceLive endpoint
azd env set AZURE_VOICELIVE_ENDPOINT "https://your-resource.services.ai.azure.com/"

# Optional: Customize voice (defaults to en-US-Ava:DragonHDLatestNeural)
azd env set AZURE_VOICELIVE_VOICE "en-US-Ava:DragonHDLatestNeural"

# Optional: Enable file logging (defaults to false in production)
azd env set ENABLE_LOGGING "false"
```

### 3. Deploy to Azure

```bash
# Provision infrastructure and deploy application
azd up

# This will:
# 1. Create resource group
# 2. Create Container Registry
# 3. Create Log Analytics workspace
# 4. Create Container Apps Environment
# 5. Build and push Docker image
# 6. Deploy Container App
# 7. Configure managed identity
# 8. Set environment variables
```

### 4. Access Your Application

After deployment completes:

```bash
# Get the application URL
azd env get-values | grep AZURE_CONTAINER_APP_ENDPOINT

# Or view in browser
azd show
```

Visit the URL shown (e.g., `https://ca-yourenv.eastus.azurecontainerapps.io`)

## Development Workflow

### Deploy Updates

```bash
# Deploy code changes
azd deploy

# Or provision + deploy
azd up
```

### View Logs

```bash
# Stream application logs
az containerapp logs show \
  --name <container-app-name> \
  --resource-group rg-<env-name> \
  --follow

# Or use Azure Portal
azd show --endpoint web
# Click "Log stream" in portal
```

### Monitor Application

```bash
# Open in Azure Portal
azd monitor

# View metrics and logs in Application Insights
```

## Environment Variables

The deployment uses these environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_VOICELIVE_ENDPOINT` | Yes | - | Your Azure VoiceLive API endpoint |
| `AZURE_VOICELIVE_VOICE` | No | `en-US-Ava:DragonHDLatestNeural` | TTS voice for responses |
| `ENABLE_LOGGING` | No | `false` | Enable file logging |
| `AZURE_VOICELIVE_INSTRUCTIONS_FILE` | No | `system_instructions.txt` | Path to instructions |

Set environment variables:
```bash
azd env set <VARIABLE_NAME> "<value>"
```

## Infrastructure Details

The deployment creates:

### Resource Group
- Name: `rg-<environmentName>`
- Contains all resources

### Container Registry
- Name: `cr<environmentName>`
- SKU: Basic
- Admin enabled for azd

### Container Apps Environment
- Name: `cae-<environmentName>`
- Log Analytics workspace included
- 30-day retention

### Container App
- Name: `ca-<environmentName>`
- CPU: 0.5 cores
- Memory: 1 GiB
- Min replicas: 1
- Max replicas: 10
- Auto-scale on HTTP requests (10 concurrent)
- Managed identity enabled
- Public ingress on port 8000

### Managed Identity
- Name: `id-<environmentName>`
- System-assigned identity for the Container App
- Used for Azure authentication (no keys needed!)

## Cost Estimation

**Development/Testing:**
- ~$5-10/month (mostly idle)

**Production (moderate use):**
- ~$20-50/month
- Scales based on usage

**High traffic:**
- Scales automatically
- Pay only for what you use

## Troubleshooting

### Deployment fails with "endpoint not set"

```bash
# Verify environment variable is set
azd env get-values | grep AZURE_VOICELIVE_ENDPOINT

# Set it if missing
azd env set AZURE_VOICELIVE_ENDPOINT "https://your-endpoint.services.ai.azure.com/"
```

### Container fails to start

```bash
# Check container logs
az containerapp logs show \
  --name <app-name> \
  --resource-group <rg-name> \
  --follow

# Check container app status
az containerapp show \
  --name <app-name> \
  --resource-group <rg-name> \
  --query "properties.runningStatus"
```

### Authentication errors

The app uses **Managed Identity** for authentication. Ensure:
1. Managed identity is enabled on the Container App
2. The identity has permissions to access Azure VoiceLive API
3. No hardcoded credentials are needed!

### Can't access the app URL

```bash
# Verify ingress is enabled
az containerapp show \
  --name <app-name> \
  --resource-group <rg-name> \
  --query "properties.configuration.ingress"

# Check if external ingress is enabled
# Should show: "external": true
```

## Cleanup

### Delete all resources

```bash
# Delete environment and all Azure resources
azd down

# When prompted, confirm deletion
# This removes:
# - Resource group
# - All contained resources
# - Environment configuration
```

### Keep environment, delete resources only

```bash
# Delete Azure resources but keep azd environment
azd down --purge

# Re-deploy later with
azd up
```

## Advanced Configuration

### Custom Domain

1. Add custom domain in Azure Portal:
   ```bash
   az containerapp hostname add \
     --name <app-name> \
     --resource-group <rg-name> \
     --hostname yourdomain.com
   ```

2. Add DNS CNAME record pointing to the Container App FQDN

### Scale Configuration

Edit `infra/core/host/container-app.bicep`:

```bicep
// Change scaling parameters
param containerMinReplicas int = 2  // Always run 2 instances
param containerMaxReplicas int = 20 // Scale up to 20
```

Then redeploy:
```bash
azd up
```

### Add Application Insights

The deployment includes Log Analytics. To add Application Insights:

```bash
# Create Application Insights
az monitor app-insights component create \
  --app voice-translation-insights \
  --location eastus \
  --resource-group rg-<env-name> \
  --workspace <log-analytics-workspace-id>
```

## CI/CD Integration

### GitHub Actions

```bash
# Configure GitHub Actions for azd
azd pipeline config

# This creates .github/workflows/azure-dev.yml
# Push to trigger deployment
```

### Manual GitHub Actions Setup

1. Get Azure credentials:
   ```bash
   azd auth login --use-device-code
   azd env get-values
   ```

2. Add secrets to GitHub repository:
   - `AZURE_CREDENTIALS`
   - `AZURE_ENV_NAME`
   - `AZURE_VOICELIVE_ENDPOINT`

## Next Steps

1. ✅ Deploy to production environment
2. 📊 Set up monitoring alerts
3. 🔒 Configure custom domain with SSL
4. 🚀 Enable CI/CD pipeline
5. 📈 Review cost optimization

## Resources

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [Managed Identity](https://learn.microsoft.com/azure/active-directory/managed-identities-azure-resources/)
- [azd templates](https://azure.github.io/awesome-azd/)

---

**Need help?** Check the [troubleshooting section](#troubleshooting) or open an issue.

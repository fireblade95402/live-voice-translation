# Azure Container Apps Deployment Setup - Summary

## ✅ What Was Created

Your repository is now ready for Azure Container Apps deployment using Azure Developer CLI (azd).

### Core Deployment Files

1. **`azure.yaml`** - Azure Developer CLI configuration
   - Defines the service and deployment settings
   - Specifies Python language and Container App hosting

2. **`Dockerfile`** - Container image definition
   - Based on Python 3.11-slim
   - Installs audio processing dependencies
   - Exposes port 8000 for web traffic
   - Runs uvicorn server

3. **`infra/`** - Infrastructure as Code (Bicep)
   - `main.bicep` - Main deployment template
   - `main.parameters.json` - Parameter mapping
   - `core/host/container-app.bicep` - Container App resources

### Configuration Files

4. **`.dockerignore`** - Docker build exclusions
5. **`.azd/config.json`** - azd service configuration
6. **`.gitignore`** - Updated to ignore `.azure/` folder

### Documentation

7. **`DEPLOYMENT.md`** - Complete deployment guide
   - Prerequisites
   - Step-by-step instructions
   - Troubleshooting
   - Cost estimation
   - Advanced configuration

8. **`README.md`** - Updated with Azure deployment section

### Helper Scripts

9. **`deploy-azure.ps1`** - Windows PowerShell deployment script
10. **`deploy-azure.sh`** - Linux/macOS bash deployment script

### Code Updates

11. **`main.py`** - Updated to use `DefaultAzureCredential`
12. **`server.py`** - Updated to use `DefaultAzureCredential`

## 🚀 Quick Deploy

### Option 1: Using Helper Script (Easiest)

**Windows:**
```powershell
.\deploy-azure.ps1
```

**Linux/macOS:**
```bash
chmod +x deploy-azure.sh
./deploy-azure.sh
```

### Option 2: Manual Deployment

```bash
# 1. Login
azd auth login

# 2. Initialize
azd init

# 3. Set endpoint
azd env set AZURE_VOICELIVE_ENDPOINT "https://your-endpoint.services.ai.azure.com/"

# 4. Deploy
azd up
```

## 📦 What Gets Deployed to Azure

When you run `azd up`, it creates:

### Resource Group
- Name: `rg-<your-env-name>`
- Contains all resources below

### Container Registry
- Name: `cr<yourenvname>` (no hyphens)
- SKU: Basic
- Stores Docker images

### Log Analytics Workspace
- Name: `<env-name>-logs`
- 30-day retention
- Used for monitoring

### Container Apps Environment
- Name: `cae-<your-env-name>`
- Managed platform for containers
- Integrated with Log Analytics

### Container App
- Name: `ca-<your-env-name>`
- Resources: 0.5 CPU cores, 1 GB RAM
- Auto-scaling: 1-10 replicas
- Public HTTPS ingress
- WebSocket support enabled

### Managed Identity
- Name: `id-<your-env-name>`
- Used for secure authentication
- No credentials needed in code!

## 🔒 Security Features

✅ **Managed Identity** - No hardcoded credentials  
✅ **HTTPS/WSS** - SSL/TLS encryption enabled  
✅ **Secrets Management** - Environment variables stored securely  
✅ **Private Container Registry** - Images not publicly accessible  
✅ **Azure RBAC** - Role-based access control  

## 💰 Cost Estimate

**Development (low usage):**
- Container Registry (Basic): ~$5/month
- Container App (idle): ~$0-5/month
- Log Analytics: ~$2-3/month
- **Total: ~$7-13/month**

**Production (moderate usage):**
- Container Registry: ~$5/month
- Container App: ~$20-40/month (scales with load)
- Log Analytics: ~$5-10/month
- **Total: ~$30-55/month**

**Note:** Scales automatically - pay only for actual usage!

## 🔧 Configuration

### Environment Variables Set via `azd env set`:

Only `AZURE_VOICELIVE_ENDPOINT` is required. All others fall back to the
defaults baked into [infra/main.parameters.json](infra/main.parameters.json).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_VOICELIVE_ENDPOINT` | Yes | - | Your VoiceLive API endpoint |
| `AZURE_VOICELIVE_MODEL` | No | `gpt-realtime` | Realtime model deployment name |
| `AZURE_VOICELIVE_VOICE` | No | `en-US-AvaMultilingualNeural` | TTS voice |
| `ENABLE_LOGGING` | No | `false` | File logging |
| `ENABLE_INPUT_TRANSCRIPTION` | No | `true` | "Spoken" bubble in the UI |
| `VOICELIVE_TRANSCRIPTION_MODEL` | No | `gpt-4o-transcribe` | Transcription model |
| `VOICELIVE_TRANSCRIPTION_LANGUAGE` | No | `en-US` | Transcription language hint |
| `VOICELIVE_VAD_THRESHOLD` | No | `0.8` | VAD threshold |
| `VOICELIVE_VAD_PREFIX_PADDING_MS` | No | `300` | VAD prefix padding (ms) |
| `VOICELIVE_VAD_SILENCE_MS` | No | `1000` | Silence required to end turn (ms) |
| `VOICELIVE_ECHO_CANCELLATION` | No | `true` | Echo cancellation |
| `VOICELIVE_NOISE_REDUCTION` | No | `true` | Noise reduction |
| `VOICELIVE_NOISE_REDUCTION_TYPE` | No | `azure_deep_noise_suppression` | Noise reduction algorithm |

See [.env.example](.env.example) for full descriptions.

### Managed in Bicep (automatic):

- `AZURE_VOICELIVE_INSTRUCTIONS_FILE` - Points to `system_instructions.txt`
- `SERVER_MODE=true`
- Port 8000 exposure
- WebSocket configuration
- Auto-scaling rules
- Health checks

## 📊 Monitoring

After deployment:

```bash
# View application URL
azd env get-values | grep AZURE_CONTAINER_APP_ENDPOINT

# Stream logs
azd monitor

# Or use Azure CLI
az containerapp logs show \
  --name ca-<env-name> \
  --resource-group rg-<env-name> \
  --follow
```

## 🔄 Update Workflow

Deploy code changes:

```bash
# Deploy code updates
azd deploy

# Or full redeploy (infra + code)
azd up
```

## 🧹 Cleanup

Remove all Azure resources:

```bash
# Delete everything
azd down

# Confirm when prompted
```

## 📚 Next Steps

1. **Deploy**: Run `azd up` or use the helper script
2. **Test**: Visit the deployed URL
3. **Monitor**: Check logs with `azd monitor`
4. **Customize**: Edit `infra/` files for custom configuration
5. **CI/CD**: Set up GitHub Actions with `azd pipeline config`

## 🆘 Troubleshooting

**Problem**: Deployment fails with endpoint error  
**Solution**: Verify `azd env set AZURE_VOICELIVE_ENDPOINT` was run

**Problem**: Container won't start  
**Solution**: Check logs with `azd monitor`

**Problem**: Can't access the URL  
**Solution**: Verify ingress is enabled (external: true in Bicep)

**Full troubleshooting guide**: See [DEPLOYMENT.md](DEPLOYMENT.md)

## 📖 Resources

- [Full Deployment Guide](DEPLOYMENT.md)
- [Azure Developer CLI Docs](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Container Apps Docs](https://learn.microsoft.com/azure/container-apps/)
- [Bicep Docs](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)

---

**Ready to deploy?** Run `.\deploy-azure.ps1` (Windows) or `./deploy-azure.sh` (Linux/macOS)!

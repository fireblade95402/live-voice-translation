# GitHub Actions CI/CD Setup Guide

This guide explains how to set up automated deployments to Azure Container Apps using GitHub Actions.

## Prerequisites

1. Repository pushed to GitHub
2. Azure resources deployed at least once with `azd up`
3. GitHub repository with admin access

## Setup Methods

### Method 1: Automated Setup (Recommended)

Use azd to automatically configure GitHub Actions:

```bash
# This will create service principal and configure GitHub secrets
azd pipeline config
```

This command:
1. Creates an Azure service principal
2. Configures federated credentials
3. Adds GitHub secrets and variables
4. Commits the workflow file

### Method 2: Manual Setup

#### Step 1: Create Azure Service Principal

```bash
# Get your subscription ID
az account show --query id -o tsv

# Create service principal
az ad sp create-for-rbac \
  --name "github-actions-voice-translation" \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID> \
  --sdk-auth
```

Copy the JSON output.

#### Step 2: Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

**Add these secrets:**

| Secret Name | Value | Source |
|-------------|-------|--------|
| `AZURE_CREDENTIALS` | Full JSON from service principal | Step 1 output |
| `AZURE_VOICELIVE_ENDPOINT` | Your VoiceLive endpoint | From `.env` |

**Add these variables (all optional except `AZURE_ENV_NAME` / `AZURE_LOCATION` / `AZURE_SUBSCRIPTION_ID`):**

| Variable Name | Value | Example / Default |
|---------------|-------|-------------------|
| `AZURE_ENV_NAME` | Your environment name | `voice-translation-prod` |
| `AZURE_LOCATION` | Azure region | `eastus` |
| `AZURE_SUBSCRIPTION_ID` | Your subscription ID | From `az account show` |
| `AZURE_VOICELIVE_MODEL` | Realtime model | `gpt-realtime` |
| `AZURE_VOICELIVE_VOICE` | TTS voice | `en-US-AvaMultilingualNeural` |
| `ENABLE_INPUT_TRANSCRIPTION` | "Spoken" bubble | `true` |
| `VOICELIVE_TRANSCRIPTION_MODEL` | Transcription model | `gpt-4o-transcribe` |
| `VOICELIVE_TRANSCRIPTION_LANGUAGE` | Language hint | `en-US` |
| `VOICELIVE_VAD_THRESHOLD` | VAD threshold | `0.8` |
| `VOICELIVE_VAD_SILENCE_MS` | End-of-turn silence (ms) | `1000` |

Any variable omitted falls back to the default in [infra/main.parameters.json](../infra/main.parameters.json).

#### Step 3: Enable Workflow

The workflow file is already in `.github/workflows/azure-deploy.yml`.

Push to `main` branch to trigger deployment:

```bash
git add .
git commit -m "Enable Azure deployment"
git push origin main
```

## Workflow Triggers

The workflow runs automatically on:
- **Push to main branch** - Deploys changes automatically
- **Manual trigger** - Click "Run workflow" in GitHub Actions tab

## Monitoring Deployments

### View Deployment Status

1. Go to your GitHub repository
2. Click "Actions" tab
3. Select the latest workflow run

### View Deployment Summary

After successful deployment, the workflow creates a summary with:
- Application URL
- Environment name
- Azure location

### Troubleshooting Failed Deployments

Check the workflow logs:
1. Go to Actions tab
2. Click the failed run
3. Expand the failed step
4. Review error messages

Common issues:
- Missing secrets/variables
- Service principal permissions
- Azure quota limits
- Invalid configuration

## Advanced Configuration

### Deploy to Multiple Environments

Create separate workflows for staging and production:

**`.github/workflows/deploy-staging.yml`:**
```yaml
name: Deploy to Staging
on:
  push:
    branches:
      - develop
env:
  AZURE_ENV_NAME: voice-translation-staging
```

**`.github/workflows/deploy-production.yml`:**
```yaml
name: Deploy to Production
on:
  push:
    branches:
      - main
env:
  AZURE_ENV_NAME: voice-translation-prod
```

### Add Approval Gates

Require manual approval before production deployment:

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: production
      url: ${{ steps.get-url.outputs.url }}
    # ... rest of job
```

Then configure environment protection rules in GitHub Settings → Environments.

### Run Tests Before Deploy

Add a test job:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/

  deploy:
    needs: test
    runs-on: ubuntu-latest
    # ... deployment steps
```

## Security Best Practices

✅ **Use Federated Credentials** - More secure than static credentials  
✅ **Limit Service Principal Scope** - Grant minimum required permissions  
✅ **Rotate Secrets Regularly** - Update credentials periodically  
✅ **Use Environment Secrets** - Separate prod/staging credentials  
✅ **Enable Branch Protection** - Require reviews before merging  

## Cost Optimization

The workflow only runs on pushes to main. To reduce costs:

1. **Skip deployment for docs changes:**
   ```yaml
   on:
     push:
       branches:
         - main
       paths-ignore:
         - '**.md'
         - 'docs/**'
   ```

2. **Deploy on schedule (nightly builds):**
   ```yaml
   on:
     schedule:
       - cron: '0 2 * * *'  # 2 AM daily
   ```

## Cleanup

### Disable Workflow

Delete or rename `.github/workflows/azure-deploy.yml`.

### Remove Service Principal

```bash
# List service principals
az ad sp list --display-name "github-actions-voice-translation"

# Delete by app ID
az ad sp delete --id <APP_ID>
```

### Remove GitHub Secrets

Settings → Secrets and variables → Actions → Delete each secret/variable

## Resources

- [GitHub Actions Docs](https://docs.github.com/actions)
- [Azure Login Action](https://github.com/Azure/login)
- [azd GitHub Action](https://github.com/Azure/setup-azd)
- [Federated Credentials](https://learn.microsoft.com/azure/developer/github/connect-from-azure)

---

**Ready to automate?** Run `azd pipeline config` to get started!

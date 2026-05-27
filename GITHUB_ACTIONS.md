# GitHub Actions CI/CD

The workflow at [.github/workflows/azure-deploy.yml](.github/workflows/azure-deploy.yml)
deploys the app to Azure Container Apps via `azd` on every push to `main`
(and on manual dispatch).

## One-time setup

The easiest path is to let `azd` configure everything (service principal,
federated credential, GitHub secrets/variables, workflow commit):

```bash
azd pipeline config
```

## Manual setup

If you'd rather configure GitHub yourself, create the items below under
**Settings → Secrets and variables → Actions**.

### Secrets

| Secret | Description |
|--------|-------------|
| `AZURE_SPEECH_RESOURCE_ID` | Full ARM resource ID of your Speech / AI Services resource. |

### Variables

| Variable | Required | Example |
|----------|----------|---------|
| `AZURE_CLIENT_ID` | yes | App registration / federated credential client ID. |
| `AZURE_TENANT_ID` | yes | Tenant ID. |
| `AZURE_SUBSCRIPTION_ID` | yes | Target subscription. |
| `AZURE_ENV_NAME` | yes | `azd` environment name, e.g. `voice-translation-prod`. |
| `AZURE_LOCATION` | yes | Region to deploy the Container App into (e.g. `eastus`). |
| `AZURE_SPEECH_REGION` | yes | Region of the Speech resource (may differ from `AZURE_LOCATION`). |
| `AZURE_SPEECH_DEFAULT_VOICE` | no | Default neural voice. |

The federated credential used by `AZURE_CLIENT_ID` must have permission to
deploy into the target subscription/resource group.

## Triggers

- Push to `main`
- `workflow_dispatch` (manual run via the Actions tab)

## Monitoring

Open the **Actions** tab in GitHub, pick the run, and expand each step.
On success the summary panel shows the deployed Container App URL.

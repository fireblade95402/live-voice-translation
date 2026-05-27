targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

@description('Full ARM resource ID of the Azure Speech / AI Services resource the app authenticates against.')
param azureSpeechResourceId string

@description('Azure region of the Speech resource (e.g. swedencentral, eastus2).')
param azureSpeechRegion string

@description('Default neural voice used when no per-locale override is set.')
param azureSpeechDefaultVoice string = 'en-US-AvaMultilingualNeural'

// Tags that should be applied to all resources
var tags = {
  'azd-env-name': environmentName
  'app-name': 'live-voice-translation'
}

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

// Container Apps Environment and Container App
module containerApp './core/host/container-app.bicep' = {
  name: 'container-app'
  scope: rg
  params: {
    name: 'ca-${environmentName}'
    location: location
    tags: tags
    containerAppsEnvironmentName: 'cae-${environmentName}'
    containerRegistryName: 'cr${replace(environmentName, '-', '')}'
    serviceName: 'web'
    exists: false
    containerCpuCoreCount: '0.5'
    containerMemory: '1Gi'
    secrets: []
    env: [
      {
        name: 'AZURE_SPEECH_RESOURCE_ID'
        value: azureSpeechResourceId
      }
      {
        name: 'AZURE_SPEECH_REGION'
        value: azureSpeechRegion
      }
      {
        name: 'AZURE_SPEECH_DEFAULT_VOICE'
        value: azureSpeechDefaultVoice
      }
    ]
  }
}

// Grant the Container App's managed identity rights to use the Speech resource.
// `Cognitive Services Speech User` (f2dc8367-1007-4938-bd23-fe263f013447) is
// the least-privilege role that allows AAD-token based access to Speech
// (recognition + synthesis + translation).
var cognitiveServicesSpeechUserRole = 'f2dc8367-1007-4938-bd23-fe263f013447'

var resourceIdParts = split(azureSpeechResourceId, '/')
var targetSubscriptionId = resourceIdParts[2]
var targetResourceGroupName = resourceIdParts[4]

module speechRoleAssignment './core/security/role-assignment.bicep' = {
  name: 'speech-role-assignment'
  scope: resourceGroup(targetSubscriptionId, targetResourceGroupName)
  params: {
    resourceId: azureSpeechResourceId
    principalId: containerApp.outputs.identityPrincipalId
    roleDefinitionId: cognitiveServicesSpeechUserRole
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output AZURE_CONTAINER_APP_ENDPOINT string = containerApp.outputs.uri
output AZURE_CONTAINER_APP_NAME string = containerApp.outputs.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApp.outputs.containerRegistryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApp.outputs.containerRegistryName
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output SERVICE_WEB_IDENTITY_PRINCIPAL_ID string = containerApp.outputs.identityPrincipalId

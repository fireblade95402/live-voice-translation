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

@description('Azure VoiceLive API endpoint')
param azureVoiceliveEndpoint string

@description('Azure VoiceLive realtime model deployment name')
param azureVoiceliveModel string = 'gpt-realtime'

@description('Azure VoiceLive Voice setting')
param azureVoiceliveVoice string = 'en-US-AvaMultilingualNeural'

@description('Enable logging to files')
param enableLogging string = 'false'

@description('Enable user-input transcription (the "Spoken" bubble)')
param enableInputTranscription string = 'true'

@description('Transcription model: azure-speech | gpt-4o-transcribe | gpt-4o-mini-transcribe | whisper-1')
param voiceliveTranscriptionModel string = 'gpt-4o-transcribe'

@description('Transcription language hint (BCP-47 for azure-speech, ISO-639-1 for gpt-4o/whisper)')
param voiceliveTranscriptionLanguage string = 'en-US'

@description('VAD threshold (0.0-1.0). Higher = stricter.')
param voiceliveVadThreshold string = '0.8'

@description('Padding (ms) added before detected speech.')
param voiceliveVadPrefixPaddingMs string = '300'

@description('Silence (ms) required to end a turn.')
param voiceliveVadSilenceMs string = '1000'

@description('Acoustic echo cancellation (true/false).')
param voiceliveEchoCancellation string = 'true'

@description('Noise reduction (true/false).')
param voiceliveNoiseReduction string = 'true'

@description('Noise reduction algorithm.')
param voiceliveNoiseReductionType string = 'azure_deep_noise_suppression'

@description('Azure OpenAI/Cognitive Services resource ID for role assignment')
param cognitiveServicesResourceId string = ''

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
    secrets: [
      {
        name: 'voicelive-endpoint'
        value: azureVoiceliveEndpoint
      }
    ]
    env: [
      {
        name: 'AZURE_VOICELIVE_ENDPOINT'
        secretRef: 'voicelive-endpoint'
      }
      {
        name: 'AZURE_VOICELIVE_MODEL'
        value: azureVoiceliveModel
      }
      {
        name: 'AZURE_VOICELIVE_VOICE'
        value: azureVoiceliveVoice
      }
      {
        name: 'AZURE_VOICELIVE_INSTRUCTIONS_FILE'
        value: 'system_instructions.txt'
      }
      {
        name: 'ENABLE_LOGGING'
        value: enableLogging
      }
      {
        name: 'ENABLE_INPUT_TRANSCRIPTION'
        value: enableInputTranscription
      }
      {
        name: 'VOICELIVE_TRANSCRIPTION_MODEL'
        value: voiceliveTranscriptionModel
      }
      {
        name: 'VOICELIVE_TRANSCRIPTION_LANGUAGE'
        value: voiceliveTranscriptionLanguage
      }
      {
        name: 'VOICELIVE_VAD_THRESHOLD'
        value: voiceliveVadThreshold
      }
      {
        name: 'VOICELIVE_VAD_PREFIX_PADDING_MS'
        value: voiceliveVadPrefixPaddingMs
      }
      {
        name: 'VOICELIVE_VAD_SILENCE_MS'
        value: voiceliveVadSilenceMs
      }
      {
        name: 'VOICELIVE_ECHO_CANCELLATION'
        value: voiceliveEchoCancellation
      }
      {
        name: 'VOICELIVE_NOISE_REDUCTION'
        value: voiceliveNoiseReduction
      }
      {
        name: 'VOICELIVE_NOISE_REDUCTION_TYPE'
        value: voiceliveNoiseReductionType
      }
      {
        name: 'SERVER_MODE'
        value: 'true'
      }
    ]
  }
}

// Grant Cognitive Services OpenAI User role to the Container App's managed identity
// This allows the app to access Azure OpenAI/VoiceLive resources
var cognitiveServicesOpenAIUserRole = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

// Parse the resource ID to get subscription and resource group
var resourceIdParts = split(cognitiveServicesResourceId, '/')
var targetSubscriptionId = !empty(cognitiveServicesResourceId) ? resourceIdParts[2] : ''
var targetResourceGroupName = !empty(cognitiveServicesResourceId) ? resourceIdParts[4] : ''

module openAiRoleAssignment './core/security/role-assignment.bicep' = if (!empty(cognitiveServicesResourceId)) {
  name: 'openai-role-assignment'
  scope: resourceGroup(targetSubscriptionId, targetResourceGroupName)
  params: {
    resourceId: cognitiveServicesResourceId
    principalId: containerApp.outputs.identityPrincipalId
    roleDefinitionId: cognitiveServicesOpenAIUserRole
    principalType: 'ServicePrincipal'
  }
}

// Output the Container App URL
output AZURE_CONTAINER_APP_ENDPOINT string = containerApp.outputs.uri
output AZURE_CONTAINER_APP_NAME string = containerApp.outputs.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApp.outputs.containerRegistryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApp.outputs.containerRegistryName
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output SERVICE_WEB_IDENTITY_PRINCIPAL_ID string = containerApp.outputs.identityPrincipalId

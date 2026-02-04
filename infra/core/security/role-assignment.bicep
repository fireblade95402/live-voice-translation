targetScope = 'resourceGroup'

@description('The resource ID to assign the role to')
param resourceId string

@description('The principal ID to assign the role to')
param principalId string

@description('The role definition ID')
param roleDefinitionId string

@description('The principal type (default: ServicePrincipal)')
param principalType string = 'ServicePrincipal'

// Create role assignment on the resource
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceId, principalId, roleDefinitionId)
  properties: {
    roleDefinitionId: '/subscriptions/${subscription().subscriptionId}/providers/Microsoft.Authorization/roleDefinitions/${roleDefinitionId}'
    principalId: principalId
    principalType: principalType
  }
}

output roleAssignmentId string = roleAssignment.id

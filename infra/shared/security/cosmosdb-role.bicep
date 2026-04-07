metadata description = 'Assigns the Cosmos DB Built-in Data Contributor role to a principal on a Cosmos DB account.'

param cosmosDbAccountName string
param principalId string

@description('Cosmos DB Built-in Data Contributor role definition ID')
var roleDefinitionId = '00000000-0000-0000-0000-000000000002'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosDbAccountName
}

resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, principalId, roleDefinitionId)
  properties: {
    principalId: principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${roleDefinitionId}'
    scope: cosmosAccount.id
  }
}

#!/bin/bash

source config.env

# Register some things
az provider register --namespace Microsoft.VirtualMachineImages
az provider register --namespace Microsoft.Compute
az provider register --namespace Microsoft.ContainerInstance
az provider register --namespace Microsoft.KeyVault

az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
az identity create --resource-group "$RESOURCE_GROUP" --name "$AIB_IDENTITY" --location "$LOCATION"

# Give the logged in user storage permissions

# storage account scope - no need?
# az role assignment create \
#  --assignee $(az ad signed-in-user show --query id -o tsv) \
#  --role "Storage Blob Data Owner" \
#  --scope /subscriptions/$SUBSCRIPTION/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT

# subscription scope
az role assignment create \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --role "Storage Blob Data Owner" \
  --scope /subscriptions/$SUBSCRIPTION

USER_IDENTITY="/subscriptions/$SUBSCRIPTION/resourceGroups/detonator-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/$AIB_IDENTITY"
az role assignment create \
  --assignee-object-id $(az identity show --ids $USER_IDENTITY --query principalId -o tsv) \
  --role "Contributor" \
  --scope "/subscriptions/$SUBSCRIPTION/resourceGroups/detonator-rg"


# Create storage account
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --access-tier Hot

az storage account create \
  --resource-group "$RESOURCE_GROUP" \
  --name $AIB_LOGS \
  --sku Standard_LRS \
  --kind StorageV2 \
  --location "Switzerland North"

# Change permissions
az storage account update \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --allow-blob-public-access true

# Create container for scripts
az storage container create \
  --auth-mode login \
  --name scripts \
  --account-name "$STORAGE_ACCOUNT" \
  --public-access blob

# even more stuff?!
az storage container create \
  --name logs \
  --account-name $AIB_LOGS \
  --auth-mode login





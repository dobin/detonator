#!/bin/bash

set -euo pipefail

# 1. Find the resource group starting with IT_detonator
RG=$(az group list --query "[?starts_with(name, 'IT_detonator')].name | [0]" -o tsv)

if [ -z "$RG" ]; then
  echo "No resource group starting with IT_detonator found."
  exit 1
fi

echo "Using resource group: $RG"

# 2. Get the storage account name
STORAGE_ACCOUNT=$(az storage account list --resource-group "$RG" --query "[0].name" -o tsv)

if [ -z "$STORAGE_ACCOUNT" ]; then
  echo "No storage account found in resource group $RG."
  exit 1
fi

echo "Using storage account: $STORAGE_ACCOUNT"

# 3. Get the storage account key
STORAGE_KEY=$(az storage account keys list --resource-group "$RG" --account-name "$STORAGE_ACCOUNT" --query "[0].value" -o tsv)

# 4. List blobs in the 'packerlogs' container to find the customization.log
BLOB_PATH=$(az storage blob list \
  --container-name packerlogs \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --query "[?contains(name, 'customization.log')].name | [0]" \
  -o tsv)

if [ -z "$BLOB_PATH" ]; then
  echo "customization.log not found in packerlogs container."
  exit 1
fi

echo "Found blob: $BLOB_PATH"

# 5. Download the customization.log
az storage blob download \
  --container-name packerlogs \
  --name "$BLOB_PATH" \
  --file customization.log \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY"

echo "Downloaded customization.log"
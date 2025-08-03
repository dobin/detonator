#!/bin/bash

source config.env

az storage blob upload \
  --account-name $STORAGE_ACCOUNT \
  --container-name scripts \
  --name install-agent.ps1 \
  --file ./install-agent.ps1 \
  --auth-mode login \
  --overwrite


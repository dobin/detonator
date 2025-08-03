#!/bin/bash

source config.env

az storage blob upload \
  --account-name $STORAGE_ACCOUNT \
  --container-name scripts \
  --name rededr.zip \
  --file "$1" \
  --auth-mode login \
  --overwrite 

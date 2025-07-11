
source config.env

echo "Running Azure image builder script..."

echo "Upload install-agent.ps1 script to Azure Storage..."
bash "./upload_script.sh"
curl https://detonator1.blob.core.windows.net/scripts/install-agent.ps1

echo 
echo "Deleting existing image if it exists..."
az image delete \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AIB_DISTRIBUTE_IMAGE"

sleep 2

echo
echo "Deleting existing image template if it exists..."
az image builder delete \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AIB_IMAGE_TEMPLATE"

sleep 2

echo
echo "Template..."
cat image_template.json

echo
echo "Creating a new image template..."
az image builder create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AIB_IMAGE_TEMPLATE" \
  --location "$LOCATION" \
  --image-template image_template.json 

echo
echo "-------------------------------------------------------"
echo "Create image template..."
az image builder run \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AIB_IMAGE_TEMPLATE"
echo "-------------------------------------------------------"


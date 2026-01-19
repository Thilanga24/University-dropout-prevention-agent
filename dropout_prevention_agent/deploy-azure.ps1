# Azure Container Apps Deployment Script
# University Dropout Prevention Agent

Write-Host "Starting Azure deployment..." -ForegroundColor Green

# Variables
$resourceGroup = "dp-agent-rg"
$location = "southeastasia"
$acrName = "dpagent" + (Get-Random -Maximum 9999)
$envName = "dp-env"
$appName = "dp-agent"

# Step 1: Create resource group
Write-Host "`n1. Creating resource group..." -ForegroundColor Yellow
az group create --name $resourceGroup --location $location

# Step 2: Create container registry
Write-Host "`n2. Creating container registry ($acrName)..." -ForegroundColor Yellow
az acr create --resource-group $resourceGroup --name $acrName --sku Basic

# Step 3: Build Docker image
Write-Host "`n3. Building Docker image in Azure..." -ForegroundColor Yellow
az acr build --registry $acrName --image dropout-prevention:v1 .

# Step 4: Install Container Apps extension
Write-Host "`n4. Setting up Container Apps..." -ForegroundColor Yellow
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App

# Step 5: Create Container Apps environment
Write-Host "`n5. Creating Container Apps environment..." -ForegroundColor Yellow
az containerapp env create --resource-group $resourceGroup --name $envName --location $location

# Step 6: Deploy the app
Write-Host "`n6. Deploying container app..." -ForegroundColor Yellow
az containerapp create `
  --resource-group $resourceGroup `
  --name $appName `
  --environment $envName `
  --image "$acrName.azurecr.io/dropout-prevention:v1" `
  --target-port 8501 `
  --ingress external `
  --registry-server "$acrName.azurecr.io" `
  --cpu 1.0 `
  --memory 2.0Gi

# Step 7: Get the URL
Write-Host "`n7. Getting app URL..." -ForegroundColor Yellow
$appUrl = az containerapp show --resource-group $resourceGroup --name $appName --query properties.configuration.ingress.fqdn -o tsv

Write-Host "`n================================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host "Your app is available at: https://$appUrl" -ForegroundColor Cyan
Write-Host "`nResource Group: $resourceGroup" -ForegroundColor Gray
Write-Host "Location: $location" -ForegroundColor Gray
Write-Host "================================================" -ForegroundColor Green

#!/usr/bin/env bash
# Deploy the Drive semantic router (delivery 042) to Azure App Service Linux, Free tier (F1),
# with the Google OAuth secrets in Azure Key Vault (resolved by App Service Key Vault references).
#
# Prerequisites: az CLI logged in (`az login`), run from the repo root.
# Secrets are read from the environment and never printed:
#   export GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... GOOGLE_REFRESH_TOKEN=...
#
# Image, pick one:
#   IMAGE=ghcr.io/<user>/drive-router:1 [REGISTRY_USER=.. REGISTRY_PASSWORD=..]   free, image built by you
#   (IMAGE unset)  -> creates an Azure Container Registry Basic and builds in the cloud (~5 EUR/month!)
#
#   ./driverouter/deploy_azure.sh --dry-run    print the commands, change nothing
#   ./driverouter/deploy_azure.sh
set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

LOCATION="${LOCATION:-westeurope}"
RG="${RG:-rg-drive-router}"
PLAN="${PLAN:-plan-drive-router-f1}"
APP="${APP:-drive-router-$(whoami | tr -cd 'a-z0-9' | cut -c1-8)}"   # must be globally unique
KV="${KV:-kv-drive-router-$(whoami | tr -cd 'a-z0-9' | cut -c1-6)}" # 3-24 chars, globally unique
ACR="${ACR:-acrdriverouter$(whoami | tr -cd 'a-z0-9' | cut -c1-8)}"
IMAGE="${IMAGE:-}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
APP_DRY_RUN="${APP_DRY_RUN:-true}"          # first deploy: classify and log only, move nothing
SYNC_INTERVAL_MINUTES="${SYNC_INTERVAL_MINUTES:-30}"

run() {
  if [[ $DRY_RUN == 1 ]]; then
    # mask anything that looks like a secret value in the preview
    printf '+ %s\n' "$*" | sed -E 's/(--value|--container-registry-password)[ =]?[^ ]+/\1 ****/g'
  else
    "$@"
  fi
}

need() { [[ -n "${!1:-}" ]] || { echo "missing env var: $1" >&2; exit 1; }; }
if [[ $DRY_RUN == 0 ]]; then
  need GOOGLE_CLIENT_ID; need GOOGLE_CLIENT_SECRET; need GOOGLE_REFRESH_TOKEN
  az account show >/dev/null || { echo "run 'az login' first" >&2; exit 1; }
fi

echo "== 1. Resource group + App Service plan (Linux, F1 Free)"
run az group create --name "$RG" --location "$LOCATION" --output none
run az appservice plan create --name "$PLAN" --resource-group "$RG" --location "$LOCATION" \
    --is-linux --sku F1 --output none

echo "== 2. Container image"
REG_ARGS=()
if [[ -z "$IMAGE" ]]; then
  echo "   IMAGE not set: Azure Container Registry Basic (NOT free, ~5 EUR/month) + cloud build"
  run az acr create --name "$ACR" --resource-group "$RG" --sku Basic --admin-enabled true --output none
  run az acr build --registry "$ACR" --image "drive-router:$TAG" --file driverouter/Dockerfile .
  IMAGE="$ACR.azurecr.io/drive-router:$TAG"
  if [[ $DRY_RUN == 0 ]]; then
    REG_ARGS=(--container-registry-url "https://$ACR.azurecr.io"
              --container-registry-user "$(az acr credential show -n "$ACR" --query username -o tsv)"
              --container-registry-password "$(az acr credential show -n "$ACR" --query 'passwords[0].value' -o tsv)")
  fi
elif [[ -n "${REGISTRY_USER:-}" ]]; then
  REG_ARGS=(--container-registry-url "https://${IMAGE%%/*}"
            --container-registry-user "$REGISTRY_USER" --container-registry-password "$REGISTRY_PASSWORD")
fi

echo "== 3. Web App (Linux container) + system-assigned managed identity"
run az webapp create --name "$APP" --resource-group "$RG" --plan "$PLAN" \
    --container-image-name "$IMAGE" --output none
if [[ ${#REG_ARGS[@]} -gt 0 ]]; then
  run az webapp config container set --name "$APP" --resource-group "$RG" \
      --container-image-name "$IMAGE" "${REG_ARGS[@]}" --output none
fi
PRINCIPAL_ID="<principal-id>"
[[ $DRY_RUN == 0 ]] && PRINCIPAL_ID="$(az webapp identity assign --name "$APP" --resource-group "$RG" --query principalId -o tsv)"
[[ $DRY_RUN == 1 ]] && run az webapp identity assign --name "$APP" --resource-group "$RG"

echo "== 4. Key Vault (RBAC) + secrets"
run az keyvault create --name "$KV" --resource-group "$RG" --location "$LOCATION" \
    --enable-rbac-authorization true --output none
KV_ID="<kv-id>"; ME="<your-object-id>"
if [[ $DRY_RUN == 0 ]]; then
  KV_ID="$(az keyvault show --name "$KV" --query id -o tsv)"
  ME="$(az ad signed-in-user show --query id -o tsv)"
fi
# you write the secrets, the app only reads them
run az role assignment create --assignee "$ME" --role "Key Vault Secrets Officer" --scope "$KV_ID" --output none
run az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
    --role "Key Vault Secrets User" --scope "$KV_ID" --output none
[[ $DRY_RUN == 0 ]] && sleep 30   # RBAC propagation

SYNC_API_KEY="${SYNC_API_KEY:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')}"
set_secret() {  # name, env var holding the value
  if [[ $DRY_RUN == 1 ]]; then
    echo "+ az keyvault secret set --vault-name $KV --name $1 --value ****"
  else
    az keyvault secret set --vault-name "$KV" --name "$1" --value "${!2}" --output none
  fi
}
set_secret google-client-id GOOGLE_CLIENT_ID
set_secret google-client-secret GOOGLE_CLIENT_SECRET
set_secret google-refresh-token GOOGLE_REFRESH_TOKEN
set_secret sync-api-key SYNC_API_KEY

echo "== 5. App settings (secrets as Key Vault references, never as plain values)"
ref() { echo "@Microsoft.KeyVault(VaultName=$KV;SecretName=$1)"; }
run az webapp config appsettings set --name "$APP" --resource-group "$RG" --output none --settings \
    "GOOGLE_CLIENT_ID=$(ref google-client-id)" \
    "GOOGLE_CLIENT_SECRET=$(ref google-client-secret)" \
    "GOOGLE_REFRESH_TOKEN=$(ref google-refresh-token)" \
    "SYNC_API_KEY=$(ref sync-api-key)" \
    "WEBSITES_PORT=8000" \
    "WEBSITES_CONTAINER_START_TIME_LIMIT=600" \
    "DRY_RUN=$APP_DRY_RUN" \
    "SYNC_INTERVAL_MINUTES=$SYNC_INTERVAL_MINUTES" \
    "INBOX_FOLDER_PATH=${INBOX_FOLDER_PATH:-05_In_Arrivo_Da_Smistare}" \
    "MAX_FILES_PER_RUN=${MAX_FILES_PER_RUN:-25}"
if [[ -n "${APPLICATIONINSIGHTS_CONNECTION_STRING:-}" ]]; then
  run az webapp config appsettings set --name "$APP" --resource-group "$RG" --output none \
      --settings "APPLICATIONINSIGHTS_CONNECTION_STRING=$APPLICATIONINSIGHTS_CONNECTION_STRING"
fi
run az webapp update --name "$APP" --resource-group "$RG" --https-only true --output none
run az webapp log config --name "$APP" --resource-group "$RG" --docker-container-logging filesystem --output none
run az webapp restart --name "$APP" --resource-group "$RG"

echo "== 6. Check"
URL="https://$APP.azurewebsites.net"
echo "   health:  curl $URL/health      (first start: model load, allow 1-3 min)"
echo "   sync:    curl -X POST -H \"X-API-Key: \$(az keyvault secret show --vault-name $KV -n sync-api-key --query value -o tsv)\" $URL/sync-documents"
echo "   logs:    az webapp log tail --name $APP --resource-group $RG"
echo "   DRY_RUN=$APP_DRY_RUN — when the logged choices look right:"
echo "            az webapp config appsettings set -n $APP -g $RG --settings DRY_RUN=false"

#!/bin/bash
# Enables Google OAuth Easy Auth on an Azure Container Apps frontend container.
# Run this after your app is deployed to Container Apps.
#
# Prerequisites:
#   1. Go to https://console.cloud.google.com → APIs & Services → Credentials
#   2. Create an OAuth 2.0 Client ID (Web application)
#   3. Add authorised redirect URI:
#        https://<FRONTEND_FQDN>/.auth/login/google/callback
#   4. Set the variables below or pass them as arguments.
#
# Usage:
#   ./deploy/enable-auth.sh <SUBSCRIPTION_ID> <RESOURCE_GROUP> <APP_NAME> <CLIENT_ID> <CLIENT_SECRET>
set -euo pipefail

SUBSCRIPTION_ID="${1:?ERROR: Pass Azure Subscription ID as \$1}"
RESOURCE_GROUP="${2:?ERROR: Pass Resource Group name as \$2}"
FRONTEND_APP_NAME="${3:?ERROR: Pass Container App name as \$3}"
GOOGLE_CLIENT_ID="${4:?ERROR: Pass Google client ID as \$4}"
GOOGLE_CLIENT_SECRET="${5:?ERROR: Pass Google client secret as \$5}"

echo "=== Setting subscription ==="
az account set --subscription "$SUBSCRIPTION_ID"

echo "=== Configuring Google OAuth provider ==="
az containerapp auth google update \
  --name "$FRONTEND_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --client-id "$GOOGLE_CLIENT_ID" \
  --client-secret "$GOOGLE_CLIENT_SECRET" \
  --output none

echo "=== Enabling Easy Auth and setting unauthenticated action ==="
az containerapp auth update \
  --name "$FRONTEND_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --enabled true \
  --unauthenticated-client-action RedirectToLoginPage \
  --output none

echo ""
echo "============================================"
echo "Easy Auth enabled!"
echo "Auth flow:"
echo "  1. Easy Auth enforces Google login (redirect)"
echo "  2. EmailAllowlistMiddleware checks X-MS-CLIENT-PRINCIPAL-NAME allowlist"
echo "  3. Frontend gets Google ID token via GSI silent sign-in"
echo "  4. Backend validates Google JWT with JWKS (independent of Azure)"
echo "============================================"

#!/bin/bash
# Image verification script for Agentic Federated CBDC Fraud Detection System

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

IMAGES=(
    "dusman/federated-fraud-agentic-coordinator:latest"
    "dusman/federated-fraud-secure-aggregator:latest"
    "dusman/federated-fraud-policy-manager:latest"
    "dusman/federated-fraud-model-registry:latest"
    "dusman/federated-fraud-local-agent:latest"
    "dusman/federated-fraud-local-gnn:latest"
    "dusman/federated-fraud-privacy-layer:latest"
    "dusman/federated-fraud-transaction-graph:latest"
    "dusman/federated-fraud-alerting:latest"
)

echo -e "${YELLOW}Checking for Agentic Federated Fraud Detection System Image Verification${NC}"
echo -e "${YELLOW}Checking for ${#IMAGES[@]} images...${NC}"

echo

ALL_EXIST=true
MISSING_IMAGES=()

for IMAGE in "${IMAGES[@]}"; do
    if docker image inspect "$IMAGE" > /dev/null 2>&1; then
        SIZE=$(docker images --format "{{.Size}}" $IMAGE | head -1)
        echo -e "${GREEN}✓ Found: $IMAGE${NC} ($SIZE)"
    else
        echo -e "${RED}✗ Missing: $IMAGE${NC}"
        MISSING_IMAGES+=("$IMAGE")
        ALL_EXIST=false
    fi
done

echo
if [ "$ALL_EXIST" = true ]; then
    echo -e "${GREEN}✅ All images are present!${NC}"
else
    echo -e "${RED}❌ Missing ${#MISSING_IMAGES[@]} images:${NC}"
    for IMG in "${MISSING_IMAGES[@]}; do
        echo "  - $IMG"
    done
fi

echo -e "\n${YELLOW}Run DEPLOYMENT-GUIDE.md for the correct build commands!${NC}"

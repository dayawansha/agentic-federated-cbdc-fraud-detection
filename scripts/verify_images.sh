#!/bin/bash
# Image verification script for Agentic Federated CBDC Fraud Detection System

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_PREFIX="dusman/federated-fraud"
IMAGES=(
    "${IMAGE_PREFIX}-agentic-coordinator:${IMAGE_TAG}"
    "${IMAGE_PREFIX}-federated-model-aggregator:${IMAGE_TAG}"
    "${IMAGE_PREFIX}-policy-manager:${IMAGE_TAG}"
    "${IMAGE_PREFIX}-model-registry:${IMAGE_TAG}"
    "${IMAGE_PREFIX}-local-agent:${IMAGE_TAG}"
    "${IMAGE_PREFIX}-local-gnn:${IMAGE_TAG}"
    "${IMAGE_PREFIX}-privacy-layer:${IMAGE_TAG}"
    "${IMAGE_PREFIX}-transaction-graph:${IMAGE_TAG}"
    "${IMAGE_PREFIX}-alerting:${IMAGE_TAG}"
    "${IMAGE_PREFIX}-fraud-dashboard:${IMAGE_TAG}"
)

echo -e "${YELLOW}Checking Agentic Federated Fraud Detection images${NC}"
echo -e "${YELLOW}Tag: ${IMAGE_TAG}${NC}"
echo -e "${YELLOW}Checking ${#IMAGES[@]} images...${NC}"

echo

ALL_EXIST=true
MISSING_IMAGES=()

for IMAGE in "${IMAGES[@]}"; do
    if docker image inspect "$IMAGE" > /dev/null 2>&1; then
        SIZE=$(docker images --format "{{.Size}}" "$IMAGE" | head -1)
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
    for IMG in "${MISSING_IMAGES[@]}"; do
        echo "  - $IMG"
    done
fi

echo -e "\n${YELLOW}Run doc/DEPLOYMENT-GUIDE.md for the correct build commands.${NC}"

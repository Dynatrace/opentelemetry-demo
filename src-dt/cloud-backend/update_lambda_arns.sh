#!/bin/bash

# Updates the OneAgent Lambda layer ARNs in config.yaml for every stage.
#
# Per-stage platform token (scope fleet-management:oneagents:download) is read from
# DT_INSTALL_TOKEN_<STAGE>, e.g. DT_INSTALL_TOKEN_DEV, DT_INSTALL_TOKEN_HARDENING.

# Functions

get_lambda_oneagent_layer_arn() {
    local env=$1
    local techtype=$2
    local api_url token_var

    api_url=$(yq e ".stage.${env}.api_url" "$CONFIG_FILE")
    token_var="DT_INSTALL_TOKEN_$(echo "$env" | tr '[:lower:]' '[:upper:]')"

    curl -sS --fail-with-body -H "Authorization: Bearer ${!token_var}" \
        "$api_url/api/v1/deployment/lambda/layer?arch=x86&techtype=$techtype&region=us-east-1&withCollector=included" \
        | jq -er '.arns[0].arn'
}

# Main

set -euo pipefail

echo "Updating OneAgent Lambda layer ARNs with the latest versions for all stages..."

export CONFIG_FILE=${CONFIG_FILE:-"$(dirname "$0")/config.yaml"}

for STAGE in $(yq -r '.stage | keys | .[]' "$CONFIG_FILE"); do
    for TECH in python nodejs; do
        LAYER_ARN=$(get_lambda_oneagent_layer_arn "$STAGE" "$TECH")
        echo "$STAGE|$TECH = $LAYER_ARN"
        yq e -i ".stage.${STAGE}.agent.arn_layer_pattern_${TECH} = \"$LAYER_ARN\"" "$CONFIG_FILE"
    done
done

echo ""
echo "Updated config.yaml with latest Dynatrace OneAgent Lambda layer ARNs for all stages."
git --no-pager diff "$CONFIG_FILE"

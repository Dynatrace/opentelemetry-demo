#!/bin/bash

set -euo pipefail

# Functions

get_lambda_oneagent_layer_arn() {
    local env=$1
    local techtype=$2
    local api_url=$(yq e ".${env}.api_url" "$CONFIG_FILE")
    
    layer_arn=$(curl -s -H "Authorization: Bearer $DEV_DT_INSTALL_TOKEN" \
        "$api_url/api/v1/deployment/lambda/layer?arch=x86&techtype=$techtype&region=us-east-1&withCollector=included" \
        | jq -r .arns[].arn)

    echo ${layer_arn}
}

# Main
export CONFIG_FILE=${CONFIG_FILE:-"../config.yaml"}

for STAGE in $(yq -r '.stage | keys | .[]' "$CONFIG_FILE"); do
    LAYER_ARN=$(get_lambda_oneagent_layer_arn "$STAGE" "python")
    yq e -i ".${STAGE}.agent.arn_layer_pattern_python = \"$LAYER_ARN\"" "$CONFIG_FILE"

    LAYER_ARN=$(get_lambda_oneagent_layer_arn "$STAGE" "nodejs")
    yq e -i ".${STAGE}.agent.arn_layer_pattern_nodejs = \"$LAYER_ARN\"" "$CONFIG_FILE"
done

echo "Updated config.yaml with latest Dynatrace OneAgent Lambda layer ARNs for all stages."
git diff "$CONFIG_FILE"

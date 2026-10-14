#!/bin/bash

# Updates the OneAgent Lambda layer ARNs in config.yaml for every stage.
#
# Per-stage platform token (scope fleet-management:oneagents:download) is read from
# DT_INSTALL_TOKEN_<STAGE>, e.g. DT_INSTALL_TOKEN_DEV, DT_INSTALL_TOKEN_HARDENING.
#
# Each Dynatrace layer is copied into the currently connected AWS account (us-east-1)
# and config.yaml gets the ARN of the copy. A layer name already present in the
# account is reused, not republished.

# ======== Functions =========

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

# Copies a layer version into the connected AWS account, prints the resulting ARN.
copy_layer_to_connected_account() {
    local source_arn=$1
    local layer_name existing info url size sha runtimes archs license zip result

    layer_name=$(cut -d: -f7 <<<"$source_arn")

    existing=$(aws lambda list-layer-versions --region "$AWS_REGION" --layer-name "$layer_name" \
        --query 'LayerVersions[0].LayerVersionArn' --output text)
    if [[ "$existing" != "None" ]]; then
        echo "$existing"
        return
    fi

    echo "Publishing $layer_name to account $ACCOUNT_ID" >&2
    info=$(aws lambda get-layer-version-by-arn --region "$AWS_REGION" --arn "$source_arn")
    url=$(jq -r '.Content.Location' <<<"$info")
    size=$(jq -r '.Content.CodeSize' <<<"$info")
    sha=$(jq -r '.Content.CodeSha256' <<<"$info")
    runtimes=$(jq -r '.CompatibleRuntimes // [] | join(" ")' <<<"$info")
    archs=$(jq -r '.CompatibleArchitectures // [] | join(" ")' <<<"$info")
    license=$(jq -r '.LicenseInfo // empty' <<<"$info")

    zip=$(mktemp --suffix=.zip)
    trap 'rm -f "$zip"' RETURN
    curl -sS --fail -o "$zip" "$url"

    # Integrity of the download: size and base64 SHA-256 must match the source metadata.
    if [[ "$(stat -c %s "$zip")" != "$size" ]]; then
        echo "Size mismatch for $source_arn" >&2
        return 1
    fi
    if [[ "$(openssl dgst -sha256 -binary "$zip" | base64)" != "$sha" ]]; then
        echo "SHA-256 mismatch for $source_arn" >&2
        return 1
    fi

    result=$(aws lambda publish-layer-version --region "$AWS_REGION" --layer-name "$layer_name" \
        --description "$(jq -r '.Description // empty' <<<"$info")" \
        --zip-file "fileb://$zip" \
        ${runtimes:+--compatible-runtimes $runtimes} \
        ${archs:+--compatible-architectures $archs} \
        ${license:+--license-info "$license"})

    # Integrity of the copy: published hash must equal the source hash.
    if [[ "$(jq -r '.Content.CodeSha256' <<<"$result")" != "$sha" ]]; then
        echo "Published copy of $source_arn has a different SHA-256" >&2
        return 1
    fi
    jq -r '.LayerVersionArn' <<<"$result"
}

# ======== Main =========

set -euo pipefail

AWS_REGION=us-east-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Connected AWS account: $ACCOUNT_ID ($AWS_REGION)"

echo "Updating OneAgent Lambda layer ARNs with the latest versions for all stages..."

export CONFIG_FILE=${CONFIG_FILE:-"$(dirname "$0")/config.yaml"}

for STAGE in $(yq -r '.stage | keys | .[]' "$CONFIG_FILE"); do
    for TECH in python nodejs; do
        SOURCE_ARN=$(get_lambda_oneagent_layer_arn "$STAGE" "$TECH")
        LAYER_ARN=$(copy_layer_to_connected_account "$SOURCE_ARN")
        echo "$STAGE|$TECH = $SOURCE_ARN -> $LAYER_ARN"
        yq e -i ".stage.${STAGE}.agent.arn_layer_pattern_${TECH} = \"$LAYER_ARN\"" "$CONFIG_FILE"
    done
done

echo ""
echo "Updated config.yaml with latest Dynatrace OneAgent Lambda layer ARNs for all stages."
git --no-pager diff "$CONFIG_FILE"

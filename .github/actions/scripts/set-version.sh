#!/bin/bash

BUILD_VERSION=$1
WORKDIR=${2:-.}
BUILD_DATE=${3:-$(date '+%Y-%m-%d %H:%M')}
BUILD_COMMIT=${4:-$(git log --pretty=format:'%h' -n 1)}

if [ -z "$BUILD_VERSION" ]; then
    echo "Build version not set"
    exit 1
fi

cd $WORKDIR

echo "Build version: $BUILD_VERSION, date: $BUILD_DATE, commit: $BUILD_COMMIT, path: $(pwd)"

yq -i ".default.image.tag = \"$BUILD_VERSION\"" charts/astroshop/values.yaml

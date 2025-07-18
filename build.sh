#!/bin/bash
###############################################################################
# Copyright 2024 Google, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
###############################################################################

VERSION="v${1:-0.1}"

APP="${2:-parameter-store}"            # default to parameter-store if not given a value
DOCKERFILE="Dockerfile"

source .env

if [[ -z "${REPO_HOST}" ]]; then
    echo "REPO_HOST is not set. Aborting."
    exit 1
fi

if [[ -z "${PROJECT_ID}" ]]; then
    echo "PROJECT_ID is not set. Aborting."
    exit 1
fi

if [[ -z "${REPO_FOLDER}" ]]; then
    REPO_FOLDER="parameter-store"
fi

if ! docker build -f ${DOCKERFILE} -t "${APP}:${VERSION}" .; then
    echo "Cannot build docker image"
    exit 1
fi

if ! docker tag "${APP}:${VERSION}" "${REPO_HOST}/${PROJECT_ID}/${REPO_FOLDER}/${APP}:${VERSION}"; then
    echo "Cannot Tag Docker Build with version ${VERSION}"
    exit 1
fi

if ! docker tag "${APP}:${VERSION}" "${REPO_HOST}/${PROJECT_ID}/${REPO_FOLDER}/${APP}:latest"; then
    echo "Cannot Tag Docker Build with latest"
    exit 1
fi

if ! docker push "${REPO_HOST}/${PROJECT_ID}/${REPO_FOLDER}/${APP}:${VERSION}"; then
    echo "Cannot Push Version ${VERSION}"
    exit 1
fi

if ! docker push "${REPO_HOST}/${PROJECT_ID}/${REPO_FOLDER}/${APP}:latest"; then
    echo "Cannot Push Version Latest"
    exit 1
fi

#!/usr/bin/env bash

set -euxo pipefail

module_dir="${1}"
environment="${2}"
echo "${environment}"

PYTHON_BIN="python3"
which ${PYTHON_BIN}

BASE_DIR="${module_dir}/.."

SRC_DIR="src"
DEPS_DIR="module/dist/deps/python"
APP_DIR="module/dist/app"

pushd "${BASE_DIR}"

rm -rf "${APP_DIR}" || true

rsync -aL --progress --exclude-from="${SRC_DIR}/rsync-exclude.txt" "${SRC_DIR}/" "${APP_DIR}"

if [[ "${environment}" == "local" ]]; then
  rsync -aL --exclude-from="${SRC_DIR}/rsync-exclude.txt" "${DEPS_DIR}/" "${APP_DIR}"
fi

find "${APP_DIR}" -exec touch -t 201401010000 {} +;

popd || true
exit 0

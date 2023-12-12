#!/usr/bin/env bash

set -euxo pipefail

module_dir="${1}"

PYTHON_BIN="python3"
which ${PYTHON_BIN}

BASE_DIR="${module_dir}/.."

SRC_DIR="src"
DEPS_DIR="module/dist/deps/python"

pushd "${BASE_DIR}"

rm -rf "${DEPS_DIR}" || true
mkdir -p "${DEPS_DIR}"

${PYTHON_BIN} -m pip install --upgrade pip
${PYTHON_BIN} -m pip install \
  -r "${SRC_DIR}/requirements.txt" --platform manylinux2014_x86_64 \
  --implementation cp --only-binary=:all: --target "${DEPS_DIR}"


cp "${SRC_DIR}/cloudlogbase.cfg" "${DEPS_DIR}/spine_aws_common/cloudlogbase.cfg"

find "${DEPS_DIR}" -exec touch -t 201401010000 {} +;

popd || true

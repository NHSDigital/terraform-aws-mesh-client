#!/bin/bash
# mesh_aws_client.sh

set -euxo pipefail

module_dir="${1}"
environment="${2}"
echo "${environment}"

DEPS_DIR="${module_dir}/dist/deps/python"
CODE_DIR="${module_dir}/dist/app"
PYTHON_BIN="python3"

# Deterministic dir
SCRIPT_DIR="$(cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"
pushd "${SCRIPT_DIR}"

# Check for python
which ${PYTHON_BIN}

# Create code dir
rm -rf "${CODE_DIR}" || true
mkdir -p "${CODE_DIR}"
mkdir -p "${CODE_DIR}/shared"

# Copy code
cp -r ../../src/*.py "${CODE_DIR}/"
cp -r ../../src/*.cfg "${CODE_DIR}/"
cp -r ../../src/shared/*.py "${CODE_DIR}/shared"

if [[ "${environment}" == "local" ]]; then
  cp -a "${DEPS_DIR}/." "${CODE_DIR}"
fi

find "${CODE_DIR}" -exec touch -t 201401010000 {} +;

popd || true
exit 0

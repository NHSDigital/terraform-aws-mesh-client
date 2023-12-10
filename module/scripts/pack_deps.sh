#!/bin/bash
# mesh_aws_client_dependencies.sh

set -euxo pipefail


module_dir="${1}"

DEPS_DIR="${module_dir}/dist/deps/python"
PYTHON_BIN="python3"

# Deterministic dir
SCRIPT_DIR="$(cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"
cd "${SCRIPT_DIR}"

# Check for python
which ${PYTHON_BIN}

# Create deps dir
rm -rf "${DEPS_DIR}" || true
mkdir -p "${DEPS_DIR}"


# Install deps
${PYTHON_BIN} -m pip install --upgrade pip
${PYTHON_BIN} -m pip install \
  -r ../../src/requirements.txt --platform manylinux2014_x86_64 \
  --implementation cp --only-binary=:all: --target "${DEPS_DIR}"

find "${DEPS_DIR}" -exec touch -t 201401010000 {} +;

# This will then be zipped by terraform
exit 0

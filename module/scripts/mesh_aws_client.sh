#!/bin/bash
# mesh_aws_client.sh

set -e
set -u
set -x
set -o pipefail

CODE_DIR="../mesh_client_aws_serverless/mesh_client_aws_serverless"
PYTHON_BIN="python3"

# Deterministic dir
SCRIPT_DIR="$(cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"
pushd "${SCRIPT_DIR}"

# Check for python
which ${PYTHON_BIN}

# Create code dir
mkdir -p ${CODE_DIR}
rm -rf ${CODE_DIR:?}/*

# Copy code
cp -r ../../mesh_client_aws_serverless/*.py ${CODE_DIR}/

popd || true
exit 0

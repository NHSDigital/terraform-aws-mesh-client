#!/usr/bin/env bash

set -euo pipefail
PWD="$(pwd)"

ps -ocommand= -p "${PPID}"

if ! make requirements; then
  echo "make requirements failed"
  exit 1
fi

if ! make check-secrets-all; then
  echo "make check-secrets-all failed"
  exit 1
fi

echo ""
echo "check formatting ..."
echo ""

if ! make black-check; then
  echo ""
  echo "black-check failed"
  echo ""
  exit 1
fi


if ! make ruff-check; then
  echo ""
  echo "ruff-check failed"
  echo ""
  exit 1
fi

echo ""

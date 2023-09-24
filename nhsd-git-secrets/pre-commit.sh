#!/usr/bin/env bash

# Note that this will be invoked by the git hook from the repo root, so cd .. isn't required

# These only need to be run once per workstation but are included to try and ensure they are present
./nhsd-git-secrets/git-secrets --add-provider -- cat nhsd-git-secrets/nhsd-rules-deny.txt

echo "Scanning staged and unstaged files for secrets"
./nhsd-git-secrets/git-secrets --scan --recursive
echo "Scanning untracked files for secrets"
./nhsd-git-secrets/git-secrets --scan --untracked
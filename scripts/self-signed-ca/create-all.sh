#!/usr/bin/env bash
# shellcheck disable=SC2154
set -euo pipefail
pushd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
# shellcheck source=/dev/null

this_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null ; pwd -P)

# get command line args
server_dns_name1="${1-localhost}"
arg2="${2-?}"
arg3="${3-?}"


if [[ "${arg2}" == "--overwrite" ]]; then
    server_dns_name2="${arg3}"
else
    server_dns_name2="${arg2}"
fi

certs_env_file="${this_dir}/.certs.env"

# check if ok to proceed vs overwrite arg
if [[ ! "$*" =~ "--overwrite" ]]; then
    if [[ -f "${certs_env_file}" ]]; then
        echo -e "Certificate files already exist and --overwrite flag not set, normal exit."
        exit 0
    fi
fi

# clean up
echo -e "\nCleaning up any previous run:\n"
rm -rf "${this_dir}/certs"
rm -rf "${this_dir}/ca"
rm -f "${certs_env_file}"

# create CAs
./create-ca.sh server root
./create-ca.sh server sub
./create-ca.sh client root
./create-ca.sh client sub sub1
./create-ca.sh client sub sub2
cat ./ca/client/sub1/crt.pem ./ca/client/sub2/crt.pem ./ca/client/root/crt.pem > ./bundles/client-ca-all-bundle.pem


# create server certificate
# ./create-server-cert.sh <dns_name1> [dns_name2]
if [[ "${server_dns_name2}" == "?" ]]; then
    ./create-server-cert.sh "${server_dns_name1}"
else
    ./create-server-cert.sh "${server_dns_name1}" "${server_dns_name2}"
fi

# create client certificates
# ./create-client-cert.sh <name> <type> <ca_name>
./create-client-cert.sh valid valid sub1
./create-client-cert.sh valid2 valid sub2


# create env vars for docker
./create-env-file.sh "${server_dns_name1}"

echo -e "\nCertificate run complete.\n"



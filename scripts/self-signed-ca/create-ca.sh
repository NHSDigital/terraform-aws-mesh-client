#!/usr/bin/env bash
# shellcheck disable=SC2154
set -euo pipefail
pushd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
# shellcheck source=/dev/null

this_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P)

# - ENVIRONMENT -
usage() {
  echo ""
  echo "USAGE: create-ca.sh <server|client|unknown> <root|sub> [ca-name]"
  echo
}

ca_purpose=${1-_}
ca_type=${2-_}
ca_name=${3-sub}
if ! { [[ "${ca_purpose}" == "server" || "${ca_purpose}" == "client" || "${ca_purpose}" == "unknown" ]]; }; then
    usage
    exit 1
fi

if ! { [[ "${ca_type}" == "root" || "${ca_type}" == "sub" ]]; }; then
    usage
    exit 1
fi

if [[ "${ca_type}" == "root"  ]]; then
    ca_name="root"
fi

export CONF_CA_NAME="${ca_purpose}-${ca_name}-ca"
export CONF_CA_DIR="${this_dir}/ca/${ca_purpose}/${ca_name}"
export CONF_SUB_CA_ORG_NAME="${ca_name}"
ca_dir="${CONF_CA_DIR}"
crl_dir="${CONF_CA_DIR}/crl"


# initialise ca structure
mkdir -p "${crl_dir}" "${CONF_CA_DIR}/newcerts"

touch "${ca_dir}/index.txt"
touch "${crl_dir}/crl.pem"
echo 1001 > "${ca_dir}/serial"
echo 01 > "${crl_dir}/crlnumber"


ca_key="${ca_dir}/key.pem"
ca_crt="${ca_dir}/crt.pem"
crl_file="${crl_dir}/crl.pem"
ca_conf="${this_dir}/conf/${ca_type}-ca.conf"

# - PROCESSING -
if [[ "${ca_type}" == "root" ]]; then
  # self-signed root ca
  echo ""
  echo "Generating self-signed root-ca: ${ca_purpose}"
  openssl req -newkey rsa:4096 -nodes -keyout "${ca_key}" -new -x509 -out "${ca_crt}" -days 36500 \
      -config "${ca_conf}" -extensions v3_ca

  echo "Generating initial crl file for ${ca_purpose} ${ca_name}"
  openssl ca -gencrl -config "${ca_conf}" -out "${crl_file}"
fi

if [[ "${ca_type}" == "sub" ]]; then
  # self-signed sub ca
  ca_csr="${ca_dir}/csr.pem"
  root_ca_dir="$(realpath "${ca_dir}/../root")"
  root_ca_key="${root_ca_dir}/key.pem"
  root_ca_crt="${root_ca_dir}/crt.pem"
#
#  echo ""
#  echo "Generating self-signed sub-ca: ${ca_purpose} ${ca_name}"
#  openssl req -newkey rsa:4096 -nodes -keyout "${ca_key}" -new -x509 -out "${ca_crt}" -days 36500 \
#      -config "${ca_conf}" -extensions v3_ca
#
#  echo "Generating initial crl file for ${ca_purpose} ${ca_name}"
#  openssl ca -gencrl -config "${ca_conf}" -out "${crl_dir}/crl.pem"
#
#
  echo ""
  echo "Generating sub ca key and csr: ${ca_purpose} ${ca_name}"
  openssl req -newkey rsa:4096 -nodes -keyout "${ca_key}" -new -out "${ca_csr}" \
      -config "${ca_conf}"

  echo ""
  echo "Signing ${ca_purpose} ${ca_name} crt with root-ca key: ${root_ca_key}"
  openssl x509 -req -in "${ca_csr}" \
      -CA "${root_ca_crt}" -CAkey "${root_ca_key}" -CAcreateserial \
      -out "${ca_crt}" -days 36500 -sha256 \
      -extfile "${ca_conf}" -extensions v3_intermediate_ca

  echo "Generating initial crl file for sub ca: ${ca_purpose} ${ca_name}"
  openssl ca -gencrl -config "${ca_conf}" -out "${crl_file}"

  # create chained public bundle
  bundles_dir="${this_dir}/bundles"
  mkdir -p "${bundles_dir}"
  cat "${root_ca_crt}" "${ca_crt}" > "${bundles_dir}/${ca_purpose}-${ca_name}-ca-bundle.pem"


fi

# intermediate ca



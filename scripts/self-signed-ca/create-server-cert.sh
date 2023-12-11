#!/usr/bin/env bash
# shellcheck disable=SC2154
set -euo pipefail
pushd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
# shellcheck source=/dev/null
this_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P)

# command line args
dns_name1="${1-?}"
dns_name2="${2-?}"
ca_name="${3-sub}"

if [[ ${dns_name1} == "?" ]]; then
      echo -e "\nUSAGE: create-cert.sh <dns_name1> [dns_name2] [ca_name]\n"
      exit 1
fi

cert_dir="${this_dir}/certs/server/${dns_name1}"
mkdir -p "${cert_dir}"

cert_key="${cert_dir}/key.pem"
cert_crt="${cert_dir}/crt.pem"
cert_csr="${cert_dir}/csr.pem"

export CONF_CA_NAME="server-${ca_name}-ca"
export CONF_CA_DIR="${this_dir}/ca/server/${ca_name}"
export CONF_SUB_CA_ORG_NAME="${ca_name}"
ca_conf="${this_dir}/conf/sub-ca.conf"
# webserver cert

echo -e "Generating websvr key and csr:\n"
csr_conf="${this_dir}/conf/server.conf"

if [[ ${dns_name2} == "?" ]]; then
  san="subjectAltName = DNS:${dns_name1}"
else
  san="subjectAltName = DNS:${dns_name1}, DNS:${dns_name2}"
fi

export CN="${dns_name1}"
openssl req -newkey rsa:2048 -nodes -keyout "${cert_key}" -new -out "${cert_csr}" -config "${csr_conf}" -extensions v3_req -addext "${san}"

#extra_extensions=""
#if [[ "${type}" == "client" ]]; then
#  extra_extensions="-extensions usr_cert"
#fi

echo -e "Signing websvr crt with intermediate-ca:\n"
openssl ca -batch -notext -in "${cert_csr}" -out "${cert_crt}" -days 36500 \
    -config "${ca_conf}" -extensions server_cert

server_root_ca_crt="${this_dir}/ca/server/root/crt.pem"
server_sub_ca_crt="${this_dir}/ca/server/sub/crt.pem"

echo -e "Verifying webserver certificate chain\n"
if [[ ! "$(openssl verify -show_chain -CAfile "${server_root_ca_crt}" -untrusted "${server_sub_ca_crt}" "${cert_crt}")" =~ 'depth=2' ]]; then
  echo "Error: chain should have depth=2"
  exit 1
fi

echo -e "${dns_name1} server certificate created successfully\n"

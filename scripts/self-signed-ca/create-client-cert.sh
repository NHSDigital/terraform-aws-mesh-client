#!/usr/bin/env bash
# shellcheck disable=SC2154
set -euo pipefail
pushd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
# shellcheck source=/dev/null
this_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P)

# command line args
name="${1-?}"
type="${2-?}" # valid | revoked | expired | unknown | devices-valid
ca_name="${3-sub}"
args="${name}${type}"

if [[ ${args} =~ "?" ]] || ! { [[ "${type}" == "valid" || "${type}" == "revoked" ||
    "${type}" == "expired" || "${type}" == "unknown" ]]; }; then
        echo -e "\nUSAGE: create-client-cert.sh <name> <valid|revoked|revoked2|expired|unknown> <sub1|sub2|unknown|DigiCert>"
        exit 1
fi

ca_purpose="client"
if [[ "${type}" == "unknown" ]]; then
    ca_purpose="unknown"
fi

ca_fullname="${ca_purpose}-${ca_name}"
export CONF_CA_NAME="${ca_fullname}-ca"
export CONF_CA_DIR="${this_dir}/ca/${ca_purpose}/${ca_name}"
export CONF_SUB_CA_ORG_NAME="${ca_name}"
export CN="${CN-${name}.${ca_purpose}}"


csr_conf="${this_dir}/conf/client.conf"
root_ca_dir="${this_dir}/ca/${ca_purpose}/root"
root_ca_crt="${root_ca_dir}/crt.pem"
ca_conf="${this_dir}/conf/sub-ca.conf"
ca_crl_dir="${CONF_CA_DIR}/crl"
ca_crl_file="${ca_crl_dir}/crl.pem"
ca_crt="${CONF_CA_DIR}/crt.pem"
cert_dir="${this_dir}/certs/client/${name}"
mkdir -p "${cert_dir}"

cert_key="${cert_dir}/key.pem"
cert_crt="${cert_dir}/crt.pem"
cert_csr="${cert_dir}/csr.pem"

period="-days 18250"
verify_match_re="OK.+depth=2"
if [[ "${type}" == "expired" ]]; then
    period="-startdate 20190101000000Z -enddate 20201231235959Z"
    verify_match_re="certificate has expired"
elif [[ "${type}" == "revoked" ]]; then
    verify_match_re="certificate revoked"
fi


# PROCESSING

envs="$(printenv | grep CONF_CLIENT || true)\n$(printenv | grep CN || true)"
echo -e "$envs"

echo -e "Generating ${name} key and csr:\n"
openssl req -newkey rsa:2048 -nodes -keyout "${cert_key}" -new -out "${cert_csr}" -config "${csr_conf}" -extensions v3_req -extensions usr_cert


echo -e "Signing ${name} crt with ${ca_fullname} intermediate-ca:\n"
# shellcheck disable=SC2086
openssl ca -batch -notext -in "${cert_csr}" -out "${cert_crt}" ${period} \
    -config "${ca_conf}" -extensions usr_cert


if [[ "${type}" == "revoked" ]]; then
    echo -e "Revoking ${name} crt with ${ca_fullname} intermediate-ca:\n"
    openssl ca -config "${ca_conf}" -revoke "${cert_crt}"

    echo -e "Regenerating crl file for ${ca_fullname} intermediate-ca:\n"
    openssl ca -gencrl -config "${ca_conf}" -out "${ca_crl_file}"
fi



set +e # <-- some verify errors are intentional, we match expected output below
echo -e "Verifying ${name} certificate state\n"
# verify picks up on any potential issues in our scripts by checking we got what we asked for
verify_output="$(openssl verify -show_chain -crl_check -extended_crl -policy_check \
        -CAfile "${root_ca_crt}" -untrusted "${ca_crt}" \
        -CRLfile "${ca_crl_file}" \
        "${cert_crt}" 2>&1)"
set -e

if [[ ! ${verify_output} =~ ${verify_match_re} ]]; then
    echo "${verify_output}"
    echo -e "\nError: verify output should match '${verify_match_re}'\n"
   exit 1
fi



echo -e "Creating pfx cert for ${name}\n"
openssl pkcs12 -export -passout pass: -out "${cert_dir}/crt.pfx" -inkey "${cert_key}" \
    -in "${cert_crt}" -certfile "${root_ca_crt}"


echo -e "'${name}' client certificate created successfully\n"

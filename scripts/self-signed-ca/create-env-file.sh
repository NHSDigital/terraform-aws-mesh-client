#!/usr/bin/env bash
# shellcheck disable=SC2154
set -euo pipefail
pushd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
# shellcheck source=/dev/null
this_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P)

dns_name="${1-?}"
if [[ ${dns_name} == "?" ]]; then
      echo -e "\nUSAGE: create-env-file.sh <dns_name>\n"
      exit 1
fi

env_file="${this_dir}/.certs.env"

echo -e "\nBuilding ${env_file} strings from certificates..."

server_cert_dir="${this_dir}/certs/server/${dns_name}"
server_crt_value=$(<"${server_cert_dir}/crt.pem")
server_key_value=$(<"${server_cert_dir}/key.pem")

valid_client_cert_dir="${this_dir}/certs/client/valid"
valid_client_crt_value=$(<"${valid_client_cert_dir}/crt.pem")
valid_client_key_value=$(<"${valid_client_cert_dir}/key.pem")

{
    echo -e "\n#_BEGIN_CERTS_SECTION_"

    echo -e "\n# ${server_cert_dir}/crt.pem"
    # shellcheck disable=SC2028
    echo "MESH_SERVER_CRT=\"${server_crt_value//$'\n'/\\\\n}\\\n\""  # replacing newlines here to simulate how escaped newlines come in env vars in ECS

    echo -e "\n# ${server_cert_dir}/key.pem"
    # shellcheck disable=SC2028
    echo "MESH_SERVER_KEY=\"${server_key_value//$'\n'/\\\\n}\\\n\""

    echo -e "\n# ${valid_client_cert_dir}/crt.pem"
    # shellcheck disable=SC2028
    echo "MESH_VALID_CLIENT_CRT=\"${valid_client_crt_value//$'\n'/\\\\n}\\\n\""

    echo -e "\n# ${valid_client_cert_dir}/key.pem"
    # shellcheck disable=SC2028
    echo "MESH_VALID_CLIENT_KEY=\"${valid_client_key_value//$'\n'/\\\\n}\\\n\""

    echo -e "\n#_END_CERTS_SECTION_\n"

} > "${env_file}"

echo -e "done.\n\n"

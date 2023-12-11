#!/usr/bin/env bash
# shellcheck disable=SC2154


# script to create various digicert PEMS
# to put in X-Spine-ClientCert header in certificate_header_checks_tests.py

set_good_digicert_exports() {
    export CONF_CLIENT_EMAILADDRESS="mesh.spine@hscic.gov.uk"
    export CONF_CLIENT_O="Health & Social Care Information Centre"
    export CONF_CLIENT_L="Leeds"
    export CONF_CLIENT_OU="some other unit"
    export CONF_CLIENT_C="GB"
    export CONF_CLIENT_ST="West Yorkshire"
    export CN="vic.mesh-client.nhs.uk"
}

./create-ca.sh client sub DigiCert
set_good_digicert_exports
./create-client-cert.sh digicert-good valid DigiCert

export CONF_CLIENT_EMAILADDRESS="vic@bob.com"
./create-client-cert.sh digicert-wrong-emailAddress valid DigiCert

set_good_digicert_exports
export CONF_CLIENT_O="Vic & Bob Inc"
./create-client-cert.sh digicert-wrong-organizationName valid DigiCert

set_good_digicert_exports
export CONF_CLIENT_L="Liverpool"
./create-client-cert.sh digicert-wrong-localityName valid DigiCert

set_good_digicert_exports
export CONF_CLIENT_C="US"
./create-client-cert.sh digicert-wrong-countryName valid DigiCert

set_good_digicert_exports
export CN="vic.bob.com"
./create-client-cert.sh digicert-wrong-commonName valid DigiCert

set_good_digicert_exports
export CN="meshui.mesh-client.nhs.uk"
./create-client-cert.sh digicert-good-meshui valid DigiCert

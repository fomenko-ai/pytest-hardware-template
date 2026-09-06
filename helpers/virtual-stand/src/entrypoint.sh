#!/bin/sh
set -eu

if [ -z "${VIRTUAL_DUT_PASSWORD:-}" ]; then
    echo "VIRTUAL_DUT_PASSWORD is required" >&2
    exit 2
fi

printf 'tester:%s\n' "${VIRTUAL_DUT_PASSWORD}" | chpasswd
unset VIRTUAL_DUT_PASSWORD

ssh-keygen -A
exec /usr/sbin/sshd -D -e

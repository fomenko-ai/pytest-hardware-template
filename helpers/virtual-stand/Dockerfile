FROM alpine:3.24.1

RUN apk add --no-cache openssh-server \
    && adduser -D -s /bin/sh tester \
    && mkdir -p /run/sshd \
    && sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && printf '\nPermitRootLogin no\nAllowUsers tester\n' >> /etc/ssh/sshd_config

COPY src/virtual-device /usr/local/bin/virtual-device
COPY src/entrypoint.sh /usr/local/bin/virtual-stand-entrypoint

RUN chmod 0755 /usr/local/bin/virtual-device /usr/local/bin/virtual-stand-entrypoint

EXPOSE 22

ENTRYPOINT ["virtual-stand-entrypoint"]

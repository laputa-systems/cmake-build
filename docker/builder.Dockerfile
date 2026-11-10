FROM alpine@sha256:020dfcbaaf4cc1078bf2d9c7ba31a8466e334061dcd2f248001d68f79e52c000

COPY keys/ /etc/apk/keys/
COPY apks/ /tmp/apks/

RUN set -eux; \
    apk add --no-cache --no-scripts --repositories-file /dev/null /tmp/apks/*.apk; \
    rm -rf /tmp/apks

RUN set -eux; \
    for tool in gcc cc g++ c++ ld as ar; do ! command -v "$tool"; done; \
    for pkg in gcc binutils musl-dev libstdc++-dev openssl-dev; do ! apk info -e "$pkg"; done

ENV TMPDIR=/src/.work/tmp
WORKDIR /src

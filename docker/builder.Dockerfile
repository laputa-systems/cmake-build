FROM alpine@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6

COPY apks/ /tmp/apks/

RUN set -eux; \
    apk add --no-cache --no-scripts --repositories-file /dev/null /tmp/apks/*.apk; \
    rm -rf /tmp/apks

RUN set -eux; \
    for tool in gcc cc g++ c++ ld as ar; do ! command -v "$tool"; done; \
    for pkg in gcc binutils musl-dev libstdc++-dev openssl-dev; do ! apk info -e "$pkg"; done

ENV TMPDIR=/src/.work/tmp
WORKDIR /src

FROM alpine:latest
RUN apk add --no-cache ca-certificates curl jq openssh-client sshpass \
    && addgroup -g 3000 monitor \
    && adduser -D -u 1000 -G monitor monitor
COPY --chmod=755 pon-monitor.sh /usr/local/bin/pon-monitor
VOLUME /data
CMD ["pon-monitor"]

FROM alpine
RUN apk add --no-cache ca-certificates curl jq openssh-client sshpass
COPY --chmod=755 pon-monitor.sh /usr/local/bin/pon-monitor
VOLUME /data
CMD ["pon-monitor"]

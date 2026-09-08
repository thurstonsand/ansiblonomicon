#!/bin/sh
set -eu

compose() {
  docker compose --project-name "$COMPOSE_PROJECT_NAME" --file "$STACK_FILE" "$@"
}

container_id() {
  compose ps --quiet "$1"
}

health_status() {
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1"
}

network_mode() {
  docker inspect -f '{{.HostConfig.NetworkMode}}' "$1"
}

started_at() {
  docker inspect -f '{{.State.StartedAt}}' "$1"
}

repair() {
  echo "repairing $1 via Compose force-recreate"
  compose up --detach --force-recreate --no-build --no-deps "$1"
}

while :; do
  gluetun_id=$(container_id "$GLUETUN_SERVICE")
  if [ -z "$gluetun_id" ]; then
    echo "Gluetun is missing; waiting for Compose reconciliation"
    sleep "$INTERVAL"
    continue
  fi

  gluetun_health=$(health_status "$gluetun_id")
  if [ "$gluetun_health" != "healthy" ]; then
    sleep "$INTERVAL"
    continue
  fi
  gluetun_started_at=$(started_at "$gluetun_id")

  for dependent in $DEPENDENTS; do
    dependent_id=$(container_id "$dependent")
    if [ -z "$dependent_id" ]; then
      echo "$dependent is missing; waiting for Compose reconciliation"
      continue
    fi

    attached_id=$(network_mode "$dependent_id")
    attached_id=${attached_id#container:}
    dependent_started_at=$(started_at "$dependent_id")
    if [ "$attached_id" != "$gluetun_id" ] || [ "$dependent_started_at" \< "$gluetun_started_at" ]; then
      repair "$dependent"
    fi
  done

  sleep "$INTERVAL"
done

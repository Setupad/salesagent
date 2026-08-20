# Setupad VPS PR Deployment Runbook

This runbook describes how to deploy Setupad fork or PR branch changes to the
Setupad VPS before they are approved in the official Prebid repository.

Target server: `root@209.38.235.125`

Current observed runtime shape:

- Host nginx terminates public HTTP/HTTPS on ports `80` and `443`.
- Host PostgreSQL 17 is running locally on port `5432`.
- The app runs as Docker container `sales-agent`.
- The currently deployed app image is locally tagged as `local-sales-agent:main-test`.
- Source checkout used for deployment is `/opt/salesagent`.
- Runtime env lives in `/opt/salesagent/.env`; do not print or commit it.

## Branch Roles

- `main`: clean sync branch for the official upstream repository.
- `feature/<topic>` or `pr/<topic>`: one reviewable branch per upstream PR.
- `deploy/base`: Setupad-only deployment patch branch. Keep runtime-only changes
  here when they are needed for the VPS but should not be included in upstream PRs.
- `deploy/vps`: deployment aggregation branch. Build this from current upstream
  `main`, then merge or cherry-pick `deploy/base` and the PR branches that should
  be live on the VPS.

Do not base upstream PR branches on `deploy/base` or `deploy/vps`.

## Local Setup

Keep the official repository as `origin` and add the Setupad fork as `setupad`:

```bash
git remote -v
git remote add setupad https://github.com/Setupad/salesagent.git
git fetch origin main
git fetch setupad main
```

If `setupad` already exists, use `git remote set-url setupad ...` instead of
adding it again.

## Prepare Deployment Branch

For one PR branch:

```bash
git fetch origin main
git fetch setupad feature/my-change
git switch -C deploy/vps origin/main
git merge --no-ff deploy/base
git merge --no-ff setupad/feature/my-change
```

For multiple pending PR branches, merge each branch into `deploy/vps` in the
order you want to test them.

Always record the exact commit SHA that will be deployed:

```bash
git rev-parse --short HEAD
git status --short --branch
```

## Read-Only Server Inspection

Before changing the server, verify the active runtime:

```bash
ssh root@209.38.235.125 '
  set -eu
  hostname
  docker ps --format "{{.Names}} {{.Image}} {{.Status}} {{.Ports}}"
  systemctl list-units --type=service --state=running --no-pager --no-legend \
    | grep -Ei "sales|adcp|nginx|docker|postgres|caddy|traefik" || true
  ss -ltnp | grep -E ":(80|443|8000|8080|5432)" || true
  cd /opt/salesagent
  git status --short --branch
  git log -1 --oneline
'
```

Do not print `.env`; it contains secrets.

## Backup Before First Deploy

On the VPS, capture deployment metadata and a database backup before the first
fork deploy or before any deploy with migrations:

```bash
ssh root@209.38.235.125 '
  set -eu
  mkdir -p /root/salesagent-deploy-backups
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  docker inspect sales-agent > /root/salesagent-deploy-backups/sales-agent-$ts.inspect.json
  docker image inspect local-sales-agent:main-test > /root/salesagent-deploy-backups/image-main-test-$ts.inspect.json
  cp /opt/salesagent/docker-compose.yml /root/salesagent-deploy-backups/docker-compose-$ts.yml 2>/dev/null || true
  cp /etc/nginx/nginx.conf /root/salesagent-deploy-backups/nginx-$ts.conf 2>/dev/null || true
  runuser -u postgres -- pg_dump --format=custom adcp > /root/salesagent-deploy-backups/salesagent-$ts.dump
'
```

If the database name is not `adcp`, identify it from the server's existing
`DATABASE_URL` without printing the password.

## Build Image On The VPS

Build by immutable commit SHA, not by `latest`:

```bash
DEPLOY_REF=<commit-sha-or-branch>

ssh root@209.38.235.125 "
  set -eu
  cd /opt/salesagent
  git fetch origin main
  git fetch setupad || true
  git fetch setupad '$DEPLOY_REF' || true
  git checkout '$DEPLOY_REF'
  short_sha=\$(git rev-parse --short HEAD)
  docker build -t local-sales-agent:\$short_sha .
  docker image inspect local-sales-agent:\$short_sha --format 'built {{.Id}} {{.Created}}'
"
```

If the deploy branch exists only on your laptop, push it to the Setupad fork
before running this step:

```bash
git push setupad deploy/vps
```

## Deploy Image

The observed production container uses the image tag `local-sales-agent:main-test`.
The least disruptive manual rollout is to retag the tested SHA image to that
runtime tag, recreate the container with the existing environment, and keep the
previous image metadata from the backup step for rollback.

Because container recreation details depend on the current run command, inspect
the exact options first:

```bash
ssh root@209.38.235.125 '
  docker inspect sales-agent --format "Image={{.Config.Image}} Restart={{.HostConfig.RestartPolicy.Name}} Network={{.HostConfig.NetworkMode}}"
  docker inspect sales-agent --format "{{range .Config.Env}}{{println .}}{{end}}" | sed "s/=.*//" | sort
'
```

Then recreate using the same env file and port mapping:

```bash
SHORT_SHA=<short-sha>

ssh root@209.38.235.125 "
  set -eu
  docker tag local-sales-agent:$SHORT_SHA local-sales-agent:main-test
  docker rm -f sales-agent
  docker run -d \
    --name sales-agent \
    --restart unless-stopped \
    --env-file /opt/salesagent/.env \
    -p 8000:8000 \
    local-sales-agent:main-test
  docker logs --tail=200 sales-agent
  curl -fsS http://127.0.0.1:8000/health
"
```

After the local health check passes, verify the public HTTPS domain:

```bash
curl -fsS https://<salesagent-domain>/health
```

## MCP OAuth Checks

MCP OAuth metadata and access-token audience validation depend on the public
sales agent URL. Before deploying MCP OAuth changes, verify `/opt/salesagent/.env`
contains the correct public domain settings without printing secret values:

```bash
ssh root@209.38.235.125 '
  set -eu
  cd /opt/salesagent
  grep -E "^(SALES_AGENT_DOMAIN|MCP_OAUTH_ISSUER|MCP_OAUTH_AUDIENCE)=" .env | sed "s/=.*$/=<set>/"
'
```

For the default configuration, `SALES_AGENT_DOMAIN=<salesagent-domain>` is enough.
Set `MCP_OAUTH_ISSUER` or `MCP_OAUTH_AUDIENCE` only when the public OAuth issuer
or canonical MCP resource URL differs from `https://<salesagent-domain>` and
`https://<salesagent-domain>/mcp`.

After deployment, verify the OAuth discovery documents over public HTTPS:

```bash
curl -fsS https://<salesagent-domain>/.well-known/oauth-protected-resource
curl -fsS https://<salesagent-domain>/.well-known/oauth-authorization-server
```

New advertisers receive both the existing permanent API token and OAuth client
credentials. OAuth-capable MCP clients should request a short-lived token from
`/oauth/token` using `grant_type=client_credentials` and `resource=https://<salesagent-domain>/mcp`,
then call `/mcp` with `Authorization: Bearer <access-token>`.

## Rollback

If the rollout fails before migrations complete, retag the previous image digest
or tag and recreate `sales-agent` with the same `docker run` command.

If the rollout ran irreversible migrations, restore the PostgreSQL dump before
returning to the previous app image.

## Promotion To Automation

After this manual flow has worked at least once, add a fork-owned GitHub Actions
workflow that:

1. Builds `deploy/vps` or a selected branch to `ghcr.io/setupad/salesagent:<sha>`.
2. Requires manual `workflow_dispatch` for deployment.
3. SSHes to the VPS, pulls the selected SHA image, recreates `sales-agent`, and
   checks `/health`.

Avoid automatic deploy-on-every-push until rollback and migration handling have
been tested.
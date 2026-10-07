# 7. Deployment — staging and production on Contabo

**Do not deploy to production until staging has passed every check below.**
Development → Staging → Production. Code reaches production only from the `main` branch through a
reviewed merge from `develop`; never commit directly to `main`.

## Recommended shape

Run Pakkmaxx CRM as its **own Docker Compose project** using Frappe's official `frappe_docker` images
(the same tooling your ERPNext deployment uses), completely separate from ERPNext:

```
Contabo VPS (Ubuntu 24.04)
├── existing ERPNext stack            (unchanged)
├── pakkmaxx-crm-staging  stack       own MariaDB, Redis, volumes  → staging-crm.<domain>
└── pakkmaxx-crm          stack       own MariaDB, Redis, volumes  → crm.<domain>
       ↑ reverse proxy (the one already in front of ERPNext, or nginx-proxy/Traefik) with HTTPS
```

Staging can live on the same VPS while traffic is low; move it to a second small VPS later if needed.

### Before you start — check on the VPS
- Free resources: Frappe v16 + CRM needs ~2 GB RAM per stack (4 GB+ VPS total with ERPNext; 8 GB comfortable)
  and ~10 GB disk per stack. `free -h`, `df -h`, `docker system df`.
- Which reverse proxy fronts ERPNext and which ports are taken: `docker ps`, `ss -tlnp`.
- DNS: create `crm.<domain>` and `staging-crm.<domain>` A records pointing at the VPS.
- Docker Engine ≥ 23 with compose plugin (`docker compose version`).

## 1. Source repository
Push this app to a **private** Git repository (e.g. GitHub `pakkmaxx/pakkmaxx_crm`):
`main` = production, `develop` = staging. Protect `main` (pull requests only).
Create a read-only deploy token for the image build.

## 2. Build the image (on the VPS or in CI)

```bash
git clone https://github.com/frappe/frappe_docker ~/pakkmaxx-crm-docker && cd ~/pakkmaxx-crm-docker
cat > apps.json <<'JSON'
[
  {"url": "https://github.com/frappe/crm", "branch": "v1.86.0"},
  {"url": "https://<deploy-token>@github.com/<org>/pakkmaxx_crm", "branch": "main"}
]
JSON
chmod 600 apps.json
docker build --no-cache \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-16 \
  --secret=id=apps_json,src=apps.json \
  --tag=pakkmaxx/crm:$(date +%Y%m%d)-main \
  --file=images/layered/Containerfile .
shred -u apps.json
```
For staging, build with `"branch": "develop"` and tag `…-develop`. Pin Frappe CRM to a tested tag;
upgrade it deliberately on staging first.

## 3. Compose file (one per environment)

```bash
cd ~/pakkmaxx-crm-docker
cat > ~/pakkmaxx-crm-staging.env <<'ENV'
CUSTOM_IMAGE=pakkmaxx/crm
CUSTOM_TAG=<tag>-develop
PULL_POLICY=never
DB_PASSWORD=<long random>
HTTP_PUBLISH_PORT=127.0.0.1:8091     # behind the existing reverse proxy; 8092 for production
ENV
chmod 600 ~/pakkmaxx-crm-staging.env
# --project-name is REQUIRED here: without it `config` pins volume names to `frappe_docker_*`
# and a second stack would mount the first stack's database volume.
docker compose --project-name pakkmaxx-crm-staging --env-file ~/pakkmaxx-crm-staging.env \
  -f compose.yaml -f overrides/compose.mariadb.yaml -f overrides/compose.redis.yaml \
  -f overrides/compose.noproxy.yaml config > ~/pakkmaxx-crm-staging.yaml
docker compose --project-name pakkmaxx-crm-staging -f ~/pakkmaxx-crm-staging.yaml up -d
```
The project name keeps containers, network and volumes separate from ERPNext. MariaDB is only reachable
on the stack's private Docker network (no published DB port).

## 4. Create the site

```bash
docker compose --project-name pakkmaxx-crm-staging exec backend \
  bench new-site staging-crm.<domain> --mariadb-user-host-login-scope='%' \
  --db-root-password '<DB_PASSWORD>' --admin-password '<strong admin password>' \
  --install-app crm --install-app pakkmaxx_crm
docker compose --project-name pakkmaxx-crm-staging exec backend \
  bench --site staging-crm.<domain> enable-scheduler
docker compose --project-name pakkmaxx-crm-staging exec backend \
  bench --site staging-crm.<domain> set-config host_name https://staging-crm.<domain>
```
(`'%'` here is scoped to the private compose network.) Do **not** set `developer_mode` on staging or
production.

## 5. HTTPS and proxy
Point `staging-crm.<domain>` at `127.0.0.1:8091` in the reverse proxy you already run (nginx: `proxy_pass`
with `Host` header preserved; Traefik/nginx-proxy: labels/VIRTUAL_HOST) and issue a Let's Encrypt
certificate. Only 80/443 should be open publicly (`ufw allow 80,443/tcp`; SSH restricted).

## 6. Staging checks (all must pass)

| Check | How |
|---|---|
| Automated tests | `bench --site <a test site> run-tests --app pakkmaxx_crm` in the image or locally against the same commit |
| Migration test | restore a copy of production's latest backup into staging (`bench --site … restore`), then `bench --site … migrate` — no errors |
| Workflow test | walk the [main flow](04-workflows.md) in `/crm` on a phone: WhatsApp lead → contact → qualify → follow-up → opportunity → won → customer → repeat opportunity; also Lost and Unqualified |
| Permission test | create demo users (`scripts/create_demo_users.py`) and run `PKX_BASE=https://staging-crm.<domain> PKX_HOST=staging-crm.<domain> PKX_PASSWORD=… python3 scripts/http_smoke_test.py` → 25/25; delete demo users afterwards |
| Authentication test | login/logout, password reset email, 2FA for managers & admins (System Settings → Enable Two Factor Auth), API key auth, session expiry |
| Performance check | dashboard and reports load < 2 s with realistic data; `docker stats` memory headroom |
| Security review | admin password rotated; no `developer_mode`; DB not exposed; HTTPS only; `allow_tests` off; no demo users; System Manager only for technical admins; backups encrypted off-site |
| Backup / restore | take a backup and restore it into a scratch site |

## 7. Production
Repeat steps 2–5 with project name `pakkmaxx-crm`, the `main` image tag, port `127.0.0.1:8092`, site
`crm.<domain>`, a different DB password. Then:

```bash
# scheduler on, backups with files, encrypted, daily off-site copy
docker compose --project-name pakkmaxx-crm exec backend bench --site crm.<domain> enable-scheduler
docker compose --project-name pakkmaxx-crm exec backend bench --site crm.<domain> set-config encryption_key "<keep a copy offline>"
```
Add `overrides/compose.backup-cron.yaml` (or a host cron running
`bench --site crm.<domain> backup --with-files`) and copy `sites/*/private/backups` off the VPS
(e.g. Contabo Object Storage / S3 via rclone). Configure an outgoing Email Account for notifications.
Create real users with the Pakkmaxx role profiles and build the CRM Sales Hierarchy.

## 8. Releasing an update
1. Merge to `develop` → build `-develop` image → on staging: **backup**, `docker compose … up -d`,
   `bench --site … migrate`, run the staging checks.
2. Pull request `develop` → `main`, review, merge.
3. On production: **backup first** (`bench --site crm.<domain> backup --with-files`), build/tag the `main`
   image, update `CUSTOM_TAG`, `docker compose --project-name pakkmaxx-crm -f ~/pakkmaxx-crm.yaml up -d`,
   then `bench --site crm.<domain> migrate`.
4. Rollback: previous image tag + restore the pre-release backup.

## Current deployment (Contabo VPS 169.58.1.243, `vmi3434181`)

This server already runs ERPNext, Mattermost, Glampack, Pakkmax WhatsApp and others. Ports 80/443 belong
to the **Caddy** container `pakkmax-caddy-1` (config `/opt/pakkmax/Caddyfile`), which routes by container
name over the Docker network `pakkmax_web`. Pakkmaxx CRM follows that pattern instead of publishing ports.

| | Staging |
|---|---|
| URL | https://crm-staging.169-58-1-243.sslip.io (Let's Encrypt via Caddy; no DNS needed) |
| Directory | `/opt/pakkmaxx-crm` (`frappe_docker/`, `apps.json`, `staging.env`, `staging-compose.yaml`, `secrets/`) |
| Compose project | `pakkmaxx-crm-staging` — own MariaDB 11.8, Redis, volumes; only `frontend` joins `pakkmax_web` (`compose.pakkmax-web.yaml`) |
| Image | `pakkmaxx/crm:<date>-develop-<commit>` built on the VPS from `develop` + Frappe CRM v1.86.0 |
| Caddy block | appended to `/opt/pakkmax/Caddyfile` (backup `Caddyfile.bak-*`), proxies to `pakkmaxx-crm-staging-frontend-1:8080` |

Common commands (on the VPS):

```bash
cd /opt/pakkmaxx-crm
DC="docker compose --project-name pakkmaxx-crm-staging -f staging-compose.yaml"
SITE=crm-staging.169-58-1-243.sslip.io
$DC ps
$DC exec backend bench --site $SITE backup --with-files
$DC exec backend bench --site $SITE migrate

# release a new develop build to staging
cd frappe_docker && TAG=$(date +%Y%m%d)-develop-$(git ls-remote https://github.com/collinsasante/pakkmaxx_crm refs/heads/develop | cut -c1-7)
docker build --build-arg=FRAPPE_BRANCH=version-16 --secret=id=apps_json,src=../apps.json \
  --tag=pakkmaxx/crm:$TAG --file=images/layered/Containerfile . && cd ..
sed -i "s/^CUSTOM_TAG=.*/CUSTOM_TAG=$TAG/" staging.env
docker compose --env-file staging.env -f frappe_docker/compose.yaml -f frappe_docker/overrides/compose.mariadb.yaml \
  -f frappe_docker/overrides/compose.redis.yaml -f compose.pakkmax-web.yaml config > staging-compose.yaml
$DC exec backend bench --site $SITE backup --with-files
$DC up -d && $DC exec backend bench --site $SITE migrate
```

Validate Caddy changes before reloading:
`docker cp <file> pakkmax-caddy-1:/tmp/c && docker exec pakkmax-caddy-1 caddy validate --adapter caddyfile --config /tmp/c`
then `docker exec pakkmax-caddy-1 caddy reload --adapter caddyfile --config /etc/caddy/Caddyfile`.

> Staging's compose file was generated before the `--project-name` fix, so its volumes are named
> `frappe_docker_db-data`, `frappe_docker_sites`, `frappe_docker_redis-queue-data`. They are pinned in
> `staging-compose.yaml`; do not regenerate that file without keeping those names (or migrating the data).

### Production

| | Production |
|---|---|
| URL | https://crm.pakkmax.com (Cloudflare DNS only → 169.58.1.243; Let's Encrypt via Caddy) |
| Compose project | `pakkmaxx-crm` — volumes `pakkmaxx-crm_db-data`, `pakkmaxx-crm_sites`, `pakkmaxx-crm_redis-queue-data` |
| Files | `/opt/pakkmaxx-crm/production.env`, `production-compose.yaml`, `secrets/production/`, `apps.production.json` (branch `main`) |
| Image | `pakkmaxx/crm:<date>-main-<commit>` |
| Backups | `/opt/pakkmaxx-crm/backup.sh` via root cron at 02:45 → `/opt/pakkmaxx-crm/backups/<stamp>/` (14 days), log `/var/log/pakkmaxx-crm-backup.log` |

```bash
cd /opt/pakkmaxx-crm
DC="docker compose --project-name pakkmaxx-crm -f production-compose.yaml"
SITE=crm.pakkmax.com
# generate the compose file (always with --project-name)
docker compose --project-name pakkmaxx-crm --env-file production.env -f frappe_docker/compose.yaml \
  -f frappe_docker/overrides/compose.mariadb.yaml -f frappe_docker/overrides/compose.redis.yaml \
  -f compose.pakkmax-web.yaml config > production-compose.yaml
# release: ./backup.sh, build the main image, update CUSTOM_TAG in production.env, regenerate, then
$DC up -d && $DC exec backend bench --site $SITE migrate
```

New sites: do **not** run Frappe's Setup Wizard — Frappe CRM hooks it to create demo data. Mark setup
complete instead (System Settings `setup_complete`, each Installed Application `is_setup_complete`), and
check System Settings: time zone **Africa/Accra**, country Ghana, currency GHS.

Off-site copies of `/opt/pakkmaxx-crm/backups` are not configured yet (add rclone to Contabo Object
Storage / S3 / Google Drive).

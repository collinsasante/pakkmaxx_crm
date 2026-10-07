# 1. Installation (local development)

## Versions

| Component | Version |
|---|---|
| Frappe Framework | 16.50.0 (`version-16` branch) |
| Frappe CRM | 1.86.0 (tag `v1.86.0`; supports Frappe `>=15,<17`) |
| pakkmaxx_crm | this repository |
| Python | 3.14 (Frappe v16 requires `>=3.14,<3.15`) |
| Node | 24+ (Frappe v16 requires `>=24`) |
| MariaDB | 11.8 (utf8mb4) |
| Redis | 6+ |
| bench CLI | frappe-bench 5.31 |

## macOS layout used for development

```
~/pakkmaxx-crm/
├── tools/            bench CLI venv, yarn, env.sh, mariadb client shims
├── secrets/          generated passwords (chmod 700, never commit)
└── frappe-bench/     the bench (bench cannot live in a path with spaces)
    ├── apps/frappe, apps/crm, apps/pakkmaxx_crm   ← this repo
    └── sites/pakkmaxx-crm.localhost (dev), sites/test.pakkmaxx.localhost (tests)
```

MariaDB runs in its own Docker container `pakkmaxx-crm-mariadb` (volume `pakkmaxx_crm_mariadb`) bound to
`127.0.0.1:3307`, isolated from every other project. `tools/bin/mariadb` and `tools/bin/mariadb-dump` are
shims that run the MariaDB client inside that container (Frappe v16 needs the `mariadb` CLI for
restores/backups).

## Daily commands

```bash
source ~/pakkmaxx-crm/tools/env.sh
docker start pakkmaxx-crm-mariadb               # if not running
cd ~/pakkmaxx-crm/frappe-bench
bench start                                     # web on http://pakkmaxx-crm.localhost:8000
```

Open `http://pakkmaxx-crm.localhost:8000/crm` (sales app) or `/app/pakkmaxx-crm` (dashboard).
Administrator password: `~/pakkmaxx-crm/secrets/admin_password`.

After pulling changes:

```bash
bench --site pakkmaxx-crm.localhost migrate
bench build --app pakkmaxx_crm
```

Run tests:

```bash
bench --site test.pakkmaxx.localhost run-tests --app pakkmaxx_crm
```

## Reproducing the setup from scratch

```bash
# prerequisites (macOS): python 3.14, node 24+, redis, docker, pkgconf, mariadb-connector-c
brew install pkgconf mariadb-connector-c
export PKG_CONFIG_PATH=/opt/homebrew/opt/mariadb-connector-c/lib/pkgconfig   # mysqlclient build

# database
docker run -d --name pakkmaxx-crm-mariadb --restart unless-stopped \
  -p 127.0.0.1:3307:3306 -e MARIADB_ROOT_PASSWORD="$DB_ROOT_PW" -e MARIADB_AUTO_UPGRADE=1 \
  -v pakkmaxx_crm_mariadb:/var/lib/mysql mariadb:11.8 \
  --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci --skip-character-set-client-handshake

# bench
python3.14 -m venv tools/bench-env && tools/bench-env/bin/pip install frappe-bench
npm install --prefix tools yarn@1
bench init --frappe-branch version-16 --python python3.14 frappe-bench
cd frappe-bench
bench get-app --branch v1.86.0 crm https://github.com/frappe/crm
bench get-app pakkmaxx_crm <this-repo-url>
bench new-site pakkmaxx-crm.localhost --mariadb-user-host-login-scope='%' \
  --db-host 127.0.0.1 --db-port 3307 --db-root-password "$DB_ROOT_PW" \
  --admin-password "$ADMIN_PW" --install-app crm --install-app pakkmaxx_crm
bench --site pakkmaxx-crm.localhost set-config developer_mode 1
```

`--mariadb-user-host-login-scope='%'` is only for this local setup (the Docker port is bound to
127.0.0.1). Production uses a private Docker network instead — see the deployment guide.

Installing `pakkmaxx_crm` (and every `bench migrate`) runs `pakkmaxx_crm.install.setup`, which is
idempotent: it creates roles, role profiles, custom fields, seed data, the lead workflow and CRM layouts
**only when missing**, so administrator changes survive upgrades.

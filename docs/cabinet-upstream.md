# Cabinet frontend (vendored)

Custom cabinet UI lives in `cabinet/` inside the remnabot monorepo (`k4lantar4/remnabot`).
There is **no** separate `k4lantar4/bedolaga-cabinet` fork.

## Remotes (local dev clone)

Optional standalone clone at `/opt/bedolaga-cabinet` for faster `npm` iteration:

| Remote     | URL                                              | Use |
|------------|--------------------------------------------------|-----|
| `upstream` | `https://github.com/BEDOLAGA-DEV/bedolaga-cabinet.git` | Read-only upstream merges |
| `remnabot` | `https://github.com/k4lantar4/remnabot.git`      | Push custom line (`cabinet/` path in monorepo) |

After changes in a standalone clone, copy into monorepo:

```bash
rsync -a --delete \
  --exclude='.git' --exclude='node_modules' --exclude='dist' \
  /opt/bedolaga-cabinet/ /opt/bot-remnawave/cabinet/
```

Or work directly in `/opt/bot-remnawave/cabinet/`.

## Pull upstream cabinet updates

From monorepo root:

```bash
git fetch upstream-cabinet   # add once: git remote add upstream-cabinet https://github.com/BEDOLAGA-DEV/bedolaga-cabinet.git
git subtree pull --prefix=cabinet upstream-cabinet main --squash
```

Or from `/opt/bedolaga-cabinet`:

```bash
git fetch upstream
git merge upstream/main
# resolve conflicts, then rsync into bot-remnawave/cabinet/
```

## Docker build

`docker-compose.yml` builds `cabinet-frontend` from `./cabinet` (not a sibling repo).

```bash
docker compose build cabinet-frontend
docker compose up -d cabinet-frontend
```

## Vendored baseline

- Source branch: `fix/currency-display-toman` (Persian Phase A currency display)
- Upstream base: BEDOLAGA-DEV/bedolaga-cabinet `main` (post #448)

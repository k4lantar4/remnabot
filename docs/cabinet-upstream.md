# Cabinet frontend (vendored)

Custom cabinet UI lives in `cabinet/` inside the remnabot monorepo (`k4lantar4/remnabot`).
There is **no** separate `k4lantar4/bedolaga-cabinet` fork.

## Official development path

**Work only in** `/opt/bot-remnawave/cabinet/` — this is what Docker and CI build from.
Do not rely on a sibling clone for merges or deploys.

## Remotes (monorepo root)

| Remote              | URL                                                        | Use |
|---------------------|------------------------------------------------------------|-----|
| `upstream-cabinet`  | `https://github.com/BEDOLAGA-DEV/bedolaga-cabinet.git`     | Read-only upstream merges (push blocked: `no_push`) |
| `remnabot`          | `https://github.com/k4lantar4/remnabot.git`                | Push custom line (`cabinet/` path in monorepo) |

Add once (already configured in production clone):

```bash
git remote add upstream-cabinet https://github.com/BEDOLAGA-DEV/bedolaga-cabinet.git
git remote set-url --push upstream-cabinet no_push
git fetch upstream-cabinet main
```

## Pull upstream cabinet updates (archive merge)

Preferred method — no subtree history required:

```bash
git fetch upstream-cabinet
mkdir -p /tmp/cabinet-upstream
git archive upstream-cabinet/main | tar -x -C /tmp/cabinet-upstream
# diff /tmp/cabinet-upstream with cabinet/ and merge into cabinet/
# preserve overlays: useCurrency.ts (skipFxConversion for fa), fa.json toman keys
cd cabinet && npm ci && npm run build
```

Commit as a single concern, e.g. `chore(cabinet): merge upstream X.XX preserving toman display overlay`.

**Subtree** (`git subtree pull --prefix=cabinet upstream-cabinet main`) is optional for later if you want unified history; not required for the first merge round.

## Legacy standalone clone (optional)

`/opt/bedolaga-cabinet` may still exist for faster local `npm` iteration. It is **not** required for upstream merges.

If you develop there, sync back into the monorepo:

```bash
rsync -a --delete \
  --exclude='.git' --exclude='node_modules' --exclude='dist' \
  /opt/bedolaga-cabinet/ /opt/bot-remnawave/cabinet/
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

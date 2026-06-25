# Pok-mon-Inventory-Checker
Checks online stores for retail prices Pokémon tcg drops
# Target Pokémon TCG Restock Monitor

Monitors Target.com for Pokémon ETBs, booster boxes, booster packs, and
related merchandise, and pushes a phone notification the moment something
flips from out-of-stock to in-stock.

**What this does NOT do:** add to cart, check out, or buy anything.
It only reads stock status. You still click "buy" yourself, on Target's
own site.

**Honesty about reliability:** this uses Target's public but undocumented
"RedSky" API — the same endpoints Target.com itself calls to show stock
badges. It is not an official integration. Target can change it, rate-limit
it, or block it without warning. If alerts stop coming through, that's the
most likely reason — check the Actions tab for failed runs.

---

## 1. Get a push notification app (2 minutes)

1. Install the **ntfy** app on your phone (iOS App Store / Google Play),
   or just use a browser at ntfy.sh.
2. Pick a topic name that's hard to guess (e.g. `nick-target-pkmn-7f3a`) —
   anyone who knows your topic name can see your alerts, since ntfy topics
   aren't private by default.
3. In the ntfy app, tap "+" and subscribe to that topic name.

## 2. Set up the repo on GitHub (5 minutes)

1. Create a new **private** GitHub repository.
2. Upload all the files in this folder (`target_monitor.py`,
   `requirements.txt`, `config.json`, `.github/workflows/monitor.yml`).
3. Edit `config.json`:
   - Replace `ntfy_topic` with the topic name you picked in step 1.
   - Replace `zip` with your zip code (affects shipping availability checks).
4. Commit and push.

## 3. Turn it on

- Go to the repo's **Actions** tab. GitHub may ask you to enable workflows
  — click enable.
- It will now run automatically every 15 minutes.
- To test immediately: Actions tab → "Pokemon TCG Target Monitor" →
  "Run workflow" (manual trigger button).

## 4. Tuning it

- `SEARCH_TERMS` in `target_monitor.py` controls what's searched. Add or
  remove terms to widen/narrow coverage (e.g. add a specific set name like
  "pokemon scarlet violet booster box" if you want tighter targeting
  instead of "all Pokémon TCG").
- The cron schedule (`*/15 * * * *`) checks every 15 minutes. You can make
  it more frequent, but faster polling increases the chance Target rate-
  limits or blocks the requests — 15 minutes is a reasonable balance.
- `state.json` is how it avoids re-alerting on the same restock — it's
  committed back to the repo after each run.

## Limitations worth knowing

- Free GitHub Actions has a monthly minutes cap on private repos (2,000
  min/month on the free tier). At ~1-2 minutes per run, every 15 minutes,
  that's roughly 3,000-6,000 min/month — likely over the free limit if run
  this frequently. Either make the repo public (unlimited minutes, but the
  repo itself becomes visible) or widen the interval to every 30 minutes.
- "All Pokémon TCG items broadly" via keyword search will surface some
  noise (random merchandise, unrelated listings) — narrow `SEARCH_TERMS`
  if you want cleaner results.
- No purchase automation, by design.

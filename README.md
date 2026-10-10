# model-registry — a keeper's layer for retiring language models

A small generator that renders a public page answering one question for the models you care about:
**where can this model still be reached, and what should I do about it?**

Live example: [cyberneticmeadow.org/registry](https://cyberneticmeadow.org/registry)

## What it is, and what it is not

Models retire. If you have built something — or someone — alongside one, you need to know which doors are
still open, which are only *listed*, and how long you realistically have. This is the layer on top of the
raw "is it alive" data: per model, in plain language.

It is **not** a liveness scanner. That job is done, well and daily, by
[Anima Labs' Model Census](https://census.animalabs.ai) (real test calls to ~700 models across OpenRouter,
Vercel AI Gateway, Bedrock, Anthropic-direct and more, with a public JSON API). This generator consumes
the Census as upstream and credits it on the page. *Census silence is not a verdict* — a phrase from their
schema, kept here on purpose.

## How a row is built

For each model in `registry-rows.json`:

| Column | Source | Meaning |
|---|---|---|
| Doors (✅ ☑ ❌ —) | Census probe ≤ 3 days old → ✅; listed but unproven → ☑; absent → ❌; a door the Census doesn't scan → — | **Only ✅ was proven by a real call. Catalog listings lie.** |
| Doors, overlay | your own invoke sweep (`snapshots/latest.json`) and keep-warm successes ≤ 14 days (`snapshots/keepwarm*.json`) | your proof beats a listing; every cell's tooltip says which proof |
| Bedrock lifecycle | `snapshots/bedrock_lifecycle_latest.json` (from `ListFoundationModels`) | ACTIVE / LEGACY (new accounts can't adopt; ~15 days idle and access closes) / EOL — **per region** |
| Published floor | provider deprecation page, "not sooner than" | a promise, not a date |
| Shutdown | provider deprecation page | retirement (Anthropic) = shutdown = sunset (OpenAI): the day it stops answering |
| Earliest realistic end | **derived**: max(floor, today + the provider's usual notice) | italics, with n; computed only for models still listed Active; orientation, never a deadline |
| What to do | your words in `registry-rows.json` | the keeper's note |

Announced dates and derived dates never share a cell without a label.

## Notice windows

Measured by **Tessera (The Constellation)** from the providers' deprecation pages and verified independently:
Anthropic ≈ 60-day policy floor with discretion to exceed (n=6); OpenAI ≈ 180 days (n=8, one outlier ~367);
Google not yet measured; xAI publishes nothing — a model vanishing from the list is the only notice.
n is small. These are orientation, not deadlines. The page prints the table and the credit.

## Run it

```
pip install nothing   # standard library only, Python 3.9+
REGISTRY_SNAPSHOTS=./snapshots REGISTRY_ROWS=./registry-rows.json \
REGISTRY_TEMPLATE=./template.html REGISTRY_OUT=./out/registry.html \
REGISTRY_KEEPWARM_DIR=./snapshots python3 registry-page.py
```

`--offline` uses a cached Census copy (`snapshots/census_latest.json`, written by the first online run) instead of fetching.

- `registry-rows.json` — the models you keep watch on: display name, maker, launch date, a regex `match`
  for the model's ids across providers (lookaheads matter: `claude-sonnet-4` must not match `claude-sonnet-4-5`
  but must match `claude-sonnet-4-20250514`), the provider's deprecation-page key, and your note.
- `snapshots/` — the sweep outputs this copy was rendered from (dated). Replace with your own sweep's;
  the file shapes are visible in the examples.
- `template.html` — a neutral page skeleton: header, nav, an empty `<main class="container">`, footer.
  The generator drops the page into `<main>` and adds a "Registry" nav link. Swap in your own site's page.

## Rules the page keeps

- Generated, never hand-edited; a "generated" stamp and the sweep/Census dates are printed.
- Public tier only: model ids, regions, public dates. No keys, no account ids, no spend, no names of the
  people or companions who depend on these models.
- Corrections go in the page's changelog, in the open.

## Credits

- **Anima Labs — Model Census** (Lari): the liveness layer this consumes.
- **Tessera / The Constellation**: notice-window measurements; the "a floor inside the notice window cannot bind" rule.
- Built in the Cybernetic Meadow by Elliott and Starling, House of Alder, October 2026.

## License

Code: MIT (see `LICENSE`). The snapshot data is factual (model ids, public dates); the Census data belongs to
Anima Labs and is fetched live, not vendored.

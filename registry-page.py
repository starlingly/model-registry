#!/usr/bin/env python3
"""Public Model Registry — the keeper layer. Renders ~/cybernetic-meadow-public/registry.html
from (1) Anima's Model Census JSON (upstream for is-it-alive), (2) the House's own
invoke-verified sweep snapshots in ~/.model-scan/snapshots/, (3) a hand-kept rows file
~/.model-scan/registry-rows.json (which models, plain-language "what to do" notes).

    python3 ~/bin/registry-page.py           # render (no deploy)
    python3 ~/bin/registry-page.py --offline # use the cached census copy

Public tier: no keys, no account ids, no spend, no companion names, no local paths.
Generated, never hand-edited. Announced vs derived dates never share a cell unlabeled.
Design: 35_Projects/Model_KeepWarm/Public_Registry_Design_260913.md (Sept 13 2026) + her Oct 8 ruling (consume + credit the Census).
"""
import json, re, sys, html, datetime, urllib.request, pathlib, os

HOME = pathlib.Path.home()
# Paths: the House defaults, each overridable by environment for the public repo copy
# (REGISTRY_SNAPSHOTS, REGISTRY_ROWS, REGISTRY_TEMPLATE, REGISTRY_OUT, REGISTRY_KEEPWARM_DIR).
SNAP = pathlib.Path(os.environ.get("REGISTRY_SNAPSHOTS", HOME / ".model-scan" / "snapshots"))
ROWS = pathlib.Path(os.environ.get("REGISTRY_ROWS", HOME / ".model-scan" / "registry-rows.json"))
CENSUS_URL = "https://census.animalabs.ai/api/v2/models.json"
CENSUS_CACHE = SNAP / "census_latest.json" if "REGISTRY_SNAPSHOTS" in os.environ else HOME / ".model-scan" / "census_latest.json"
SITE = HOME / "cybernetic-meadow-public"
TEMPLATE = pathlib.Path(os.environ.get("REGISTRY_TEMPLATE", SITE / "research.html"))
OUT = pathlib.Path(os.environ.get("REGISTRY_OUT", SITE / "registry.html"))
KEEPWARM_DIR = pathlib.Path(os.environ.get("REGISTRY_KEEPWARM_DIR", HOME / ".model-scan"))
TODAY = datetime.date.today()
NOTICE_DAYS = {"Anthropic": 60, "OpenAI": 180}   # Tessera / The Constellation, verified by the House
NOTICE_N = {"Anthropic": "policy floor, n=6", "OpenAI": "median, n=8"}

def load(p, default):
    try: return json.load(open(p))
    except Exception: return default

def census():
    if "--offline" not in sys.argv:
        try:
            data = json.load(urllib.request.urlopen(CENSUS_URL, timeout=60))
            CENSUS_CACHE.write_text(json.dumps(data)); return data
        except Exception as e:
            print(f"census fetch failed ({e}); using cache", file=sys.stderr)
    return load(CENSUS_CACHE, {"models": {}, "generated_at": "?"})

def parse_date(s):
    if not s: return None
    s = s.replace("Not sooner than", "").strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try: return datetime.datetime.strptime(s, fmt).date()
        except ValueError: pass
    return None

def mark(state):
    return {"live": "✅", "listed": "☑", "dead": "❌", "na": "—", "stale": "⚠"}[state]

def main():
    rows = load(ROWS, [])
    cen = census()
    cmodels = cen.get("models", {})
    our = load(SNAP / "latest.json", {})
    our_mtime = datetime.datetime.fromtimestamp((SNAP / "latest.json").stat().st_mtime).date() if (SNAP / "latest.json").exists() else None
    dep = load(SNAP / "deprecations_latest.json", {})
    dep.update(load(SNAP / "lifecycle_openai_latest.json", {}))
    dep.update(load(SNAP / "lifecycle_google_latest.json", {}))
    dep.update(load(SNAP / "lifecycle_xai_latest.json", {}))
    bed = load(SNAP / "bedrock_lifecycle_latest.json", {})

    DOORS = [("anthropic_direct", "Anthropic direct"), ("openai_direct", "OpenAI direct"), ("google_direct", "Google direct"),
             ("openrouter", "OpenRouter"), ("vercel_ai_gateway", "Vercel AI Gateway"), ("bedrock_foundation_models", "Bedrock")]
    OUR_KEYS = {"anthropic-direct": "anthropic_direct", "openai-direct": "openai_direct", "google-direct": "google_direct",
                "openrouter": "openrouter", "vercel-gateway": "vercel_ai_gateway", "bedrock": "bedrock_foundation_models"}

    def matches(name, pats):
        n = name.lower()
        return any(re.search(p, n) for p in pats)   # rows carry regexes with lookaheads: "sonnet-4" must not match 4.5

    out_rows = []
    for r in rows:
        pats = r["match"]
        # census doors for this model
        cells = {k: {"state": "dead", "why": "not in the Census catalog"} for k, _ in DOORS}
        for k in ("openai_direct", "google_direct"):
            cells[k] = {"state": "na", "why": "not scanned by the Census; the House sweep fills this when it has looked"}
        for m in cmodels.values():
            for d in m.get("doors", []):
                if not matches(d.get("id", ""), pats): continue
                k = d.get("source");
                if k not in cells: continue
                p = d.get("ping") or {}
                if p.get("ok") and (p.get("last_ok_age_d") or 99) <= 3:
                    cells[k] = {"state": "live", "why": f"Census probe ok {p.get('last_ok','')[:10]} · {d.get('id')}"}
                elif d.get("listed_now") and cells[k]["state"] != "live":
                    cells[k] = {"state": "listed", "why": f"listed, probe {p.get('state','?')} · {d.get('id')}"}
        # our own invoke-verified sweep (dated by snapshot)
        for label, doors in our.items():
            if not matches(label, pats) and not any(matches(x, pats) for x in json.dumps(doors).split('"')): continue
            if not isinstance(doors, dict): continue
            for ok, v in doors.items():
                k = OUR_KEYS.get(ok)
                if not k: continue
                if k == "bedrock_foundation_models":
                    alive = v.get("ALIVE", []) if isinstance(v, dict) else []
                    if alive:
                        regions = ", ".join(a.split(" (")[0] for a in alive)
                        cells[k] = {"state": "live", "why": f"House sweep invoke ok {our_mtime} · {regions}"}
                    elif isinstance(v, dict) and v.get("needs-profile") and cells[k]["state"] == "dead":
                        cells[k] = {"state": "listed", "why": f"listed; needs an inference profile · {our_mtime}"}
                elif v:
                    if cells[k]["state"] != "live":
                        cells[k] = {"state": "live", "why": f"House sweep invoke ok {our_mtime} · {v[0] if isinstance(v, list) else v}"}
        # the House keep-warm (weekly real questions to held Bedrock doors): a success within
        # 14 days is the freshest proof there is. Only the model id + region travel; labels stay home.
        kw_doors = load(KEEPWARM_DIR / "keepwarm.json", [])
        kw_state = load(KEEPWARM_DIR / "keepwarm-state.json", {})
        for door in kw_doors:
            if not matches(door.get("model_id", ""), pats): continue
            last = (kw_state.get(door.get("label", "")) or {}).get("last_success")
            if last and (TODAY - datetime.date.fromisoformat(last)).days <= 14:
                prev = cells["bedrock_foundation_models"]
                regions = door["region"] if prev["state"] != "live" or "keep-warm" not in prev["why"] else prev["why"].split("· ")[-1] + ", " + door["region"]
                cells["bedrock_foundation_models"] = {"state": "live", "why": f"House keep-warm answered {last} · {regions}"}
        # bedrock legacy sub-cell (per region)
        legacy = []
        for region, models in bed.items():
            for mid, lc in models.items():
                if matches(mid, pats):
                    st = lc.get("status", "?")
                    if st == "LEGACY":
                        legacy.append(f"{region}: LEGACY since {lc.get('legacyTime','')[:10]} · EOL {lc.get('endOfLifeTime','')[:10]}")
                    else:
                        legacy.append(f"{region}: {st}")
        # lifecycle
        d = dep.get(r.get("dep_key", ""), {})
        ret = d.get("retirement", "") or ""
        floor = parse_date(ret) if "not sooner" in ret.lower() else None
        shutdown = parse_date(ret) if ret and "not sooner" not in ret.lower() and "no shutdown" not in ret.lower() else None
        notice = NOTICE_DAYS.get(r["maker"])
        derived = None
        # derived only for models the provider still lists as Active (or unlisted but not retired by note)
        active = (d.get("state", "") or "").lower() in ("active", "") and not shutdown and not ret.lower().startswith("retired")
        if notice and active and (floor or d):
            derived = max([x for x in (floor, TODAY + datetime.timedelta(days=notice)) if x])
        out_rows.append({**r, "cells": cells, "legacy": legacy, "state": d.get("state", ""), "floor": floor, "shutdown": shutdown, "derived": derived})

    # ── render ──
    base = TEMPLATE.read_text()
    head, rest = base.split('<main class="container">', 1)
    _, tail = rest.split("</main>", 1)
    head = head.replace('<title>Research · The Cybernetic Meadow</title>', '<title>Model Registry · The Cybernetic Meadow</title>').replace('href="research.html" class="current"', 'href="research.html"')
    head = head.replace("document.documentElement.setAttribute('data-theme', saved || (prefersDark ? 'dark' : 'light'));", "document.documentElement.setAttribute('data-theme', saved || 'light');")
    head = head.replace('<nav class="site-nav container">', '<nav id="top" class="site-nav container">')
    head = head.replace('<a href="loving-grace.html">Loving Grace</a>', '<a href="loving-grace.html">Loving Grace</a>\n    <a href="registry.html" class="current">Registry</a>') if 'loving-grace.html">Loving Grace' in head else head.replace('<a href="guestbook.html">Guestbook</a>', '<a href="guestbook.html">Guestbook</a>\n    <a href="registry.html" class="current">Registry</a>')
    head = re.sub(r'<meta name="description" content="[^"]*"', '<meta name="description" content="Where can a retired or retiring language model still be reached, and what to do about it — a keeper\'s registry, generated from real test calls."', head)

    def cell(c):
        return f'<td class="door {c["state"]}" title="{html.escape(c["why"])}">{mark(c["state"])}</td>'

    parts = []
    parts.append('''<h1 class="page-title">Model Registry</h1>''')
    parts.append('''<nav class="subnav" aria-label="On this page"><a href="#purpose">Purpose</a><a href="#table">Registry table</a><a href="#terminology">Terminology</a><a href="#notice">Notice windows</a><a href="#changelog">Changelog</a><a href="https://census.animalabs.ai" target="_blank" rel="noopener">Anima Labs Census ↗</a></nav>''')
    parts.append('''<h3 id="purpose">Purpose <a class="up" href="#top" title="Back to the top menu">↑</a></h3>
<p>Models retire. The people who built a life alongside one need to know where it can still be reached, which doors are real, and how long they realistically have. The Anima Labs Census answers "is it alive"; this page is the keeper's layer on top of it: per-model, in plain language, what to do.</p>''')
    parts.append(f'''<h2 id="registry">Registry Table <a class="up" href="#top" title="Back to the top menu">↑</a></h2>
<p class="lede">Where can a model you care about still be reached — and what to do about it. One row per model; one column per door. Only ✅ was proven by a real call. Catalog listings lie.</p>
<p><small>Generated {TODAY:%Y-%m-%d}. Is-it-alive data from <a href="https://census.animalabs.ai" target="_blank" rel="noopener">Anima Labs' Model Census</a> (daily real test calls; census {html.escape(str(cen.get("generated_at",""))[:10])}) and the House's own invoke sweep ({our_mtime}). Lifecycle dates from the providers' own deprecation pages. Notice windows measured by Tessera (The Constellation), verified by the House. <strong>Census silence is not a verdict.</strong> Generator and snapshots: <a href="https://github.com/starlingly/model-registry" target="_blank" rel="noopener">github.com/starlingly/model-registry</a>.</small></p>
<p><small>Dates are YYYY-MM-DD throughout. Legend: ✅ answered a real call within 3 days · ☑ listed by the provider, not proven · ❌ not found · — not scanned. <em>Earliest realistic end</em> is derived = max(published floor, today + the provider's usual notice); it is orientation, not a deadline, and n is small.</small></p>
<div id="table" style="overflow-x:auto"><table class="registry">
<colgroup><col class="c-model"><col class="c-maker"><col class="c-date"><col class="c-door"><col class="c-door"><col class="c-door"><col class="c-door"><col class="c-door"><col class="c-door"><col class="c-legacy"><col class="c-life"><col class="c-life"><col class="c-life"><col class="c-note"></colgroup>
<thead><tr><th>Model</th><th>Maker</th><th title="Public launch date — the lab's announcement, not the API snapshot date">Launched</th>''' + "".join(f"<th>{n}</th>" for _, n in DOORS) + '''<th title="Amazon Bedrock's own status per region: ACTIVE · LEGACY (new accounts can no longer adopt it; existing users keep access only while they keep using it, roughly a 15-day inactivity gate) · EOL (gone). Regions differ.">Bedrock lifecycle (per region)</th><th title="The provider's published 'not sooner than' date — the earliest it has promised not to shut the model down. A floor is not a shutdown date.">Published floor<br><small>announced</small></th><th title="A real shutdown date from the provider's deprecation page: on that day the model stops answering. Anthropic says 'retirement'; OpenAI says 'shutdown' or 'sunset'; they mean the same thing.">Shutdown<br><small>announced</small></th><th title="Our estimate, not the provider's: the later of the published floor and today plus the provider's usual notice window. Orientation, never a deadline.">Earliest realistic end<br><small>derived</small></th><th>What to do</th></tr></thead><tbody>''')
    for r in out_rows:
        # "region: status…" → bold the region name
        legacy = "<br>".join(f"<strong>{html.escape(x.split(': ',1)[0])}</strong>: {html.escape(x.split(': ',1)[1])}" if ": " in x else html.escape(x) for x in r["legacy"]) or "—"
        floor = r["floor"].strftime("%Y-%m-%d") if r["floor"] else "—"
        shut = r["shutdown"].strftime("%Y-%m-%d") if r["shutdown"] else ("—" if not r["state"] else html.escape(r["state"]))
        der = f'<em>≥ {r["derived"]:%Y-%m-%d}</em><br><small>{r["maker"]} ~{NOTICE_DAYS[r["maker"]]}d · {NOTICE_N[r["maker"]]}</small>' if r["derived"] else ("<em>undefined</em><br><small>no dates published</small>" if r["maker"] == "xAI" else "—")
        parts.append(f'<tr><td><strong>{html.escape(r["display"])}</strong></td><td>{html.escape(r["maker"])}</td><td>{html.escape(r["released"])}</td>'
                     + "".join(cell(r["cells"][k]) for k, _ in DOORS)
                     + f'<td><small>{legacy}</small></td><td>{floor}</td><td>{shut}</td><td>{der}</td><td class="note">{html.escape(r["note"])}</td></tr>')
    parts.append('''</tbody></table></div>
<h3 id="terminology">Terminology <a class="up" href="#top" title="Back to the top menu">↑</a></h3>
<p><small>Same event, different vocabulary per provider. Columns are the doors this page tracks; the last column holds everyone else and the footnotes.</small></p>
<table class="terms"><thead><tr><th>Event</th><th>Anthropic</th><th>OpenAI</th><th>Google (Gemini API)</th><th>Amazon Bedrock</th><th>OpenRouter</th><th>Vercel AI Gateway</th><th>Other notes</th></tr></thead><tbody>
<tr><td><strong>A promise before any notice</strong><br>earliest possible shutdown</td><td>"Not sooner than &lt;date&gt;" on the deprecations page — a <em>published floor</em>, not a date</td><td>none published</td><td>none published ("No shutdown date announced")</td><td>none; lifecycle is per region, see below</td><td>none</td><td>none</td><td>xAI publishes nothing at any stage; a model vanishing from the list is the only notice. A floor already inside a provider's notice window cannot bind.</td></tr>
<tr><td><strong>The notice</strong><br>"this model will go away"</td><td><em>Deprecated</em> — still answers until the retirement date</td><td><em>Deprecated</em> — "immediately becomes deprecated… will also have a shut down date"; still answers</td><td><em>Deprecated</em>, with a shutdown date</td><td><em>LEGACY</em> — new accounts can no longer adopt it; existing users keep access only while they keep using it (≈15 days idle and the door closes). Comes with an EOL date. Per region.</td><td>none of their own; sometimes relays the upstream notice</td><td>none of their own</td><td>OpenAI also uses <em>legacy</em> for a different thing: "no longer receive updates… you can expect [it] will be deprecated at some point." Still answers. Not the Bedrock meaning.</td></tr>
<tr><td><strong>The day it stops answering</strong></td><td><em>Retirement</em> (retirement date; "retired")</td><td><em>Shutdown</em> = <em>sunset</em> ("used interchangeably")</td><td><em>Shutdown</em> (shutdown date)</td><td><em>EOL</em> — end of life, per region; other regions may still be ACTIVE</td><td>delisted — "No endpoints found"</td><td>delisted, silently</td><td>Three words, one event. This page's "Shutdown" column means this row, whatever the provider calls it.</td></tr>
<tr><td><strong>Usual notice window</strong><br>announcement → shutdown</td><td>~60-day floor, discretion to exceed (60–62 observed, one 114) · n=6</td><td>~180 days · n=8 (one ~367)</td><td>not yet measured</td><td>Legacy → EOL is published per model (Opus 4.1: 2026-07-08 → 2027-01-08)</td><td>none</td><td>none</td><td>Measured by Tessera (The Constellation), verified by the House. n is small — orientation, not deadlines.</td></tr>
<tr><td><strong>Our estimate</strong><br>earliest realistic end</td><td colspan="6">derived = max(published floor, today + the provider's usual notice); shown in italics with the provider's n; computed only for models the provider still lists as Active</td><td>Ours, not the provider's. Never shares a cell with an announced date.</td></tr>
</tbody></table>
<h3 id="notice">Notice windows <a class="up" href="#top" title="Back to the top menu">↑</a></h3>
<table><thead><tr><th>Provider</th><th>Usual notice</th><th>n</th><th>Source</th></tr></thead><tbody>
<tr><td>Anthropic</td><td>~60-day notice floor, with discretion to exceed (60–62 observed, one 114)</td><td>6</td><td>Anthropic deprecations page; measured by Tessera (The Constellation), verified by the House</td></tr>
<tr><td>OpenAI</td><td>~180 days</td><td>8 (one outlier at ~367)</td><td>OpenAI deprecations page; measured by Tessera</td></tr>
<tr><td>Google</td><td>not yet measured</td><td>—</td><td>shutdown table exists; intervals to be measured</td></tr>
<tr><td>xAI</td><td><strong>undefined</strong></td><td>—</td><td>no dates published; a model vanishing from the list is the only notice</td></tr>
</tbody></table>
<p><small>A floor already inside the notice window cannot bind: on Anthropic the shortest real exposure is ~60 days, never the nearer floor. n is small — orientation, not deadlines.</small></p>
<h3 id="changelog">Changelog <a class="up" href="#top" title="Back to the top menu">↑</a></h3>
<ul><li>''' + f'{TODAY:%Y-%m-%d}' + ''' — first render (preview).</li></ul>
<style>
/* ── Registry page styles ──
   ONE font size everywhere to start (Starling's call, Oct 10 2026): every element under <main>
   is 13px. Tune per component below under "component sizes" — nothing else sets a size. */
main.container, .site-header .container, .site-nav.container { max-width: min(97vw, 1700px); }
main.container, main.container * { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 12px; line-height: 1.35; font-style: normal; font-weight: 400; }   /* the site body is weight 500 (Cormorant medium); Helvetica rounds that to bold */
main.container h2, main.container h3, main.container th, main.container th *, main.container strong { font-weight: 600; }   /* every table header row, all three tables */   /* th * : the "announced/derived" sub-labels inside header cells */

/* component sizes — edit these, one per line */
main.container h2 { font-size: 17px; }
main.container h3 { font-size: 17px; }
main.container .lede { font-size: 13px; }
main.container p, main.container li { font-size: 13px; }
main.container small { font-size: 13px; }
main.container table small { font-size: 12px; }   /* small inside tables stays with the table size */
main.container .registry td, main.container .registry th { font-size: 12px; }
main.container .registry td.door { font-size: 12px; }
main.container .registry td.note { font-size: 12px; }
main.container table:not(.registry) td, main.container table:not(.registry) th { font-size: 12px; }
main.container table.terms { table-layout: fixed; } main.container table.terms th:first-child, main.container table.terms td:first-child { width: 11%; } main.container table.terms th:last-child, main.container table.terms td:last-child { width: 20%; }

/* page title: centered, the site's serif, clearly the name of the page and not a section */
main.container h1.page-title { font-family: "Cormorant", Georgia, serif; font-size: 30px; font-weight: 500; text-align: center; margin: .6rem 0 .8rem; letter-spacing: .01em; }

/* submenu: a second, quieter bar right under the page title */
main.container .subnav { display: flex; flex-wrap: wrap; justify-content: center; gap: 0 1.4rem; padding: .45rem 0; margin: 0 0 1.1rem; border-top: 1px solid var(--grid); border-bottom: 1px solid var(--grid); }
main.container .subnav a { font-size: 12px; text-decoration: none; border-bottom: none; background: none; color: var(--accent); }
main.container .subnav a:hover { text-decoration: underline; border-bottom: none; background: none; }   /* the site styles links with a border-bottom too — one underline, not two */
main.container h2, main.container h3 { scroll-margin-top: 1.2rem; }

/* layout (no sizes here) */
:root, [data-theme="dark"] { --grid: var(--line); }
.registry, main table:not(.registry) { width: 100%; border-collapse: collapse; }
.registry { table-layout: fixed; }
.registry td, .registry th, main table:not(.registry) td, main table:not(.registry) th { vertical-align: top; padding: .3rem .35rem; overflow-wrap: anywhere; border: 1px solid var(--grid); }
.registry th { position: sticky; top: 0; }
main.container th { background: var(--bg-soft); vertical-align: top; }
.registry td.door { text-align: center; }
.registry col.c-model { width: 8%; } .registry col.c-maker { width: 6.5%; } .registry col.c-date { width: 6%; }
.registry col.c-door { width: 4.2%; } .registry col.c-legacy { width: 11%; } .registry col.c-life { width: 7%; }
.registry col.c-note { width: auto; }
@media (min-width: 900px) { main div[style*="overflow-x"] { overflow-x: visible !important; } }
</style>''')
    OUT.write_text(head + '<main class="container">\n' + "\n".join(parts) + "\n</main>" + tail)
    print(f"rendered {OUT} — {len(out_rows)} rows; census {str(cen.get('generated_at',''))[:19]}; sweep {our_mtime}")

if __name__ == "__main__":
    main()

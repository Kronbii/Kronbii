"""
Draws recent commits as white light split by a prism.

    ACCESS_TOKEN=... USER_NAME=Kronbii python prism.py

Runs in the daily workflow and writes assets/prism-light.svg and
assets/prism-dark.svg. A beam -- the commits of the last `prism_days` (90 by
default here) to the repositories in `prism_include` -- enters a prism and leaves as a spectrum, one band per
repository, each as wide as its share of the commits. The biggest band is
always the green end of the spectrum and the rest run towards magenta, the
two colours of the card's fringe.

Private repositories are never drawn, and anything in readme.prism_exclude
(profile.toml) is left out. An API failure leaves the last drawing in place
and exits cleanly.
"""
import os
import sys
import tomllib
from datetime import datetime, timedelta, timezone

import requests

from card import CONFIG, SAGE, WIDTH, esc

OUT = 'assets/prism-{}.svg'
FONT = 'ConsolasFallback,Consolas,Menlo,monospace'
HEIGHT = 300
DAYS = 30
BANDS = 5                    # repositories drawn; the rest share one grey band
QUERY = '''query($login: String!, $from: DateTime!) { user(login: $login) {
  contributionsCollection(from: $from) { commitContributionsByRepository(maxRepositories: 100) {
    repository { nameWithOwner isPrivate } contributions { totalCount } } } } }'''

# Green to magenta, through the colours between them.
SPECTRUM = {
    'dark': ('#a6e68f', '#8fd9b6', '#8fc2e0', '#a9a6e6', '#cf9ae0', '#e08fd0'),
    'light': ('#4b8a35', '#2f8670', '#3a6f99', '#5d5aa8', '#8a4a9c', '#a03f8c'),
}

# Geometry: an equilateral prism, the beam entering its left face low and
# leaving its right face, then fanning out to the label column.
TOP, LEFT, RIGHT = (300, 92), (222, 228), (378, 228)
X_FAN = 652


def lerp(p, q, f):
    return (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)


def repositories():
    token, login = os.environ.get('ACCESS_TOKEN'), os.environ.get('USER_NAME', 'Kronbii')
    if not token:
        sys.exit('prism.py needs ACCESS_TOKEN (a GitHub token) in the environment')
    with open(CONFIG, 'rb') as f:
        cfg = tomllib.load(f).get('readme', {})
    days = cfg.get('prism_days', DAYS)
    include = set(cfg.get('prism_include', []))
    exclude = set(cfg.get('prism_exclude', []))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT00:00:00Z')
    response = requests.post('https://api.github.com/graphql', timeout=60,
                             json={'query': QUERY, 'variables': {'login': login, 'from': since}},
                             headers={'authorization': f'token {token}'})
    response.raise_for_status()
    body = response.json()
    if 'errors' in body:
        raise RuntimeError(body['errors'])
    rows = body['data']['user']['contributionsCollection']['commitContributionsByRepository']
    out = [(r['repository']['nameWithOwner'], r['contributions']['totalCount']) for r in rows
           if not r['repository']['isPrivate']
           and (not include or r['repository']['nameWithOwner'] in include)
           and r['repository']['nameWithOwner'] not in exclude]
    return sorted(out, key=lambda r: -r[1]), login, days, bool(include)


def build(repos, login, t, theme, days=DAYS, curated=False):
    total = sum(n for _, n in repos)
    shown = repos[:BANDS]
    rest = repos[BANDS:]
    bands = [(name.split('/', 1)[1] if name.lower().startswith(login.lower() + '/') else name, n, i)
             for i, (name, n) in enumerate(shown)]
    if rest:
        bands.append((f'{len(rest)} more {"repository" if len(rest) == 1 else "repositories"}',
                      sum(n for _, n in rest), None))

    p_in = lerp(LEFT, TOP, .42)
    p_out = lerp(TOP, RIGHT, .5)
    beam_start = (36, p_in[1] + 26)

    # Each band: a thin slice of the exit point, widening to its share of the
    # fan. Every band is drawn to the same scale, but each gets a row at least
    # ROW tall so a small one still has room for its label; `scale` is the
    # largest that fits all the rows in the fan.
    fan_top, fan_bottom, gap, row = 74, 274, 5, 21
    room = fan_bottom - fan_top - gap * max(0, len(bands) - 1)
    shares = [n / total if total else 1 / len(bands) for _, n, _ in bands]
    lo, hi = 0.0, float(room)
    for _ in range(40):
        scale = (lo + hi) / 2
        lo, hi = (scale, hi) if sum(max(row, s * scale) for s in shares) <= room else (lo, scale)
    scale = lo
    exit_h = 12
    y, ey = fan_top, p_out[1] - exit_h / 2
    shapes, labels = [], []
    spectrum = SPECTRUM[theme]
    for k, ((label, n, i), share) in enumerate(zip(bands, shares)):
        h, slot = max(2.5, share * scale), max(row, share * scale)
        top = y + (slot - h) / 2
        eh = exit_h * share
        colour = spectrum[min(i, len(spectrum) - 1)] if i is not None else t['muted']
        shapes.append(f'<path class="band" d="M{p_out[0]:.1f} {ey:.1f} L{X_FAN} {top:.1f} L{X_FAN} {top + h:.1f} '
                      f'L{p_out[0]:.1f} {ey + eh:.1f} Z" fill="{colour}" style="animation-delay:{-k * 0.9:.1f}s"/>')
        mid = y + slot / 2 + 4.5
        labels.append(f'<text x="{X_FAN + 40}" y="{mid:.1f}" text-anchor="end" fill="{colour}">{n}</text>'
                      f'<text x="{X_FAN + 50}" y="{mid:.1f}" fill="{t["ink"] if i is not None else t["muted"]}">{esc(label)}</text>')
        y += slot + gap
        ey += eh

    m, g = t['fringe'][1], t['fringe'][0]
    prism = f'M{TOP[0]} {TOP[1]} L{RIGHT[0]} {RIGHT[1]} L{LEFT[0]} {LEFT[1]} Z'
    what = 'my robotics, embedded and vision repositories' if curated else 'public repositories'
    headline = (f'<tspan fill="{t["key"]}">{total:,}</tspan> commits to {what} in the last {days} days'
                if total else f'No commits to {what} in the last {days} days')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="{FONT}" role="img" aria-label="{total} commits to {what} in the last {days} days, by repository: {esc(', '.join(f'{b[0]} {b[1]}' for b in bands))}">
<style>
.photons {{ stroke-dasharray: 3 22; animation: flow 2.5s linear infinite; }}
.band {{ opacity: .78; animation: breathe 5s ease-in-out infinite; }}
@keyframes flow {{ to {{ stroke-dashoffset: -50; }} }}
@keyframes breathe {{ 0%, 100% {{ opacity: .7; }} 50% {{ opacity: .92; }} }}
@media (prefers-reduced-motion: reduce) {{ .photons, .band {{ animation: none; }} }}
</style>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="15" fill="{t['bg']}" stroke="{t['edge']}"/>
<text x="36" y="44" font-size="15" fill="{t['fg']}">{headline}</text>
<line x1="{beam_start[0]}" y1="{beam_start[1]:.1f}" x2="{p_in[0]:.1f}" y2="{p_in[1]:.1f}" stroke="{t['ink']}" stroke-width="11" stroke-linecap="round" opacity=".08"/>
<line x1="{beam_start[0]}" y1="{beam_start[1]:.1f}" x2="{p_in[0]:.1f}" y2="{p_in[1]:.1f}" stroke="{t['ink']}" stroke-width="3" stroke-linecap="round" opacity=".85"/>
<line class="photons" x1="{beam_start[0]}" y1="{beam_start[1]:.1f}" x2="{p_in[0]:.1f}" y2="{p_in[1]:.1f}" stroke="{t['bg']}" stroke-width="3" stroke-linecap="round" opacity=".7"/>
<text x="{beam_start[0]}" y="{beam_start[1] + 24:.1f}" font-size="11" fill="{t['muted']}">{days} days of commits</text>
{''.join(shapes) if total else ''}
<line x1="{p_in[0]:.1f}" y1="{p_in[1]:.1f}" x2="{p_out[0]:.1f}" y2="{p_out[1]:.1f}" stroke="{t['ink']}" stroke-width="2.4" stroke-linecap="round" opacity=".55"/>
<g fill="none" stroke-width="1.6" stroke-linejoin="round">
  <g style="mix-blend-mode:{t['blend']}" opacity=".85">
    <path d="{prism}" stroke="{m}" transform="translate(-1.2 0)"/>
    <path d="{prism}" stroke="{g}" transform="translate(1.2 0)"/>
  </g>
  <path d="{prism}" stroke="{t['brand']}" fill="{t['brand']}" fill-opacity=".07"/>
  <path d="M{lerp(TOP, LEFT, .18)[0]:.1f} {lerp(TOP, LEFT, .18)[1]:.1f} L{lerp(TOP, LEFT, .5)[0]:.1f} {lerp(TOP, LEFT, .5)[1]:.1f}" stroke="{t['ink']}" stroke-opacity=".35" transform="translate(9 2)"/>
</g>
<g font-size="13">{''.join(labels) if total else ''}</g>
</svg>
"""


def main():
    try:
        repos, login, days, curated = repositories()
    except (requests.RequestException, RuntimeError, KeyError, TypeError) as e:
        print(f'warning: could not read recent commits ({e}); {OUT.format("*")} left as they are')
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for theme, t in SAGE.items():
        with open(OUT.format(theme), 'w', encoding='utf-8') as f:
            f.write(build(repos, login, t, theme, days, curated))
    print(f'wrote {OUT.format("light")} and {OUT.format("dark")}: '
          f'{sum(n for _, n in repos)} commits across {len(repos)} public repositories')


if __name__ == '__main__':
    main()

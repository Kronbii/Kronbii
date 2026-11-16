"""
Draws the card as a camera would see me: assets/sight-light.svg and -dark.svg.

    python sight.py

The left half is my profile photo after a real computer-vision pipeline --
a coarse sensor frame, Canny edges, Shi-Tomasi corners, their Delaunay mesh
and the face OpenCV's Haar cascade finds. sight_trace.py computes all of that
once into cache/sight.json; this script only draws it, so it runs every day
on the standard library plus lxml.

The right half is the card's own information, read from the rows in
profile.toml and grouped the way a detector groups what it finds. The GitHub
numbers come from dark_mode.svg, which today.py has just refreshed.

On load the frame acquires out of noise, the edges trace themselves, corners
pop, the mesh grows out from the face, the face box locks on, and the readout
flickers on group by group (about four seconds, once). After that only the
REC light, the frame counter, a slow scan line and the lens's green/magenta
fringe keep moving. Everything rests on the finished image: without CSS, or
with reduced motion, the card is simply complete.
"""
import json
import os
import tomllib

from lxml import etree

from card import CONFIG, SAGE, WIDTH, esc, mark

OUT = 'assets/sight-{}.svg'
TRACE = 'cache/sight.json'
CARD = 'dark_mode.svg'
FONT = 'ConsolasFallback,Consolas,Menlo,monospace'
ADVANCE = .6

HEIGHT = 560
VX, VY = 16, 16                     # the camera viewport's top-left corner
PX = 500                            # the readout column's left edge
PR = WIDTH - 16                     # and its right edge
ROW = 18

STATS = {'repos': 'repo_data', 'contrib': 'contrib_data', 'stars': 'star_data',
         'commits': 'commit_data', 'followers': 'follower_data', 'loc': 'loc_data',
         'loc_add': 'loc_add', 'loc_del': 'loc_del', 'age': 'age_data'}


def T(x, y, s, size, fill, anchor='start', weight=None, track=0, cls=None, extra=''):
    """A label whose width is fixed, whatever monospace the viewer falls back to."""
    length = len(s) * size * ADVANCE + track * max(len(s) - 1, 0)
    w = f' font-weight="{weight}"' if weight else ''
    c = f' class="{cls}"' if cls else ''
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{w}{c}{extra} '
            f'textLength="{length:g}" lengthAdjust="spacingAndGlyphs">{esc(s)}</text>')


def live_stats():
    """The card's live numbers, as today.py last wrote them."""
    try:
        root = etree.parse(CARD).getroot()
    except (OSError, etree.XMLSyntaxError):
        return {}
    out = {}
    for name, eid in STATS.items():
        el = root.find(f".//*[@id='{eid}']")
        if el is not None and el.text:
            out[name] = el.text.strip()
    return out


def groups(cfg, stats):
    """profile.toml's rows, split at blanks and rules into named groups."""
    ph = cfg.get('placeholders', {})
    out, cur, name = [], [], None

    def close():
        if cur:
            out.append((name, list(cur)))
        cur.clear()

    for row in cfg['rows']:
        if row.get('blank'):
            close()
            name = None
        elif 'rule' in row:
            close()
            name = row['rule']
        elif 'stats' in row:
            if not any(r[0] == 'stats' for r in cur):
                cur.append(('stats', None))
        elif 'key' in row:
            value = row['value']
            if value.startswith('{') and value.endswith('}'):
                key = value[1:-1]
                value = stats.get(key) or ph.get(key, '')
            cur.append((row['key'], value))
    close()

    named = []
    for i, (title, rows) in enumerate(out):
        keys = [k for k, _ in rows if k != 'stats']
        prefix = keys[0].split('.')[0] if keys and all('.' in k for k in keys) and \
            len({k.split('.')[0] for k in keys}) == 1 else None
        if not title:
            title = prefix or ('System' if i == 0 else f'Group {i}')
        clean = [(k if k == 'stats' else (k.split('.', 1)[1] if prefix else k).replace('.', ' '), v)
                 for k, v in rows]
        named.append((title, clean))
    return named


def value_text(x, y, value, t, size=13.5):
    """A value, with **starred** parts in bold brand colour."""
    parts = value.split('**')
    spans, total = [], 0
    for i, part in enumerate(parts):
        if not part:
            continue
        em = i % 2 == 1
        style = f' font-weight="700" fill="{t["key"]}"' if em else ''
        spans.append(f'<tspan{style}>{esc(part)}</tspan>')
        total += len(part)
    length = total * size * ADVANCE
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{t["value"]}" '
            f'textLength="{length:g}" lengthAdjust="spacingAndGlyphs">{"".join(spans)}</text>')


def tab(x, y, label, t, size=10):
    """A detector's label tab, sitting on the top edge of its box."""
    w = len(label) * size * ADVANCE + 1.2 * (len(label) - 1) + 12
    return (f'<rect x="{x:g}" y="{y - 13:g}" width="{w:g}" height="15" rx="2" fill="{t["brand"]}"/>'
            + T(x + 6, y - 2, label, size, t['brand_ink'], weight=700, track=1.2,
                extra=' letter-spacing="1.2"'))


def brackets(x, y, w, h, arm, stroke, width=1.5, cls=''):
    """Four corner brackets around a box."""
    c = f' class="{cls}"' if cls else ''
    d = (f'M{x:g} {y + arm:g}V{y:g}H{x + arm:g}M{x + w - arm:g} {y:g}H{x + w:g}V{y + arm:g}'
         f'M{x + w:g} {y + h - arm:g}V{y + h:g}H{x + w - arm:g}M{x + arm:g} {y + h:g}H{x:g}V{y + h - arm:g}')
    return f'<path{c} d="{d}" fill="none" stroke="{stroke}" stroke-width="{width}"/>'


def readout(cfg, stats, t, start):
    """The right-hand column: header, one detection box per group, stat tiles."""
    out = []
    y = 36
    out.append(f'<g class="flick" style="animation-delay:.2s">'
               f'<use href="#rmark" x="{PX}" y="{y - 17}" fill="{t["brand"]}"/>'
               + T(PX + 34, y, cfg.get('user', 'rami@kronbii'), 16, t['ink'])
               + f'<line x1="{PX + 34 + 12 * 16 * ADVANCE + 12:g}" y1="{y - 5}" x2="{PR - 80}" y2="{y - 5}" stroke="{t["cc"]}"/>'
               + T(PR, y, 'SUBJECT 01', 11, t['muted'], anchor='end', track=1.5, extra=' letter-spacing="1.5"')
               + '</g>')
    y = 58
    delay = start
    for title, rows in groups(cfg, stats):
        is_stats = rows and rows[0][0] == 'stats'
        inner = (2 * 40 + 6) if is_stats else len(rows) * ROW
        h = inner + 16
        box = [f'<rect x="{PX}" y="{y}" width="{PR - PX}" height="{h}" rx="3" fill="none" stroke="{t["edge"]}"/>',
               brackets(PX, y, PR - PX, h, 9, t['key'], 1.4),
               tab(PX + 10, y + 1, title.upper(), t)]
        body = []
        if is_stats:
            tiles = [('REPOS', stats.get('repos', '')), ('CONTRIBUTED', stats.get('contrib', '')),
                     ('STARS', stats.get('stars', '')), ('FOLLOWERS', stats.get('followers', ''))]
            tw = (PR - PX - 16 - 3 * 8) / 4
            for k, (label, val) in enumerate(tiles):
                tx = PX + 8 + k * (tw + 8)
                body.append(tile(tx, y + 10, tw, label, val, t))
            wide = (PR - PX - 16 - 8) / 2
            body.append(tile(PX + 8, y + 56, wide * .62, 'COMMITS', stats.get('commits', ''), t))
            loc_x = PX + 8 + wide * .62 + 8
            loc_w = PR - 8 - loc_x
            body.append(tile(loc_x, y + 56, loc_w, 'LINES OF CODE', stats.get('loc', ''), t,
                             add=stats.get('loc_add'), dele=stats.get('loc_del')))
        else:
            for k, (key, val) in enumerate(rows):
                ry = y + 8 + ROW * k + 13
                body.append(f'<g class="flick" style="animation-delay:{delay + .12 + k * .07:.2f}s">'
                            + T(PX + 14, ry, key.upper(), 10.5, t['muted'], track=1.2, extra=' letter-spacing="1.2"')
                            + value_text(PX + 132, ry, val, t) + '</g>')
        out.append(f'<g class="snap" style="animation-delay:{delay:.2f}s">{"".join(box)}</g>' + ''.join(body))
        y += h + 11
        delay += .32
    return '\n'.join(out), y - 11, delay


def tile(x, y, w, label, value, t, add=None, dele=None):
    out = [f'<rect x="{x:g}" y="{y}" width="{w:g}" height="40" rx="3" fill="{t["edge"]}" fill-opacity=".45"/>',
           T(x + 8, y + 13, label, 9.5, t['muted'], track=1.2, extra=' letter-spacing="1.2"'),
           T(x + 8, y + 32, value, 16, t['ink'], weight=700)]
    if add and dele:
        vx = x + 8 + len(value) * 16 * ADVANCE + 10
        out.append(T(vx, y + 32, f'+{add}', 11.5, t['add']))
        out.append(T(vx + (len(add) + 1) * 11.5 * ADVANCE + 8, y + 32, f'−{dele}', 11.5, t['dele']))
    return f'<g class="flick tile">{"".join(out)}</g>'


def overlay(trace):
    """Edges, mesh, corners and the face box, in viewport coordinates moved onto the card."""
    ox, oy = VX, VY
    pts = [(x + ox, y + oy) for x, y in trace['features']]
    out = []
    # edges: each traces itself in, top of the list (the longest) first
    for i, line in enumerate(trace['edges']):
        d = 'M' + 'L'.join(f'{x + ox:.1f} {y + oy:.1f}' for x, y in line)
        out.append(f'<path class="e draw" pathLength="1" style="animation-delay:{.45 + .006 * i:.3f}s" d="{d}"/>')
    # the mesh, outward from the face in five rings
    mesh = trace['mesh']
    rings = 5
    for r in range(rings):
        chunk = mesh[r * len(mesh) // rings:(r + 1) * len(mesh) // rings]
        d = ''.join(f'M{pts[a][0]:.1f} {pts[a][1]:.1f}L{pts[b][0]:.1f} {pts[b][1]:.1f}' for a, b in chunk)
        out.append(f'<path class="m grow" style="animation-delay:{1.35 + .18 * r:.2f}s" d="{d}"/>')
    # scene corners, then the corners on me
    fx, fy, fw, fh = trace['face']
    cx, cy = fx + fw / 2 + ox, fy + fh / 2 + oy
    for x, y in trace['scene']:
        out.append(f'<circle class="s pop" style="animation-delay:{1.0 + ((x + ox) - VX) / 460 * .5:.2f}s" '
                   f'cx="{x + ox:.1f}" cy="{y + oy:.1f}" r="1.3"/>')
    for x, y in pts:
        dist = ((x - cx) ** 2 + (y - cy) ** 2) ** .5
        out.append(f'<circle class="f pop" style="animation-delay:{1.1 + dist / 300 * .6:.2f}s" '
                   f'cx="{x:.1f}" cy="{y:.1f}" r="2"/>')
    return '\n'.join(out)


def face(trace, t):
    fx, fy, fw, fh = trace['face']
    x, y = fx + VX, fy + VY
    label = 'FACE · RAMI KRONBI'
    return (f'<g class="lock" style="transform-origin:{x + fw / 2:.1f}px {y + fh / 2:.1f}px">'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{fw:.1f}" height="{fh:.1f}" fill="none" class="b" stroke-width=".8" stroke-opacity=".55"/>'
            + brackets(x, y, fw, fh, 14, 'currentColor', 2, cls='b').replace('stroke="currentColor"', '')
            + '</g>'), (x, y, label)


def build(cfg, trace, stats, theme, t):
    w, h = trace['view']
    cx, cy = VX + w / 2, VY + h / 2
    m, g = t['fringe'][1], t['fringe'][0]
    dark = theme == 'dark'
    colors = dict(e=t['brand'], m=t['brand'], f=t['ink'], s=t['muted'], b=t['brand'])
    style = ';'.join(f'--{k}:{v}' for k, v in colors.items())
    fringe_m = ';'.join(f'--{k}:{m}' for k in colors)
    fringe_g = ';'.join(f'--{k}:{g}' for k in colors)
    box, (bx, by, label) = face(trace, t)
    read, bottom, end = readout(cfg, stats, t, 2.45)
    n_feat, n_mesh, n_edge = len(trace['features']) + len(trace['scene']), len(trace['mesh']), len(trace['edges'])
    lw = len(label) * 10 * ADVANCE + 1.2 * (len(label) - 1) + 12
    counter = digits(VX + w - 12, VY + h - 12, t)
    aria = (f'Rami Kronbi, seen by a computer-vision pipeline: my photo with its edges, '
            f'{n_feat} corners, a Delaunay mesh and the face a Haar cascade finds, beside the '
            f'card: {", ".join(title for title, _ in groups(cfg, stats))}.')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="{FONT}" role="img" aria-label="{esc(aria)}">
<style>
text {{ white-space: pre; }}
.e {{ fill: none; stroke: var(--e); stroke-width: .9; stroke-opacity: {.5 if dark else .6}; stroke-linejoin: round; }}
.m {{ fill: none; stroke: var(--m); stroke-width: .7; stroke-opacity: {.55 if dark else .6}; }}
.f {{ fill: none; stroke: var(--f); stroke-width: 1.1; }}
.s {{ fill: var(--s); }}
.b {{ stroke: var(--b); }}
.draw {{ stroke-dasharray: 1; animation: draw .9s cubic-bezier(.3,.6,.3,1) both; }}
@keyframes draw {{ from {{ stroke-dashoffset: 1; }} to {{ stroke-dashoffset: 0; }} }}
.grow {{ animation: grow .6s ease-out both; }}
@keyframes grow {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
.pop {{ transform-box: fill-box; transform-origin: center; animation: pop .35s cubic-bezier(.3,1.6,.5,1) both; }}
@keyframes pop {{ from {{ transform: scale(0); }} to {{ transform: none; }} }}
.lock {{ animation: lock .55s cubic-bezier(.2,.9,.25,1.15) 2.05s both; }}
@keyframes lock {{ 0% {{ transform: scale(1.7); opacity: 0; }} 40% {{ opacity: 1; }} 100% {{ transform: none; opacity: 1; }} }}
.tag {{ animation: grow .3s ease-out 2.45s both; }}
.noise {{ animation: noise 1.15s ease-in .1s both; }}
@keyframes noise {{ 0%, 35% {{ opacity: .95; }} 100% {{ opacity: 0; }} }}
.snap {{ animation: snap .3s cubic-bezier(.2,.9,.3,1.2) both; transform-box: fill-box; transform-origin: center; }}
@keyframes snap {{ from {{ transform: scale(1.025); opacity: 0; }} to {{ transform: none; opacity: 1; }} }}
.flick {{ animation: flick .32s steps(1, end) both; }}
@keyframes flick {{ 0% {{ opacity: 0; }} 30% {{ opacity: .7; }} 55% {{ opacity: .15; }} 80%, 100% {{ opacity: 1; }} }}
.tile {{ animation-delay: {end - .1:.2f}s; }}
.lens {{ mix-blend-mode: {t['blend']}; opacity: .85; }}
.lm {{ transform-origin: {cx:g}px {cy:g}px; transform: scale(1.007); animation: lm 9s ease-in-out {end:.2f}s infinite; }}
.lg {{ transform-origin: {cx:g}px {cy:g}px; transform: scale(.993); animation: lg 9s ease-in-out {end:.2f}s infinite; }}
@keyframes lm {{ 0%, 100% {{ transform: scale(1.007); }} 50% {{ transform: scale(1.016); }} }}
@keyframes lg {{ 0%, 100% {{ transform: scale(.993); }} 50% {{ transform: scale(.984); }} }}
.rec {{ animation: rec 1.25s steps(1, end) infinite; }}
@keyframes rec {{ 0%, 49% {{ opacity: 1; }} 50%, 100% {{ opacity: .15; }} }}
.scan {{ animation: scan 6.25s linear {end:.2f}s infinite; }}
@keyframes scan {{ from {{ transform: translateY(0); }} to {{ transform: translateY({h}px); }} }}
.roll {{ animation: roll steps(10, end) infinite; }}
@keyframes roll {{ from {{ transform: translateY(0); }} to {{ transform: translateY(-120px); }} }}
@media (prefers-reduced-motion: reduce) {{
  .draw, .grow, .pop, .lock, .tag, .noise, .snap, .flick, .lm, .lg, .rec, .scan, .roll {{ animation: none; }}
  .scan {{ opacity: 0; }}
}}
</style>
<defs>
<clipPath id="view"><rect x="{VX}" y="{VY}" width="{w}" height="{h}" rx="9"/></clipPath>
<pattern id="lines" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="{t['ink'] if not dark else '#000'}" opacity="{.05 if not dark else .35}"/></pattern>
<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="3">
<animate attributeName="seed" values="1;2;3;4;5;6;7;8;9;10;11;12" dur="1.2s" calcMode="discrete" fill="freeze"/></feTurbulence>
<feColorMatrix type="matrix" values="0 0 0 0 {int(t['brand'][1:3], 16) / 255:.3f} 0 0 0 0 {int(t['brand'][3:5], 16) / 255:.3f} 0 0 0 0 {int(t['brand'][5:7], 16) / 255:.3f} 0 0 0 1.6 -.45"/></filter>
<linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t['brand']}" stop-opacity="0"/><stop offset="1" stop-color="{t['brand']}" stop-opacity=".22"/></linearGradient>
<g id="ov">
{overlay(trace)}
{box}
</g>
<g id="rmark">{mark(0, 0, 24)}</g>
</defs>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="15" fill="{t['bg']}" stroke="{t['edge']}"/>
<g clip-path="url(#view)">
<image href="data:image/png;base64,{trace['frame'][theme]}" x="{VX}" y="{VY}" width="{w}" height="{h}" preserveAspectRatio="none" image-rendering="optimizeSpeed" style="image-rendering:pixelated"/>
<rect x="{VX}" y="{VY}" width="{w}" height="{h}" fill="url(#lines)"/>
<g class="lens"><use class="lm" href="#ov" style="{fringe_m}"/><use class="lg" href="#ov" style="{fringe_g}"/></g>
<use href="#ov" style="{style}"/>
<rect class="scan" x="{VX}" y="{VY - 60}" width="{w}" height="60" fill="url(#beam)"/>
<rect class="noise" x="{VX}" y="{VY}" width="{w}" height="{h}" fill="{t['bg']}" opacity="0"/>
<rect class="noise" x="{VX}" y="{VY}" width="{w}" height="{h}" filter="url(#grain)" opacity="0"/>
</g>
<g class="tag">
<rect x="{bx:.1f}" y="{by - 17:.1f}" width="{lw:g}" height="15" rx="2" fill="{t['brand']}"/>
{T(bx + 6, by - 6, label, 10, t['brand_ink'], weight=700, track=1.2, extra=' letter-spacing="1.2"')}
</g>
{brackets(VX + 6, VY + 6, w - 12, h - 12, 22, t['key'], 1.6)}
<g fill="{t['bg']}" fill-opacity=".72">
<rect x="{VX + 14}" y="{VY + 14}" width="92" height="22" rx="3"/>
<rect x="{VX + w - 70}" y="{VY + 14}" width="56" height="22" rx="3"/>
<rect x="{VX + 14}" y="{VY + h - 36}" width="{len(f'{n_feat} CORNERS · {n_mesh} MESH EDGES · {n_edge} EDGES') * 10 * ADVANCE + 1 * 40 + 14:g}" height="22" rx="3"/>
<rect x="{VX + w - 128}" y="{VY + h - 36}" width="114" height="22" rx="3"/>
</g>
<g fill="{t['brand']}">{mark(VX + 20, VY + 18, 18)}</g>
{T(VX + 44, VY + 29, 'CAM 01', 11, t['ink'], weight=700, track=1.5, extra=' letter-spacing="1.5"')}
<circle class="rec" cx="{VX + w - 58}" cy="{VY + 25}" r="4" fill="{t['dele']}"/>
{T(VX + w - 48, VY + 29, 'REC', 11, t['ink'], weight=700, track=1.5, extra=' letter-spacing="1.5"')}
{T(VX + 21, VY + h - 21, f'{n_feat} CORNERS · {n_mesh} MESH EDGES · {n_edge} EDGES', 10, t['fg'], track=1, extra=' letter-spacing="1"')}
{T(VX + w - 121, VY + h - 21, 'FRAME', 10, t['fg'], track=1, extra=' letter-spacing="1"')}
{counter}
{read}
</svg>
"""


def digits(right, base, t, n=5, size=11):
    """A frame counter at 24 fps: each digit a strip of 0-9 rolling in steps."""
    adv = size * ADVANCE + 1
    out = []
    for k in range(n):
        x = right - (n - k) * adv
        period = 10 ** (n - k) / 24
        strip = ''.join(f'<tspan x="{x:.1f}" y="{base + 12 * i:g}">{i}</tspan>' for i in range(10))
        out.append(f'<g clip-path="url(#dg)"><text class="roll" style="animation-duration:{period:.4f}s" '
                   f'font-size="{size}" font-weight="700" fill="{t["brand"]}">{strip}</text></g>')
    return (f'<defs><clipPath id="dg"><rect x="{right - n * adv - 2:.1f}" y="{base - 10}" width="{n * adv + 4:.1f}" height="13"/></clipPath></defs>'
            + ''.join(out))


def main():
    try:
        with open(TRACE, encoding='utf-8') as f:
            trace = json.load(f)
    except (OSError, ValueError) as e:
        if all(os.path.exists(OUT.format(th)) for th in SAGE):
            print(f'sight.py: {TRACE} unreadable ({e}); the card stays as it was')
            return
        raise SystemExit(f'sight.py: {TRACE} missing -- run: python sight_trace.py')
    with open(CONFIG, 'rb') as f:
        cfg = tomllib.load(f)
    stats = live_stats()
    for name, value in cfg.get('placeholders', {}).items():
        stats.setdefault(name, value)       # the last numbers card.py was built with
    os.makedirs('assets', exist_ok=True)
    for theme, t in SAGE.items():
        svg = build(cfg, trace, stats, theme, t)
        etree.fromstring(svg.encode())
        with open(OUT.format(theme), 'w', encoding='utf-8') as f:
            f.write(svg)
    print(f'wrote {OUT.format("light")} and {OUT.format("dark")} '
          f'({os.path.getsize(OUT.format("dark")) // 1024} KB); stats {stats.get("commits", "?")} commits')


if __name__ == '__main__':
    main()

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


def overlay(trace, ox=VX, oy=VY, s=1, left=VX, span=460, rs=1.3, rf=2, keep=None):
    """
    Edges, mesh, corners and the face box, in viewport coordinates moved onto
    the card: scaled by s and offset by (ox, oy). keep=(x0, y0, x1, y1) drops
    what falls wholly outside a cropped frame; left/span place the scene
    corners' left-to-right pop across that frame.
    """
    pts = [(x * s + ox, y * s + oy) for x, y in trace['features']]

    def inside(x, y):
        return keep is None or (keep[0] <= x <= keep[2] and keep[1] <= y <= keep[3])

    out = []
    # edges: each traces itself in, top of the list (the longest) first
    for i, line in enumerate(trace['edges']):
        if not any(inside(x * s + ox, y * s + oy) for x, y in line):
            continue
        d = 'M' + 'L'.join(f'{x * s + ox:.1f} {y * s + oy:.1f}' for x, y in line)
        out.append(f'<path class="e draw" pathLength="1" style="animation-delay:{.45 + .006 * i:.3f}s" d="{d}"/>')
    # the mesh, outward from the face in five rings
    mesh = trace['mesh']
    rings = 5
    for r in range(rings):
        chunk = [(a, b) for a, b in mesh[r * len(mesh) // rings:(r + 1) * len(mesh) // rings]
                 if inside(*pts[a]) or inside(*pts[b])]
        d = ''.join(f'M{pts[a][0]:.1f} {pts[a][1]:.1f}L{pts[b][0]:.1f} {pts[b][1]:.1f}' for a, b in chunk)
        out.append(f'<path class="m grow" style="animation-delay:{1.35 + .18 * r:.2f}s" d="{d}"/>')
    # scene corners, then the corners on me
    fx, fy, fw, fh = trace['face']
    cx, cy = (fx + fw / 2) * s + ox, (fy + fh / 2) * s + oy
    for x, y in trace['scene']:
        if not inside(x * s + ox, y * s + oy):
            continue
        out.append(f'<circle class="s pop" style="animation-delay:{1.0 + ((x * s + ox) - left) / span * .5:.2f}s" '
                   f'cx="{x * s + ox:.1f}" cy="{y * s + oy:.1f}" r="{rs:g}"/>')
    for x, y in pts:
        if not inside(x, y):
            continue
        dist = ((x - cx) ** 2 + (y - cy) ** 2) ** .5
        out.append(f'<circle class="f pop" style="animation-delay:{1.1 + dist / (300 * s) * .6:.2f}s" '
                   f'cx="{x:.1f}" cy="{y:.1f}" r="{rf:g}"/>')
    return '\n'.join(out)


def face(trace, t, ox=VX, oy=VY, s=1, arm=14):
    fx, fy, fw, fh = trace['face']
    x, y, fw, fh = fx * s + ox, fy * s + oy, fw * s, fh * s
    label = 'FACE · RAMI KRONBI'
    return (f'<g class="lock" style="transform-origin:{x + fw / 2:.1f}px {y + fh / 2:.1f}px">'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{fw:.1f}" height="{fh:.1f}" fill="none" class="b" stroke-width=".8" stroke-opacity=".55"/>'
            + brackets(x, y, fw, fh, arm, 'currentColor', 2, cls='b').replace('stroke="currentColor"', '')
            + '</g>'), (x, y, label)


def css(t, dark, end, cx, cy, travel):
    """The card's motion: acquisition on load, then only the lens, REC, scan line and counter."""
    return f"""<style>
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
@keyframes scan {{ from {{ transform: translateY(0); }} to {{ transform: translateY({travel}px); }} }}
.roll {{ animation: roll steps(10, end) infinite; }}
@keyframes roll {{ from {{ transform: translateY(0); }} to {{ transform: translateY(-120px); }} }}
@media (prefers-reduced-motion: reduce) {{
  .draw, .grow, .pop, .lock, .tag, .noise, .snap, .flick, .lm, .lg, .rec, .scan, .roll {{ animation: none; }}
  .scan {{ opacity: 0; }}
}}
</style>
"""


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
{css(t, dark, end, cx, cy, h)}<defs>
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



# ---------------------------------------------------------------------------
# The phone card. GitHub gives the README about 293 px on a phone, so the
# desktop card would shrink to 30% and its text to 3-4 px. This one is drawn
# for that width: 320 units across (1 unit is about a CSS pixel there), the
# camera frame cropped close around me on top, then the same detections
# stacked one under another, nothing under 11 units. It carries the same
# acquisition sequence and the same lens, REC and scan line as the desktop
# card, and rests on the finished image in the same way.

PHONE_OUT = 'assets/sight-phone-{}.svg'
PW = 320                                # viewBox width, units
PM = 8                                  # the card's margin around the frame and the boxes
P_CROP = (20, 66, 420)                  # x0, y0 and width of the viewport region the frame shows
P_FH = 200                              # the frame's height, units
P_LINE = 15.5                           # line pitch of the readout
P_KEY, P_VAL = 11, 12                   # key and value sizes
P_PAD = 7                               # inner padding of a detection box


def p_lines(value, chars):
    """A value's characters with their bold flags, wrapped at spaces into lines of at most `chars`."""
    flags = []
    for i, part in enumerate(value.split('**')):
        flags += [(c, i % 2 == 1) for c in part]
    text = ''.join(c for c, _ in flags)
    lines, start = [], 0
    while len(text) - start > chars:
        cut = text.rfind(' ', start, start + chars + 1)
        if cut <= start:
            cut = start + chars
        lines.append(flags[start:cut])
        start = cut + 1 if text[cut:cut + 1] == ' ' else cut
    lines.append(flags[start:])
    return lines


def p_value(x, y, line, t):
    """One wrapped line of a value, with its bold parts in the brand colour."""
    spans, run, bold = [], '', None
    for c, b in line + [(None, None)]:
        if b != bold and run:
            style = f' font-weight="700" fill="{t["key"]}"' if bold else ''
            spans.append(f'<tspan{style}>{esc(run)}</tspan>')
            run = ''
        if c is not None:
            run += c
            bold = b
    return (f'<text x="{x:g}" y="{y:g}" font-size="{P_VAL}" fill="{t["value"]}" '
            f'textLength="{len(line) * P_VAL * ADVANCE:g}" lengthAdjust="spacingAndGlyphs">{"".join(spans)}</text>')


def p_tab(x, y, label, t):
    """A detector's label tab on the top edge of its box, at phone size."""
    size, track = 11, 1
    w = len(label) * size * ADVANCE + track * (len(label) - 1) + 12
    return (f'<rect x="{x:g}" y="{y - 13:g}" width="{w:g}" height="16" rx="2" fill="{t["brand"]}"/>'
            + T(x + 6, y - 1, label, size, t['brand_ink'], weight=700, track=track,
                extra=f' letter-spacing="{track}"'))


def p_tile(x, y, w, label, value, t, add=None, dele=None):
    """A stat tile: label over a big number, lines added and removed stacked at its right."""
    out = [f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="40" rx="3" fill="{t["edge"]}" fill-opacity=".45"/>',
           T(x + 7, y + 14, label, 11, t['muted']),
           T(x + 7, y + 33, value, 16, t['ink'], weight=700)]
    if add and dele:
        out.append(T(x + w - 7, y + 14, f'+{add}', 11, t['add'], anchor='end'))
        out.append(T(x + w - 7, y + 33, f'−{dele}', 11, t['dele'], anchor='end'))
    return f'<g class="flick tile">{"".join(out)}</g>'


def p_row(x, y, w, tiles, t):
    """Tiles side by side across w: each as wide as its label or number needs, the slack shared out."""
    gap = 5
    need = []
    for label, value, add, dele in tiles:
        n = max(len(label) * 11, len(value) * 16) * ADVANCE + 14
        if add and dele:
            n = max(len(label) * 11 * ADVANCE + 10 + len(add) * 11 * ADVANCE + 1,
                    len(value) * 16 * ADVANCE + 10 + len(dele) * 11 * ADVANCE + 1) + 14
        need.append(n)
    slack = w - sum(need) - gap * (len(tiles) - 1)
    if slack < 0:
        return None
    out, tx = [], x
    for (label, value, add, dele), n in zip(tiles, need):
        tw = n + slack / len(tiles)
        out.append(p_tile(tx, y, tw, label, value, t, add, dele))
        tx += tw + gap
    return ''.join(out)


def p_readout(cfg, stats, t, start, top, step=.25):
    """
    The detections, stacked: a box per group of rows, then the GitHub numbers
    as tiles. They start while the frame is still acquiring (the desktop card
    waits for the face lock), since on a phone they are most of what's on screen.
    """
    x0, w = PM, PW - 2 * PM
    cx0, cw = x0 + P_PAD, w - 2 * P_PAD
    out, y, delay = [], top, start
    for title, rows in groups(cfg, stats):
        is_stats = rows and rows[0][0] == 'stats'
        body = []
        if is_stats:
            row1 = [('REPOS', stats.get('repos', ''), None, None), ('CONTRIBUTED', stats.get('contrib', ''), None, None),
                    ('STARS', stats.get('stars', ''), None, None), ('FOLLOWERS', stats.get('followers', ''), None, None)]
            row2 = [('COMMITS', stats.get('commits', ''), None, None),
                    ('LINES OF CODE', stats.get('loc', ''), stats.get('loc_add'), stats.get('loc_del'))]
            rows_out = [p_row(cx0, 0, cw, r, t) for r in (row1, row2)]
            if any(r is None for r in rows_out):            # a number outgrew its tile: one tile per row pair
                rows_out = [p_row(cx0, 0, cw, r, t) for r in (row1[:2], row1[2:], row2[:1], row2[1:])]
            ty = y + 12
            for r in rows_out:
                body.append(f'<g transform="translate(0 {ty:g})">{r}</g>')
                ty += 45
            h = ty - y + 1
        else:
            kw = max(len(k) for k, _ in rows) * P_KEY * ADVANCE
            vx = cx0 + kw + 7
            chars = int((x0 + w - P_PAD - vx) // (P_VAL * ADVANCE))
            ly = y + 22
            for k, (key, val) in enumerate(rows):
                lines = p_lines(val, chars)
                body.append(f'<g class="flick" style="animation-delay:{delay + .12 + k * .07:.2f}s">'
                            + T(cx0, ly, key.upper(), P_KEY, t['muted'])
                            + ''.join(p_value(vx, ly + i * P_LINE, line, t) for i, line in enumerate(lines))
                            + '</g>')
                ly += len(lines) * P_LINE
            h = ly - P_LINE - y + 8
        box = [f'<rect x="{x0}" y="{y:g}" width="{w}" height="{h:g}" rx="3" fill="none" stroke="{t["edge"]}"/>',
               brackets(x0, y, w, h, 8, t['key'], 1.4),
               p_tab(x0 + 9, y + 1, title.upper(), t)]
        out.append(f'<g class="snap" style="animation-delay:{delay:.2f}s">{"".join(box)}</g>' + ''.join(body))
        y += h + 16
        delay += step
    return '\n'.join(out), y - 16, delay


def build_phone(cfg, trace, stats, theme, t):
    cx0, cy0, cwid = P_CROP
    s = (PW - 2 * PM) / cwid                     # viewport px -> phone units
    FX, FY, FW, FH = PM, PM, PW - 2 * PM, P_FH
    ox, oy = FX - cx0 * s, FY - cy0 * s           # where the viewport's origin lands
    vw, vh = trace['view']
    cx, cy = FX + FW / 2, FY + FH / 2
    m, g = t['fringe'][1], t['fringe'][0]
    dark = theme == 'dark'
    colors = dict(e=t['brand'], m=t['brand'], f=t['ink'], s=t['muted'], b=t['brand'])
    style = ';'.join(f'--{k}:{v}' for k, v in colors.items())
    fringe_m = ';'.join(f'--{k}:{m}' for k in colors)
    fringe_g = ';'.join(f'--{k}:{g}' for k in colors)
    box, (bx, by, label) = face(trace, t, ox, oy, s, arm=10)
    ov = overlay(trace, ox, oy, s, left=FX, span=FW, rs=1.1, rf=1.6, keep=(FX, FY, FX + FW, FY + FH))
    n_feat, n_mesh, n_edge = len(trace['features']) + len(trace['scene']), len(trace['mesh']), len(trace['edges'])
    lw = len(label) * 11 * ADVANCE + 1 * (len(label) - 1) + 12

    # the header under the frame: who this is
    hy = FY + FH + 26
    user = cfg.get('user', 'rami@kronbii')
    ux = PM + 26
    uw = len(user) * 15 * ADVANCE
    subj = 'SUBJECT 01'
    sw = len(subj) * 11 * ADVANCE + (len(subj) - 1)
    header = (f'<g class="flick" style="animation-delay:.2s">'
              f'<use href="#rmark" x="{PM}" y="{hy - 15}" fill="{t["brand"]}"/>'
              + T(ux, hy, user, 15, t['ink'])
              + f'<line x1="{ux + uw + 10:g}" y1="{hy - 5}" x2="{PW - PM - sw - 10:g}" y2="{hy - 5}" stroke="{t["cc"]}"/>'
              + T(PW - PM, hy, subj, 11, t['muted'], anchor='end', track=1, extra=' letter-spacing="1"')
              + '</g>')
    read, bottom, end = p_readout(cfg, stats, t, .9, hy + 27)
    H = round(bottom + PM)

    counts = f'{n_feat} CORNERS · {n_mesh} MESH EDGES · {n_edge} EDGES'
    counts_w = len(counts) * 11 * ADVANCE
    rec_w = 8 + 8 + 6 + 3 * 11 * ADVANCE + 2 + 8 + 5 * (11 * ADVANCE + 1) + 6
    rec_x = FX + FW - 8 - rec_w
    counter = digits(FX + FW - 13, FY + 24, t)
    aria = (f'Rami Kronbi, seen by a computer-vision pipeline: my photo with its edges, '
            f'{n_feat} corners, a Delaunay mesh and the face a Haar cascade finds, above the '
            f'card: {", ".join(title for title, _ in groups(cfg, stats))}.')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{PW * 2}" height="{H * 2}" viewBox="0 0 {PW} {H}" font-family="{FONT}" role="img" aria-label="{esc(aria)}">
{css(t, dark, end, cx, cy, FH + 40)}<defs>
<clipPath id="view"><rect x="{FX}" y="{FY}" width="{FW}" height="{FH}" rx="8"/></clipPath>
<pattern id="lines" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="{t['ink'] if not dark else '#000'}" opacity="{.05 if not dark else .35}"/></pattern>
<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="3">
<animate attributeName="seed" values="1;2;3;4;5;6;7;8;9;10;11;12" dur="1.2s" calcMode="discrete" fill="freeze"/></feTurbulence>
<feColorMatrix type="matrix" values="0 0 0 0 {int(t['brand'][1:3], 16) / 255:.3f} 0 0 0 0 {int(t['brand'][3:5], 16) / 255:.3f} 0 0 0 0 {int(t['brand'][5:7], 16) / 255:.3f} 0 0 0 1.6 -.45"/></filter>
<linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t['brand']}" stop-opacity="0"/><stop offset="1" stop-color="{t['brand']}" stop-opacity=".22"/></linearGradient>
<g id="ov">
{ov}
{box}
</g>
<g id="rmark">{mark(0, 0, 20)}</g>
</defs>
<rect x=".5" y=".5" width="{PW - 1}" height="{H - 1}" rx="12" fill="{t['bg']}" stroke="{t['edge']}"/>
<g clip-path="url(#view)">
<image href="data:image/png;base64,{trace['frame'][theme]}" x="{ox:.2f}" y="{oy:.2f}" width="{vw * s:.2f}" height="{vh * s:.2f}" preserveAspectRatio="none" image-rendering="optimizeSpeed" style="image-rendering:pixelated"/>
<rect x="{FX}" y="{FY}" width="{FW}" height="{FH}" fill="url(#lines)"/>
<g class="lens"><use class="lm" href="#ov" style="{fringe_m}"/><use class="lg" href="#ov" style="{fringe_g}"/></g>
<use href="#ov" style="{style}"/>
<rect class="scan" x="{FX}" y="{FY - 40}" width="{FW}" height="40" fill="url(#beam)"/>
<rect class="noise" x="{FX}" y="{FY}" width="{FW}" height="{FH}" fill="{t['bg']}" opacity="0"/>
<rect class="noise" x="{FX}" y="{FY}" width="{FW}" height="{FH}" filter="url(#grain)" opacity="0"/>
</g>
<g class="tag">
<rect x="{bx:.1f}" y="{by - 18:.1f}" width="{lw:g}" height="16" rx="2" fill="{t['brand']}"/>
{T(bx + 6, by - 6, label, 11, t['brand_ink'], weight=700, track=1, extra=' letter-spacing="1"')}
</g>
{brackets(FX + 5, FY + 5, FW - 10, FH - 10, 16, t['key'], 1.5)}
<g fill="{t['bg']}" fill-opacity=".72">
<rect x="{FX + 9}" y="{FY + 9}" width="{25 + 6 * 11 * ADVANCE + 5 * 1.5 + 8:g}" height="21" rx="3"/>
<rect x="{rec_x:g}" y="{FY + 9}" width="{rec_w:g}" height="21" rx="3"/>
<rect x="{FX + 9}" y="{FY + FH - 30}" width="{counts_w + 12:g}" height="21" rx="3"/>
</g>
<g fill="{t['brand']}">{mark(FX + 14, FY + 12, 15)}</g>
{T(FX + 34, FY + 24, 'CAM 01', 11, t['ink'], weight=700, track=1.5, extra=' letter-spacing="1.5"')}
<circle class="rec" cx="{rec_x + 12:g}" cy="{FY + 19.5}" r="4" fill="{t['dele']}"/>
{T(rec_x + 22, FY + 24, 'REC', 11, t['ink'], weight=700, track=1, extra=' letter-spacing="1"')}
{counter}
{T(FX + 15, FY + FH - 15, counts, 11, t['fg'])}
{header}
{read}
</svg>
"""

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
        for out, draw in ((OUT, build), (PHONE_OUT, build_phone)):
            svg = draw(cfg, trace, stats, theme, t)
            etree.fromstring(svg.encode())
            with open(out.format(theme), 'w', encoding='utf-8') as f:
                f.write(svg)
    print(f'wrote {OUT.format("light")} and {OUT.format("dark")} '
          f'({os.path.getsize(OUT.format("dark")) // 1024} KB), and the phone pair '
          f'({os.path.getsize(PHONE_OUT.format("dark")) // 1024} KB); stats {stats.get("commits", "?")} commits')


if __name__ == '__main__':
    main()

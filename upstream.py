"""
Draws my open-source work as three instrument cards.

    ACCESS_TOKEN=... USER_NAME=Kronbii python upstream.py

Writes assets/upstream-<project>-light.svg and -dark.svg for every project in
PROJECTS, one card each, so README.md can link each card to its own place:

    easypid      the library I wrote, beside a scope tracing its step response
    betaflight   my merged pull requests, beside a blackbox-style gyro log
    openfront    my merged pull requests, beside territories spreading on a map

and a phone twin of each, assets/upstream-<project>-phone-light.svg and -dark.svg,
which README.md shows instead on screens up to 640 px wide: the same instrument
and facts stacked into one column, so nothing shrinks to a third of its size.

The pull requests and easyPID's version are read from GitHub on every run, so
a newly merged fix shows up the next morning. The scope trace is computed, not
drawn: Pid below is a port of easyPID's own update step, run against a
simulated motor once with anti-windup and once without. The blackbox log and
the map are illustrations of the projects, not data from them.

An API failure leaves the last cards in place and exits cleanly; with no cards
drawn yet, the facts in BAKED are drawn instead.
"""
import base64
import heapq
import math
import os
import random
import re
from datetime import datetime

import requests

from card import SAGE, WIDTH, esc

OUT = 'assets/upstream-{}-{}.svg'
API = 'https://api.github.com'
FONT = 'ConsolasFallback,Consolas,Menlo,monospace'
ADVANCE = 0.6                # monospace advance as a fraction of the font size
BEAT = 60 / 96               # the profile's calm tempo
CYCLE = 16 * BEAT            # 10 s: sweep (8 beats), hold, fade (2 beats)
MAX_PRS = 3                  # pull requests listed per project; the count covers all

PROJECTS = [
    dict(key='easypid', name='easyPID', repo='Kronbii/easyPID',
         kicker='Author · Arduino Library Manager',
         href='https://github.com/Kronbii/easyPID',
         about='My PID controller library for Arduino, for any board. Each controller '
               'is its own instance, with anti-windup, derivative filtering and an '
               'optional relay autotuner.',
         caption='On the scope: its own update step steering a simulated motor, with '
                 'anti-windup on, and off (faint).'),
    dict(key='betaflight', name='Betaflight', repo='betaflight/betaflight',
         kicker='Contributor · flight controller firmware',
         href='https://github.com/betaflight/betaflight/pulls?q=is%3Apr+author%3AKronbii'),
    dict(key='openfront', name='OpenFront', repo='openfrontio/OpenFrontIO',
         kicker='Contributor · real-time strategy game',
         href='https://github.com/openfrontio/OpenFrontIO/pulls?q=is%3Apr+author%3AKronbii'),
]

# What the cards show when GitHub can't be asked and nothing is drawn yet. Live
# results are merged with these, so a search that comes back short never drops
# a pull request that is known to be merged.
BAKED = {
    'easypid': '1.1.0',
    'betaflight': [
        dict(number=15705, title='fix(flash): honour short die reads in w25m_readBytes',
             merged='2026-10-29T18:38:17Z'),
        dict(number=15706, title='fix(rx): give the Redpine CC2500 driver its own debug mode',
             merged='2026-09-16T18:24:21Z'),
    ],
    'openfront': [
        dict(number=4985, title='Prevent iOS double-tap page zoom from softlocking the HUD',
             merged='2026-08-13T21:01:29Z'),
        dict(number=4868, title='Make the end timer warnings more visible',
             merged='2026-08-07T23:06:09Z'),
    ],
}

# ── layout ──────────────────────────────────────────────────────────────────
PAD = 22                     # card edge to screen
SCREEN_W = 372
TEXT_X = PAD + SCREEN_W + 30
TEXT_R = WIDTH - 30
BODY = 15                    # px, the size of titles and prose
COLS = int((TEXT_R - TEXT_X) // (BODY * ADVANCE))
MIN_H = 250

# The instrument screens: a phosphor scope on black, chart paper on white.
SCREEN = {
    'dark': dict(bg='#060807', grid='#121814', axis='#1e2922', label='#5f6a5e'),
    'light': dict(bg='#ebece3', grid='#dcdfd3', axis='#c6ccba', label='#7d847a'),
}
# Three channels, green through blue to magenta, as in the prism.
CHANNELS = {
    'dark': ('#a6e68f', '#8fc2e0', '#e08fd0'),
    'light': ('#4b8a35', '#3a6f99', '#a03f8c'),
}


# ── data ────────────────────────────────────────────────────────────────────
def fetch():
    """The live facts: merged pull requests per project and easyPID's version."""
    token, login = os.environ.get('ACCESS_TOKEN'), os.environ.get('USER_NAME', 'Kronbii')
    if not token:
        raise RuntimeError('no ACCESS_TOKEN in the environment')
    session = requests.Session()
    session.headers.update(authorization=f'token {token}', accept='application/vnd.github+json')
    data = {}
    for p in PROJECTS:
        if p['key'] == 'easypid':
            r = session.get(f'{API}/repos/{p["repo"]}/contents/library.properties', timeout=60)
            r.raise_for_status()
            props = base64.b64decode(r.json()['content']).decode()
            data['easypid'] = re.search(r'^version=(.+)$', props, re.M).group(1).strip()
            continue
        r = session.get(f'{API}/search/issues', timeout=60, params={
            'q': f'author:{login} repo:{p["repo"]} is:pr is:merged', 'per_page': 100})
        r.raise_for_status()
        data[p['key']] = [dict(number=i['number'], title=i['title'],
                               merged=i['pull_request']['merged_at'])
                          for i in r.json()['items'] if i.get('pull_request', {}).get('merged_at')]
    return data


def merged_with_baked(data):
    out = {'easypid': data.get('easypid') or BAKED['easypid']}
    for key in ('betaflight', 'openfront'):
        prs = {pr['number']: pr for pr in BAKED[key]}
        prs.update({pr['number']: pr for pr in data.get(key, [])})
        out[key] = sorted(prs.values(), key=lambda pr: pr['merged'], reverse=True)
    return out


def day(stamp):
    return datetime.fromisoformat(stamp.replace('Z', '+00:00')).strftime('%-d %b %Y')


# ── easyPID, run for real ───────────────────────────────────────────────────
class Pid:
    """
    PIDController::computePID and applyAntiWindup from easyPID 1.1.0, line for
    line: DIRECT action, no integral limits, an EMA derivative filter, and
    conditional-integration anti-windup (ANTIWINDUP_CLAMP) or none.
    """

    def __init__(self, kp, ki, kd, lo, hi, antiwindup=True, alpha=0.8):
        self.kp, self.ki, self.kd, self.lo, self.hi = kp, ki, kd, lo, hi
        self.antiwindup, self.alpha = antiwindup, alpha
        self.integral = self.previous = self.filtered = 0.0
        self.first = True

    def update(self, setpoint, measurement, dt):
        error = setpoint - measurement
        p = self.kp * error
        before = self.integral
        self.integral += error * dt
        if self.first:                      # no previous error to difference yet
            derivative = self.filtered = 0.0
            self.first = False
        else:
            derivative = (error - self.previous) / dt
        self.filtered = self.alpha * self.filtered + (1 - self.alpha) * derivative
        raw = p + self.ki * self.integral + self.kd * self.filtered
        out = min(max(raw, self.lo), self.hi)
        # Conditional integration: undo only what drives further into saturation.
        if self.antiwindup and ((raw > self.hi and error > 0) or (raw < self.lo and error < 0)):
            self.integral = before
        self.previous = error
        return out


SIM_T, SIM_DT = 6.0, 0.01
STEPS = [(0.25, 0.8), (3.25, -0.4)]          # (time s, setpoint)


def simulate(antiwindup):
    """A motor as two first-order lags, driven through a ±1 actuator."""
    rnd = random.Random(7)
    pid = Pid(4.0, 6.0, 0.15, -1.0, 1.0, antiwindup)
    x1 = x2 = 0.0
    rows = []
    for k in range(int(SIM_T / SIM_DT)):
        t = k * SIM_DT
        sp = 0.0
        for ts, v in STEPS:
            if t >= ts:
                sp = v
        y = x2 + rnd.gauss(0, 0.004)        # a little sensor noise for the D term to meet
        u = pid.update(sp, y, SIM_DT)
        for _ in range(10):
            h = SIM_DT / 10
            x1 += h * (u - x1) / 0.6
            x2 += h * (x1 - x2) / 0.15
        rows.append((t, sp, y, u))
    return rows


# ── drawing helpers ─────────────────────────────────────────────────────────
def text(x, y, s, size, fill, weight=None, anchor='start', track=False):
    """A label stretched to a fixed width, so any fallback monospace fits.
    `track` spreads the letters: True for the cards' kickers, or a fraction of the size."""
    width = len(s) * size * (ADVANCE + (.16 if track is True else track or 0))
    adjust = 'spacing' if track else 'spacingAndGlyphs'
    bold = f' font-weight="{weight}"' if weight else ''
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}"{bold} '
            f'text-anchor="{anchor}" textLength="{width:g}" lengthAdjust="{adjust}">{esc(s)}</text>')


def fringed(x, y, s, size, fill, t, anchor='end'):
    m, g = t['fringe'][1], t['fringe'][0]
    return (f'<g class="fringe fm">{text(x, y, s, size, m, 700, anchor)}</g>'
            f'<g class="fringe fg">{text(x, y, s, size, g, 700, anchor)}</g>'
            f'{text(x, y, s, size, fill, 700, anchor)}')


def wrap(s, width):
    lines, line = [], ''
    for word in s.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f'{line} {word}'.strip()
    return lines + [line]


def path(points):
    return 'M' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)


def cycle(begin_beats):
    """Timing for one loop of CYCLE, started `begin_beats` in so t=0 is never blank."""
    return f'dur="{CYCLE:g}s" begin="-{begin_beats * BEAT:g}s" repeatCount="indefinite"'


def graticule(x, y, w, h, s, cols=10, rows=8):
    lines = []
    for i in range(1, cols):
        gx = x + w * i / cols
        lines.append(f'M{gx:.1f},{y}V{y + h}')
    for j in range(1, rows):
        gy = y + h * j / rows
        lines.append(f'M{x},{gy:.1f}H{x + w}')
    cx, cy = x + w / 2, y + h / 2
    ticks = [f'M{x + w * i / (cols * 5):.1f},{cy - 2}v4' for i in range(1, cols * 5)]
    ticks += [f'M{cx - 2},{y + h * j / (rows * 5):.1f}h4' for j in range(1, rows * 5)]
    return (f'<path d="{"".join(lines)}" stroke="{s["grid"]}" stroke-width="1" fill="none"/>'
            f'<path d="M{x},{cy}H{x + w}M{cx},{y}V{y + h}{"".join(ticks)}" stroke="{s["axis"]}" '
            f'stroke-width="1" fill="none"/>')


# ── the three screens ───────────────────────────────────────────────────────
def scope(t, theme, x, y, w, h, lab=10, compact=False):
    """easyPID's step response, swept across a two-channel scope; `lab` sizes its labels,
    and `compact` (the phone card) puts CH2's label at the right, clear of the saturated drive."""
    s = SCREEN[theme]
    on, off = simulate(True), simulate(False)
    mx, top, split = 14, y + 18, y + h * 0.68
    x0, x1 = x + mx, x + w - mx
    values = [r[2] for r in on + off] + [r[1] for r in on]
    lo, hi = min(values) - .08, max(values) + .08

    def px(time):
        return x0 + (x1 - x0) * time / SIM_T

    def py(v):
        return split - 8 - (split - 8 - top) * (v - lo) / (hi - lo)

    u_top, u_bot = split + 12, y + h - 14

    def pu(v):
        return u_bot - (u_bot - u_top) * (v + 1) / 2

    keep = range(0, len(on), 2)
    measured = path([(px(on[k][0]), py(on[k][2])) for k in keep])
    ghost = path([(px(off[k][0]), py(off[k][2])) for k in keep])
    effort = path([(px(on[k][0]), pu(on[k][3])) for k in keep])
    sp, last = [(px(0), py(0))], 0.0
    for ts, v in STEPS:
        sp += [(px(ts), py(last)), (px(ts), py(v))]
        last = v
    setpoint = path(sp + [(px(SIM_T), py(last))])

    m, g = t['fringe'][1], t['fringe'][0]
    traces = f"""<path d="{setpoint}" stroke="{t['muted']}" stroke-width="1.2" stroke-dasharray="4 3" fill="none"/>
<path d="{ghost}" stroke="{m}" stroke-width="1.4" opacity=".5" fill="none"/>
<path d="M{x0},{pu(1):.1f}H{x1}M{x0},{pu(-1):.1f}H{x1}" stroke="{s['axis']}" stroke-dasharray="2 3"/>
<path d="{effort}" stroke="{CHANNELS[theme][1]}" stroke-width="1.3" fill="none"/>
<g class="fringe fm"><use href="#ep-trace" stroke="{m}"/></g>
<g class="fringe fg"><use href="#ep-trace" stroke="{g}"/></g>
<use href="#ep-trace" stroke="{t['brand']}" filter="url(#ep-soft)" opacity=".6"/>
<use href="#ep-trace" stroke="{t['brand']}"/>"""

    # The beam: a dot riding the measured trace while the sweep draws it.
    samples = [on[k] for k in range(0, len(on), 12)] + [on[-1]]
    times = ';'.join(f'{.5 * i / (len(samples) - 1):.4f}' for i in range(len(samples))) + ';1'
    cys = ';'.join(f'{py(r[2]):.1f}' for r in samples) + f';{py(samples[-1][2]):.1f}'
    sweep = 9                               # beats in: t=0 lands in the hold, fully drawn
    beam = f"""<g>
<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.49;.5;1" {cycle(sweep)}/>
<line y1="{y + 4}" y2="{y + h - 4}" stroke="{t['brand']}" stroke-width="1" opacity=".22">
<animate attributeName="x1" values="{x0};{x1};{x1}" keyTimes="0;.5;1" {cycle(sweep)}/>
<animate attributeName="x2" values="{x0};{x1};{x1}" keyTimes="0;.5;1" {cycle(sweep)}/></line>
<circle r="7" fill="{t['brand']}" opacity=".35" filter="url(#ep-glow)">
<animate attributeName="cx" values="{x0};{x1};{x1}" keyTimes="0;.5;1" {cycle(sweep)}/>
<animate attributeName="cy" values="{cys}" keyTimes="{times}" {cycle(sweep)}/></circle>
<circle r="2.6" fill="{t['ink']}">
<animate attributeName="cx" values="{x0};{x1};{x1}" keyTimes="0;.5;1" {cycle(sweep)}/>
<animate attributeName="cy" values="{cys}" keyTimes="{times}" {cycle(sweep)}/></circle>
</g>"""

    defs = f"""<path id="ep-trace" d="{measured}" stroke-width="2" fill="none" stroke-linejoin="round"/>
<clipPath id="ep-sweep"><rect x="{x0 - 2}" y="{y}" width="{x1 - x0 + 4}" height="{h}">
<animate attributeName="width" values="0;{x1 - x0 + 4};{x1 - x0 + 4}" keyTimes="0;.5;1" {cycle(sweep)}/></rect></clipPath>
<filter id="ep-glow" x="-2" y="-2" width="5" height="5"><feGaussianBlur stdDeviation="3"/></filter>
<filter id="ep-soft" x="-.1" y="-.2" width="1.2" height="1.4"><feGaussianBlur stdDeviation="2.2"/></filter>"""

    labels = (text(x + mx, y + 14, 'CH1  position', lab, s['label']) +
              (text(x1, split + lab - 1, 'CH2  drive  ±1', lab, s['label'], anchor='end') if compact else
               text(x + mx, split + lab - 1, 'CH2  drive  ±1', lab, s['label'])))
    live = f"""<g class="live"><g clip-path="url(#ep-sweep)">
<animate attributeName="opacity" values="1;1;0" keyTimes="0;.875;1" {cycle(sweep)}/>
{traces}</g>{beam}</g>"""
    still = f'<g class="still">{traces}</g>'
    return defs, graticule(x, y, w, h, s) + labels + live + still


def blackbox(t, theme, x, y, w, h, lab=10, compact=False):
    """A blackbox-style log of three gyro axes chasing their setpoints, scrolling.
    `compact` (the phone card, where the lanes are short) sets the axis names on
    small plates above the traces instead of beneath them."""
    s = SCREEN[theme]
    rnd = random.Random(15705)
    period = 360                            # px of log before it repeats exactly
    lanes = ('roll', 'pitch', 'yaw')
    lane_h = (h - 20) / 3
    grid = [f'M{x},{y + 10 + lane_h * i:.1f}H{x + w}' for i in range(1, 3)]
    grid += [f'M{x + 10 + i * period / 8:.1f},{y}V{y + h}' for i in range(1, 8) if 10 + i * period / 8 < w]
    out = [f'<path d="{"".join(grid)}" stroke="{s["grid"]}" fill="none"/>']

    log, names = [], []
    for i, name in enumerate(lanes):
        amp = (lane_h / 2 - 6) * (.55 if name == 'yaw' else 1)
        harmonics = [(k, rnd.uniform(.3, 1) / k ** .7, rnd.uniform(0, 2 * math.pi))
                     for k in (1, 2, 3, 5, 7)]
        norm = sum(a for _, a, _ in harmonics)
        noise = [(k, rnd.uniform(.4, 1), rnd.uniform(0, 2 * math.pi)) for k in range(46, 60, 3)]

        def stick(u):
            return sum(a * math.sin(2 * math.pi * k * u / period + ph) for k, a, ph in harmonics) / norm

        def gyro(u):
            lag = stick(u - 8)
            overshoot = .2 * (lag - stick(u - 15))
            jitter = sum(a * math.sin(2 * math.pi * k * u / period + ph) for k, a, ph in noise) * .022
            return lag + overshoot + jitter

        mid = y + 10 + lane_h * (i + .5)
        out.append(f'<path d="M{x},{mid:.1f}H{x + w}" stroke="{s["axis"]}" stroke-dasharray="2 4"/>')
        colour = CHANNELS[theme][i]
        span = [u for u in range(0, 2 * period + 1, 2)]
        set_d = path([(x + 10 + u, mid - amp * stick(u)) for u in span])
        gyro_d = path([(x + 10 + u, mid - amp * gyro(u)) for u in span])
        log.append(f'<path d="{set_d}" stroke="{colour}" stroke-width="1.1" opacity=".42" fill="none"/>'
                   f'<path d="{gyro_d}" stroke="{colour}" stroke-width="1.6" fill="none" stroke-linejoin="round"/>')
        if compact:
            base = mid - lane_h / 2 + 3 + lab
            names.append(f'<rect x="{x + 7}" y="{base - lab * .85:.1f}" width="{len(name) * lab * ADVANCE + 10:g}" '
                         f'height="{lab + 3:g}" rx="3" fill="{s["bg"]}" opacity=".88"/>'
                         + text(x + 12, base, name, lab, s['label']))
        else:
            out.append(text(x + 12, mid - lane_h / 2 + 4 + lab, name, lab, s['label']))

    scroll = (f'<animateTransform attributeName="transform" type="translate" values="0 0;-{period} 0" '
              f'dur="{CYCLE * 1.5:g}s" repeatCount="indefinite"/>')
    defs = f'<clipPath id="bb-clip"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10"/></clipPath>'
    head = x + w / 2
    body = ''.join(log)
    out.append(f'<g clip-path="url(#bb-clip)"><g class="live">{scroll}{body}</g>'
               f'<g class="still">{body}</g></g>')
    out += names
    out.append(f'<path d="M{head},{y + 6}V{y + h - 6}" stroke="{t["dele"]}" stroke-width="1.2" opacity=".75"/>'
               f'<path d="M{head - 4},{y + 6}h8l-4,5z" fill="{t["dele"]}" opacity=".75"/>')
    return defs, ''.join(out)


def territory(t, theme, x, y, w, h, lab=10, buckets=20, compact=False):
    """Three players' territories spreading across a pixel map until they meet,
    in `buckets` waves. `compact` (the phone card's wide, short screen) also
    prefers a world whose land is spread evenly from left to right."""
    s = SCREEN[theme]
    cell = 6
    cols, rows = int((w - 14) // cell), int((h - 14) // cell)
    ox, oy = x + (w - cols * cell) / 2, y + (h - rows * cell) / 2
    def fairness(m):
        if not compact:
            return m[4]
        thirds = [sum(1 for c, _ in m[0] if int(3 * c / cols) == k) / len(m[0]) for k in range(3)]
        return m[4] + 2 * (max(thirds) - min(thirds))

    land, seeds, arrival, owner = min((world(cols, rows, n) for n in range(48)), key=fairness)[:4]
    horizon = sorted(arrival.values())[int(len(arrival) * .88)]     # some land stays neutral
    claimed = {k: v / horizon for k, v in arrival.items() if v <= horizon}

    def runs(cells):
        """Cells as one path, each row's neighbours merged into a single bar."""
        by_row, out = {}, []
        for c, r in cells:
            by_row.setdefault(r, []).append(c)
        for r, cs in sorted(by_row.items()):
            cs.sort()
            start = prev = cs[0]
            for c in cs[1:] + [None]:
                if c == prev + 1:
                    prev = c
                    continue
                n = (prev - start + 1) * cell
                out.append(f'M{ox + start * cell:g},{oy + r * cell:g}h{n:g}v{cell}h-{n:g}z')
                if c is not None:
                    start = prev = c
        return ''.join(out)

    def border(cells):
        mine = set(cells)
        return [k for k in mine if any((k[0] + dc, k[1] + dr) not in mine
                                       for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)))]

    colours = [CHANNELS[theme][i] for i in (0, 2, 1)]
    grid = (f'<pattern id="of-cells" x="{ox:g}" y="{oy:g}" width="{cell}" height="{cell}" '
            f'patternUnits="userSpaceOnUse"><path d="M0,0H{cell}M0,0V{cell}" stroke="{s["bg"]}" '
            f'stroke-width="1.2"/></pattern>'
            f'<pattern id="of-sea" x="{ox:g}" y="{oy:g}" width="{2 * cell}" height="{2 * cell}" '
            f'patternUnits="userSpaceOnUse"><circle cx="{cell / 2:g}" cy="{cell / 2:g}" r=".8" '
            f'fill="{s["axis"]}"/></pattern>')
    out = [f'<rect x="{ox:g}" y="{oy:g}" width="{cols * cell}" height="{rows * cell}" fill="url(#of-sea)"/>',
           f'<path d="{runs(land)}" fill="{s["axis"]}"/>']
    live, still = [], []
    for p, colour in enumerate(colours):
        mine = [k for k in claimed if owner[k] == p]
        edge = runs(border(mine))
        still.append(f'<path d="{runs(mine)}" fill="{colour}" opacity=".5"/>'
                     f'<path d="{edge}" fill="{colour}"/>')
        for b in range(buckets):
            cells = [k for k in mine if min(int(claimed[k] * buckets), buckets - 1) == b]
            if not cells:
                continue
            a = .02 + .54 * b / buckets
            live.append(f'<path d="{runs(cells)}" fill="{colour}" opacity="0">'
                        f'<animate attributeName="opacity" values="0;0;1;.5;.5;0" '
                        f'keyTimes="0;{a:.3f};{a + .015:.3f};{a + .09:.3f};.875;1" {cycle(10.5)}/></path>')
        # Once the race is over the borders settle in, as the game draws them.
        live.append(f'<path d="{edge}" fill="{colour}" opacity="0">'
                    f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;.6;.66;.875;1" '
                    f'{cycle(10.5)}/></path>')
    out.append(f'<g class="live">{"".join(live)}</g><g class="still">{"".join(still)}</g>')
    out.append(f'<rect x="{ox:g}" y="{oy:g}" width="{cols * cell}" height="{rows * cell}" fill="url(#of-cells)"/>')
    for colour, (c, r) in zip(colours, seeds):
        cx, cy = ox + c * cell + cell / 2, oy + r * cell + cell / 2
        out.append(f'<circle cx="{cx:g}" cy="{cy:g}" r="5.5" fill="{s["bg"]}" stroke="{colour}" stroke-width="2"/>'
                   f'<circle cx="{cx:g}" cy="{cy:g}" r="2" fill="{colour}"/>')
    return grid, ''.join(out)


def world(cols, rows, seed):
    """
    A map for the territory screen: land from smooth value noise faded at the
    edges, three capitals far apart, and when each land cell is reached in a
    race outwards over uneven ground. Returns (land, capitals, arrival, owner,
    imbalance) so the caller can keep the fairest of a few worlds.
    """
    rnd = random.Random(4868 + seed)
    scale = 8
    coarse = [[rnd.random() for _ in range(cols // scale + 3)] for _ in range(rows // scale + 3)]

    def noise(c, r):
        fx, fy = c / scale, r / scale
        i, j = int(fx), int(fy)
        a, b = fx - i, fy - j
        a, b = a * a * (3 - 2 * a), b * b * (3 - 2 * b)
        return ((coarse[j][i] * (1 - a) + coarse[j][i + 1] * a) * (1 - b) +
                (coarse[j + 1][i] * (1 - a) + coarse[j + 1][i + 1] * a) * b)

    field = {}
    for r in range(rows):
        for c in range(cols):
            edge = min(c, r, cols - 1 - c, rows - 1 - r) / 5
            field[c, r] = noise(c, r) * min(1, .5 + edge)
    level = sorted(field.values())[int(len(field) * .45)]
    land = {k for k, v in field.items() if v > level}

    inland = [k for k in land if 4 <= k[0] < cols - 4 and 4 <= k[1] < rows - 4] or list(land)
    seeds = [min(inland, key=lambda k: abs(k[0] - cols * .22) + abs(k[1] - rows * .45))]
    for _ in range(2):
        seeds.append(max(inland, key=lambda k: min(abs(k[0] - a) + abs(k[1] - b) for a, b in seeds)))
    arrival, owner, heap = {}, {}, [(0.0, p, k) for p, k in enumerate(seeds)]
    heapq.heapify(heap)
    while heap:
        d, p, k = heapq.heappop(heap)
        if k in arrival:
            continue
        arrival[k], owner[k] = d, p
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (k[0] + dc, k[1] + dr)
            if n in land and n not in arrival:
                heapq.heappush(heap, (d + rnd.uniform(.6, 2.2), p, n))
    # Fair shares, most of the land reached, and long fronts where they meet.
    shares = [sum(1 for v in owner.values() if v == p) for p in range(3)]
    reached = sum(shares) / len(land)
    fronts = sum(1 for (c, r), p in owner.items() for n in ((c + 1, r), (c, r + 1))
                 if n in owner and owner[n] != p)
    score = (max(shares) - min(shares)) / sum(shares) + (1 - reached) - fronts / (cols + rows)
    return land, seeds, arrival, owner, score


SCREENS = {'easypid': scope, 'betaflight': blackbox, 'openfront': territory}


# ── the card ────────────────────────────────────────────────────────────────
def content(p, facts, t):
    """The text column below the header, and the baseline it ends on."""
    out, y = [], 142
    if p['key'] == 'easypid':
        for line in wrap(p['about'], COLS):
            out.append(text(TEXT_X, y, line, BODY, t['fg']))
            y += 22
        y += 10
        for line in wrap(p['caption'], int((TEXT_R - TEXT_X) // (13 * ADVANCE))):
            out.append(text(TEXT_X, y, line, 13, t['muted']))
            y += 19
        return out, y - 19
    for pr in facts[p['key']][:MAX_PRS]:
        out.append(text(TEXT_X, y, f'#{pr["number"]}', BODY, t['key'], 700))
        out.append(text(TEXT_R, y, f'merged {day(pr["merged"])}', 13, t['muted'], anchor='end'))
        prefix = re.match(r'^[a-z]+(\([^)]*\))?!?: ', pr['title'])
        prefix = prefix.group(0) if prefix else ''
        for k, line in enumerate(wrap(pr['title'], COLS)):
            y += 22 if k == 0 else 21
            if k == 0 and prefix and line.startswith(prefix):
                out.append(text(TEXT_X, y, prefix.rstrip(), BODY, t['muted']))
                out.append(text(TEXT_X + len(prefix) * BODY * ADVANCE, y, line[len(prefix):], BODY, t['ink']))
            else:
                out.append(text(TEXT_X, y, line, BODY, t['ink']))
        y += 36
    return out, y - 36


def header(p, facts, t):
    if p['key'] == 'easypid':
        figure, under = f'v{facts["easypid"]}', 'latest release ↗'
    else:
        n = len(facts[p['key']])
        figure, under = str(n), f'merged pull request{"s" if n != 1 else ""} ↗'
    return (text(TEXT_X, 46, p['kicker'].upper(), 12, t['muted'], track=True) +
            text(TEXT_X, 84, p['name'], 30, t['ink'], 700) +
            fringed(TEXT_R, 78, figure, 40, t['brand'], t) +
            text(TEXT_R, 100, under, 12, t['key'], anchor='end') +
            f'<line x1="{TEXT_X}" y1="114" x2="{TEXT_R}" y2="114" stroke="{t["edge"]}"/>')


def label(p, facts):
    if p['key'] == 'easypid':
        return (f'easyPID {facts["easypid"]}, my PID controller library on the Arduino Library Manager. '
                f'{p["about"]} {p["caption"]}')
    prs = facts[p['key']]
    listed = '; '.join(f'#{pr["number"]} {pr["title"]}, merged {day(pr["merged"])}' for pr in prs[:MAX_PRS])
    return f'{p["name"]}: {len(prs)} merged pull requests of mine. {listed}.'


def style(t):
    """The cards' shared CSS: the lens fringe breathing, and a still frame for reduced motion."""
    return f"""<style>
text {{ white-space: pre; }}
.fringe {{ mix-blend-mode: {t['blend']}; opacity: .85; }}
.fm {{ transform: translateX(-.9px); animation: fm 9s ease-in-out infinite; }}
.fg {{ transform: translateX(.9px); animation: fg 9s ease-in-out infinite; }}
@keyframes fm {{ 0%, 100% {{ transform: translateX(-.7px); }} 50% {{ transform: translateX(-2px); }} }}
@keyframes fg {{ 0%, 100% {{ transform: translateX(.7px); }} 50% {{ transform: translateX(2px); }} }}
.still {{ display: none; }}
@media (prefers-reduced-motion: reduce) {{
  .fm, .fg {{ animation: none; }}
  .live {{ display: none !important; }}
  .still {{ display: inline !important; }}
}}
</style>"""


def build(p, facts, theme, h):
    t = SAGE[theme]
    defs, screen = SCREENS[p['key']](t, theme, PAD, PAD, SCREEN_W, h - 2 * PAD)
    body, _ = content(p, facts, t)
    s = SCREEN[theme]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{h}" viewBox="0 0 {WIDTH} {h}" font-family="{FONT}" role="img" aria-label="{esc(label(p, facts))}">
{style(t)}
<defs>{defs}</defs>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="{h - 1}" rx="15" fill="{t['bg']}" stroke="{t['edge']}"/>
<rect x="{PAD}" y="{PAD}" width="{SCREEN_W}" height="{h - 2 * PAD}" rx="10" fill="{s['bg']}"/>
{screen}
<rect x="{PAD + .5}" y="{PAD + .5}" width="{SCREEN_W - 1}" height="{h - 2 * PAD - 1}" rx="10" fill="none" stroke="{t['edge']}"/>
{header(p, facts, t)}
{''.join(body)}
</svg>
"""


# ── the phone card ──────────────────────────────────────────────────────────
# On a phone GitHub gives the README about 293 px, so the 985 px cards above
# would shrink to a third and their text to 5 px. The phone card is drawn on
# a 320-unit canvas (1 unit is about 0.92 px there) and stacks the same parts:
# the instrument full width on top, then the header, then the text. It is
# written at twice its size so it fills a wider phone without blurring.
PHONE_OUT = 'assets/upstream-{}-phone-{}.svg'
P_W = 320
P_PAD = 10                   # card edge to screen
P_SCREEN_H = 136
P_X, P_R = 16, P_W - 16      # the text column
P_BODY = 13                  # pull request titles
P_PROSE = 12                 # easyPID's paragraph
P_SMALL = 11                 # dates, captions, kickers: the smallest type on the card


def phone_header(p, facts, t, y):
    """Kicker, name and the big figure, starting below the screen at y; returns (svg, rule y)."""
    if p['key'] == 'easypid':
        figure, under = f'v{facts["easypid"]}', 'latest release ↗'
    else:
        n = len(facts[p['key']])
        figure, under = str(n), f'merged pull request{"s" if n != 1 else ""} ↗'
    kicker, name, rule = y + 24, y + 53, y + 79
    return (text(P_X, kicker, p['kicker'].upper(), P_SMALL, t['muted'], track=.04) +
            text(P_X, name, p['name'], 22, t['ink'], 700) +
            fringed(P_R, name, figure, 28, t['brand'], t) +
            text(P_R, name + 16, under, P_SMALL, t['key'], anchor='end') +
            f'<line x1="{P_X}" y1="{rule}" x2="{P_R}" y2="{rule}" stroke="{t["edge"]}"/>'), rule


def phone_content(p, facts, t, y):
    """The text under the header, from baseline y; returns (svg parts, last baseline)."""
    out = []
    if p['key'] == 'easypid':
        for k, line in enumerate(wrap(p['about'], int((P_R - P_X) // (P_PROSE * ADVANCE)))):
            y += 0 if k == 0 else 17
            out.append(text(P_X, y, line, P_PROSE, t['fg']))
        y += 6
        for line in wrap(p['caption'], int((P_R - P_X) // (P_SMALL * ADVANCE))):
            y += 14
            out.append(text(P_X, y, line, P_SMALL, t['muted']))
        return out, y
    cols = int((P_R - P_X) // (P_BODY * ADVANCE))
    for i, pr in enumerate(facts[p['key']][:MAX_PRS]):
        y += 0 if i == 0 else 30
        out.append(text(P_X, y, f'#{pr["number"]}', P_BODY, t['key'], 700))
        out.append(text(P_R, y, f'merged {day(pr["merged"])}', P_SMALL, t['muted'], anchor='end'))
        prefix = re.match(r'^[a-z]+(\([^)]*\))?!?: ', pr['title'])
        prefix = prefix.group(0) if prefix else ''
        for k, line in enumerate(wrap(pr['title'], cols)):
            y += 20 if k == 0 else 18
            if k == 0 and prefix and line.startswith(prefix):
                out.append(text(P_X, y, prefix.rstrip(), P_BODY, t['muted']))
                out.append(text(P_X + len(prefix) * P_BODY * ADVANCE, y, line[len(prefix):], P_BODY, t['ink']))
            else:
                out.append(text(P_X, y, line, P_BODY, t['ink']))
    return out, y


def build_phone(p, facts, theme):
    t = SAGE[theme]
    s = SCREEN[theme]
    sw = P_W - 2 * P_PAD
    extra = dict(buckets=12) if p['key'] == 'openfront' else {}
    defs, screen = SCREENS[p['key']](t, theme, P_PAD, P_PAD, sw, P_SCREEN_H, lab=P_SMALL, compact=True, **extra)
    head, rule = phone_header(p, facts, t, P_PAD + P_SCREEN_H)
    body, last = phone_content(p, facts, t, rule + 24)
    h = last + 14
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{2 * P_W}" height="{2 * h}" viewBox="0 0 {P_W} {h}" font-family="{FONT}" role="img" aria-label="{esc(label(p, facts))}">
{style(t)}
<defs>{defs}</defs>
<rect x=".5" y=".5" width="{P_W - 1}" height="{h - 1}" rx="12" fill="{t['bg']}" stroke="{t['edge']}"/>
<rect x="{P_PAD}" y="{P_PAD}" width="{sw}" height="{P_SCREEN_H}" rx="8" fill="{s['bg']}"/>
{screen}
<rect x="{P_PAD + .5}" y="{P_PAD + .5}" width="{sw - 1}" height="{P_SCREEN_H - 1}" rx="8" fill="none" stroke="{t['edge']}"/>
{head}
{''.join(body)}
</svg>
"""


# My place on committers.top's list of Lebanon's most active GitHub users, read
# from its badge and redrawn as a pill like the profile's links, so the rank
# sits in the Sage palette instead of the badge's stock blue.
RANK_URL = 'https://user-badge.committers.top/lebanon/Kronbii.svg'
RANK_OUT = 'assets/upstream-rank-{}.svg'
RANK_BAKED = 15


RANK_PHONE_OUT = 'assets/upstream-rank-phone-{}.svg'
RANK_PHONE_MAX = 290         # px: the pill is drawn 1:1, and a phone's README is about 293 px


def rank_phone_svg(n, t):
    """
    The rank pill for phones, where the one-line pill would be 435 px: the
    rank large and fringed like the cards' figures, the rest on two lines.
    """
    num, top, bottom = f'#{n}', 'in Lebanon by public commits', 'committers.top ↗'
    small, h = 12, 46
    pad_l, gap, pad_r = 14, 11, 16
    text_w = max(len(top), len(bottom)) * small * ADVANCE
    size = min(22, (RANK_PHONE_MAX - pad_l - gap - text_w - pad_r) / (len(num) * ADVANCE))
    num_w = len(num) * size * ADVANCE
    w = pad_l + num_w + gap + text_w + pad_r
    tx = pad_l + num_w + gap
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h}" viewBox="0 0 {w:g} {h}" font-family="{FONT}" role="img" aria-label="{esc(f'{num} {top} · committers.top')}">
<style>text {{ white-space: pre; }}</style>
<rect x=".75" y=".75" width="{w - 1.5:g}" height="{h - 1.5:g}" rx="{(h - 1.5) / 2:g}" fill="{t['bg']}" stroke="{t['edge']}" stroke-width="1.5"/>
<g style="mix-blend-mode:{t['blend']}" opacity=".85">{text(pad_l - .8, h / 2 + size * .35, num, round(size, 2), t['fringe'][1], 700)}{text(pad_l + .8, h / 2 + size * .35, num, round(size, 2), t['fringe'][0], 700)}</g>
{text(pad_l, h / 2 + size * .35, num, round(size, 2), t['brand'], 700)}
<line x1="{tx - gap / 2 - .5:g}" y1="11" x2="{tx - gap / 2 - .5:g}" y2="{h - 11}" stroke="{t['edge']}" stroke-width="1.5"/>
{text(tx, 20, top, small, t['ink'])}
{text(tx, 36, bottom, small, t['key'])}
</svg>
"""


def rank():
    from parts import link_svg
    outputs = {RANK_OUT.format(theme): theme for theme in SAGE}
    outputs.update({RANK_PHONE_OUT.format(theme): theme for theme in SAGE})
    write = list(outputs)
    try:
        r = requests.get(RANK_URL, timeout=20)
        r.raise_for_status()
        n = int(re.search(r'Lebanon #(\d+)', r.text).group(1))
    except Exception as e:                  # the site, the network, or a new badge layout
        write = [f for f in outputs if not os.path.exists(f)]
        if not write:
            print(f'upstream.py: could not read the committers.top rank ({e}); the pill stays as it was')
            return
        n = RANK_BAKED
    for path in write:
        t = SAGE[outputs[path]]
        svg = (rank_phone_svg(n, t) if '-phone-' in path else
               link_svg(f'#{n} in Lebanon by public commits · committers.top ↗', t, primary=False))
        with open(path, 'w', encoding='utf-8') as f:
            f.write(svg)
    print(f'committers.top  #{n} in Lebanon')


def main():
    rank()
    outputs = [out.format(p['key'], theme) for out in (OUT, PHONE_OUT) for p in PROJECTS for theme in SAGE]
    write = set(outputs)
    try:
        live = fetch()
    except Exception as e:                  # the API, the network, or no token
        write = {f for f in outputs if not os.path.exists(f)}
        if not write:
            print(f'upstream.py: could not read GitHub ({e}); the cards stay as they were')
            return
        print(f'upstream.py: could not read GitHub ({e}); drawing the baked facts where a card is missing')
        live = {}
    facts = merged_with_baked(live)
    h = max(MIN_H, *(content(p, facts, SAGE['light'])[1] + 34 for p in PROJECTS))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for p in PROJECTS:
        for theme in SAGE:
            for path, draw in ((OUT.format(p['key'], theme), lambda: build(p, facts, theme, h)),
                               (PHONE_OUT.format(p['key'], theme), lambda: build_phone(p, facts, theme))):
                if path in write:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(draw())
        shown = facts[p['key']] if p['key'] != 'easypid' else f'v{facts["easypid"]}'
        print(f'{p["name"]:11} {len(shown) if isinstance(shown, list) else shown}'
              f'{" merged" if isinstance(shown, list) else ""}')


if __name__ == '__main__':
    main()

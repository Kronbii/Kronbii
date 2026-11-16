"""
Draws the What I build reel: one short scene per project, in turn.

    python reel.py

Reads [[readme.who]] in profile.toml and writes assets/reel-light.svg and
assets/reel-dark.svg, plus the row of project links under the reel in
README.md (between the who markers). It also writes assets/reel-phone-light.svg
and -dark.svg: the same reel stacked for a phone, each drawing above its text.

Each scene is a small line drawing of what the project does, beside who it is
for and the discipline it belongs to. Scenes come into focus out of the green/magenta fringe -- a blur and a
colour split that close up, like a lens racking focus -- hold for eight beats
at 96 BPM, and drift out again. The motion is SMIL, so it plays in a README
<img>; a viewer that asks for reduced motion sees the first scene, still.
"""
import math
import tomllib

from card import CONFIG, SAGE, WIDTH, esc

OUT = 'assets/reel-{}.svg'
README = 'README.md'
WHO_START, WHO_END = '<!-- who:start -->', '<!-- who:end -->'
FONT = 'ConsolasFallback,Consolas,Menlo,monospace'
HEIGHT = 300
BEAT = 60 / 96
SCENE = 8 * BEAT            # 5 s on screen
FOCUS = BEAT                # the rack in and out
LEAD = 2 * BEAT             # the reel opens two beats into the first scene, in focus
EASE = '0.4 0 0.2 1'


def timeline(points, dur):
    """[(seconds, value), ...] -> SMIL values/keyTimes/keySplines over `dur`."""
    pts = sorted(points, key=lambda p: p[0])
    if pts[0][0] > 0:
        pts.insert(0, (0, pts[0][1]))
    if pts[-1][0] < dur:
        pts.append((dur, pts[-1][1]))
    times, last = [], -1.0
    for t, _ in pts:
        t = min(max(t, last + 0.001), dur)
        times.append(t)
        last = t
    times[-1] = dur
    return (';'.join(str(v) for _, v in pts),
            ';'.join(f'{t / dur:.5f}' for t in times),
            ';'.join([EASE] * (len(pts) - 1)))


def anim(attr, points, dur, tag='animate', extra=''):
    values, times, splines = timeline(points, dur)
    if dur == SCENE:            # a scene's own motion, kept in step with LEAD
        extra += f' begin="-{LEAD:g}s"'
    return (f'<{tag} attributeName="{attr}" dur="{dur:g}s" repeatCount="indefinite" '
            f'values="{values}" keyTimes="{times}" calcMode="spline" keySplines="{splines}"{extra}/>')


def pts(seq):
    return ' '.join(f'{x:g},{y:g}' for x, y in seq)


def wrap(text, width):
    lines, line = [], ''
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f'{line} {word}'.strip()
    return lines + [line]


# ── the five drawings, each in a 240 x 240 box, timed over one SCENE ─────────
# `t` is the theme. Lines are drawn in the brand colour; joints carry a dot
# marker, like the keypoints a vision model returns.

def sign(t):
    """A hand's keypoints moving from an open hand to an L; text appears beside it."""
    wrist = (68, 212)
    a = [[(35, 165), (22, 145), (14, 128), (8, 112)], [(52, 120), (48, 92), (46, 72), (45, 54)],
         [(70, 114), (70, 84), (70, 62), (70, 44)], [(88, 118), (91, 90), (93, 70), (94, 54)],
         [(104, 128), (110, 106), (114, 90), (117, 76)]]
    b = [[(35, 165), (20, 156), (6, 150), (-6, 146)], [(52, 120), (51, 92), (50, 72), (49, 52)],
         [(70, 114), (73, 100), (67, 95), (63, 103)], [(88, 118), (90, 104), (84, 100), (80, 108)],
         [(104, 128), (106, 116), (100, 113), (97, 121)]]
    fingers = ''.join(
        f'<polyline points="{pts([wrist] + fa)}" marker-start="url(#j)" marker-mid="url(#j)" marker-end="url(#j)">'
        + anim('points', [(0, pts([wrist] + fa)), (1.0, pts([wrist] + fa)), (1.9, pts([wrist] + fb)),
                          (3.4, pts([wrist] + fb)), (4.3, pts([wrist] + fa))], SCENE)
        + '</polyline>' for fa, fb in zip(a, b))
    knuckles = f'<polyline points="{pts([a[0][0], a[1][0], a[2][0], a[3][0], a[4][0]])}" stroke-opacity=".6"/>'
    bars = ''.join(
        f'<rect x="150" y="{y}" height="7" rx="3.5" fill="{t["ink"]}" stroke="none" width="0">'
        + anim('width', [(0, 0), (start, 0), (start + 0.8, w), (SCENE, w)], SCENE) + '</rect>'
        for y, start, w in ((110, 2.0, 62), (127, 2.7, 38)))
    caret = (f'<line x1="196" y1="124" x2="196" y2="138" stroke="{t["ink"]}" stroke-width="1.5">'
             f'<animate attributeName="opacity" values="1;0;1" dur="{2 * BEAT:g}s" repeatCount="indefinite"/></line>')
    return f"""
<rect x="-12" y="36" width="140" height="186" rx="6" stroke-dasharray="4 5" stroke-opacity=".45" stroke-width="1.2"/>
{knuckles}{fingers}
<path d="M132 124 H140 M136 119 L141 124 L136 129" stroke-width="1.6"/>
<rect x="144" y="98" width="92" height="52" rx="8"/>
{bars}{caret}"""


def face(t):
    """A face on a small device's screen; its expression and the scores change."""
    jaw = ''.join(
        f'<circle cx="{90 + 42 * math.cos(math.radians(a)):.1f}" cy="{128 + 52 * math.sin(math.radians(a)):.1f}" '
        f'r="2.2" fill="{t["brand"]}" stroke="none"/>' for a in range(20, 170, 25))
    brow = lambda d0, d1: f'<path d="{d0}">' + anim('d', [(0, d0), (1.4, d0), (2.3, d1), (3.6, d1), (4.4, d0)], SCENE) + '</path>'
    mouth0, mouth1 = 'M74 152 Q90 152 106 152', 'M74 148 Q90 166 106 148'
    bars = ''.join(
        f'<rect x="{x}" width="11" rx="2" fill="{t["brand"]}" fill-opacity="{op}" stroke="none" y="{200 - h0}" height="{h0}">'
        + anim('height', [(0, h0), (1.6, h0), (2.5, h1), (3.6, h1), (4.4, h0)], SCENE)
        + anim('y', [(0, 200 - h0), (1.6, 200 - h0), (2.5, 200 - h1), (3.6, 200 - h1), (4.4, 200 - h0)], SCENE)
        + '</rect>' for x, h0, h1, op in ((186, 62, 22, '.45'), (203, 20, 74, '.9'), (220, 30, 26, '.45')))
    return f"""
<rect x="8" y="30" width="164" height="196" rx="16"/>
<circle cx="90" cy="42" r="2.5" fill="{t['brand']}" stroke="none"/>
<rect x="44" y="70" width="92" height="114" rx="4" stroke-dasharray="4 5" stroke-opacity=".45" stroke-width="1.2"/>
<ellipse cx="90" cy="128" rx="42" ry="52" stroke-opacity=".55"/>
{jaw}
<circle cx="74" cy="118" r="3.5" fill="{t['brand']}" stroke="none"/>
<circle cx="106" cy="118" r="3.5" fill="{t['brand']}" stroke="none"/>
{brow('M64 104 L82 100', 'M64 99 L82 94')}{brow('M98 100 L116 104', 'M98 94 L116 99')}
<path d="M90 120 L86 138 L94 139" stroke-opacity=".7"/>
<path d="{mouth0}">{anim('d', [(0, mouth0), (1.4, mouth0), (2.3, mouth1), (3.6, mouth1), (4.4, mouth0)], SCENE)}</path>
<line x1="182" y1="200" x2="236" y2="200" stroke-opacity=".5"/>
{bars}"""


def desk(t):
    """Someone slouches; the desk rises and tilts to meet them, the light turns green."""
    m, g = t['fringe'][1], t['fringe'][0]
    slouch, upright = [(60, 168), (76, 146), (94, 128)], [(60, 168), (62, 142), (64, 116)]
    arm0, arm1 = [(94, 128), (110, 146), (132, 150)], [(64, 116), (88, 134), (128, 140)]
    key = lambda p0, p1: [(0, p0), (1.2, p0), (2.4, p1), (3.8, p1), (4.5, p0)]
    return f"""
<line x1="6" y1="214" x2="234" y2="214" stroke-opacity=".6"/>
<path d="M30 172 H76 M52 172 V214 M30 172 L26 128" stroke-opacity=".7"/>
<path d="M60 168 L94 170 L94 212" stroke-opacity=".8"/>
<polyline points="{pts(slouch)}" marker-start="url(#j)" marker-mid="url(#j)" marker-end="url(#j)">{anim('points', key(pts(slouch), pts(upright)), SCENE)}</polyline>
<polyline points="{pts(arm0)}" marker-mid="url(#j)" marker-end="url(#j)">{anim('points', key(pts(arm0), pts(arm1)), SCENE)}</polyline>
<circle r="11" cx="104" cy="116">{anim('cx', key(104, 66), SCENE)}{anim('cy', key(116, 100), SCENE)}</circle>
<line x1="170" y1="214" x2="170" y2="178" stroke-width="5"/>
<g>{anim('transform', key('0 0', '0 -8'), SCENE, tag='animateTransform', extra=' type="translate"')}
  <line x1="170" y1="184" x2="170" y2="152" stroke-width="3"/>
  <g>{anim('transform', key('0 170 150', '-9 170 150'), SCENE, tag='animateTransform', extra=' type="rotate"')}
    <line x1="120" y1="150" x2="222" y2="150" stroke-width="3.5"/>
    <path d="M214 150 L222 106" stroke-opacity=".8"/>
    <rect x="213" y="96" width="17" height="10" rx="2"/>
    <circle cx="130" cy="158" r="4.5" stroke="none" fill="{m}">{anim('fill', key(m, g), SCENE)}</circle>
  </g>
</g>"""


def rover(t):
    """The rover's LiDAR sweeps the ground, finds a buried mine, and the arm reaches for it."""
    o = (36, 122)
    ray = lambda deg: (o[0] + 170 * math.cos(math.radians(deg)), o[1] + 170 * math.sin(math.radians(deg)))
    (x1, y1), (x2, y2) = ray(14), ray(24)
    arm0 = [(88, 152), (100, 134), (90, 124), (82, 136)]
    arm1 = [(88, 152), (122, 130), (154, 148), (172, 182)]
    found = [(0, 0), (2.1, 0), (2.2, .9), (3.1, 0), (3.2, .9), (4.1, 0), (SCENE, 0)]
    return f"""
<clipPath id="ground"><rect x="0" y="0" width="240" height="192"/></clipPath>
<line x1="4" y1="192" x2="236" y2="192"/>
<line x1="4" y1="206" x2="236" y2="206" stroke-dasharray="2 7" stroke-opacity=".4"/>
<g clip-path="url(#ground)">
  <g>{anim('transform', [(0, f'-16 {o[0]} {o[1]}'), (1.9, f'4 {o[0]} {o[1]}'), (3.6, f'4 {o[0]} {o[1]}'), (4.6, f'-16 {o[0]} {o[1]}')], SCENE, tag='animateTransform', extra=' type="rotate"')}
    <path d="M{o[0]} {o[1]} L{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f} Z" fill="{t['brand']}" fill-opacity=".14" stroke="none"/>
    <line x1="{o[0]}" y1="{o[1]}" x2="{(x1 + x2) / 2:.1f}" y2="{(y1 + y2) / 2:.1f}" stroke-opacity=".5" stroke-width="1.2"/>
  </g>
</g>
<ellipse cx="176" cy="200" rx="8" ry="3.5" stroke-dasharray="3 3"/>
<circle cx="176" cy="199" r="4" stroke-width="1.5" opacity="0">{anim('r', [(0, 4), (2.1, 4), (3.1, 18), (3.15, 4), (4.1, 18), (SCENE, 18)], SCENE)}{anim('opacity', found, SCENE)}</circle>
<rect x="16" y="150" width="74" height="26" rx="5"/>
<circle cx="30" cy="184" r="8"/><circle cx="76" cy="184" r="8"/>
<line x1="36" y1="150" x2="36" y2="127"/>
<circle cx="36" cy="122" r="5" fill="{t['bg']}"/>
<polyline points="{pts(arm0)}" marker-mid="url(#j)" marker-end="url(#j)">{anim('points', [(0, pts(arm0)), (2.4, pts(arm0)), (3.4, pts(arm1)), (4.1, pts(arm1)), (4.7, pts(arm0))], SCENE)}</polyline>"""


def road(t):
    """A fixed camera times a car between two marks; the reading comes with its margin."""
    c = (186, 96)
    def wedge(half):
        a0, a1 = math.radians(-90 - half), math.radians(-90 + half)
        return (f'M{c[0]} {c[1]} L{c[0] + 28 * math.cos(a0):.1f} {c[1] + 28 * math.sin(a0):.1f} '
                f'A28 28 0 0 1 {c[0] + 28 * math.cos(a1):.1f} {c[1] + 28 * math.sin(a1):.1f} Z')
    needle = [(0, f'-70 {c[0]} {c[1]}'), (2.7, f'-70 {c[0]} {c[1]}'), (3.4, f'18 {c[0]} {c[1]}'), (4.6, f'18 {c[0]} {c[1]}')]
    shown = [(0, 0), (2.8, 0), (3.4, 1), (SCENE, 1)]
    return f"""
<clipPath id="lane"><rect x="0" y="0" width="240" height="240"/></clipPath>
<line x1="0" y1="206" x2="240" y2="206"/>
<line x1="0" y1="222" x2="240" y2="222" stroke-dasharray="10 9" stroke-opacity=".45"/>
<line x1="18" y1="206" x2="18" y2="62"/>
<rect x="10" y="48" width="28" height="15" rx="3"/>
<circle cx="38" cy="55" r="2.2" fill="{t['brand']}" stroke="none"/>
<path d="M38 60 L106 206 M38 60 L206 206" stroke-dasharray="3 6" stroke-opacity=".45" stroke-width="1.2"/>
<path d="M106 150 V206 M206 150 V206" stroke-dasharray="4 4" stroke-opacity=".7" stroke-width="1.3"/>
<path d="M106 142 H206 M106 137 V147 M206 137 V147" stroke-width="1.3"/>
<g clip-path="url(#lane)"><g>{anim('transform', [(0, '-70 206'), (3.2, '250 206'), (SCENE, '250 206')], SCENE, tag='animateTransform', extra=' type="translate"')}
  <path d="M0 -6 V-15 Q0 -18 3 -18 H12 L20 -28 H40 L48 -18 H58 Q61 -18 61 -15 V-6 Z" fill="{t['bg']}"/>
  <circle cx="13" cy="-5" r="5" fill="{t['bg']}"/><circle cx="48" cy="-5" r="5" fill="{t['bg']}"/>
</g></g>
<rect x="144" y="40" width="88" height="76" rx="8"/>
<path d="M158 96 A28 28 0 0 1 214 96" stroke-opacity=".6"/>
<g>{anim('transform', needle, SCENE, tag='animateTransform', extra=' type="rotate"')}
  <path d="{wedge(13)}" fill="{t['brand']}" fill-opacity=".22" stroke="none" opacity="0">{anim('opacity', shown, SCENE)}</path>
  <line x1="{c[0]}" y1="{c[1]}" x2="{c[0]}" y2="{c[1] - 26}" stroke-width="2.2"/>
</g>
<circle cx="{c[0]}" cy="{c[1]}" r="3" fill="{t['brand']}" stroke="none"/>
<text x="{c[0]}" y="{c[1] + 15}" font-size="10" fill="{t['muted']}" stroke="none" text-anchor="middle">km/h</text>"""


def runway(t):
    """A sensor at the runway's edge sweeps the surface while the edge lights run."""
    left, right = ((36, 226), (104, 40)), ((204, 226), (136, 40))
    surface = f'{pts([left[0], left[1], right[1], right[0]])}'
    lights = []
    for i, f in enumerate([.08, .22, .36, .5, .64, .78, .92]):
        for (x0, y0), (x1, y1) in (left, right):
            x, y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            lights.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{2.6 - 1.4 * f:.1f}" fill="{t["brand"]}" stroke="none" opacity=".3">'
                          f'<animate attributeName="opacity" values=".25;1;.25;.25" keyTimes="0;.12;.3;1" dur="{4 * BEAT:g}s" '
                          f'begin="{i * BEAT / 2:g}s" repeatCount="indefinite"/></circle>')
    o = (34, 116)
    ray = lambda deg: (o[0] + 220 * math.cos(math.radians(deg)), o[1] + 220 * math.sin(math.radians(deg)))
    (x1, y1), (x2, y2) = ray(-6), ray(6)
    sweep = [(0, f'30 {o[0]} {o[1]}'), (2.2, f'-22 {o[0]} {o[1]}'), (4.4, f'30 {o[0]} {o[1]}')]
    bars = ''.join(f'<rect x="{x}" y="208" width="6" height="14" rx="1" fill="{t["brand"]}" fill-opacity=".5" stroke="none"/>'
                   for x in range(66, 176, 14))
    return f"""
<clipPath id="surface"><polygon points="{surface}"/></clipPath>
<polygon points="{surface}" fill="{t['brand']}" fill-opacity=".05" stroke="none"/>
<line x1="{left[0][0]}" y1="{left[0][1]}" x2="{left[1][0]}" y2="{left[1][1]}"/>
<line x1="{right[0][0]}" y1="{right[0][1]}" x2="{right[1][0]}" y2="{right[1][1]}"/>
<line x1="120" y1="200" x2="120" y2="44" stroke-dasharray="12 10" stroke-opacity=".55"/>
{bars}
<g clip-path="url(#surface)"><g>{anim('transform', sweep, SCENE, tag='animateTransform', extra=' type="rotate"')}
  <path d="M{o[0]} {o[1]} L{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f} Z" fill="{t['brand']}" fill-opacity=".2" stroke="none"/>
</g></g>
{''.join(lights)}
<line x1="22" y1="226" x2="22" y2="122"/>
<line x1="10" y1="226" x2="34" y2="226" stroke-opacity=".6"/>
<rect x="12" y="108" width="24" height="15" rx="3"/>
<circle cx="34" cy="116" r="3" fill="{t['brand']}" stroke="none"/>"""


def ballot(t):
    """A record in three languages, tied to its source; a new version joins its history."""
    m, g = t['fringe'][1], t['fringe'][0]
    tabs = ''.join(
        f'<rect x="{14 + i * 38}" y="14" width="34" height="18" rx="5" fill="{t["brand"]}" fill-opacity="0" stroke-width="1.3">'
        f'<animate attributeName="fill-opacity" values="{";".join(".35" if j == i else "0" for j in range(3))};{".35" if i == 0 else "0"}" '
        f'keyTimes="0;.33;.66;1" calcMode="discrete" dur="{SCENE:g}s" begin="-{LEAD:g}s" repeatCount="indefinite"/></rect>'
        f'<text x="{31 + i * 38}" y="27" font-size="10" text-anchor="middle" fill="{t["ink"]}" stroke="none">{lang}</text>'
        for i, lang in enumerate(('AR', 'EN', 'FR')))
    grow = [(0, 70), (2.4, 70), (3.0, 104), (SCENE, 104)]
    appear = [(0, 0), (2.4, 0), (2.9, 1), (SCENE, 1)]
    ring = [(0, 0), (2.4, 0), (2.5, .8), (3.6, 0), (SCENE, 0)]
    return f"""
{tabs}
<rect x="14" y="40" width="150" height="132" rx="10"/>
<circle cx="40" cy="72" r="12"/>
<rect x="60" y="64" width="80" height="8" rx="4" fill="{t['ink']}" stroke="none"/>
<rect x="60" y="78" width="54" height="6" rx="3" fill="{t['muted']}" stroke="none"/>
<rect x="28" y="104" width="120" height="7" rx="3.5" fill="{t['brand']}" fill-opacity=".55" stroke="none"/>
<rect x="28" y="119" height="7" rx="3.5" fill="{t['brand']}" fill-opacity=".55" stroke="none" width="70">{anim('width', grow, SCENE)}</rect>
<rect x="28" y="134" width="96" height="7" rx="3.5" fill="{t['brand']}" fill-opacity=".55" stroke="none"/>
<path d="M164 122 C186 122 182 82 200 82" stroke-dasharray="3 4" stroke-width="1.5"/>
<path d="M200 56 H222 L232 66 V104 H200 Z M222 56 V66 H232" stroke-width="1.6"/>
<path d="M206 76 H226 M206 85 H226 M206 94 H220" stroke-opacity=".6" stroke-width="1.4"/>
<line x1="18" y1="206" x2="226" y2="206" stroke-opacity=".6"/>
{''.join(f'<circle cx="{x}" cy="206" r="4.5" fill="{t["bg"]}"/>' for x in (34, 74, 114, 154))}
<circle cx="194" cy="206" r="4.5" fill="{t['brand']}" stroke="none" opacity="0">{anim('opacity', appear, SCENE)}</circle>
<circle cx="194" cy="206" r="5" stroke-width="1.4" opacity="0">{anim('r', [(0, 5), (2.4, 5), (3.6, 16), (SCENE, 16)], SCENE)}{anim('opacity', ring, SCENE)}</circle>
<text x="194" y="228" font-size="9" text-anchor="middle" fill="{t['muted']}" stroke="none">now</text>"""


def survey(t):
    """A survey instrument measures points along the ground; the profile plots itself."""
    def bez(p0, c1, c2, p1, u):
        return tuple((1 - u) ** 3 * a + 3 * (1 - u) ** 2 * u * b + 3 * (1 - u) * u ** 2 * c + u ** 3 * d
                     for a, b, c, d in zip(p0, c1, c2, p1))
    seg1 = ((0, 196), (40, 170), (70, 188), (110, 172))
    seg2 = ((110, 172), (150, 156), (180, 178), (240, 160))
    marks = [bez(*seg1, .75), bez(*seg2, .2), bez(*seg2, .45), bez(*seg2, .7), bez(*seg2, .92)]
    dots = ''.join(
        f'<g opacity="0">{anim("opacity", [(0, 0), (1.0 + .45 * i, 0), (1.2 + .45 * i, 1), (SCENE, 1)], SCENE)}'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{t["brand"]}" stroke="none"/>'
        f'<line x1="{x:.1f}" y1="{y - 6:.1f}" x2="{x:.1f}" y2="{y - 16:.1f}" stroke-width="1.2" stroke-opacity=".6"/></g>'
        for i, (x, y) in enumerate(marks))
    # The panel plots the measured heights, scaled into its box.
    lo, hi = min(y for _, y in marks), max(y for _, y in marks)
    plot = [(140 + i * 21, 80 - (hi - y) / max(1, hi - lo) * 34) for i, (_, y) in enumerate(marks)]
    length = sum(math.dist(a, b) for a, b in zip(plot, plot[1:]))
    draw = [(0, length), (1.2, length), (3.4, 0), (SCENE, 0)]
    return f"""
<path d="M{seg1[0][0]} {seg1[0][1]} C{seg1[1][0]} {seg1[1][1]} {seg1[2][0]} {seg1[2][1]} {seg1[3][0]} {seg1[3][1]} C{seg2[1][0]} {seg2[1][1]} {seg2[2][0]} {seg2[2][1]} {seg2[3][0]} {seg2[3][1]}"/>
<path d="M40 146 L22 210 M40 146 L58 210 M40 146 L40 212" stroke-opacity=".8"/>
<rect x="28" y="126" width="24" height="20" rx="3"/>
<line x1="40" y1="126" x2="40" y2="110"/><circle cx="40" cy="105" r="5"/>
<line x1="52" y1="134" x2="{marks[-1][0]:.1f}" y2="{marks[-1][1] - 16:.1f}" stroke-dasharray="3 5" stroke-opacity=".5" stroke-width="1.2"/>
{dots}
<rect x="128" y="30" width="106" height="66" rx="8"/>
<path d="M138 86 H226 M138 86 V40" stroke-opacity=".45" stroke-width="1.2"/>
<polyline points="{pts(plot)}" stroke-dasharray="{length:.1f}" stroke-dashoffset="{length:.1f}">{anim('stroke-dashoffset', draw, SCENE)}</polyline>"""


def fpv(t):
    """A 5-inch quad hovers on its thrust; then it flies itself home."""
    bob = [(0, '0 0'), (1.2, '0 -6'), (2.5, '0 0'), (3.7, '0 -6'), (SCENE, '0 0')]
    arrow = lambda x: (f'<path d="M{x} 100 V70 M{x - 5} 76 L{x} 70 L{x + 5} 76" stroke-width="1.6">'
                       f'<animate attributeName="opacity" values=".45;1;.45" dur="{2 * BEAT:g}s" repeatCount="indefinite"/></path>'
                       f'<text x="{x + 8}" y="80" font-size="11" fill="{t["brand"]}" stroke="none">T</text>')
    crumbs = ''.join(
        f'<circle cx="{x}" cy="{y}" r="2.4" fill="{t["brand"]}" stroke="none" opacity="0">'
        f'{anim("opacity", [(0, 0), (2.6 + .25 * i, 0), (2.75 + .25 * i, 1), (SCENE, 1)], SCENE)}</circle>'
        for i, (x, y) in enumerate([(132, 150), (146, 162), (160, 172), (174, 180), (188, 186), (200, 190)]))
    return f"""
<line x1="8" y1="214" x2="232" y2="214" stroke-opacity=".6"/>
<path d="M190 214 V200 L202 190 L214 200 V214" stroke-width="1.6"/>
<circle cx="26" cy="34" r="3" fill="{t['brand']}" stroke="none"/>
<path d="M34 40 A10 10 0 0 1 32 50 M40 38 A16 16 0 0 1 36 56" stroke-opacity=".5" stroke-width="1.2"/>
{crumbs}
<g>{anim('transform', bob, SCENE, tag='animateTransform', extra=' type="translate"')}
  {arrow(52)}{arrow(176)}
  <ellipse cx="52" cy="106" rx="26" ry="3" fill="{t['brand']}" fill-opacity=".25" stroke-opacity=".7">
    <animate attributeName="rx" values="26;22;26" dur="{BEAT / 2:g}s" repeatCount="indefinite"/></ellipse>
  <ellipse cx="176" cy="106" rx="26" ry="3" fill="{t['brand']}" fill-opacity=".25" stroke-opacity=".7">
    <animate attributeName="rx" values="22;26;22" dur="{BEAT / 2:g}s" repeatCount="indefinite"/></ellipse>
  <rect x="46" y="108" width="12" height="12" rx="2"/><rect x="170" y="108" width="12" height="12" rx="2"/>
  <line x1="58" y1="124" x2="170" y2="124" stroke-width="3"/>
  <rect x="86" y="116" width="56" height="14" rx="4"/>
  <rect x="94" y="102" width="40" height="12" rx="2" fill="{t['brand']}" fill-opacity=".2"/>
  <path d="M142 128 L152 134 L148 140 L138 134 Z" stroke-width="1.5"/>
  <line x1="92" y1="116" x2="84" y2="98" stroke-width="1.5"/>
  <path d="M114 132 V166 M109 160 L114 166 L119 160" stroke-width="1.6"/>
  <text x="122" y="164" font-size="11" fill="{t['brand']}" stroke="none">W</text>
</g>"""


SCENES = {'sign': sign, 'face': face, 'desk': desk, 'rover': rover, 'road': road,
          'runway': runway, 'ballot': ballot, 'survey': survey, 'fpv': fpv}


def build(who, t):
    n = len(who)
    dur = n * SCENE
    m, g = t['fringe'][1], t['fringe'][0]
    scenes = []
    for k, w in enumerate(who):
        a, b = k * SCENE - LEAD, (k + 1) * SCENE - LEAD
        if k == 0:      # already in focus when the reel opens; racks back in at the loop's end
            rack = lambda far, near: [(0, near), (b - FOCUS, near), (b, far), (dur - LEAD, far),
                                      (dur - LEAD + FOCUS, near), (dur, near)]
        else:
            rack = lambda far, near: [(0, far), (a, far), (a + FOCUS, near), (b - FOCUS, near), (b, far), (dur, far)]
        blur, shift, seen = rack(7, 0), rack(9, .55), rack(0, 1)
        lines = wrap(w['line'], 66)
        text = '\n'.join(f'<text x="300" y="{186 + 22 * i}" font-size="14.5" fill="{t["muted"]}">{esc(l)}</text>'
                         for i, l in enumerate(lines[:3]))
        scenes.append(f"""
<filter id="f{k}" x="-5%" y="-10%" width="110%" height="120%" color-interpolation-filters="sRGB">
  <feGaussianBlur in="SourceGraphic" stdDeviation="0" result="b">{anim('stdDeviation', blur, dur)}</feGaussianBlur>
  <feOffset in="b" dx="-.55" result="l">{anim('dx', [(s, -v) for s, v in shift], dur)}</feOffset>
  <feOffset in="b" dx=".55" result="r">{anim('dx', shift, dur)}</feOffset>
  <feFlood flood-color="{m}"/><feComposite in2="l" operator="in" result="lm"/>
  <feFlood flood-color="{g}"/><feComposite in2="r" operator="in" result="rg"/>
  <feBlend in="lm" in2="rg" mode="{'screen' if t['blend'] == 'screen' else 'multiply'}" result="fringe"/>
  <feMerge><feMergeNode in="fringe"/><feMergeNode in="b"/></feMerge>
</filter>
<g class="scene s{k}" filter="url(#f{k})" opacity="{1 if k == 0 else 0}">{anim('opacity', seen, dur)}
  <g transform="translate(32 30)" fill="none" stroke="{t['brand']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{SCENES[w['scene']](t)}
  </g>
  <text x="300" y="66" font-size="12" letter-spacing="2" fill="{t['muted']}">{esc(w.get('kicker', '').upper())} · {k + 1:02d}/{n:02d}</text>
  <text x="300" y="116" font-size="36" fill="{t['ink']}">{esc(w['for'])}</text>
  <text x="300" y="152" font-size="18" fill="{t['key']}">{esc(w['project'])}</text>
  {text}
</g>""")

    pip_w, pip_gap = 26, 8
    pips = ''.join(f'<rect x="{300 + i * (pip_w + pip_gap)}" y="262" width="{pip_w}" height="3" rx="1.5" fill="{t["cc"]}"/>'
                   for i in range(n))
    cursor = (f'<rect x="300" y="261" width="{pip_w}" height="5" rx="2.5" fill="{t["brand"]}">'
              f'<animate attributeName="x" dur="{dur:g}s" repeatCount="indefinite" calcMode="discrete" '
              f'values="{";".join(str(300 + i * (pip_w + pip_gap)) for i in [*range(n), 0])}" '
              f'keyTimes="0;{";".join(f"{(i * SCENE - LEAD) / dur:.5f}" for i in range(1, n + 1))}"/></rect>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="{FONT}" role="img" aria-label="What I build, and for whom: {esc(', '.join(w['for'] for w in who))}">
<style>
@media (prefers-reduced-motion: reduce) {{ .scene {{ opacity: 0 !important; filter: none !important; }} .s0 {{ opacity: 1 !important; }} }}
</style>
<defs>
<marker id="j" viewBox="-3 -3 6 6" markerWidth="6" markerHeight="6" markerUnits="userSpaceOnUse"><circle r="2.6" fill="{t['brand']}"/></marker>
</defs>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="15" fill="{t['bg']}" stroke="{t['edge']}"/>
{''.join(scenes)}
{pips}{cursor}
</svg>
"""


# ── the phone reel ──────────────────────────────────────────────────────────
# The README shows this copy when the screen is 640 px wide or less. It is the
# same reel stacked: each drawing above its text, at type a phone can read. The
# canvas is 320 units wide, drawn at twice that, so on a 375 px phone (a 293 px
# README column) one unit is about 0.92 px.
PHONE_W = 320
PAD = 12
ADVANCE = .6
DRAW_Y = 22                 # where each 240-unit drawing box starts (its top rows are empty)
DRAW_X = (PHONE_W - 240) / 2
TEXT_Y = DRAW_Y + 239       # the drawings end by y 232 of their box, the ballot's label by 230
LINE = 16


def label(x, y, s, size, fill, anchor='start', track=0, weight=None):
    """Text squeezed or stretched to exactly its monospace width."""
    w = len(s) * size * ADVANCE + max(0, len(s) - 1) * track
    bold = f' font-weight="{weight}"' if weight else ''
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{bold} '
            f'textLength="{w:g}" lengthAdjust="spacingAndGlyphs">{esc(s)}</text>')


def phone_text(w, t):
    """The words under a phone scene, and the height they need."""
    cols = int((PHONE_W - 2 * PAD) / (12 * ADVANCE))
    y = TEXT_Y + 22
    out = [label(PAD, y, w['for'], 22, t['ink'])]
    y += 22
    for line in wrap(w['project'], cols):
        out.append(label(PAD, y, line, 12, t['key'], weight=700))
        y += LINE
    y += 6
    for line in wrap(w['line'], cols):
        out.append(label(PAD, y, line, 12, t['muted']))
        y += LINE
    return '\n'.join(out), y - LINE


def phone_drawing(fn, t):
    """A scene's drawing with its small labels raised to phone size."""
    import re
    return re.sub(r'font-size="(9|10)"', 'font-size="11"', fn(t))


def build_phone(who, t):
    n = len(who)
    dur = n * SCENE
    m, g = t['fringe'][1], t['fringe'][0]
    words = [phone_text(w, t) for w in who]
    bottom = max(b for _, b in words)
    pip_y = bottom + 16
    height = round(pip_y + 3 + 10)
    scenes = []
    for k, w in enumerate(who):
        a, b = k * SCENE - LEAD, (k + 1) * SCENE - LEAD
        if k == 0:
            rack = lambda far, near: [(0, near), (b - FOCUS, near), (b, far), (dur - LEAD, far),
                                      (dur - LEAD + FOCUS, near), (dur, near)]
        else:
            rack = lambda far, near: [(0, far), (a, far), (a + FOCUS, near), (b - FOCUS, near), (b, far), (dur, far)]
        blur, shift, seen = rack(5, 0), rack(7, .5), rack(0, 1)
        kicker = w.get('kicker', '').upper()
        scenes.append(f"""
<filter id="f{k}" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">
  <feGaussianBlur in="SourceGraphic" stdDeviation="0" result="b">{anim('stdDeviation', blur, dur)}</feGaussianBlur>
  <feOffset in="b" dx="-.5" result="l">{anim('dx', [(s, -v) for s, v in shift], dur)}</feOffset>
  <feOffset in="b" dx=".5" result="r">{anim('dx', shift, dur)}</feOffset>
  <feFlood flood-color="{m}"/><feComposite in2="l" operator="in" result="lm"/>
  <feFlood flood-color="{g}"/><feComposite in2="r" operator="in" result="rg"/>
  <feBlend in="lm" in2="rg" mode="{'screen' if t['blend'] == 'screen' else 'multiply'}" result="fringe"/>
  <feMerge><feMergeNode in="fringe"/><feMergeNode in="b"/></feMerge>
</filter>
<g class="scene s{k}" filter="url(#f{k})" opacity="{1 if k == 0 else 0}">{anim('opacity', seen, dur)}
  {label(PAD, 24, kicker, 11, t['muted'], track=1.5)}
  {label(PHONE_W - PAD, 24, f'{k + 1:02d}/{n:02d}', 11, t['muted'], 'end', track=1.5)}
  <g transform="translate({DRAW_X:g} {DRAW_Y})" fill="none" stroke="{t['brand']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{phone_drawing(SCENES[w['scene']], t)}
  </g>
  {words[k][0]}
</g>""")

    pip_w, pip_gap = 26, 8
    pips = ''.join(f'<rect x="{PAD + i * (pip_w + pip_gap)}" y="{pip_y:g}" width="{pip_w}" height="3" rx="1.5" fill="{t["cc"]}"/>'
                   for i in range(n))
    cursor = (f'<rect x="{PAD}" y="{pip_y - 1:g}" width="{pip_w}" height="5" rx="2.5" fill="{t["brand"]}">'
              f'<animate attributeName="x" dur="{dur:g}s" repeatCount="indefinite" calcMode="discrete" '
              f'values="{";".join(str(PAD + i * (pip_w + pip_gap)) for i in [*range(n), 0])}" '
              f'keyTimes="0;{";".join(f"{(i * SCENE - LEAD) / dur:.5f}" for i in range(1, n + 1))}"/></rect>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{2 * PHONE_W}" height="{2 * height}" viewBox="0 0 {PHONE_W} {height}" font-family="{FONT}" role="img" aria-label="What I build, and for whom: {esc(', '.join(w['for'] for w in who))}">
<style>
text {{ white-space: pre; }}
@media (prefers-reduced-motion: reduce) {{ .scene {{ opacity: 0 !important; filter: none !important; }} .s0 {{ opacity: 1 !important; }} }}
</style>
<defs>
<marker id="j" viewBox="-3 -3 6 6" markerWidth="6" markerHeight="6" markerUnits="userSpaceOnUse"><circle r="2.6" fill="{t['brand']}"/></marker>
</defs>
<rect x=".5" y=".5" width="{PHONE_W - 1}" height="{height - 1}" rx="12" fill="{t['bg']}" stroke="{t['edge']}"/>
{''.join(scenes)}
{pips}{cursor}
</svg>
"""


def main():
    with open(CONFIG, 'rb') as f:
        who = tomllib.load(f).get('readme', {}).get('who', [])
    if not who:
        raise SystemExit(f'{CONFIG} has no [[readme.who]] entries')
    unknown = {w['scene'] for w in who} - set(SCENES)
    if unknown:
        raise SystemExit(f'unknown scene(s) {", ".join(sorted(unknown))}; pick from {", ".join(SCENES)}')
    for theme, t in SAGE.items():
        with open(OUT.format(theme), 'w', encoding='utf-8') as f:
            f.write(build(who, t))
        with open(OUT.format(f'phone-{theme}'), 'w', encoding='utf-8') as f:
            f.write(build_phone(who, t))

    with open(README, encoding='utf-8') as f:
        text = f.read()
    if WHO_START in text and WHO_END in text:
        # One pill per project that has a page, drawn like the link pills.
        from parts import OUT as PARTS, link_svg, picture, slug
        linked = [w for w in who if w.get('href')]
        for w in linked:
            for theme, t in SAGE.items():
                with open(f'{PARTS}/who-{slug(w["project"])}-{theme}.svg', 'w', encoding='utf-8') as f:
                    f.write(link_svg(f'{w["project"]} ↗', t, primary=False))
        row = '\n'.join(picture(f'who-{slug(w["project"])}', w['project'], w['href']) for w in linked)
        head, rest = text.split(WHO_START, 1)
        _, tail = rest.split(WHO_END, 1)
        with open(README, 'w', encoding='utf-8') as f:
            f.write(f'{head}{WHO_START}\n{row}\n{WHO_END}{tail}')
    print(f'wrote {OUT.format("light")} and {OUT.format("dark")}, and their phone twins: {len(who)} scenes, '
          f'{len(who) * SCENE:g} s a loop')


if __name__ == '__main__':
    main()

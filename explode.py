"""
Draws "What I build with" as an exploded assembly drawing.

    python explode.py

Writes assets/explode-light.svg and assets/explode-dark.svg, and phone copies
(assets/explode-phone-*.svg) with the parts list under the drawing. Local
only: the drawing changes when the parts list below does, not from day to day.

The robot is a composite, not one project: a tracked chassis, its drive, a
compute deck and a top deck carrying the arm, the servos and the sensors --
the parts I keep reaching for, from the rover, OmniSign, the desk, the race
car and the drones. Each part has a numbered balloon that matches a row of
the bill of materials beside it, and the software and languages close the
list.

It is plotted the way a two-pen plotter would draw it. The whole drawing is
defined once and drawn twice, once by a magenta pen and once by a green one,
a fraction of a pixel out of register. On paper the two inks multiply, so
where both pens agree the line is near black and the misregistration leaves a
magenta edge on one side and a green one on the other -- this version's
chromatic aberration. On the dark sheet the inks add (screen) instead.

The assembly slowly closes and opens again. It rests exploded, with every
balloon showing, so a viewer without CSS animation or with reduced motion
gets the annotated drawing. Every layer moves straight down the vertical
axis, which an isometric camera shows as a straight screen move, so one CSS
translate per layer is the whole animation.

Geometry is a small isometric renderer: convex solids (boxes, prisms,
cylinders) shaded in four tones by facing, outlined only where faces meet at
a crease or at the silhouette, round bodies shaded with drafting lines along
their axis, and painted back to front. Layers are stacked so each one sits
wholly above the last, which makes "draw the layers bottom to top" a correct
painter's order at every point of the animation. The drive sits inside an
open hull, so its layer is clipped by the hull's near walls.
"""
import math
import os

from card import SAGE, WIDTH, esc

OUT = 'assets/explode-{}.svg'
FONT = 'ConsolasFallback,Consolas,Menlo,monospace'
ADVANCE = 0.6
HEIGHT = 580

# ── the camera ──────────────────────────────────────────────────────────────
AZ, EL = math.radians(34), math.radians(26)
CA, SA, CE, SE = math.cos(AZ), math.sin(AZ), math.cos(EL), math.sin(EL)
VIEW = (SA * CE, CA * CE, SE)                       # toward the viewer
LIGHT = (-.36, .62, .7)                             # from the upper left
_n = math.sqrt(sum(c * c for c in LIGHT))
LIGHT = tuple(c / _n for c in LIGHT)


def project(p):
    x, y, z = p
    return ((x * CA - y * SA), (x * SA + y * CA) * SE - z * CE)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    n = math.sqrt(dot(a, a)) or 1
    return mul(a, 1 / n)


def depth(p):
    return dot(p, VIEW)


# ── solids ──────────────────────────────────────────────────────────────────
class Solid:
    """A convex polyhedron with decorations that live on its faces."""

    def __init__(self, verts, faces, smooth=False, tone=0):
        self.verts, self.faces, self.smooth, self.tone = verts, faces, smooth, tone
        c = mul(sum_points(verts), 1 / len(verts))
        self.centre = c
        self.normals = []
        for f in faces:
            n = newell([verts[i] for i in f])
            fc = mul(sum_points([verts[i] for i in f]), 1 / len(f))
            if dot(n, sub(fc, c)) < 0:
                n = mul(n, -1)
            self.normals.append(n)
        self.deco = []          # (kind, data, normal-or-None)
        self.axis = None        # for round bodies: (base, top, radius)

    def line(self, pts, normal=None, cls='ln', closed=False):
        self.deco.append(('line', (pts, cls, closed), normal))
        return self

    def dot(self, p, r=1.0, normal=None):
        self.deco.append(('dot', (p, r), normal))
        return self

    def patch(self, pts, normal=None, cls='t4'):
        self.deco.append(('patch', (pts, cls), normal))
        return self

    def ring(self, centre, u, v, r, normal=None, cls='ln', n=28, fill=None):
        pts = [add(centre, add(mul(u, r * math.cos(a)), mul(v, r * math.sin(a))))
               for a in (2 * math.pi * k / n for k in range(n))]
        if fill:
            self.patch(pts, normal, fill)
        self.line(pts, normal, cls, closed=True)
        return self


def sum_points(ps):
    s = (0, 0, 0)
    for p in ps:
        s = add(s, p)
    return s


def newell(ps):
    nx = ny = nz = 0
    for i, a in enumerate(ps):
        b = ps[(i + 1) % len(ps)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return norm((nx, ny, nz))


def prism(profile, origin, u, v, w, length, smooth=False, tone=0):
    """Extrude a convex 2D profile (in the u, v plane at origin) along w."""
    n = len(profile)
    verts = []
    for k in (0, length):
        for (a, b) in profile:
            verts.append(add(origin, add(add(mul(u, a), mul(v, b)), mul(w, k))))
    faces = [list(range(n)), list(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return Solid(verts, faces, smooth, tone)


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


def box(x0, x1, y0, y1, z0, z1, tone=0):
    return prism([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], (0, 0, z0), X, Y, Z, z1 - z0, tone=tone)


def cyl(c, axis, r, length, n=28, tone=0):
    """A cylinder whose base centre is c, running `length` along `axis`."""
    w = norm(axis)
    u = norm(cross(w, Z if abs(w[2]) < .9 else X))
    v = cross(w, u)
    prof = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    s = prism(prof, c, u, v, w, length, smooth=True, tone=tone)
    s.axis = (c, add(c, mul(w, length)), r, u, v, w)
    return s


def tone_of(n):
    l = dot(n, LIGHT)
    if l > .66:
        return 1
    if l > .3:
        return 2
    if l > -.12:
        return 3
    return 4


# ── rendering one solid ─────────────────────────────────────────────────────
def fmt(p):
    return f'{p[0]:.1f},{p[1]:.1f}'


def path_of(pts2, closed=True):
    return 'M' + ' L'.join(fmt(p) for p in pts2) + ('Z' if closed else '')


def render(s, P):
    """SVG for one solid: tone fills, crease/silhouette edges, decorations."""
    out = []
    vis = [dot(n, VIEW) > 1e-6 for n in s.normals]
    for f, n, v in zip(s.faces, s.normals, vis):
        if not v:
            continue
        cls = f't{min(4, tone_of(n) + s.tone)}' if not s.smooth else \
            (f't{min(4, 1 + s.tone)}' if n[2] > .9 or n[2] < -.9 or
             (s.axis and abs(dot(n, s.axis[5])) > .9) else f't{min(4, 2 + s.tone)}')
        out.append(f'<path class="{cls}" d="{path_of([P(s.verts[i]) for i in f])}"/>')
    # edges: silhouette, or a real crease between two visible faces
    edges = {}
    for fi, f in enumerate(s.faces):
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            edges.setdefault((min(a, b), max(a, b)), []).append(fi)
    segs = []
    for (a, b), fs in edges.items():
        vs = [vis[i] for i in fs]
        if not any(vs):
            continue
        if len(fs) == 2 and all(vs):
            if dot(s.normals[fs[0]], s.normals[fs[1]]) > math.cos(math.radians(25)):
                continue
        segs.append((P(s.verts[a]), P(s.verts[b])))
    # drafting lines along the axis of a round body, denser toward the shaded side
    if s.axis:
        c0, c1, r, u, v, w = s.axis
        for k in range(48):
            a = 2 * math.pi * k / 48
            nrm = add(mul(u, math.cos(a)), mul(v, math.sin(a)))
            facing = dot(nrm, VIEW)
            shade = dot(nrm, LIGHT)
            if facing < .12 or shade > -.05:
                continue
            step = 2 if shade > -.45 else 1
            if k % step:
                continue
            off = mul(nrm, r)
            inset = mul(w, min(1.2, .08 * dist(c0, c1)))
            segs.append((P(add(add(c0, off), inset)), P(sub(add(c1, off), inset))))
    if segs:
        out.append('<path class="ln" d="' + ''.join(f'M{fmt(a)}L{fmt(b)}' for a, b in segs) + '"/>')
    fine = []
    for kind, data, n in s.deco:
        if n is not None and dot(n, VIEW) <= 1e-6:
            continue
        if kind == 'patch':
            pts, cls = data
            out.append(f'<path class="{cls}" d="{path_of([P(p) for p in pts])}"/>')
        elif kind == 'line':
            pts, cls, closed = data
            (fine if cls == 'fn' else out).append(
                f'<path class="{cls}" d="{path_of([P(p) for p in pts], closed)}"/>')
        elif kind == 'dot':
            p, r = data
            q = P(p)
            out.append(f'<circle class="dt" cx="{q[0]:.1f}" cy="{q[1]:.1f}" r="{r:g}"/>')
    return ''.join(out + fine)


def paint_order(parts, P):
    """
    Back-to-front order for one layer. Two solids whose pictures overlap are
    ordered by a separating axis: if one ends where the other begins along x, y
    or z, it is the farther one (the camera looks from +x, +y, +z). Pairs with
    no separating axis, or two that disagree, fall back to centroid depth. A
    topological sort turns the pairs into an order.
    """
    n = len(parts)
    lo = [tuple(min(v[a] for v in s.verts) for a in range(3)) for s in parts]
    hi = [tuple(max(v[a] for v in s.verts) for a in range(3)) for s in parts]
    scr = []
    for s in parts:
        q = [P(v) for v in s.verts]
        scr.append((min(p[0] for p in q), min(p[1] for p in q), max(p[0] for p in q), max(p[1] for p in q)))
    after = [set() for _ in range(n)]          # after[j]: solids that must come before j
    for i in range(n):
        for j in range(i + 1, n):
            a, b = scr[i], scr[j]
            if a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]:
                continue
            i_back = any(hi[i][k] <= lo[j][k] + .01 for k in range(3))
            j_back = any(hi[j][k] <= lo[i][k] + .01 for k in range(3))
            if i_back and not j_back:
                after[j].add(i)
            elif j_back and not i_back:
                after[i].add(j)
            elif depth(parts[i].centre) <= depth(parts[j].centre):
                after[j].add(i)
            else:
                after[i].add(j)
    order, done = [], set()
    while len(order) < n:
        ready = [k for k in range(n) if k not in done and after[k] <= done]
        if not ready:                           # a cycle: take the farthest
            ready = [min((k for k in range(n) if k not in done), key=lambda k: depth(parts[k].centre))]
        k = min(ready, key=lambda k: depth(parts[k].centre))
        order.append(k)
        done.add(k)
    return [parts[k] for k in order]


def dist(a, b):
    return math.sqrt(dot(sub(a, b), sub(a, b)))


# ── the robot ───────────────────────────────────────────────────────────────
# World units are about a millimetre at rover scale; x runs forward, y to the
# robot's left, z up. Each layer is built at its assembled height; the
# explode lifts it by OFFSET[its index], more where a deck hides the one below.
OFFSET = {0: 0, 1: 34, 2: 80, 3: 150, 4: 190}
HULL = dict(x0=-78, x1=78, y0=-38, y1=38, z0=6, z1=34, wall=4)


def chassis():
    parts = []
    trk = [(-92, 10), (-80, 0), (80, 0), (92, 10), (92, 22), (80, 32), (-80, 32), (-92, 22)]
    for y0 in (-60, 40):                                  # far track first
        t = prism(trk, (0, y0, 0), X, Z, Y, 20, tone=0)
        t.normals = t.normals                             # prism along +y
        # road wheels, sprocket and idler on the outer face
        face_y = y0 + 20 if y0 > 0 else y0
        nrm = (0, 1, 0) if y0 > 0 else (0, -1, 0)
        for x in (-64, -32, 0, 32, 64):
            t.ring((x, face_y + .01 * nrm[1], 12), X, Z, 8.5, nrm, fill='t3')
            t.ring((x, face_y + .01 * nrm[1], 12), X, Z, 3, nrm)
            t.dot((x, face_y, 12), .9, nrm)
        for x in (-80, 80):
            t.ring((x, face_y + .01 * nrm[1], 16), X, Z, 10, nrm, fill='t2')
            t.ring((x, face_y + .01 * nrm[1], 16), X, Z, 4, nrm)
            for k in range(8):
                a = 2 * math.pi * k / 8
                t.dot((x + 7 * math.cos(a), face_y, 16 + 7 * math.sin(a)), .6, nrm)
        # tread grooves over the top run
        for x in range(-76, 80, 8):
            t.line([(x, y0 + 1.5, 32), (x, y0 + 18.5, 32)], Z, 'fn')
        for x in range(-76, 80, 8):
            t.line([(x, face_y, 30.5), (x, face_y, 32)], nrm, 'fn')
        parts.append(t)

    h = HULL
    hull = box(h['x0'], h['x1'], h['y0'], h['y1'], h['z0'], h['z1'])
    # it is an open tub: the top face is drawn as the rim and the inside
    top = [i for i, n in enumerate(hull.normals) if n[2] > .9][0]
    hull.faces.pop(top)
    hull.normals.pop(top)
    w = h['wall']
    rim_o = [(h['x0'], h['y0'], h['z1']), (h['x1'], h['y0'], h['z1']),
             (h['x1'], h['y1'], h['z1']), (h['x0'], h['y1'], h['z1'])]
    rim_i = [(h['x0'] + w, h['y0'] + w, h['z1']), (h['x1'] - w, h['y0'] + w, h['z1']),
             (h['x1'] - w, h['y1'] - w, h['z1']), (h['x0'] + w, h['y1'] - w, h['z1'])]
    fl = h['z0'] + 3
    # far inside walls and the floor, seen through the opening
    hull.patch([(h['x0'] + w, h['y0'] + w, fl), (h['x1'] - w, h['y0'] + w, fl),
                (h['x1'] - w, h['y1'] - w, fl), (h['x0'] + w, h['y1'] - w, fl)], Z, 't2')
    hull.patch([(h['x0'] + w, h['y0'] + w, fl), (h['x1'] - w, h['y0'] + w, fl),
                (h['x1'] - w, h['y0'] + w, h['z1']), (h['x0'] + w, h['y0'] + w, h['z1'])], Z, 't3')
    hull.patch([(h['x0'] + w, h['y0'] + w, fl), (h['x0'] + w, h['y1'] - w, fl),
                (h['x0'] + w, h['y1'] - w, h['z1']), (h['x0'] + w, h['y0'] + w, h['z1'])], Z, 't4')
    hull.line([(h['x0'] + w, h['y1'] - w, fl), (h['x0'] + w, h['y0'] + w, fl),
               (h['x1'] - w, h['y0'] + w, fl)], Z)
    hull.line([(h['x0'] + w, h['y0'] + w, fl), (h['x0'] + w, h['y0'] + w, h['z1'])], Z)
    # the rim: a band between the outer and inner edges
    for i in range(4):
        j = (i + 1) % 4
        hull.patch([rim_o[i], rim_o[j], rim_i[j], rim_i[i]], Z, 't1')
    hull.line(rim_o, Z, closed=True)
    hull.line(rim_i, Z, closed=True)
    # screws on the rim and a seam round the sides
    for (x, y) in ((h['x0'] + 2, h['y0'] + 2), (h['x1'] - 2, h['y0'] + 2),
                   (h['x1'] - 2, h['y1'] - 2), (h['x0'] + 2, h['y1'] - 2),
                   (0, h['y1'] - 2), (0, h['y0'] + 2)):
        hull.dot((x, y, h['z1']), .8, Z)
    hull.line([(h['x1'], h['y0'], 14), (h['x1'], h['y1'], 14)], X, 'fn')
    hull.line([(h['x0'], h['y1'], 14), (h['x1'], h['y1'], 14)], Y, 'fn')
    # a front bumper plate
    bump = box(h['x1'], h['x1'] + 5, -26, 26, 8, 22)
    for y in (-20, 20):
        bump.dot((h['x1'] + 5, y, 15), .8, X)
    parts.insert(1, hull)
    parts.insert(2, bump)
    return parts


def drive(z):
    parts = []
    for y in (-22, 22):
        # a gear motor: can, gearbox, shaft toward the track
        side = 1 if y > 0 else -1
        can = cyl((-60, y - side * 9, z + 11), (0, side, 0), 9, 18)
        can.ring(add(can.axis[1], (0, 0, 0)), X, Z, 3, (0, side, 0))
        gb = box(-71, -49, y - side * 9 - (8 if side > 0 else -8) - 4 * side, y - side * 9, z + 1, z + 21)
        parts += [gb, can] if side > 0 else [can, gb]
        # its ESC: a small board in heat shrink with three phase wires' pads
        esc_ = box(-34, -8, y - 8, y + 8, z + 2, z + 7, tone=1)
        for k in range(3):
            esc_.dot((-10, y - 5 + 5 * k, z + 7), .9, Z)
        esc_.line([(-30, y - 8, z + 4.5), (-12, y - 8, z + 4.5)], (0, -1, 0), 'fn')
        esc_.patch([(-28, y - 4, z + 7), (-18, y - 4, z + 7), (-18, y + 4, z + 7), (-28, y + 4, z + 7)], Z, 't3')
        parts.append(esc_)
    # a cable tray linking them
    tray = box(-8, 40, -6, 6, z + 1, z + 4)
    for x in range(-4, 40, 6):
        tray.line([(x, -6, z + 4), (x, 6, z + 4)], Z, 'fn')
    parts.append(tray)
    return parts


def standoff(x, y, z0, z1):
    return cyl((x, y, z0), Z, 1.8, z1 - z0, n=12)


def compute(z):
    parts = []
    deck = box(-70, 70, -36, 36, z, z + 3)
    for (x, y) in ((-66, -32), (66, -32), (66, 32), (-66, 32)):
        deck.dot((x, y, z + 3), .9, Z)
    for x in range(-60, 70, 10):
        deck.line([(x, 36, z + .5), (x, 36, z + 2.5)], Y, 'fn')
    parts.append(deck)
    zt = z + 3

    # Jetson Orin: carrier board, module with heatsink and fan
    for (x, y) in ((-60, -20), (-18, -20), (-18, 20), (-60, 20)):
        parts.append(standoff(x, y, zt, zt + 4))
    carrier = box(-63, -15, -23, 23, zt + 4, zt + 6, tone=1)
    for k in range(10):
        carrier.dot((-60 + 4.5 * k, 21, zt + 6), .55, Z)
    parts.append(carrier)
    sink = box(-58, -22, -18, 16, zt + 6, zt + 18)
    for x in range(-56, -22, 3):
        sink.line([(x, -18, zt + 7.5), (x, -18, zt + 18)], (0, -1, 0), 'fn')
    for y in range(-16, 16, 3):
        sink.line([(-22, y, zt + 7.5), (-22, y, zt + 18)], X, 'fn')
    fc = (-40, -1, zt + 18)
    sink.ring(fc, X, Y, 13, Z, fill='t2')
    sink.ring(fc, X, Y, 4, Z, fill='t3')
    for k in range(7):
        a = 2 * math.pi * k / 7
        sink.line([add(fc, (4 * math.cos(a), 4 * math.sin(a), 0)),
                   add(fc, (12 * math.cos(a + .5), 12 * math.sin(a + .5), 0))], Z)
    for (x, y) in ((-56, -16), (-24, -16), (-24, 14), (-56, 14)):
        sink.dot((x, y, zt + 18), .8, Z)
    parts.append(sink)

    # Raspberry Pi 5: board, SoC, USB and Ethernet blocks, GPIO header
    pi = box(-2, 42, -31, -3, zt + 3, zt + 5, tone=1)
    for k in range(20):
        pi.dot((0 + 2 * k, -5, zt + 5), .45, Z)
        pi.dot((0 + 2 * k, -7, zt + 5), .45, Z)
    parts += [standoff(x, y, zt, zt + 3) for (x, y) in ((1, -28), (39, -28), (39, -6), (1, -6))]
    parts.append(pi)
    soc = box(10, 20, -22, -12, zt + 5, zt + 7, tone=2)
    soc.line([(12, -14, zt + 7), (18, -14, zt + 7)], Z, 'fn')
    parts.append(soc)
    for y0 in (-29, -21, -13):
        blk = box(34, 44, y0, y0 + 7, zt + 5, zt + 11)
        blk.line([(44, y0 + 1.5, zt + 9), (44, y0 + 5.5, zt + 9)], X, 'fn')
        parts.append(blk)

    # ESP32 dev board: module with its shield can and printed antenna
    esp = box(4, 36, 8, 22, zt + 3, zt + 5, tone=1)
    for k in range(15):
        esp.dot((6 + 2 * k, 9.5, zt + 5), .45, Z)
        esp.dot((6 + 2 * k, 20.5, zt + 5), .45, Z)
    parts += [standoff(x, y, zt, zt + 3) for (x, y) in ((6, 10), (34, 10), (34, 20), (6, 20))]
    parts.append(esp)
    can = box(16, 30, 11, 19, zt + 5, zt + 7)
    can.line([(18, 13, zt + 7), (28, 13, zt + 7), (28, 17, zt + 7), (18, 17, zt + 7)], Z, 'fn', closed=True)
    can.line([(31, 12, zt + 5.01), (33, 12, zt + 5.01), (33, 18, zt + 5.01), (31, 18, zt + 5.01)], Z, 'fn')
    parts.append(can)

    # Arduino: board, the long ATmega DIP, USB-B jack, headers
    ard = box(46, 68, -30, 8, zt + 3, zt + 5, tone=1)
    for k in range(16):
        ard.dot((48, -27 + 2.2 * k, zt + 5), .45, Z)
        ard.dot((66, -27 + 2.2 * k, zt + 5), .45, Z)
    parts += [standoff(x, y, zt, zt + 3) for (x, y) in ((48, -28), (66, -28), (66, 6), (48, 6))]
    parts.append(ard)
    dip = box(53, 61, -20, 2, zt + 5, zt + 8, tone=2)
    for k in range(10):
        dip.line([(61, -19 + 2.2 * k, zt + 5.4), (61.8, -19 + 2.2 * k, zt + 5.4)], X, 'fn')
    dip.ring((57, -18, zt + 8), X, Y, 1, Z)
    parts.append(dip)
    usb = box(55, 66, -32, -24, zt + 5, zt + 14)
    usb.patch([(55, -32, zt + 7), (66, -32, zt + 7), (66, -32, zt + 12), (55, -32, zt + 12)], (0, -1, 0), 't4')
    parts.append(usb)

    # tall standoffs that carry the top deck
    for (x, y) in ((-66, -32), (66, -32), (66, 32), (-66, 32)):
        parts.append(standoff(x, y, zt, zt + 27))
    return parts


def top(z):
    parts = []
    deck = box(-70, 70, -36, 36, z, z + 3)
    for (x, y) in ((-66, -32), (66, -32), (66, 32), (-66, 32)):
        deck.ring((x, y, z + 3), X, Y, 2.2, Z)
    deck.line([(-70, 36, z + 1.5), (70, 36, z + 1.5)], Y, 'fn')
    parts.append(deck)
    zt = z + 3

    # GNSS: a ceramic patch antenna on a ground plane
    gp = box(-64, -40, -30, -6, zt, zt + 2, tone=1)
    patch = box(-58, -46, -24, -12, zt + 2, zt + 6, tone=0)
    patch.ring((-52, -18, zt + 6), X, Y, 1.4, Z)
    patch.line([(-56, -22, zt + 6), (-48, -22, zt + 6), (-48, -14, zt + 6), (-56, -14, zt + 6)], Z, 'fn', closed=True)
    parts += [gp, patch]

    # IMU: a small board with its chip and the axes printed on it
    imu = box(-30, -14, -30, -14, zt, zt + 2, tone=1)
    chip = box(-25, -19, -25, -19, zt + 2, zt + 3.5, tone=3)
    imu.line([(-28, -16, zt + 2), (-28, -28, zt + 2)], Z, 'fn')
    imu.line([(-28, -16, zt + 2), (-16, -16, zt + 2)], Z, 'fn')
    imu.dot((-28, -16, zt + 2), .8, Z)
    parts += [imu, chip]

    # two hobby servos, pan over tilt, with their mounting ears and horns
    for (x0, y0, zz) in ((-12, 10, zt),):
        body = box(x0, x0 + 22, y0, y0 + 12, zz, zz + 20)
        ears = box(x0 - 4, x0 + 26, y0, y0 + 12, zz + 14, zz + 16)
        for x in (x0 - 2, x0 + 24):
            ears.dot((x, y0 + 6, zz + 16), .8, Z)
        horn = cyl((x0 + 6, y0 + 6, zz + 20), Z, 3.5, 3, n=16)
        arm_ = box(x0 + 1, x0 + 17, y0 + 4.5, y0 + 7.5, zz + 23, zz + 24.5, tone=1)
        for x in (x0 + 3, x0 + 9, x0 + 15):
            arm_.dot((x, y0 + 6, zz + 24.5), .45, Z)
        body.line([(x0 + 22, y0 + 2, zz + 4), (x0 + 22, y0 + 10, zz + 4)], X, 'fn')
        parts += [body, ears, horn, arm_]

    # the 6-DoF arm, folded: turntable, shoulder, upper arm, forearm, wrist, gripper
    bx, by = 44, 0
    parts.append(cyl((bx, by, zt), Z, 15, 6))
    parts.append(cyl((bx, by, zt + 6), Z, 11, 5))
    sh = (bx, by, zt + 18)
    yoke_l = box(bx - 7, bx + 7, by - 11, by - 7, zt + 11, zt + 24)
    parts.append(yoke_l)
    parts.append(cyl((bx, by - 7, zt + 18), (0, 1, 0), 6, 14))
    yoke_r = box(bx - 7, bx + 7, by + 7, by + 11, zt + 11, zt + 24)
    parts.append(yoke_r)

    def link(a, b, half_w, half_h, tone=0):
        """A rectangular link from joint a to joint b, in the x-z plane."""
        d = norm(sub(b, a))
        nz = norm(cross(d, Y))
        prof = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
        return prism(prof, a, Y, nz, d, dist(a, b), tone=tone)

    el = add(sh, (16, 0, 34))
    wr = add(el, (30, 0, -10))
    parts.append(link(sh, el, 4.5, 3.2))
    parts.append(cyl(add(el, (0, -6, 0)), (0, 1, 0), 5, 12))
    parts.append(link(el, wr, 3.8, 2.8))
    parts.append(cyl(add(wr, (0, -5, 0)), (0, 1, 0), 4.2, 10))
    roll = cyl(add(wr, (3, 0, 0)), (1, 0, 0), 3.4, 7)
    parts.append(roll)
    g0 = add(wr, (10, 0, 0))
    palm = box(g0[0], g0[0] + 4, g0[1] - 7, g0[1] + 7, g0[2] - 4, g0[2] + 4)
    parts.append(palm)
    for s in (-1, 1):
        f = box(g0[0] + 4, g0[0] + 15, g0[1] + s * 4.5 - 1.5, g0[1] + s * 4.5 + 1.5, g0[2] - 3, g0[2] + 3, tone=1)
        parts.append(f)
    return parts


def mast(z):
    parts = []
    post = box(-48, -40, 14, 22, z, z + 46)
    for zz in range(int(z) + 6, int(z) + 46, 8):
        post.dot((-40, 18, zz), .6, X)
    parts.append(post)
    # camera on the post's front: body, lens barrel, glass
    cam = box(-40, -26, 9, 27, z + 26, z + 40)
    cam.line([(-40, 27, z + 37), (-26, 27, z + 37)], Y, 'fn')
    parts.append(cam)
    lens = cyl((-26, 18, z + 33), X, 5.5, 7)
    lens.ring(lens.axis[1], Y, Z, 3.6, X, fill='t4')
    lens.ring(lens.axis[1], Y, Z, 1.2, X)
    parts.append(lens)
    plate = box(-50, -38, 12, 24, z + 46, z + 48, tone=1)
    parts.append(plate)
    return parts


def lidar(z):
    parts = []
    base = cyl((-44, 18, z), Z, 13, 7)
    win = cyl((-44, 18, z + 7), Z, 12, 8, tone=2)
    capc = cyl((-44, 18, z + 15), Z, 13, 5)
    capc.ring(capc.axis[1], X, Y, 5, Z)
    capc.dot(capc.axis[1], .9, Z)
    parts += [base, win, capc]
    return parts


# The layers in assembled order: (name, local z, builder, explode index).
# The deck heights are set so each layer sits wholly above the one before.
def layers():
    zc = HULL['z1']                       # the compute deck sits on the rim
    zt = zc + 3 + 27                      # the top deck on the tall standoffs
    zm = zt + 3                           # the mast stands on the top deck
    zl = zm + 48                          # the LiDAR on the mast's plate
    return [
        ('chassis', chassis(), 0),
        ('drive', drive(HULL['z0'] + 3), 1),
        ('compute', compute(zc), 2),
        ('top', top(zt) + mast(zm), 3),
        ('lidar', lidar(zl), 4),
    ]


# Balloons: (item number, layer index, anchor point in assembled world space, side)
def balloons():
    zc = HULL['z1']
    zt = zc + 30
    zm = zt + 3
    zl = zm + 48
    return [
        (1, 0, (40, 50, 32), 'r'),         # tracked chassis
        (2, 1, (-60, 28, 20), 'l'),        # drive motors and ESCs
        (3, 3, (-1, 22, zt + 13), 'l'),    # servos
        (4, 3, (70, 0, zt + 40), 'r'),     # 6-DoF arm
        (5, 2, (-40, -1, zc + 21), 'l'),   # Jetson Orin
        (6, 2, (20, -17, zc + 8), 'r'),    # Raspberry Pi 5
        (7, 2, (20, 15, zc + 8), 'l'),     # ESP32
        (8, 2, (60, -2, zc + 8), 'r'),     # Arduino
        (9, 3, (-26, 18, zm + 33), 'l'),   # camera
        (10, 4, (-44, 30, zl + 11), 'l'),  # 3D LiDAR
        (11, 3, (-22, -22, zt + 4), 'r'),  # IMU
        (12, 3, (-52, -18, zt + 7), 'r'),  # GNSS
    ]


def assembly_lines():
    """Dash-dot lines between mating points: (lower layer, point, upper layer, point)."""
    zc = HULL['z1']
    zt = zc + 30
    zm = zt + 3
    zl = zm + 48
    out = []
    for (x, y) in ((-66, -32), (66, -32), (66, 32), (-66, 32)):
        out.append((0, (x, y, zc), 2, (x, y, zc)))          # compute deck onto the rim
        out.append((2, (x, y, zt), 3, (x, y, zt)))          # top deck onto the tall standoffs
    out.append((3, (-44, 18, zl), 4, (-44, 18, zl)))        # LiDAR onto the mast
    for y in (-22, 22):
        out.append((0, (-60, y, HULL['z0'] + 3), 1, (-60, y, HULL['z0'] + 4)))  # motors into the tub
    return out


BOM = [
    ('1', 'Tracked chassis', 'demining rover'),
    ('2', 'Motors + ESCs', 'drive'),
    ('3', 'Servos', 'two-axis'),
    ('4', '6-DoF arm', 'inverse kinematics'),
    ('5', 'Jetson Orin', 'edge inference'),
    ('6', 'Raspberry Pi 5', 'edge deployment'),
    ('7', 'ESP32', 'closed loop'),
    ('8', 'Arduino', 'PID'),
    ('9', 'Camera', 'computer vision'),
    ('10', '3D LiDAR', 'SLAM'),
    ('11', 'IMU', 'sensor fusion'),
    ('12', 'GNSS', 'outdoor navigation'),
]
SOFTWARE = [
    ('13', 'ROS 2 · Nav2', '3D LiDAR SLAM'),
    ('14', 'OpenCV', 'homography · RANSAC'),
    ('15', 'MediaPipe', 'sign language'),
    ('16', 'PX4', 'SITL · EKF2'),
    ('17', 'Betaflight', 'PID tuning'),
    ('18', 'C · C++ · Python', 'all of it'),
]


# ── the sheet ───────────────────────────────────────────────────────────────
def mix(a, b, k):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x + (y - x) * k):02x}' for x, y in zip(a, b))


def pen_vars(theme, pen):
    """CSS custom properties for one pen's copy of the drawing."""
    if theme == 'light':
        base, ks = '#ffffff', (0, .05, .13, .24, .38)
    else:
        base, ks = '#000000', (0, .045, .085, .14, .21)
    v = {f'--t{i}': mix(base, pen, k) for i, k in enumerate(ks)}
    v['--pen'] = pen
    return ';'.join(f'{k}:{x}' for k, x in v.items())


def text(x, y, s, size, cls='tx', anchor='start', weight=None, track=0):
    w = len(s) * size * ADVANCE + max(0, len(s) - 1) * track
    wt = f' font-weight="{weight}"' if weight else ''
    return (f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{size}"{wt} text-anchor="{anchor}" '
            f'textLength="{w:.1f}" lengthAdjust="spacingAndGlyphs">{esc(s)}</text>')


def assembly(area, size, balloon_x=None):
    """
    The exploded robot fitted into `area` (x, y, w, h) on a sheet of `size`
    (w, h): its layers in painter's order with their assembly lines, then its
    balloons. `balloon_x(left, right)` picks the two balloon columns from the
    robot's drawn left and right edges. Returns the drawing, how far each
    layer drops to close, the hull clip and the layers.
    """
    W, H = size
    L = layers()
    B = balloons()

    # fit the exploded assembly into the drawing area
    pts = []
    for name, parts, i in L:
        for s in parts:
            for p in s.verts:
                pts.append(project(add(p, (0, 0, OFFSET[i]))))
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    k = min(area[2] / (x1 - x0), area[3] / (y1 - y0))
    ox = area[0] + (area[2] - (x1 - x0) * k) / 2 - x0 * k
    oy = area[1] + (area[3] - (y1 - y0) * k) / 2 - y0 * k

    def P_for(i):
        def P(p):
            q = project(add(p, (0, 0, OFFSET[i])))
            return (ox + q[0] * k, oy + q[1] * k)
        return P

    drop = {i: OFFSET[i] * CE * k for _, _, i in L}   # px each layer travels to close

    # the hull's near walls, which hide the drive once it is inside
    h = HULL
    P0 = P_for(0)
    near = [P0((h['x1'], h['y0'], h['z1'])), P0((h['x1'], h['y1'], h['z1'])),
            P0((h['x0'], h['y1'], h['z1'])), P0((h['x0'], h['y1'], h['z0'])),
            P0((h['x1'], h['y1'], h['z0'])), P0((h['x1'], h['y0'], h['z0']))]
    clip = (f'<clipPath id="tub" clipPathUnits="userSpaceOnUse"><path clip-rule="evenodd" '
            f'd="M-10,-10H{W + 10}V{H + 10}H-10Z {path_of(near)}"/></clipPath>')

    body = []
    for name, parts, i in L:
        P = P_for(i)
        parts = paint_order(parts, P)
        inner = ''.join(render(s, P) for s in parts)
        g_ = f'<g class="L{i}">{inner}</g>'
        if name == 'drive':
            g_ = f'<g clip-path="url(#tub)">{g_}</g>'
        body.append(g_)
        lines = [(lo, a, hi, b) for lo, a, hi, b in assembly_lines() if lo == i]
        if lines:
            d = ''.join(f'M{fmt(P_for(hi)(b))}L{fmt(P_for(lo)(a))}' for lo, a, hi, b in lines)
            body.append(f'<g class="bal"><path class="cl" d="{d}"/></g>')

    # balloons, drawn last; each rides with its layer and fades as it closes
    if balloon_x:
        left_x, right_x = balloon_x(ox + x0 * k, ox + x1 * k)
    else:
        left_x, right_x = max(28, ox + x0 * k - 40), min(612, ox + x1 * k + 40)
    rows = {'l': [], 'r': []}
    for n, i, a, side in B:
        q = P_for(i)(a)
        rows[side].append((q[1], n, i, q))
    balls = {i: [] for _, _, i in L}
    for side, items in rows.items():
        items.sort()
        # spread balloons so they never touch
        ys = []
        for y, *_ in items:
            y = max(y, (ys[-1] + 24) if ys else y)
            ys.append(y)
        for (y_a, n, i, q), yb in zip(items, ys):
            bx = left_x if side == 'l' else right_x
            ex = bx + (11 if side == 'l' else -11)
            balls[i].append(
                f'<path class="ln" d="M{q[0]:.1f},{q[1]:.1f}L{ex + (14 if side == "l" else -14):.1f},{yb:.1f}H{ex:.1f}"/>'
                f'<circle class="dt" cx="{q[0]:.1f}" cy="{q[1]:.1f}" r="1.4"/>'
                f'<circle class="bl t0" cx="{bx}" cy="{yb:.1f}" r="11"/>'
                + text(bx, yb + 4.2, str(n), 12, anchor='middle', weight=700))
    for i, items in balls.items():
        if items:
            body.append(f'<g class="L{i}"><g class="bal">{"".join(items)}</g></g>')
    return body, drop, clip, L


def build(theme):
    body, drop, clip, L = assembly((74, 34, 560, HEIGHT - 34 - 52), (WIDTH, HEIGHT))

    # the bill of materials
    bx, by, bw = 642, 46, WIDTH - 642 - 26
    bom = [f'<path class="ln" d="M{bx},{by}H{bx + bw}"/>',
           text(bx, by - 10, 'BILL OF MATERIALS', 12, 'tx', weight=700, track=1.5),
           text(bx + bw, by - 10, 'QTY 1 EACH', 10, 'tx dim', 'end')]
    cols = (bx + 2, bx + 32, bx + 160)
    hy = by + 18
    for c, s in zip(cols, ('ITEM', 'PART', 'ROLE')):
        bom.append(text(c, hy, s, 9, 'tx dim', track=1))
    bom.append(f'<path class="fn" d="M{bx},{hy + 7}H{bx + bw}"/>')
    y = hy + 24
    for group, title in ((BOM, None), (SOFTWARE, 'FIRMWARE · SOFTWARE')):
        if title:
            y += 6
            bom.append(text(bx + 2, y, title, 9, 'tx dim', track=1))
            bom.append(f'<path class="fn" d="M{bx},{y + 7}H{bx + bw}"/>')
            y += 24
        for item, part, role in group:
            bom.append(text(cols[0] + 6, y, item, 11, 'tx', 'middle', weight=700))
            bom.append(text(cols[1], y, part, 12, 'tx', weight=700))
            bom.append(text(cols[2], y, role, 11, 'tx dim'))
            y += 19
    bom.append(f'<path class="ln" d="M{bx},{y - 8}H{bx + bw}"/>')
    # title block
    ty = HEIGHT - 70
    bom.append(f'<path class="ln" d="M{bx},{ty}H{bx + bw}V{HEIGHT - 26}H{bx}Z M{bx},{ty + 22}H{bx + bw} M{bx + 150},{ty + 22}V{HEIGHT - 26}"/>')
    bom.append(text(bx + 8, ty + 15, 'GENERAL ASSEMBLY · EXPLODED', 11, 'tx', weight=700, track=.5))
    bom.append(text(bx + 8, ty + 37, 'DWG 03 · SCALE NTS', 9, 'tx dim', track=.5))
    bom.append(text(bx + 158, ty + 37, 'R. KRONBII · REV 3', 9, 'tx dim', track=.5))

    note = [text(74, HEIGHT - 22, 'Not one robot: the parts I keep reaching for, across my projects.', 12, 'tx dim')]

    drawing = ''.join(body) + ''.join(bom) + ''.join(note)
    return sheet(theme, WIDTH, HEIGHT, drawing, drop, clip, L, rx=15)


LABEL = ('What I build with, as an exploded assembly drawing of a composite robot: a tracked chassis, '
         'motors and ESCs, servos, a 6-DoF arm, a Jetson Orin, a Raspberry Pi 5, an ESP32, an Arduino, '
         'a camera, a 3D LiDAR, an IMU and GNSS, with ROS 2 and Nav2, OpenCV, MediaPipe, PX4 and '
         'Betaflight, in C, C++ and Python.')


def sheet(theme, W, H, drawing, drop, clip, L, rx, size=None, shift=('.75', '.2')):
    """
    The drawing on its sheet, plotted twice by the two pens, with the layers'
    close-and-open timing. `size` is the SVG's width and height attributes when
    they differ from its viewBox (the phone copy is drawn at twice its units);
    `shift` is how far out of register the two pens print, x and y.
    """
    t = SAGE[theme]
    m, g = t['fringe'][1], t['fringe'][0]
    # timing: rest open, close, rest closed, open again -- 15 s, 24 beats at 96 BPM
    keys = []
    for _, _, i in L:
        if not i:
            continue
        keys.append(f'@keyframes c{i} {{ 0%, 34% {{ transform: none; animation-timing-function: cubic-bezier(.55,0,.3,1); }} '
                    f'{50 + i}% {{ transform: translateY({drop[i]:.1f}px); }} '
                    f'{78 + i}% {{ transform: translateY({drop[i]:.1f}px); animation-timing-function: cubic-bezier(.55,0,.3,1); }} '
                    f'{94 + i * .5:.1f}%, 100% {{ transform: none; }} }}')
        keys.append(f'.L{i} {{ animation: c{i} 15s infinite; }}')

    if theme == 'light':
        blend, paper = 'multiply', t['bg']
    else:
        blend, paper = 'screen', t['bg']
    sw, sh = size or (W, H)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{sw}" height="{sh}" viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" aria-label="{esc(LABEL)}">
<style>
text {{ white-space: pre; }}
.t0 {{ fill: var(--t0); }} .t1 {{ fill: var(--t1); }} .t2 {{ fill: var(--t2); }}
.t3 {{ fill: var(--t3); }} .t4 {{ fill: var(--t4); }}
.ln {{ fill: none; stroke: var(--pen); stroke-width: 1.1; stroke-linejoin: round; stroke-linecap: round; }}
.fn {{ fill: none; stroke: var(--pen); stroke-width: .6; stroke-linecap: round; opacity: .8; }}
.dt {{ fill: var(--pen); }}
.cl {{ fill: none; stroke: var(--pen); stroke-width: .7; stroke-dasharray: 9 3 1.5 3; opacity: .7; }}
.bl {{ stroke: var(--pen); stroke-width: 1.1; }}
.tx {{ fill: var(--pen); }}
.dim {{ opacity: .62; }}
.pen {{ mix-blend-mode: {blend}; }}
.pm {{ transform: translate(-{shift[0]}px, -{shift[1]}px); }}
.pg {{ transform: translate({shift[0]}px, {shift[1]}px); }}
{chr(10).join(keys)}
.bal {{ animation: bal 15s infinite; }}
@keyframes bal {{ 0%, 28% {{ opacity: 1; }} 36%, 88% {{ opacity: 0; }} 96%, 100% {{ opacity: 1; }} }}
@media (prefers-reduced-motion: reduce) {{ .L1, .L2, .L3, .L4, .bal {{ animation: none; }} }}
</style>
<defs>{clip}<g id="dwg">{drawing}</g></defs>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="{rx}" fill="{paper}" stroke="{t['edge']}"/>
<use href="#dwg" class="pen pm" style="{pen_vars(theme, m)}"/>
<use href="#dwg" class="pen pg" style="{pen_vars(theme, g)}"/>
</svg>
"""


# ── the phone sheet ─────────────────────────────────────────────────────────
# The README shows this copy when the screen is 640 px wide or less: the same
# assembly, now full width on top with its balloons either side, and the bill
# of materials as a list underneath. 320 units wide, drawn at twice that, so on
# a 375 px phone (a 293 px README column) one unit is about 0.92 px.
PHONE_W = 320
PAD = 12
ROW = 16


def wrap(s, cols):
    lines, line = [], ''
    for word in s.split():
        if line and len(line) + 1 + len(word) > cols:
            lines.append(line)
            line = word
        else:
            line = f'{line} {word}'.strip()
    return lines + [line]


def build_phone(theme):
    robot = (60, 14, 200, 269)
    body, drop, clip, L = assembly(robot, (PHONE_W, 2000), balloon_x=lambda left, right: (PAD + 14, PHONE_W - PAD - 14))
    bx, bw = PAD, PHONE_W - 2 * PAD
    by = robot[1] + robot[3] + 26
    bom = [text(bx, by - 9, 'BILL OF MATERIALS', 12, 'tx', weight=700, track=1.5),
           text(bx + bw, by - 9, 'QTY 1 EACH', 11, 'tx dim', 'end'),
           f'<path class="ln" d="M{bx},{by}H{bx + bw}"/>']
    cols = (bx + 12, bx + 34, bx + 158)        # item (centred), part, role
    y = by + 19
    for group, title in ((BOM, None), (SOFTWARE, 'FIRMWARE · SOFTWARE')):
        if title:
            y += 3
            bom.append(text(bx, y, title, 11, 'tx dim', track=1))
            bom.append(f'<path class="fn" d="M{bx},{y + 6}H{bx + bw}"/>')
            y += 21
        for item, part, role in group:
            bom.append(text(cols[0], y, item, 11, 'tx', 'middle', weight=700))
            bom.append(text(cols[1], y, part, 12, 'tx', weight=700))
            bom.append(text(cols[2], y, role, 11, 'tx dim'))
            y += ROW
    bom.append(f'<path class="ln" d="M{bx},{y - 9}H{bx + bw}"/>')
    y += 10
    for line in wrap('Not one robot: the parts I keep reaching for, across my projects.', int(bw / (12 * ADVANCE))):
        bom.append(text(bx, y, line, 12, 'tx dim'))
        y += 16
    H = round(y - 16 + PAD + 2)
    return sheet(theme, PHONE_W, H, ''.join(body) + ''.join(bom), drop,
                 clip.replace('V2010H', f'V{H + 10}H'), L, rx=12, size=(2 * PHONE_W, 2 * H),
                 shift=('.4', '.1'))      # small type stays crisp: the pens sit closer


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for theme in SAGE:
        svg = build(theme)
        with open(OUT.format(theme), 'w', encoding='utf-8') as f:
            f.write(svg)
        print(f'wrote {OUT.format(theme)} ({len(svg) / 1024:.1f} KB)')
        svg = build_phone(theme)
        with open(OUT.format(f'phone-{theme}'), 'w', encoding='utf-8') as f:
            f.write(svg)
        print(f'wrote {OUT.format(f"phone-{theme}")} ({len(svg) / 1024:.1f} KB)')


if __name__ == '__main__':
    main()

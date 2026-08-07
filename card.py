"""
Builds light_mode.svg and dark_mode.svg from profile.toml.

    python card.py

The card is a strict 60-character monospace grid (Andrew6rant's design), so the
leader dots on every line have to land on the same column. Counting them by hand
is miserable; this does it, and refuses to write a card whose lines don't line up.

today.py rewrites the live numbers on every scheduled run, reflowing the dots to
keep each line the width it was authored with -- so nothing here has to be kept
in sync with that file.
"""
import os
import sys
import tomllib
from lxml import etree

CONFIG = 'profile.toml'

# ── layout (changing these means re-checking the grid) ──────────────────────
WIDTH, HEIGHT = 985, 530
LINE = 60                               # visible characters per info line
ART_X, INFO_X = 15, 390
TOP, STEP = 30, 20                      # first baseline, info line height
INFO_SIZE = 16                          # px; the art panel has its own size


def art_grid(size):
    """
    (cols, rows, cell_w, line_h) for an art panel rendered at `size` px.

    Shared with asciify.py so the two agree on the grid without a constant to
    keep in sync. At size 16 this reproduces Andrew's original 38x25 panel.
    """
    cell_w = size * 0.55 * 1.09         # Consolas advance at size-adjust 109%
    line_h = size * 1.25
    avail_w = INFO_X - ART_X - 10       # leave a gutter before the info column
    avail_h = HEIGHT - TOP - 20
    return int(avail_w // cell_w), int(avail_h // line_h) + 1, cell_w, line_h

THEMES = {
    'light_mode.svg': dict(bg='#f6f8fa', fg='#24292f', key='#953800', value='#0a3069',
                           add='#1a7f37', dele='#cf222e', cc='#c2cfde'),
    'dark_mode.svg':  dict(bg='#161b22', fg='#c9d1d9', key='#ffa657', value='#a5d6ff',
                           add='#3fb950', dele='#f85149', cc='#616e7f'),
}

# id -> the {placeholder} name in profile.toml. Every id here is one today.py
# rewrites; ids ending in _dots are generated alongside.
DYNAMIC = {'age': 'age_data', 'repos': 'repo_data', 'contrib': 'contrib_data',
           'stars': 'star_data', 'commits': 'commit_data', 'followers': 'follower_data',
           'loc': 'loc_data', 'loc_add': 'loc_add', 'loc_del': 'loc_del'}


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def dots(width):
    """A leader occupying exactly `width` characters, phrased as today.py does."""
    if width < 0:
        raise ValueError('negative leader')
    return {0: '', 1: ' ', 2: '. '}[width] if width <= 2 else ' ' + '.' * (width - 2) + ' '


# A chunk is (css_class, text, element_id). Only the first chunk of a line
# carries the x/y that starts the row; the rest flow after it.
def key_chunks(key):
    """'Languages.Real' -> two highlighted words with a plain dot between."""
    out = []
    for i, part in enumerate(key.split('.')):
        if i:
            out.append((None, '.', None))
        out.append(('key', part, None))
    return out


def field(key, value, eid=None):
    """A '. Key: ..... value' row, padded to exactly LINE characters."""
    gap = LINE - 2 - len(key) - 1 - len(value)
    if gap < 0:
        raise ValueError(f'"{key}: {value}" is {-gap} characters too long for the card')
    return ([('cc', '. ', None)] + key_chunks(key) + [(None, ':', None),
            ('cc', dots(gap), f'{eid}_dots' if eid else None),
            ('value', value, eid)])


def rule(label):
    """A '- Label -———…' divider, padded to exactly LINE characters."""
    if len(label) + 5 > LINE:
        raise ValueError(f'section rule "{label}" is too long for the card')
    return [(None, label, None), (None, ' -' + '—' * (LINE - len(label) - 5) + '-—-', None)]


def stat_line(kind, labels, ph):
    """One of the three composite GitHub stats rows."""
    def val(name):
        return ('value', ph[name], DYNAMIC[name])

    if kind == 'repos':
        a, b, c = (labels + ['Repos', 'Contributed', 'Stars'][len(labels):])[:3]
        fixed = 2 + len(a) + 1 + len(ph['repos']) + 2 + len(b) + 2 + \
            len(ph['contrib']) + 4 + len(c) + 1 + len(ph['stars'])
        slack = LINE - fixed
        if slack < 0:
            raise ValueError(f'the {kind} line is {-slack} characters too long')
        # split the slack between the two leaders, favouring the right-hand one
        left = min(6, slack)
        return ([('cc', '. ', None)] + key_chunks(a) + [(None, ':', None),
                ('cc', dots(left), 'repo_data_dots'), val('repos'), (None, ' {', None)] +
                key_chunks(b) + [(None, ': ', None), val('contrib'), (None, '} | ', None)] +
                key_chunks(c) + [(None, ':', None),
                ('cc', dots(slack - left), 'star_data_dots'), val('stars')])

    if kind == 'commits':
        a, b = (labels + ['Commits', 'Followers'][len(labels):])[:2]
        fixed = 2 + len(a) + 1 + len(ph['commits']) + 3 + len(b) + 1 + len(ph['followers'])
        slack = LINE - fixed
        if slack < 0:
            raise ValueError(f'the {kind} line is {-slack} characters too long')
        right = min(10, slack)
        return ([('cc', '. ', None)] + key_chunks(a) + [(None, ':', None),
                ('cc', dots(slack - right), 'commit_data_dots'), val('commits'),
                (None, ' | ', None)] + key_chunks(b) + [(None, ':', None),
                ('cc', dots(right), 'follower_data_dots'), val('followers')])

    if kind == 'loc':
        a = (labels or ['Lines of Code on GitHub'])[0]
        fixed = 2 + len(a) + 1 + len(ph['loc']) + 3 + len(ph['loc_add']) + 2 + 2 + \
            len(ph['loc_del']) + 2 + 2
        slack = LINE - fixed
        if slack < 0:
            raise ValueError(f'the {kind} line is {-slack} characters too long')
        # the del leader gets 1 char if we can spare it; the rest goes to loc
        right = min(1, slack)
        return ([('cc', '. ', None)] + key_chunks(a) + [(None, ':', None),
                ('cc', dots(slack - right), 'loc_data_dots'), val('loc'),
                (None, ' ( ', None), ('addColor', ph['loc_add'], 'loc_add'),
                ('addColor', '++', None), (None, ', ', None),
                (None, dots(right), 'loc_del_dots'),
                ('delColor', ph['loc_del'], 'loc_del'), ('delColor', '--', None),
                (None, ' )', None)])

    raise ValueError(f'unknown stats line "{kind}" -- expected repos, commits or loc')


def rows_from(cfg):
    """profile.toml rows -> (chunks, is_spacer) in order."""
    ph = cfg.get('placeholders', {})
    out = [(rule(cfg['user']), False)]
    for i, row in enumerate(cfg['rows'], start=1):
        try:
            if row.get('blank'):
                out.append(([('cc', '. ', None)], False))
            elif 'rule' in row:
                out.append((None, True))            # blank row before a divider
                out.append((rule('- ' + row['rule']), False))
            elif 'stats' in row:
                out.append((stat_line(row['stats'], row.get('labels', []), ph), False))
            elif 'key' in row:
                value = row['value']
                eid = None
                if value.startswith('{') and value.endswith('}'):
                    name = value[1:-1]
                    if name not in DYNAMIC:
                        raise ValueError(f'unknown placeholder {value} -- expected one of '
                                         f'{", ".join("{%s}" % k for k in DYNAMIC)}')
                    value, eid = ph.get(name, name), DYNAMIC[name]
                out.append((field(row['key'], value, eid), False))
            else:
                raise ValueError('row needs one of: key, blank, rule, stats')
        except ValueError as e:
            raise SystemExit(f'{CONFIG}: row {i} ({row}): {e}')
    return out


def render(chunks, y):
    out = []
    for i, (cls, text, eid) in enumerate(chunks):
        attrs = f' x="{INFO_X}" y="{y}"' if i == 0 else ''
        if cls:
            attrs += f' class="{cls}"'
        if eid:
            attrs += f' id="{eid}"'
        out.append(f'<tspan{attrs}>{esc(text)}</tspan>' if attrs else esc(text))
    return ''.join(out)


def art_lines(path, cols, rows):
    """The ASCII panel, clipped to `cols` and padded to `rows`."""
    try:
        with open(path, encoding='utf-8') as f:
            lines = [line[:cols].rstrip() for line in f.read().split('\n')][:rows]
    except FileNotFoundError:
        raise SystemExit(f'{path} does not exist yet -- run: python asciify.py')

    # The art is generated, not read from the config, so editing [art] here has
    # no effect until asciify.py runs again. That looks exactly like the setting
    # being broken, so say so rather than quietly rendering the old panel.
    if os.path.getmtime(CONFIG) > os.path.getmtime(path):
        print(f'  warning: {CONFIG} is newer than {path}, so [art] changes are NOT '
              f'in this card.\n           run: python asciify.py && python card.py')
    return lines + [''] * (rows - len(lines))


def build(cfg, theme):
    body, y = [], TOP
    for chunks, spacer in rows_from(cfg):
        if spacer:
            y += STEP
            continue
        width = sum(len(t) for _, t, _ in chunks)
        if width not in (LINE, 2):          # 2 == a bare '. ' spacer row
            raise SystemExit(f'internal error: line at y={y} is {width} chars, not {LINE}')
        body.append(render(chunks, y))
        y += STEP
    if y - STEP > HEIGHT - 20:
        raise SystemExit(f'{CONFIG}: too many rows -- the last line falls off the {HEIGHT}px card')

    art_cfg = cfg.get('art', {})
    size = art_cfg.get('size', INFO_SIZE)
    cols, rows, _, line_h = art_grid(size)
    art = '\n'.join(f'<tspan x="{ART_X}" y="{TOP + line_h * i:g}">{esc(line)}</tspan>'
                    for i, line in enumerate(
                        art_lines(art_cfg.get('file', 'cache/art.txt'), cols, rows)))

    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="{WIDTH}px" height="{HEIGHT}px" font-size="{INFO_SIZE}px">
<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {theme['key']};}}
.value {{fill: {theme['value']};}}
.addColor {{fill: {theme['add']};}}
.delColor {{fill: {theme['dele']};}}
.cc {{fill: {theme['cc']};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="{WIDTH}px" height="{HEIGHT}px" fill="{theme['bg']}" rx="15"/>
<text x="{ART_X}" y="{TOP}" fill="{theme['fg']}" class="ascii" font-size="{size}px">
{art}
</text>
<text x="{INFO_X}" y="{TOP}" fill="{theme['fg']}">
{chr(10).join(body)}
</text>
</svg>
"""


if __name__ == '__main__':
    try:
        with open(CONFIG, 'rb') as f:
            cfg = tomllib.load(f)
    except FileNotFoundError:
        raise SystemExit(f'{CONFIG} not found -- run this from the repository root')
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f'{CONFIG} is not valid TOML: {e}')

    for filename, theme in THEMES.items():
        svg = build(cfg, theme)
        etree.fromstring(svg.encode())      # fail here rather than in the workflow
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(svg)
        print(f'wrote {filename}')

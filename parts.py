"""
Draws the pieces of the README around the card, in the card's palette.

    python parts.py

From the [readme] table in profile.toml it writes, for light and dark:

    assets/parts/headline-<theme>.svg         the bold line under the card
    assets/parts/section-<name>-<theme>.svg   a header per section
    assets/parts/work-<org>-<theme>.svg       a card per employer
    assets/parts/link-<name>-<theme>.svg      a pill per link

and rewrites the pill row and the employer cards in README.md, between the
links and work markers. Section
headers are referenced from README.md by hand, since each one sits above
content written there.

Text in an SVG shown as an <img> can't load web fonts and falls back to the
viewer's monospace, whose width varies. Every label is therefore stretched to
a fixed width with textLength, so pills and rules fit whatever font turns up.
"""
import os
import re
import tomllib

from card import CONFIG, SAGE, WIDTH, esc

OUT = 'assets/parts'
README = 'README.md'
LINKS_START, LINKS_END = '<!-- links:start -->', '<!-- links:end -->'
WORK_START, WORK_END = '<!-- work:start -->', '<!-- work:end -->'
FONT = 'ConsolasFallback,Consolas,Menlo,monospace'
ADVANCE = 0.6               # monospace advance as a fraction of the font size


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def fringe_text(x, y, text, size, fill, t, length, anchor='start'):
    """A label with the green/magenta fringe offset either side of it."""
    common = (f'x="{x:g}" y="{y:g}" font-size="{size}" textLength="{length:g}" '
              f'lengthAdjust="spacingAndGlyphs" text-anchor="{anchor}"')
    m, g = t['fringe'][1], t['fringe'][0]
    return (f'<g style="mix-blend-mode:{t["blend"]}" opacity=".85">'
            f'<text {common} fill="{m}" transform="translate(-.8 0)">{esc(text)}</text>'
            f'<text {common} fill="{g}" transform="translate(.8 0)">{esc(text)}</text></g>'
            f'<text {common} fill="{fill}">{esc(text)}</text>')


def section_svg(label, t):
    """A '- Label -———' rule the width of the card, like its own dividers."""
    size, h, y = 20, 48, 32
    dash_w = 2 * size * ADVANCE
    label_w = len(label) * size * ADVANCE
    x0 = 15
    x_label = x0 + dash_w
    x_line = x_label + label_w + size * ADVANCE
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{h}" viewBox="0 0 {WIDTH} {h}" font-family="{FONT}" role="img" aria-label="{esc(label)}">
<text x="{x0}" y="{y}" font-size="{size}" fill="{t['cc']}" textLength="{dash_w * .5:g}">-</text>
{fringe_text(x_label, y, label, size, t['key'], t, label_w)}
<line x1="{x_line:g}" y1="{y - size * .32:g}" x2="{WIDTH - 15}" y2="{y - size * .32:g}" stroke="{t['cc']}" stroke-width="1.5"/>
</svg>
"""


# The headline's last word is drawn as a crowd of dots rather than as text, so
# its glyphs come from this font, not from whatever the viewer falls back to.
# DejaVu Sans Mono is what Menlo was cut from, so it sits well beside the
# monospace the rest of the line falls back to on most machines.
CROWD_FONTS = ('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
               '/Library/Fonts/DejaVuSansMono-Bold.ttf', 'DejaVuSansMono-Bold.ttf')


def crowd(word, size, pitch):
    """
    Dots that draw `word`, as (x, y, r) from the start of its baseline: the
    glyphs are rendered four times over, sampled on a staggered grid, and each
    dot is sized by how much of its cell the letter covers.
    """
    from PIL import Image, ImageDraw, ImageFont
    for path in CROWD_FONTS:
        try:
            font = ImageFont.truetype(path, size * 4)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f'parts.py: none of {CROWD_FONTS} is installed; the headline needs one')
    left, top, right, bottom = font.getbbox(word, anchor='ls')
    pad = 8 * 4
    img = Image.new('L', (right - left + 2 * pad, bottom - top + 2 * pad), 0)
    ox, oy = pad - left, pad - top                  # the baseline origin, in pixels
    ImageDraw.Draw(img).text((ox, oy), word, font=font, fill=255, anchor='ls')
    px = img.load()
    cell = pitch * 4
    dots = []
    row = 0
    y = cell / 2
    while y < img.height:
        x = cell / 2 + (cell / 2 if row % 2 else 0)
        while x < img.width:
            x0, y0 = int(x - cell / 2), int(y - cell / 2)
            total = n = 0
            for yy in range(max(0, y0), min(img.height, int(y0 + cell))):
                for xx in range(max(0, x0), min(img.width, int(x0 + cell))):
                    total += px[xx, yy]
                    n += 1
            cover = total / (255 * n) if n else 0
            if cover > .22:
                dots.append(((x - ox) / 4, (y - oy) / 4, pitch * .5 * cover ** .5))
            x += cell
        y += cell * .866                            # rows of a hexagonal packing
        row += 1
    return dots, font.getlength(word) / 4


def headline_svg(headline, subline, t):
    """
    The bold line under the card. Its last word arrives as a crowd: a few
    hundred dots, scattered across the band when the image loads, walk in and
    settle into the letters -- society, made of people. Then the green and
    magenta fringe racks in around it and slowly breathes, the way
    ramikronbi.com treats one word of a heading.

    Every dot rests at its place in the word, and the animation only says
    where it starts from, so reduced motion (or no CSS at all) shows the word.
    """
    import random
    lead, _, word = headline.rpartition(' ')
    lead = lead + ' ' if lead else ''
    h, size, base = 132, 54, 70
    m, g = t['fringe'][1], t['fringe'][0]
    dots, word_w = crowd(word, size, 3.1)
    lead_w = len(lead) * size * ADVANCE
    x0 = (WIDTH - lead_w - word_w) / 2
    wx = x0 + lead_w
    rnd = random.Random(word)                       # the same crowd every build
    circles = []
    for x, y, r in dots:
        tx, ty = wx + x, base + y
        sx, sy = rnd.uniform(24, WIDTH - 24), rnd.uniform(10, h - 10)
        delay = .35 + rnd.uniform(0, .75) + .5 * (x / word_w)
        circles.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{r:.2f}" '
                       f'style="--x:{sx - tx:.0f}px;--y:{sy - ty:.0f}px;animation-delay:{delay:.2f}s"/>')
    settle = 2.0 + .35 + .75 + .5                   # the last dot lands
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{h}" viewBox="0 0 {WIDTH} {h}" font-family="{FONT}" role="img" aria-label="{esc(headline)}. {esc(subline)}">
<style>
text {{ white-space: pre; }}
.crowd circle {{ animation: walk 2s cubic-bezier(.2,.75,.25,1) both; }}
@keyframes walk {{ from {{ transform: translate(var(--x), var(--y)); opacity: .35; }} to {{ transform: none; opacity: 1; }} }}
.fringe {{ mix-blend-mode: {t['blend']}; }}
.fm {{ transform: translateX(-.6px); animation: fin {settle:.2f}s both, fm 9s ease-in-out {settle:.2f}s infinite; }}
.fg {{ transform: translateX(.6px); animation: fin {settle:.2f}s both, fg 9s ease-in-out {settle:.2f}s infinite; }}
@keyframes fin {{ 0%, 70% {{ opacity: 0; }} 100% {{ opacity: .9; }} }}
@keyframes fm {{ 0%, 100% {{ transform: translateX(-.6px); opacity: .9; }} 50% {{ transform: translateX(-1.5px); opacity: .9; }} }}
@keyframes fg {{ 0%, 100% {{ transform: translateX(.6px); opacity: .9; }} 50% {{ transform: translateX(1.5px); opacity: .9; }} }}
.sub {{ animation: sub 1.2s ease-out {settle - .6:.2f}s both; }}
@keyframes sub {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
@media (prefers-reduced-motion: reduce) {{ .crowd circle, .fm, .fg, .sub {{ animation: none; }} .fm, .fg {{ opacity: .9; }} }}
</style>
<defs><g id="crowd" class="crowd">
{chr(10).join(circles)}
</g></defs>
<g class="fringe fm" fill="{m}"><use href="#crowd"/></g>
<g class="fringe fg" fill="{g}"><use href="#crowd"/></g>
<text x="{x0:g}" y="{base}" font-size="{size}" font-weight="700" fill="{t['ink']}" textLength="{len(lead.rstrip()) * size * ADVANCE:g}" lengthAdjust="spacingAndGlyphs">{esc(lead.rstrip())}</text>
<use href="#crowd" fill="{t['brand']}"/>
<text class="sub" x="{WIDTH / 2:g}" y="108" text-anchor="middle" font-size="17" letter-spacing="1" fill="{t['muted']}">{esc(subline)}</text>
</svg>
"""


def wrap(text, width):
    lines, line = [], ''
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f'{line} {word}'.strip()
    return lines + [line]


def work_svg(i, job, t):
    """
    One employer, as a card the width of the profile card: a fringed index
    number, the organization and what it is, my role, and how the organization
    describes itself. README.md wraps it in a link to the organization's site.
    """
    about = wrap(job['about'], 90)
    h = 150 + 21 * len(about)
    m, g = t['fringe'][1], t['fringe'][0]
    num = f'{i + 1:02d}'
    index = lambda fill, dx: (f'<text x="{40 + dx}" y="70" font-size="44" font-weight="700" fill="{fill}">{num}</text>')
    lines = '\n'.join(f'<text x="150" y="{150 + 21 * k}" font-size="14" fill="{t["fg"]}">{esc(l)}</text>'
                      for k, l in enumerate(about))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{h}" viewBox="0 0 {WIDTH} {h}" font-family="{FONT}" role="img" aria-label="{esc(job['org'])}, {esc(job['full'])}: {esc(job['role'])}. {esc(job['about'])}">
<style>
.fm {{ animation: fm 9s ease-in-out {-3 * i}s infinite; }}
.fg {{ animation: fg 9s ease-in-out {-3 * i}s infinite; }}
@keyframes fm {{ 0%, 100% {{ transform: translateX(0); }} 50% {{ transform: translateX(-1.6px); }} }}
@keyframes fg {{ 0%, 100% {{ transform: translateX(0); }} 50% {{ transform: translateX(1.6px); }} }}
@media (prefers-reduced-motion: reduce) {{ .fm, .fg {{ animation: none; }} }}
</style>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="{h - 1}" rx="15" fill="{t['bg']}" stroke="{t['edge']}"/>
<g style="mix-blend-mode:{t['blend']}" opacity=".85"><g class="fm">{index(m, -1.2)}</g><g class="fg">{index(g, 1.2)}</g></g>{index(t['brand'], 0)}
<text x="150" y="62" font-size="30" font-weight="700" fill="{t['ink']}">{esc(job['org'])}</text>
<text x="150" y="88" font-size="13" letter-spacing=".5" fill="{t['muted']}">{esc(job['full'])}</text>
<text x="150" y="120" font-size="18" fill="{t['key']}">{esc(job['role'])}</text>
<line x1="150" y1="134" x2="{WIDTH - 40}" y2="134" stroke="{t['edge']}"/>
{lines}
<text x="{WIDTH - 40}" y="58" font-size="13" text-anchor="end" fill="{t['key']}">{esc(job['site'])} ↗</text>
</svg>
"""


def link_svg(label, t, primary):
    """A pill with a fringed dot, filled for the main link."""
    size, h = 13, 30
    text_w = len(label) * size * ADVANCE
    pad, dot, gap = 11, 6, 7
    w = pad + dot + gap + text_w + pad + 2
    cy = h / 2
    if primary:
        body = f'<rect x=".75" y=".75" width="{w - 1.5:g}" height="{h - 1.5:g}" rx="{(h - 1.5) / 2:g}" fill="{t["brand"]}"/>'
        ink, dot_fill = t['brand_ink'], t['brand_ink']
    else:
        body = (f'<rect x=".75" y=".75" width="{w - 1.5:g}" height="{h - 1.5:g}" rx="{(h - 1.5) / 2:g}" '
                f'fill="{t["bg"]}" stroke="{t["edge"]}" stroke-width="1.5"/>')
        ink, dot_fill = t['ink'], t['brand']
    dx = pad + dot / 2
    m, g = t['fringe'][1], t['fringe'][0]
    dots = (f'<g style="mix-blend-mode:{t["blend"]}" opacity=".9">'
            f'<circle cx="{dx - 1.2:g}" cy="{cy}" r="{dot / 2}" fill="{m}"/>'
            f'<circle cx="{dx + 1.2:g}" cy="{cy}" r="{dot / 2}" fill="{g}"/></g>'
            f'<circle cx="{dx:g}" cy="{cy}" r="{dot / 2}" fill="{dot_fill}"/>') if not primary else \
        f'<circle cx="{dx:g}" cy="{cy}" r="{dot / 2}" fill="{dot_fill}"/>'
    x_text = pad + dot + gap
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h}" viewBox="0 0 {w:g} {h}" font-family="{FONT}" role="img" aria-label="{esc(label)}">
{body}
{dots}
<text x="{x_text:g}" y="{cy + size * .35:g}" font-size="{size}" fill="{ink}" textLength="{text_w:g}" lengthAdjust="spacingAndGlyphs">{esc(label)}</text>
</svg>
"""


def picture(name, alt, href=None):
    """The <picture> README.md uses to show the light or dark copy of a part."""
    pic = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{OUT}/{name}-dark.svg">'
           f'<img alt="{esc(alt)}" src="{OUT}/{name}-light.svg"></picture>')
    return f'<a href="{href}">{pic}</a>' if href else pic


def main():
    with open(CONFIG, 'rb') as f:
        readme = tomllib.load(f).get('readme', {})
    os.makedirs(OUT, exist_ok=True)

    if readme.get('headline'):
        for theme, t in SAGE.items():
            with open(f'{OUT}/headline-{theme}.svg', 'w', encoding='utf-8') as f:
                f.write(headline_svg(readme['headline'], readme.get('subline', ''), t))
        print(f'headline {readme["headline"]!r}')

    for label in readme.get('sections', []):
        for theme, t in SAGE.items():
            with open(f'{OUT}/section-{slug(label)}-{theme}.svg', 'w', encoding='utf-8') as f:
                f.write(section_svg(label, t))
        print(f'section  {label:18} -> {picture("section-" + slug(label), label)}')

    jobs = readme.get('work', [])
    for i, job in enumerate(jobs):
        for theme, t in SAGE.items():
            with open(f'{OUT}/work-{slug(job["org"])}-{theme}.svg', 'w', encoding='utf-8') as f:
                f.write(work_svg(i, job, t))

    links = readme.get('links', [])
    for i, link in enumerate(links):
        for theme, t in SAGE.items():
            with open(f'{OUT}/link-{slug(link["label"])}-{theme}.svg', 'w', encoding='utf-8') as f:
                f.write(link_svg(link['label'], t, primary=(i == 0)))

    with open(README, encoding='utf-8') as f:
        text = f.read()
    blocks = [
        (LINKS_START, LINKS_END, '\n'.join(picture(f'link-{slug(l["label"])}', l['label'], l['href']) for l in links)),
        (WORK_START, WORK_END, '\n<br/>\n'.join(
            picture(f'work-{slug(j["org"])}', f'{j["org"]}, {j["full"]}: {j["role"]}', j['href']) for j in jobs)),
    ]
    for start, end, body in blocks:
        if start in text and end in text:
            head, rest = text.split(start, 1)
            _, tail = rest.split(end, 1)
            text = f'{head}{start}\n{body}\n{end}{tail}'
        else:
            print(f'{README} has no {start} ... {end} markers; skipped')
    with open(README, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'wrote {len(links)} links and {len(jobs)} employers into {README}')


if __name__ == '__main__':
    main()

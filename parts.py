"""
Draws the pieces of the README around the card, in the card's palette.

    python parts.py

From the [readme] table in profile.toml it writes, for light and dark:

    assets/parts/section-<name>-<theme>.svg   a header per section
    assets/parts/link-<name>-<theme>.svg      a pill per link

and rewrites the pill row in README.md between the links markers. Section
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

    for label in readme.get('sections', []):
        for theme, t in SAGE.items():
            with open(f'{OUT}/section-{slug(label)}-{theme}.svg', 'w', encoding='utf-8') as f:
                f.write(section_svg(label, t))
        print(f'section  {label:18} -> {picture("section-" + slug(label), label)}')

    links = readme.get('links', [])
    for i, link in enumerate(links):
        for theme, t in SAGE.items():
            with open(f'{OUT}/link-{slug(link["label"])}-{theme}.svg', 'w', encoding='utf-8') as f:
                f.write(link_svg(link['label'], t, primary=(i == 0)))

    with open(README, encoding='utf-8') as f:
        text = f.read()
    if LINKS_START in text and LINKS_END in text:
        row = '\n'.join(picture(f'link-{slug(l["label"])}', l['label'], l['href']) for l in links)
        head, rest = text.split(LINKS_START, 1)
        _, tail = rest.split(LINKS_END, 1)
        with open(README, 'w', encoding='utf-8') as f:
            f.write(f'{head}{LINKS_START}\n{row}\n{LINKS_END}{tail}')
        print(f'wrote {len(links)} links into {README}')
    else:
        print(f'{README} has no {LINKS_START} ... {LINKS_END} markers; links not written')


if __name__ == '__main__':
    main()

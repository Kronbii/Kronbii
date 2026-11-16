"""
Draws the last year of contributions as a grid a small quadcopter surveys.

    ACCESS_TOKEN=... USER_NAME=Kronbii python flight.py

Runs in the daily workflow and writes assets/flight-light.svg and
assets/flight-dark.svg, in the card's palette.

Every day starts out blank. The quad flies the grid the way a survey drone
covers a field -- a lawnmower pattern, one weekday row per pass, turning at
the ends -- and each day shows its colour as the quad's camera passes over
it. After the last pass it hovers and turns a slow full circle on the spot,
the days fade back to blank, and it flies home to start again. All of it is SMIL inside the SVG, so it plays in a README
<img> with no script; a viewer without SMIL sees the finished grid instead.

An API failure leaves the last drawing in place and exits cleanly, so it can
never stop the card's stats from updating.
"""
import os
import sys
from datetime import date

import requests

from card import SAGE, WIDTH, esc

OUT = 'assets/flight-{}.svg'
FONT = 'ConsolasFallback,Consolas,Menlo,monospace'
QUERY = '''query($login: String!) { user(login: $login) { contributionsCollection {
  contributionCalendar { totalContributions weeks { contributionDays {
    contributionCount contributionLevel date weekday } } } } } }'''
LEVEL = {'NONE': 0, 'FIRST_QUARTILE': 1, 'SECOND_QUARTILE': 2,
         'THIRD_QUARTILE': 3, 'FOURTH_QUARTILE': 4}

# Grid geometry, matching GitHub's own calendar.
CELL, PITCH = 13, 16
HEIGHT, Y0 = 226, 92                    # card height, top of the grid

# The flight, in seconds. Calm on purpose: about nine days revealed a second.
PASS, TURN, HOLD, HOME = 6.0, 0.8, 3.0, 3.5
FADE_IN, FADE_OUT = 0.35, 1.2


def calendar():
    token, login = os.environ.get('ACCESS_TOKEN'), os.environ.get('USER_NAME', 'Kronbii')
    if not token:
        sys.exit('flight.py needs ACCESS_TOKEN (a GitHub token) in the environment')
    response = requests.post('https://api.github.com/graphql', timeout=60,
                             json={'query': QUERY, 'variables': {'login': login}},
                             headers={'authorization': f'token {token}'})
    response.raise_for_status()
    body = response.json()
    if 'errors' in body:
        raise RuntimeError(body['errors'])
    return body['data']['user']['contributionsCollection']['contributionCalendar']


def build(cal, t):
    weeks = cal['weeks']
    cols = len(weeks)
    grid_w = cols * PITCH - (PITCH - CELL)
    x0 = round((WIDTH - grid_w) / 2)
    xa, xb = x0 - 24, x0 + grid_w + 24          # where each pass starts and ends
    span = xb - xa
    end = 7 * PASS + 6 * TURN                   # the last pass finishes
    dur = end + HOLD + HOME
    kt = lambda s: f'{s / dur:.5f}'

    def row_y(r):
        return Y0 + r * PITCH + CELL / 2

    def scanned_at(col, r):
        x = x0 + col * PITCH + CELL / 2
        start = r * (PASS + TURN)
        frac = (x - xa) / span if r % 2 == 0 else (xb - x) / span
        return start + PASS * frac

    levels = t['levels']
    base, days = [], []
    for col, week in enumerate(weeks):
        for day in week['contributionDays']:
            r = day['weekday']
            x, y = x0 + col * PITCH, Y0 + r * PITCH
            base.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5"/>')
            level = LEVEL.get(day['contributionLevel'], 0)
            if not level:
                continue
            s = scanned_at(col, r)
            days.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{levels[level]}">'
                f'<title>{day["contributionCount"]} on {day["date"]}</title>'
                f'<animate attributeName="opacity" dur="{dur:g}s" repeatCount="indefinite" '
                f'values="0;0;1;1;0;0" keyTimes="0;{kt(s)};{kt(s + FADE_IN)};{kt(end + HOLD)};'
                f'{kt(end + HOLD + FADE_OUT)};1"/></rect>')

    # The quad's route: each pass, then the turn down to the next row; hover;
    # fly home. Straight lines between these points, at constant speed.
    route = [(0.0, xa, row_y(0))]
    for r in range(7):
        x_end = xb if r % 2 == 0 else xa
        route.append((r * (PASS + TURN) + PASS, x_end, row_y(r)))
        if r < 6:
            route.append(((r + 1) * (PASS + TURN), x_end, row_y(r + 1)))
    route.append((end + HOLD, route[-1][1], route[-1][2]))
    route.append((dur, xa, row_y(0)))
    values = ';'.join(f'{x:g} {y:g}' for _, x, y in route)
    times = ';'.join(kt(s) for s, _, _ in route)

    # Month labels where a month's first week starts, as GitHub places them.
    months, last, last_col = [], None, -9
    for col, week in enumerate(weeks):
        first = date.fromisoformat(week['contributionDays'][0]['date'])
        if first.month != last and col - last_col >= 3:
            if col or first.day <= 7:
                months.append(f'<text x="{x0 + col * PITCH}" y="{Y0 - 10}">{first:%b}</text>')
                last_col = col
        last = first.month

    legend_x = x0 + grid_w - 5 * PITCH + (PITCH - CELL)
    legend = ''.join(f'<rect x="{legend_x + i * PITCH}" y="{30}" width="{CELL}" height="{CELL}" '
                     f'rx="2.5" fill="{c}"/>' for i, c in enumerate(levels))
    m, g = t['fringe'][1], t['fringe'][0]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="{FONT}" role="img" aria-label="{cal['totalContributions']:,} contributions in the last year">
<defs>
<g id="quad">
  <path d="M-8.5 -8.5 L8.5 8.5 M-8.5 8.5 L8.5 -8.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
  <g fill="currentColor" stroke="currentColor" stroke-width="1.1">
    <circle cx="-8.5" cy="-8.5" r="5.6" fill-opacity=".22"><animate attributeName="fill-opacity" values=".14;.3;.14" dur="0.9s" repeatCount="indefinite"/></circle>
    <circle cx="8.5" cy="-8.5" r="5.6" fill-opacity=".22"><animate attributeName="fill-opacity" values=".3;.14;.3" dur="0.9s" repeatCount="indefinite"/></circle>
    <circle cx="-8.5" cy="8.5" r="5.6" fill-opacity=".22"><animate attributeName="fill-opacity" values=".3;.14;.3" dur="0.9s" repeatCount="indefinite"/></circle>
    <circle cx="8.5" cy="8.5" r="5.6" fill-opacity=".22"><animate attributeName="fill-opacity" values=".14;.3;.14" dur="0.9s" repeatCount="indefinite"/></circle>
  </g>
  <rect x="-3.6" y="-3.6" width="7.2" height="7.2" rx="1.6" fill="currentColor"/>
</g>
</defs>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="15" fill="{t['bg']}" stroke="{t['edge']}"/>
<text x="{x0}" y="{41}" font-size="15" fill="{t['fg']}"><tspan fill="{t['key']}">{cal['totalContributions']:,}</tspan> contributions in the last year</text>
<g font-size="11" fill="{t['muted']}">
<text x="{legend_x - 8}" y="{41}" text-anchor="end">Less</text>{legend}<text x="{x0 + grid_w + 8}" y="{41}">More</text>
{''.join(months)}
</g>
<g fill="{levels[0]}">{''.join(base)}</g>
<g>{''.join(days)}</g>
<g transform="translate({xa} {row_y(0):g})">
  <animateTransform attributeName="transform" type="translate" dur="{dur:g}s" repeatCount="indefinite" calcMode="linear" values="{values}" keyTimes="{times}"/>
  <rect x="-28" y="-9.5" width="56" height="19" rx="4" fill="{t['brand']}" fill-opacity=".1" stroke="{t['brand']}" stroke-opacity=".4" stroke-dasharray="3 3"/>
  <g>
    <animateTransform attributeName="transform" type="rotate" dur="{dur:g}s" repeatCount="indefinite" values="0;0;360;360" keyTimes="0;{kt(end + 0.2)};{kt(end + HOLD - 0.2)};1" calcMode="spline" keySplines="0 0 1 1;0.45 0 0.25 1;0 0 1 1"/>
    <g style="mix-blend-mode:{t['blend']}" opacity=".85">
      <use href="#quad" transform="translate(-1 0)" style="color:{m}"/>
      <use href="#quad" transform="translate(1 0)" style="color:{g}"/>
    </g>
    <use href="#quad" style="color:{t['brand']}"/>
  </g>
</g>
</svg>
"""


# The phone version keeps the whole year by folding it: the first half of the
# weeks on one strip, the second half on a strip below it, both on the same
# columns. The quad surveys all fourteen rows as one lawnmower pattern, drops
# from the first strip to the second, turns its slow circle at the end and
# flies home. 320 units wide, drawn at 2x so it fills a phone's README column.
PHONE_OUT = 'assets/flight-phone-{}.svg'
PW = 320
ADVANCE = .6
P_CELL, P_PITCH = 8.7, 10.7
P_PASS, P_TURN, P_JUMP = 3.0, 0.6, 1.4          # about nine days revealed a second, as on desktop


def ptext(x, y, s, size, fill, anchor='start', extra=''):
    """A label stretched to its exact monospace width, whatever font the viewer falls back to."""
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" fill="{fill}" text-anchor="{anchor}"{extra} '
            f'textLength="{len(s) * size * ADVANCE:.1f}" lengthAdjust="spacingAndGlyphs">{esc(s)}</text>')


def build_phone(cal, t):
    weeks = cal['weeks']
    half = (len(weeks) + 1) // 2
    strips = [weeks[:half], weeks[half:]]
    L, R = 14, PW - 14
    grid_w = (half - 1) * P_PITCH + P_CELL
    x0 = (PW - grid_w) / 2
    xa, xb = x0 - 2, x0 + grid_w + 2
    span = xb - xa
    tops = [92, 92 + 7 * P_PITCH - (P_PITCH - P_CELL) + 34]
    height = round(tops[1] + 7 * P_PITCH - (P_PITCH - P_CELL) + 18)

    rows = 7 * len(strips)
    starts = [0.0]                              # when each row's pass begins
    for r in range(1, rows):
        starts.append(starts[-1] + P_PASS + (P_JUMP if r % 7 == 0 else P_TURN))
    end = starts[-1] + P_PASS
    dur = end + HOLD + HOME
    kt = lambda s: f'{s / dur:.5f}'

    def row_y(r):
        return tops[r // 7] + (r % 7) * P_PITCH + P_CELL / 2

    def scanned_at(x, r):
        frac = (x - xa) / span if r % 2 == 0 else (xb - x) / span
        return starts[r] + P_PASS * frac

    levels = t['levels']
    base, days, months = [], [], []
    for s, strip in enumerate(strips):
        # Month labels by GitHub's rule on the first strip. The second strip
        # names its opening month too, so each strip says where it starts,
        # unless a new month begins right after it, which then takes its place.
        marks, last = [], None
        for col, week in enumerate(strip):
            first = date.fromisoformat(week['contributionDays'][0]['date'])
            if first.month != last and (col or first.day <= 7 or s):
                if not marks or col - marks[-1][0] >= 3:
                    marks.append((col, f'{first:%b}'))
                elif s and marks[-1][0] == 0:
                    marks[-1] = (col, f'{first:%b}')
            last = first.month
        for col, week in enumerate(strip):
            for day in week['contributionDays']:
                r = s * 7 + day['weekday']
                x, y = x0 + col * P_PITCH, tops[s] + day['weekday'] * P_PITCH
                base.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{P_CELL}" height="{P_CELL}" rx="2"/>')
                level = LEVEL.get(day['contributionLevel'], 0)
                if not level:
                    continue
                at = scanned_at(x + P_CELL / 2, r)
                days.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{P_CELL}" height="{P_CELL}" rx="2" fill="{levels[level]}">'
                    f'<title>{day["contributionCount"]} on {day["date"]}</title>'
                    f'<animate attributeName="opacity" dur="{dur:g}s" repeatCount="indefinite" '
                    f'values="0;0;1;1;0;0" keyTimes="0;{kt(at)};{kt(at + FADE_IN)};{kt(end + HOLD)};'
                    f'{kt(end + HOLD + FADE_OUT)};1"/></rect>')
        months += [ptext(x0 + col * P_PITCH, tops[s] - 8, name, 11, t['muted']) for col, name in marks]

    route = [(0.0, xa, row_y(0))]
    for r in range(rows):
        x_end = xb if r % 2 == 0 else xa
        route.append((starts[r] + P_PASS, x_end, row_y(r)))
        if r < rows - 1:
            route.append((starts[r + 1], x_end, row_y(r + 1)))
    route.append((end + HOLD, route[-1][1], route[-1][2]))
    route.append((dur, xa, row_y(0)))
    values = ';'.join(f'{x:.1f} {y:.1f}' for _, x, y in route)
    times = ';'.join(kt(s) for s, _, _ in route)

    # Headline, fitted to the width; the legend at the right of the line under it.
    total = f'{cal["totalContributions"]:,}'
    first = f'{total} contributions'
    size = min(18, (R - L) / (len(first) * ADVANCE))
    head = (f'<text x="{L}" y="36" font-size="{size:.2f}" fill="{t["fg"]}" textLength="{len(first) * size * ADVANCE:.1f}" '
            f'lengthAdjust="spacingAndGlyphs"><tspan fill="{t["key"]}" font-weight="700">{total}</tspan> contributions</text>')
    lc, lp = 9, 11
    more_x = R - 4 * 11 * ADVANCE
    cells_x = more_x - 5 - (5 * lp - (lp - lc))
    legend = (ptext(cells_x - 5, 56, 'Less', 11, t['muted'], anchor='end')
              + ''.join(f'<rect x="{cells_x + i * lp:.1f}" y="{56 - lc:g}" width="{lc}" height="{lc}" rx="2" fill="{c}"/>'
                        for i, c in enumerate(levels))
              + ptext(more_x, 56, 'More', 11, t['muted']))
    m, g = t['fringe'][1], t['fringe'][0]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{PW * 2}" height="{height * 2}" viewBox="0 0 {PW} {height}" font-family="{FONT}" role="img" aria-label="{cal['totalContributions']:,} contributions in the last year">
<defs>
<g id="quad">
  <path d="M-8.5 -8.5 L8.5 8.5 M-8.5 8.5 L8.5 -8.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
  <g fill="currentColor" stroke="currentColor" stroke-width="1.1">
    <circle cx="-8.5" cy="-8.5" r="5.6" fill-opacity=".22"><animate attributeName="fill-opacity" values=".14;.3;.14" dur="0.9s" repeatCount="indefinite"/></circle>
    <circle cx="8.5" cy="-8.5" r="5.6" fill-opacity=".22"><animate attributeName="fill-opacity" values=".3;.14;.3" dur="0.9s" repeatCount="indefinite"/></circle>
    <circle cx="-8.5" cy="8.5" r="5.6" fill-opacity=".22"><animate attributeName="fill-opacity" values=".3;.14;.3" dur="0.9s" repeatCount="indefinite"/></circle>
    <circle cx="8.5" cy="8.5" r="5.6" fill-opacity=".22"><animate attributeName="fill-opacity" values=".14;.3;.14" dur="0.9s" repeatCount="indefinite"/></circle>
  </g>
  <rect x="-3.6" y="-3.6" width="7.2" height="7.2" rx="1.6" fill="currentColor"/>
</g>
</defs>
<rect x=".5" y=".5" width="{PW - 1}" height="{height - 1}" rx="12" fill="{t['bg']}" stroke="{t['edge']}"/>
{head}
{ptext(L, 56, 'in the last year', 12, t['muted'])}
{legend}
{''.join(months)}
<g fill="{levels[0]}">{''.join(base)}</g>
<g>{''.join(days)}</g>
<g transform="translate({xa:.1f} {row_y(0):.1f})">
  <animateTransform attributeName="transform" type="translate" dur="{dur:g}s" repeatCount="indefinite" calcMode="linear" values="{values}" keyTimes="{times}"/>
  <rect x="-11" y="-6.5" width="22" height="13" rx="3" fill="{t['brand']}" fill-opacity=".1" stroke="{t['brand']}" stroke-opacity=".4" stroke-dasharray="2.5 2.5"/>
  <g>
    <animateTransform attributeName="transform" type="rotate" dur="{dur:g}s" repeatCount="indefinite" values="0;0;360;360" keyTimes="0;{kt(end + 0.2)};{kt(end + HOLD - 0.2)};1" calcMode="spline" keySplines="0 0 1 1;0.45 0 0.25 1;0 0 1 1"/>
    <g transform="scale(.56)">
      <g style="mix-blend-mode:{t['blend']}" opacity=".85">
        <use href="#quad" transform="translate(-1.4 0)" style="color:{m}"/>
        <use href="#quad" transform="translate(1.4 0)" style="color:{g}"/>
      </g>
      <use href="#quad" style="color:{t['brand']}"/>
    </g>
  </g>
</g>
</svg>
"""


def main():
    try:
        cal = calendar()
    except (requests.RequestException, RuntimeError, KeyError, TypeError) as e:
        print(f'warning: could not read the contribution calendar ({e}); '
              f'{OUT.format("*")} and {PHONE_OUT.format("*")} left as they are')
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for theme, t in SAGE.items():
        with open(OUT.format(theme), 'w', encoding='utf-8') as f:
            f.write(build(cal, t))
        with open(PHONE_OUT.format(theme), 'w', encoding='utf-8') as f:
            f.write(build_phone(cal, t))
    print(f'wrote {OUT.format("light")} and {OUT.format("dark")} (and the phone pair): '
          f'{cal["totalContributions"]:,} contributions over {len(cal["weeks"])} weeks')


if __name__ == '__main__':
    main()

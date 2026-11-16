"""
Lists the newest write-ups from ramikronbi.com in README.md.

    python writing.py

Runs in the daily workflow. It reads the site's RSS feed and rewrites the
list between the writing markers in README.md. The feed carries no dates; it
lists the write-ups in the order of ramikronbi.com/writing, so this shows the
first few in that order.

A network or feed failure leaves README.md as it is and exits cleanly, so a
bad day for the site never stops the card's stats from updating.
"""
import html
import sys

import requests
from lxml import etree

FEED = 'https://ramikronbi.com/feed.xml'
README = 'README.md'
START, END = '<!-- writing:start -->', '<!-- writing:end -->'
COUNT = 4


def items():
    response = requests.get(FEED, timeout=30, headers={'User-Agent': 'Kronbii-profile-readme'})
    response.raise_for_status()
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    channel = etree.fromstring(response.content, parser).find('channel')
    for item in channel.findall('item')[:COUNT]:
        yield (item.findtext('title', '').strip(), item.findtext('link', '').strip(),
               item.findtext('description', '').strip())


def render(entries):
    rows = []
    for title, link, dek in entries:
        rows.append(f'- <a href="{html.escape(link, quote=True)}"><b>{html.escape(title)}</b></a>'
                    f'<br/>{html.escape(dek)}')
    return '\n'.join(rows)


def main():
    try:
        entries = [e for e in items() if e[0] and e[1]]
    except (requests.RequestException, etree.XMLSyntaxError, AttributeError) as e:
        print(f'warning: could not read {FEED} ({e}); README.md left as it is')
        return
    if not entries:
        print(f'warning: {FEED} has no items; README.md left as it is')
        return

    with open(README, encoding='utf-8') as f:
        text = f.read()
    if START not in text or END not in text:
        sys.exit(f'{README} has no {START} ... {END} markers')
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    with open(README, 'w', encoding='utf-8') as f:
        f.write(f'{head}{START}\n{render(entries)}\n{END}{tail}')
    print(f'wrote {len(entries)} write-ups into {README}')


if __name__ == '__main__':
    main()

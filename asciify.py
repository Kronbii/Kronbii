"""
Turns a photo into the ASCII panel on the left of the card.

    python asciify.py                 # uses [art] in profile.toml
    python asciify.py other.jpg       # override the source photo

Writes the art file card.py reads. Everything is tunable from the [art] table in
profile.toml -- see the comments there. The output is plain text on purpose:
tweaking a few characters by hand afterwards is normal and beats fighting the
tone curve, which is how Andrew6rant's originals were finished too.

The panel is small -- 38x25 characters at his original 16px -- so a straight
luminance ramp turns any busy photo into noise, because the subject and the
background land on the same characters. Instead we cut the subject out with
GrabCut, give it the dense end of the ramp, and push the background down to a
faint wash so the silhouette carries the image.
"""
import sys
import tomllib

import cv2
import numpy as np

from card import CONFIG, art_grid      # so both scripts agree on the grid

DEFAULTS = {
    'source': 'cache/avatar.png',
    'file': 'cache/art.txt',
    'size': 16,
    'fit': 'fill',
    'ramp': " .':;!*=%$@",
    'density': 0.42,
    'background': 0.0,
    'shading': 1.0,
    'despeckle': True,
    'headroom': 1.06,
    'subject_box': [0.02, 0.24, 0.98, 0.98],
}


def settings():
    with open(CONFIG, 'rb') as f:
        art = tomllib.load(f).get('art', {})
    unknown = set(art) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f'{CONFIG}: unknown [art] setting(s): {", ".join(sorted(unknown))}')
    cfg = {**DEFAULTS, **art}
    if not cfg['ramp'].startswith(' '):
        raise SystemExit(f'{CONFIG}: art.ramp must start with a space (the empty level)')
    if len(cfg['ramp']) < 2:
        raise SystemExit(f'{CONFIG}: art.ramp needs at least two characters')
    for key in ('density', 'background'):
        if not 0 <= cfg[key] <= 1:
            raise SystemExit(f'{CONFIG}: art.{key} must be between 0 and 1')
    if cfg['shading'] <= 0:
        raise SystemExit(f'{CONFIG}: art.shading must be greater than 0')
    if len(cfg['subject_box']) != 4:
        raise SystemExit(f'{CONFIG}: art.subject_box needs four numbers [x0, y0, x1, y1]')
    return cfg


def segment(img, box):
    """Cut the subject out of the background. Returns a 0/255 mask."""
    # GrabCut seeds its colour models with randomly-initialised k-means, so the
    # same photo otherwise yields slightly different art on every run -- which
    # would show up as a churning diff each time the panel is regenerated.
    cv2.setRNGSeed(0)
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    # Anything outside this rectangle is seeded as definite background, so a
    # tight box lops off whatever pokes out of it -- outstretched arms, usually.
    rect = (int(w * x0), int(h * y0), int(w * (x1 - x0)), int(h * (y1 - y0)))
    mask = np.zeros((h, w), np.uint8)
    cv2.grabCut(img, mask, rect, np.zeros((1, 65), np.float64),
                np.zeros((1, 65), np.float64), 8, cv2.GC_INIT_WITH_RECT)
    m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=2)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8), iterations=3)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    if n > 1:                            # keep the largest blob, drop stray specks
        m = (labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8) * 255
    if not m.any():
        raise SystemExit('segmentation found no subject -- widen art.subject_box, or '
                         'try a photo with more separation from the background')
    return m


def frame(img, mask, cols, rows, cell_w, line_h, fit, headroom):
    """
    Choose the crop and the character block to render it into.
    Returns (img, mask, cols, rows) for that block.

    The panel is tall and narrow; an arms-out pose is wide. The two shapes don't
    reconcile, so this is a real choice rather than a default:

      'contain'  show all of the subject, leaving blank rows above and below
      'fill'     fill the panel, cropping whatever falls outside its shape
    """
    H, W = mask.shape
    ys, xs = np.nonzero(mask)
    pad_x = int((xs.max() - xs.min()) * (headroom - 1))
    pad_y = int((ys.max() - ys.min()) * (headroom - 1))

    if fit == 'contain':
        x0, x1 = max(0, xs.min() - pad_x), min(W, xs.max() + pad_x)
        y0, y1 = max(0, ys.min() - pad_y), min(H, ys.max() + pad_y)
        img, mask = img[y0:y1, x0:x1], mask[y0:y1, x0:x1]
        h, w = mask.shape
        c = cols
        r = round(c * (h / w) * (cell_w / line_h))
        if r > rows:                    # too tall for the panel: fit height instead
            r = rows
            c = round(r * (w / h) * (line_h / cell_w))
        return img, mask, max(1, min(c, cols)), max(1, min(r, rows))

    if fit != 'fill':
        raise SystemExit(f'art.fit must be "fill" or "contain", not {fit!r}')

    aspect = (rows * line_h) / (cols * cell_w)
    cy, cx = (ys.min() + ys.max()) / 2, (xs.min() + xs.max()) / 2
    cw = min(W, (xs.max() - xs.min()) + 2 * pad_x)
    ch = cw * aspect
    if ch > H:                          # taller than the source: take full height
        ch, cw = H, H / aspect
    y = int(np.clip(cy - ch / 2, 0, H - ch))
    x = int(np.clip(cx - cw / 2, 0, W - cw))
    return img[y:y + int(ch), x:x + int(cw)], mask[y:y + int(ch), x:x + int(cw)], cols, rows


def asciify(cfg, cols, rows, cell_w, line_h):
    img = cv2.imread(cfg['source'])
    if img is None:
        raise SystemExit(f'cannot read {cfg["source"]}')
    img, mask, art_cols, art_rows = frame(img, segment(img, cfg['subject_box']),
                                          cols, rows, cell_w, line_h,
                                          cfg['fit'], cfg['headroom'])

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    small = cv2.resize(gray, (art_cols, art_rows), interpolation=cv2.INTER_AREA)
    msk = cv2.resize(mask.astype(np.float32) / 255, (art_cols, art_rows),
                     interpolation=cv2.INTER_AREA)
    inside = msk > 0.5

    # Stretch contrast within the subject alone, so the backpack, shirt and skin
    # land on different characters instead of all saturating to one.
    lo, hi = np.percentile(small[inside], 5), np.percentile(small[inside], 95)
    subject = np.clip((small - lo) / max(1e-6, hi - lo), 0, 1)
    outside = small[~inside]
    background = np.clip((small - outside.min()) / max(1e-6, float(np.ptp(outside))), 0, 1)

    # The subject is dark against a bright scene, so invert it: dark pixels
    # become dense characters and the figure reads as solid. `shading` is a
    # gamma on that ink, and `density` is the floor it never falls below.
    ink = (1 - subject) ** cfg['shading']
    floor = cfg['density']
    level = np.where(inside, floor + ink * (1 - floor), background * cfg['background'])

    ramp = cfg['ramp']
    idx = np.clip(np.round(level * (len(ramp) - 1)).astype(int), 0, len(ramp) - 1)

    if cfg['despeckle']:
        # A lone lit cell out in the background reads as dirt, not scenery.
        lit = (~inside) & (idx > 0)
        neighbours = cv2.filter2D(lit.astype(np.uint8), -1, np.ones((3, 3), np.uint8))
        idx = np.where(lit & (neighbours <= 2), 0, idx)

    indent = ' ' * ((cols - art_cols) // 2)     # centre the block in the panel
    art = [(indent + ''.join(ramp[idx[y, x]] for x in range(art_cols))).rstrip()
           for y in range(art_rows)]
    pad = rows - art_rows
    return [''] * (pad // 2) + art + [''] * (pad - pad // 2)


if __name__ == '__main__':
    cfg = settings()
    if len(sys.argv) > 1:
        cfg['source'] = sys.argv[1]
    cols, rows, cell_w, line_h = art_grid(cfg['size'])

    art = asciify(cfg, cols, rows, cell_w, line_h)
    with open(cfg['file'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(art) + '\n')
    print('\n'.join(art))
    print(f'\nwrote {cfg["file"]} from {cfg["source"]} -- '
          f'{cols}x{rows} at {cfg["size"]}px, fit={cfg["fit"]}')

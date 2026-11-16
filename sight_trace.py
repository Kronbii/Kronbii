"""
Runs a real computer-vision pipeline over my profile photo, once, for sight.py.

    python sight_trace.py

Reads cache/avatar.png and writes cache/sight.json, which sight.py turns into
the "machine sight" card every day. Run it again only when the photo changes.
It needs OpenCV, numpy, Pillow and SciPy, which the daily workflow doesn't
install: that's why its output is cached rather than computed on every run.
The face detector is OpenCV's haarcascade_frontalface_default.xml: the pip
wheel ships it (cv2.data); with a system OpenCV, point HAAR_FACE at a copy
from OpenCV's data/haarcascades.

What it records, all in the camera viewport's own pixel space:

    frame     the photo, cropped and downsampled to a coarse sensor grid,
              posterised to a few grey levels and stored as a PNG per theme
    face      the face box from OpenCV's frontal-face Haar cascade
    edges     Canny edges traced into simplified polylines
    features  Shi-Tomasi corners (goodFeaturesToTrack)
    mesh      the Delaunay triangulation of the corners on me, as edges
"""
import base64
import io
import json
import os

import cv2
import numpy as np
from PIL import Image

SRC = 'cache/avatar.png'
OUT = 'cache/sight.json'

VIEW_W, VIEW_H = 460, 528           # the camera viewport in sight.py, px
CROP = (40, 0, 440, 459)            # x0, y0, x1, y1 of the 460x460 photo
PIXEL = 4                           # viewport px per sensor pixel
LEVELS = 9                          # grey levels the frame is posterised to
SUBJECT = (0.2, 0.2, 0.88, 1.0)     # GrabCut's starting box, as in [art]

# The backlit photo needs its shadows lifted before the cascade will find a
# face in it; these are the settings that do, on this photo.
FACE_CLAHE, FACE_GAMMA = 4.0, 0.7

# Theme -> (shadow, highlight) the frame's grey levels run between. Kept low
# in contrast so the overlays drawn on top stay the brightest thing.
TONES = {'dark': ((11, 15, 13), (86, 108, 80)),
         'light': ((150, 163, 143), (238, 239, 230))}


def to_view(x, y):
    sx = VIEW_W / (CROP[2] - CROP[0])
    sy = VIEW_H / (CROP[3] - CROP[1])
    return round((x - CROP[0]) * sx, 1), round((y - CROP[1]) * sy, 1)


def frame_png(gray, theme):
    """The cropped photo as a coarse, posterised sensor image."""
    crop = gray[CROP[1]:CROP[3], CROP[0]:CROP[2]]
    small = cv2.resize(crop, (VIEW_W // PIXEL, VIEW_H // PIXEL), interpolation=cv2.INTER_AREA)
    small = np.uint8(255 * (small / 255.0) ** .62)          # lift the backlit face
    small = cv2.createCLAHE(2.6, (5, 5)).apply(small)
    q = np.round(small / 255 * (LEVELS - 1)) / (LEVELS - 1)
    lo, hi = (np.array(c, float) for c in TONES[theme])
    rgb = (lo + (hi - lo) * q[..., None]).astype(np.uint8)
    img = Image.fromarray(rgb).quantize(colors=LEVELS)
    buf = io.BytesIO()
    img.save(buf, 'PNG', optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def subject_mask(bgr):
    h, w = bgr.shape[:2]
    rect = (int(SUBJECT[0] * w), int(SUBJECT[1] * h),
            int((SUBJECT[2] - SUBJECT[0]) * w), int((SUBJECT[3] - SUBJECT[1]) * h))
    mask = np.zeros((h, w), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, rect, bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    return cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))


def cascade():
    """OpenCV's frontal-face cascade: $HAAR_FACE, else the copy in the pip wheel."""
    path = os.environ.get('HAAR_FACE')
    if not path and hasattr(cv2, 'data'):
        path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
    if not path or not os.path.exists(path):
        raise SystemExit('set HAAR_FACE to haarcascade_frontalface_default.xml from OpenCV\'s data/haarcascades')
    return path


def face_box(gray):
    src = cv2.createCLAHE(FACE_CLAHE, (8, 8)).apply(gray)
    src = np.uint8(255 * (src / 255.0) ** FACE_GAMMA)
    found = cv2.CascadeClassifier(cascade()).detectMultiScale(src, 1.05, 4, minSize=(40, 40))
    if not len(found):
        raise SystemExit('the cascade found no face; adjust FACE_CLAHE / FACE_GAMMA')
    x, y, w, h = max(found, key=lambda f: f[2] * f[3])
    (x0, y0), (x1, y1) = to_view(x, y), to_view(x + w, y + h)
    return [x0, y0, round(x1 - x0, 1), round(y1 - y0, 1)]


def edges(gray):
    smooth = cv2.bilateralFilter(gray, 9, 40, 9)
    smooth = cv2.createCLAHE(2.0, (8, 8)).apply(smooth)
    canny = cv2.Canny(smooth, 50, 130)
    canny[:, :CROP[0]] = 0
    canny[:, CROP[2]:] = 0
    contours, _ = cv2.findContours(canny, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    lines = []
    for c in contours:
        if cv2.arcLength(c, False) < 34:
            continue
        poly = cv2.approxPolyDP(c, 1.3, False).reshape(-1, 2)
        pts = [to_view(int(x), int(y)) for x, y in poly]
        lines.append(pts)
    lines.sort(key=lambda p: -len(p))
    return lines


def features(gray, mask):
    clahe = cv2.createCLAHE(2.5, (8, 8)).apply(gray)
    region = np.zeros_like(gray)
    region[CROP[1]:CROP[3], CROP[0] + 4:CROP[2] - 4] = 255
    on = cv2.goodFeaturesToTrack(clahe, 150, .015, 9, mask=cv2.bitwise_and(region, mask))
    off = cv2.goodFeaturesToTrack(clahe, 70, .03, 22, mask=cv2.bitwise_and(region, cv2.bitwise_not(mask)))
    on = [] if on is None else on.reshape(-1, 2)
    off = [] if off is None else off.reshape(-1, 2)
    return [list(to_view(*p)) for p in on], [list(to_view(*p)) for p in off]


def mesh(points, face):
    """Delaunay edges over the corners on me, short ones only."""
    from scipy.spatial import Delaunay
    if len(points) < 4:
        return []
    pts = np.array(points)
    tri = Delaunay(pts)
    fx, fy = face[0] + face[2] / 2, face[1] + face[3] / 2
    seen = set()
    for a, b, c in tri.simplices:
        for i, j in ((a, b), (b, c), (c, a)):
            i, j = min(i, j), max(i, j)
            if np.hypot(*(pts[i] - pts[j])) < 64:
                seen.add((int(i), int(j)))
    # outward from the face, so the mesh can be drawn growing from it
    def dist(e):
        mx, my = (pts[e[0]] + pts[e[1]]) / 2
        return np.hypot(mx - fx, my - fy)
    return sorted(seen, key=dist)


def main():
    bgr = cv2.imread(SRC)
    if bgr is None:
        raise SystemExit(f'{SRC} not found')
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = subject_mask(bgr)
    face = face_box(gray)
    on, off = features(gray, mask)
    data = {
        'view': [VIEW_W, VIEW_H],
        'pixel': PIXEL,
        'frame': {theme: frame_png(gray, theme) for theme in TONES},
        'face': face,
        'edges': edges(gray),
        'features': on,
        'scene': off,
        'mesh': mesh(on, face),
        'cascade': 'haarcascade_frontalface_default',
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, separators=(',', ':'))
    print(f'{OUT}: face {face}, {len(data["edges"])} edge lines '
          f'({sum(len(e) for e in data["edges"])} points), {len(on)}+{len(off)} corners, '
          f'{len(data["mesh"])} mesh edges, frame {len(data["frame"]["dark"]) // 1024} KB b64')


if __name__ == '__main__':
    main()

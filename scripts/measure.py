"""Measure a short (or a folder of them) frame by frame. Run it on the reference AND on your own render: the delta
is the to-do list (compare.py).

python measure.py <video_or_folder> [--out report.json] [--text transcript.txt] [--height 320]

Per video, every consecutive frame pair:
  camera   phase correlation -> sideways/vertical shift (fraction of frame per second) and zoom (log-scale per second,
           via phase correlation of the log-polar spectrum). Jerk = 3rd derivative, RMS, cuts excluded.
  cuts     colour-histogram break between two frames (hard cuts per minute, mean shot length)
  light    mean luma, contrast (luma std), saturation, the backdrop colour (median of the frame border)
  sound    integrated loudness (LUFS), loudness range (LU), true peak (ffmpeg ebur128)
  speech   words per second, if --text is given (a transcript; times in it are ignored)
A folder gives one entry per video plus 'summary' = the median of every metric.
"""
import json, re, subprocess, sys
from pathlib import Path

import cv2
import numpy as np

VIDEO = {'.mp4', '.mov', '.mkv', '.webm', '.m4v'}


def arg(name, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height,r_frame_rate:format=duration', '-of', 'json', str(path)],
                         capture_output=True, text=True).stdout
    j = json.loads(out)
    s = j['streams'][0]
    n, d = s['r_frame_rate'].split('/')
    return int(s['width']), int(s['height']), float(n) / float(d), float(j['format']['duration'])


def frames(path, height):
    w0, h0, fps, dur = probe(path)
    w = int(round(w0 * height / h0 / 2) * 2)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'scale={w}:{height}', '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    size = w * height * 3
    while True:
        b = p.stdout.read(size)
        if len(b) < size:
            break
        yield np.frombuffer(b, np.uint8).reshape(height, w, 3)
    p.wait()


def logpolar(gray, win):
    F = np.fft.fftshift(np.abs(np.fft.fft2(gray * win)))
    F = np.log1p(F).astype(np.float32)
    h, w = F.shape
    r = min(h, w) / 2
    return cv2.warpPolar(F, (w, h), (w / 2, h / 2), r, cv2.WARP_POLAR_LOG + cv2.INTER_LINEAR), r


def motion(prev, cur, win):
    """(dx, dy) in fraction of frame width/height, dlog = log zoom between two frames (+ = camera moves in).
    Tracked corners + a similarity fit when the frame has texture; phase correlation (shift) and the log-polar
    spectrum (zoom) when it does not (flat backdrops)."""
    a, b = prev.astype(np.uint8), cur.astype(np.uint8)
    pts = cv2.goodFeaturesToTrack(a, 300, 0.01, 6)
    if pts is not None and len(pts) >= 25:
        nxt, st, _ = cv2.calcOpticalFlowPyrLK(a, b, pts, None, winSize=(21, 21), maxLevel=3)
        good = st.ravel() == 1
        if good.sum() >= 20:
            M, inl = cv2.estimateAffinePartial2D(pts[good], nxt[good], method=cv2.RANSAC, ransacReprojThreshold=1.0)
            if M is not None and inl is not None and inl.sum() >= 15:
                h, w = prev.shape
                c = M @ np.array([w / 2, h / 2, 1.0])
                return (c[0] - w / 2) / w, (c[1] - h / 2) / h, float(np.log(np.hypot(M[0, 0], M[1, 0]))), 1.0
    (dx, dy), resp = cv2.phaseCorrelate(prev, cur, win)
    lp0, r = logpolar(prev, win)
    lp1, _ = logpolar(cur, win)
    (sx, _), _ = cv2.phaseCorrelate(lp0, lp1)
    w = prev.shape[1]
    dlog = -sx * np.log(r) / w            # spectrum shrinks when the image grows
    return dx / prev.shape[1], dy / prev.shape[0], dlog, resp


def hist(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [32, 16], [0, 180, 0, 256])
    return cv2.normalize(h, h).flatten()


def loudness(path):
    r = subprocess.run(['ffmpeg', '-nostats', '-i', str(path), '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    tail = r[r.rfind('Summary:'):]
    g = lambda k: float(m.group(1)) if (m := re.search(k + r'\s*(-?[\d.]+)', tail)) else None
    return {'lufs': g('I:'), 'lra': g('LRA:'), 'true_peak_dbtp': g('Peak:')}


def smooth(x, k=5):
    if len(x) < k:
        return np.asarray(x, float)
    return np.convolve(x, np.ones(k) / k, mode='same')


def measure(path, height=320, text=None):
    w0, h0, fps, dur = probe(path)
    luma, contr, sat, border, flat = [], [], [], [], []
    dxs, dys, dls, cuts = [], [], [], []
    prev = prevh = win = None
    for i, rgb in enumerate(frames(path, height)):
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        luma.append(g.mean())
        contr.append(g.std())
        sat.append(hsv[..., 1].mean() / 255)
        b = max(2, int(0.04 * min(g.shape)))
        edge = np.concatenate([rgb[:b].reshape(-1, 3), rgb[-b:].reshape(-1, 3), rgb[:, :b].reshape(-1, 3), rgb[:, -b:].reshape(-1, 3)])
        border.append(np.median(edge, 0))
        flat.append(float(edge.std(0).mean() < 14))   # grain alone adds ~7
        hh = hist(rgb)
        if win is None:
            win = cv2.createHanningWindow(g.shape[::-1], cv2.CV_32F)
        if prev is not None:
            cut = cv2.compareHist(prevh, hh, cv2.HISTCMP_CORREL) < 0.55
            cuts.append(cut)
            dx, dy, dl, _ = (0, 0, 0, 0) if cut else motion(prev, g, win)
            dxs.append(dx); dys.append(dy); dls.append(dl)
        prev, prevh = g, hh
    n = len(luma)
    cuts = np.array(cuts, bool)
    vx, vy, vz = (smooth(np.array(a)) * fps for a in (dxs, dys, dls))   # per second
    ok = ~cuts
    for k in range(1, 4):                                           # drop frames next to a cut from the derivatives
        ok &= ~np.roll(cuts, k) & ~np.roll(cuts, -k)

    def jerk(v):
        j = np.diff(v, 2) * fps * fps
        m = ok[2:] if len(ok) > 2 else ok
        return float(np.sqrt(np.mean(j[m[:len(j)]] ** 2))) if m.any() else 0.0

    still = ok & (np.abs(vz) < 0.02) & (np.hypot(vx, vy) < 0.01)
    ncut = int(cuts.sum())
    minutes = n / fps / 60
    res = {
        'file': str(path), 'fps': round(fps, 3), 'frames': n, 'seconds': round(n / fps, 2), 'size': [w0, h0],
        'camera': {
            'lateral_speed': round(float(np.median(np.abs(vx[ok]))) if ok.any() else 0, 4),   # frame widths / s
            'vertical_speed': round(float(np.median(np.abs(vy[ok]))) if ok.any() else 0, 4),
            'zoom_speed': round(float(np.median(np.abs(vz[ok]))) if ok.any() else 0, 4),       # log-scale / s
            'zoom_in_share': round(float(np.mean(vz[ok] > 0.02)) if ok.any() else 0, 3),
            'zoom_out_share': round(float(np.mean(vz[ok] < -0.02)) if ok.any() else 0, 3),
            'hold_share': round(float(still.mean()), 3),
            'jerk_lateral': round(jerk(vx), 3), 'jerk_zoom': round(jerk(vz), 3),
        },
        'cuts': {'count': ncut, 'per_minute': round(ncut / minutes, 1) if minutes else 0,
                 'mean_shot_s': round(n / fps / (ncut + 1), 2)},
        'light': {'luma': round(float(np.mean(luma)), 1), 'contrast': round(float(np.mean(contr)), 1),
                  'saturation': round(float(np.mean(sat)), 3),
                  'backdrop_rgb': [int(x) for x in np.median(np.array(border), 0)],
                  'flat_backdrop_share': round(float(np.mean(flat)), 3)},
        'sound': loudness(path),
    }
    if text:
        words = len(re.findall(r"[A-Za-z']+", re.sub(r'\d\d:\d\d', '', Path(text).read_text(encoding='utf-8'))))
        res['speech'] = {'words': words, 'words_per_second': round(words / (n / fps), 2)}
    return res


def summary(rows):
    def walk(keys):
        vals = [r for r in rows]
        for k in keys:
            vals = [v.get(k) if isinstance(v, dict) else None for v in vals]
        vals = [v for v in vals if isinstance(v, (int, float)) and v is not None]
        return round(float(np.median(vals)), 4) if vals else None
    out = {'videos': len(rows), 'total_frames': sum(r['frames'] for r in rows)}
    for sec in ('camera', 'cuts', 'light', 'sound', 'speech'):
        keys = {k for r in rows for k, v in r.get(sec, {}).items() if isinstance(v, (int, float))}
        if keys:
            out[sec] = {k: walk([sec, k]) for k in sorted(keys)}
    bd = [r['light']['backdrop_rgb'] for r in rows]
    out.setdefault('light', {})['backdrop_rgb'] = [int(x) for x in np.median(np.array(bd), 0)]
    return out


def main():
    src = Path(sys.argv[1])
    files = sorted(p for p in src.iterdir() if p.suffix.lower() in VIDEO) if src.is_dir() else [src]
    rows = []
    for f in files:
        print('measuring', f.name, flush=True)
        rows.append(measure(f, arg('--height', 320, int), arg('--text')))
    rep = rows[0] if len(rows) == 1 else {'summary': summary(rows), 'videos': rows}
    out = Path(arg('--out', str((src if src.is_dir() else src.parent) / 'measure.json')))
    out.write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep.get('summary', rep), indent=2))
    print('->', out)


if __name__ == '__main__':
    main()

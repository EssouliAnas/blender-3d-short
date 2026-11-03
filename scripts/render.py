"""Build and render an episode's scene with Blender in the background.

python render.py <episode_dir> build                  run scene.py -> scene.blend
python render.py <episode_dir> still <frame> [<frame> ...] [--pct 50] [--quality fast]   stills -> stills/f####.png
python render.py <episode_dir> frames [--quality fast] [--jobs 2] [--start S --end E] [--pct 100]   PNGs -> frames/
python render.py <episode_dir> times                  summary of the stopwatch log (slowest frames first)

--quality draft | fast (default) | high, applied at render time (b3d.EEVEE_PRESETS or CYCLES_PRESETS).
frames shows a live progress bar (done/total, s per frame, ETA) and mirrors it to <episode_dir>/progress.json.
Frames are resumable: existing PNGs are skipped (Blender's overwrite is off). --jobs N runs N Blender processes,
each rendering every Nth frame (two fit on an 8 GB GPU for most city/body scenes; watch VRAM).
"""
import json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def blender():
    exe = os.environ.get('BLENDER')
    if exe:
        return exe
    for root in (r'C:\Program Files\Blender Foundation', '/Applications', '/usr/bin', '/opt'):
        p = Path(root)
        if not p.exists():
            continue
        found = sorted(p.glob('Blender*/blender.exe')) + sorted(p.glob('Blender.app/Contents/MacOS/Blender')) + [x for x in [p / 'blender'] if x.exists()]
        if found:
            return str(found[-1])
    return 'blender'


def arg(name, default=None, cast=str):
    if name in sys.argv:
        return cast(sys.argv[sys.argv.index(name) + 1])
    return default


def run(cmd, log=None, quiet=False):
    if not quiet:
        print(' '.join(str(c) for c in cmd))
    with open(log, 'a') if log else open(os.devnull, 'w') as f:
        return subprocess.Popen([str(c) for c in cmd], stdout=f if log else None, stderr=subprocess.STDOUT if log else None)


def quality_expr(q):
    """The engine's preset (EEVEE or Cycles) at render time."""
    return f"b3d.apply_quality('{q}')"


def clock(sec):
    sec = int(max(sec, 0))
    return f'{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}' if sec >= 3600 else f'{sec // 60}:{sec % 60:02d}'


def progress(procs, out, start, end, status_file, label):
    """Live bar while Blender renders: done/total, s per frame, ETA. In a terminal it redraws one line; when the
    output is a file or a pipe it prints a line every 10 %. Always mirrored to progress.json (Claude reads it)."""
    total = (end - start + 1) if end is not None else None
    done = lambda: sum(1 for p in out.glob('*.png') if p.stat().st_size > 0 and p.stem.isdigit()
                       and start <= int(p.stem) <= (end if end is not None else 10 ** 9))
    tty = sys.stdout.isatty()
    t0, first = time.time(), done()
    t_first = n_first = None
    last_step = -1
    print(f'Rendering {label}: frames {start}-{end if end is not None else "end"}, {first} already done. Ctrl+C stops (resumable).')
    try:
        while True:
            alive = any(p.poll() is None for p in procs)
            n = done()
            new, el = n - first, time.time() - t0
            if new and t_first is None:
                t_first, n_first = time.time(), n          # start-up and shader compile stay out of the rate
            rate = (time.time() - t_first) / (n - n_first) if (t_first and n > n_first) else None
            left = (total - n) * rate if (rate and total) else None
            frac = n / total if total else 0
            bar = '#' * int(frac * 30) + '.' * (30 - int(frac * 30))
            line = (f'[{bar}] {n}/{total or "?"} {frac:4.0%} | {f"{rate:.1f} s/frame" if rate else "warming up"} | '
                    f'elapsed {clock(el)} | ETA {clock(left) if left is not None else "--:--"}')
            status_file.write_text(json.dumps({'label': label, 'done': n, 'total': total, 'sec_per_frame': rate and round(rate, 2),
                                               'elapsed_s': round(el), 'eta_s': left and round(left), 'running': alive}))
            if tty:
                print('\r' + line, end='', flush=True)
            elif int(frac * 10) != last_step or not alive:
                last_step = int(frac * 10)
                print(line, flush=True)
            if not alive:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        for f in out.glob('*.png'):
            if f.stat().st_size == 0:
                f.unlink()                      # placeholders of the frames that were cut off
        print('\nStopped. Run the same command again to resume.')
        sys.exit(1)
    print(f'\nDone: {done()} frames in {out}, {clock(time.time() - t0)} wall'
          + ('' if all(p.returncode == 0 for p in procs) else '  (a Blender job failed: see render_*.log)'))


def pyexpr(code):
    """A --python-expr that imports b3d (so the stopwatch and helpers are available)."""
    return f"import sys; sys.path.insert(0, r'{HERE}'); import b3d; print('DEVICE', b3d.gpu()); {code}"


def main():
    ep = Path(sys.argv[1]).resolve()
    mode = sys.argv[2]
    blend = ep / 'scene.blend'
    B = blender()
    pct = arg('--pct', 100, int)
    if mode == 'build':
        p = run([B, '-b', '--factory-startup', '--python', ep / 'scene.py', '--', str(HERE), str(blend)])
        sys.exit(p.wait())
    if mode == 'still':
        frames = [int(a) for i, a in enumerate(sys.argv[3:], 3) if a.isdigit() and not sys.argv[i - 1].startswith('--')]
        (ep / 'stills').mkdir(exist_ok=True)
        q = arg('--quality', 'fast')
        for f in frames:
            t = time.time()
            p = run([B, '-b', blend, '--python-expr', pyexpr(f'import bpy; bpy.context.scene.render.resolution_percentage={pct}; {quality_expr(q)}'),
                     '-o', ep / 'stills' / 'f####', '-F', 'PNG', '-f', f], ep / 'render.log')
            p.wait()
            print(f'still {f}: {time.time() - t:.1f}s')
        return
    if mode == 'frames':
        jobs = arg('--jobs', 1, int)
        out = ep / 'frames'
        out.mkdir(exist_ok=True)
        log = ep / 'stopwatch.jsonl'
        meta = json.loads((ep / 'scene.json').read_text()) if (ep / 'scene.json').exists() else {}
        start = arg('--start', meta.get('frame_start', 1), int)
        end = arg('--end', meta.get('frame_end'), int)
        q = arg('--quality', 'fast')
        procs = []
        for k in range(jobs):
            cmd = [B, '-b', blend, '--python-expr',
                   pyexpr(f"import bpy; sc=bpy.context.scene; sc.render.resolution_percentage={pct}; sc.render.use_overwrite=False; "
                          f"sc.render.use_placeholder=True; b3d.stopwatch(r'{log}'); {quality_expr(q)}"),
                   '-o', out / '####', '-F', 'PNG', '-s', start + k] + (['-e', end] if end is not None else []) + ['-j', jobs, '-a']
            procs.append(run(cmd, ep / f'render_{k}.log', quiet=True))
        progress(procs, out, start, end, ep / 'progress.json', f'{ep.name} ({q}, {jobs} job{"s" if jobs > 1 else ""})')
        return
    if mode == 'times':
        rows = [json.loads(l) for l in open(ep / 'stopwatch.jsonl')]
        rows.sort(key=lambda r: -r['sec'])
        tot = sum(r['sec'] for r in rows)
        print(f'{len(rows)} frames, {tot / 60:.1f} GPU-min, mean {tot / max(len(rows), 1):.1f}s')
        for r in rows[:10]:
            print(f"  frame {r['frame']:5d}  {r['sec']:6.1f}s")
        return
    sys.exit(__doc__)


if __name__ == '__main__':
    main()

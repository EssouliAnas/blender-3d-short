"""Frames -> finished vertical short. The 'real camera' layer, in one ffmpeg pass.

python finish.py <episode_dir> [--audio mix.wav] [--captions] [--fps 30] [--grain 7] [--vignette 0.22] [--soft 0.6] [--size 1080x1920]
Writes <episode_dir>/out/<name>-final.mp4 (H.264 High, yuv420p, capped at 30 Mbps: grain does not compress, AAC 320k).
--captions burns <episode_dir>/captions.srt in (sound.py writes it in every voice mode): bold white, dark outline,
2-4 words a cue, in the lower third above the Shorts buttons; the font shrinks when a cue would be too wide.

Renders are too perfect; real cameras are not (references/realism.md). Kept here, not in Blender, so they can be
tuned without re-rendering: a slightly softer lens, vignette, film grain. Bloom and dispersion are in the Blender
compositor (b3d.compositor), motion blur in the renderer. Final size is 1080x1920 (the user's choice); frames
rendered at another size are scaled to it.
"""
import re, shutil, subprocess, sys
from pathlib import Path


def arg(name, default, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


ep = Path(sys.argv[1]).resolve()
fps = arg('--fps', 30, int)
grain = arg('--grain', 7, float)
vig = arg('--vignette', 0.22, float)
soft = arg('--soft', 0.6, float)
w, h = arg('--size', '1080x1920').split('x')
audio = arg('--audio', None)
out = ep / 'out'
out.mkdir(exist_ok=True)
dst = out / f'{ep.name}-final.mp4'

vf = (f'scale={w}:{h}:flags=lanczos,'
      f'gblur=sigma={soft},'                                   # softer lens
      f'vignette=angle={vig}:mode=forward,'                    # light falloff at the edges
      f'noise=alls={grain}:allf=t,'                            # temporal film grain (after scaling, so it stays fine)
      f'format=yuv420p')
FONT = next((f for f in ('C:/Windows/Fonts/ariblk.ttf', 'C:/Windows/Fonts/arialbd.ttf',
                         '/System/Library/Fonts/Supplemental/Arial Black.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
             if Path(f).exists()), None)


def srt(path):
    sec = lambda t: sum(float(x) * m for x, m in zip(t.replace(',', '.').split(':'), (3600, 60, 1)))
    for block in re.split(r'\n\s*\n', path.read_text(encoding='utf-8').strip()):
        lines = block.strip().splitlines()
        if len(lines) >= 3:
            a, b = lines[1].split(' --> ')
            yield sec(a), sec(b), ' '.join(lines[2:])


def caption_filters(width, height):
    """One drawtext per cue. Runs ffmpeg from out/caps/ so no Windows path ever needs filter escaping."""
    from PIL import ImageFont
    caps = out / 'caps'
    shutil.rmtree(caps, ignore_errors=True)
    caps.mkdir()
    shutil.copy(FONT, caps / 'font.ttf')
    base = int(width * 0.072)
    fs = []
    for i, (a, b, text) in enumerate(srt(ep / 'captions.srt')):
        (caps / f'c{i:03d}.txt').write_text(text, encoding='utf-8')
        size = base
        while size > 30 and ImageFont.truetype(FONT, size).getlength(text) > width * 0.86:
            size -= 2
        fs.append(f"drawtext=fontfile=font.ttf:textfile=c{i:03d}.txt:fontsize={size}:fontcolor=white:borderw={max(3, size // 12)}:"
                  f"bordercolor=black@0.85:shadowx=0:shadowy={size // 18}:shadowcolor=black@0.5:x=(w-text_w)/2:"
                  f"y=h*0.64-text_h/2:enable='between(t,{a:.3f},{b:.3f})'")
    return fs, caps


def new_ffmpeg():
    """ffmpeg 7+ reads a filter from a file with -/vf; older builds with -filter_script:v."""
    v = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True).stdout
    m = re.search(r'version n?(\d+)', v)
    return not m or int(m.group(1)) >= 7


cwd = None
if '--captions' in sys.argv:
    if not (ep / 'captions.srt').exists():
        sys.exit('no captions.srt: run sound.py <ep> captions (or voice / own) first')
    fs, cwd = caption_filters(int(w), int(h))
    vf = vf.replace(',format=yuv420p', '') + ',' + ','.join(fs) + ',format=yuv420p'
    (cwd / 'filter.txt').write_text(vf, encoding='utf-8')
cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-stats', '-framerate', str(fps), '-i', str(ep / 'frames' / '%04d.png')]
if audio:
    cmd += ['-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '320k', '-shortest']
cmd += ((['-/vf', 'filter.txt'] if new_ffmpeg() else ['-filter_script:v', 'filter.txt']) if cwd else ['-vf', vf]) + ['-c:v', 'libx264', '-profile:v', 'high', '-preset', 'slow', '-crf', '18', '-maxrate', '30M', '-bufsize', '60M',
        '-tune', 'grain',
        '-movflags', '+faststart', str(dst)]
print(' '.join(cmd[:6]), '...', dst.name)
sys.exit(subprocess.call(cmd, cwd=cwd) or print(dst))

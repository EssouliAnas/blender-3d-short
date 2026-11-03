"""Voice, sound effects and the mix for one episode, from <episode_dir>/episode.json.

python sound.py <episode_dir> voice          ElevenLabs TTS with timestamps -> audio/voice.wav + words.json
python sound.py <episode_dir> clone <sample.mp3> [<sample2> ...] [--name "My voice"]
                                             ElevenLabs instant voice clone of the USER'S OWN voice -> episode.json
                                             voice.id (then run `voice`). 1-3 min of clean speech in total.
python sound.py <episode_dir> own <recording.wav|mp3|m4a>
                                             the user's own voice-over -> audio/voice.wav + words.json (word times by
                                             faster-whisper if installed, else ElevenLabs speech-to-text if a key
                                             exists, else spread over the speech the silence detector finds)
python sound.py <episode_dir> captions       no voice: words.json timed from the script at "wps" (default 2.8) +
                                             captions.srt; finish.py --captions burns them in, the user adds the
                                             voice later in their editor (the SRT matches the timing)
python sound.py <episode_dir> sfx [--dry]    ElevenLabs sound generation for every clip not yet in audio/sfx/
python sound.py <episode_dir> mix            stems -> audio/mix.wav, mastered to "target_lufs" (no voice.wav = no voice)
Every API call reports the credits it used and appends them to <episode_dir>/costs.json.
Every voice mode also writes captions.srt (2-4 words a cue) so captions are always one flag away.

episode.json:
  "script": "If you ...",                        the whole voice-over (one steady tone)
  "voice": {"id": "...", "model": "eleven_multilingual_v2", "settings": {...}}     optional
  "fps": 30, "target_lufs": -14,
  "music": "path/to/music.mp3" or null,         a licensed track; level = mix rule
  "beds":  [{"name": "room", "prompt": "quiet hospital room tone", "secs": 20, "from": 0, "to": 9.5, "db": -24}]
  "sfx":   [{"name": "knock", "prompt": "dry bone knock", "secs": 1, "at": "bones", "db": -6, "lead": 2}]
            "at": a word of the script (first match; "bones#2" = second), or a frame number. Lands "lead" frames
            before the word starts (default 2), so the hit is on the exact frame the word lands.
Mix rule (the user's): music +3 dB over its default bed level, effects at half (-6 dB), voice unchanged.
"""
import base64, json, re, subprocess, sys, time, urllib.request
from pathlib import Path

import numpy as np

SR = 48000
ep = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
E = json.loads((ep / 'episode.json').read_text(encoding='utf-8'))
A = ep / 'audio'
(A / 'sfx').mkdir(parents=True, exist_ok=True)
FPS = E.get('fps', 30)


# ---------------------------------------------------------------- ElevenLabs

def key():
    for d in [ep, *ep.parents]:
        f = d / '.env'
        if f.exists():
            for line in f.read_text().splitlines():
                if line.startswith('ELEVENLABS_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"')
    sys.exit('No ELEVENLABS_API_KEY in any .env above the episode folder (or record the voice yourself: audio/voice.wav + words.json)')


def api(path, body=None):
    req = urllib.request.Request('https://api.elevenlabs.io' + path, headers={'xi-api-key': key(), 'Content-Type': 'application/json'},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def api_form(path, fields, files):
    """multipart/form-data POST (voice cloning, speech-to-text)."""
    b = '----b3d' + str(int(time.time() * 1000))
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, p in files:
        p = Path(p)
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{p.name}"\r\n'
                     f'Content-Type: application/octet-stream\r\n\r\n'.encode() + p.read_bytes() + b'\r\n')
    body = b''.join(parts) + f'--{b}--\r\n'.encode()
    req = urllib.request.Request('https://api.elevenlabs.io' + path, data=body,
                                 headers={'xi-api-key': key(), 'Content-Type': f'multipart/form-data; boundary={b}'})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def has_key():
    try:
        return bool(key_quiet())
    except Exception:
        return False


def key_quiet():
    for d in [ep, *ep.parents]:
        f = d / '.env'
        if f.exists() and any(l.startswith('ELEVENLABS_API_KEY=') and len(l) > 20 for l in f.read_text().splitlines()):
            return True
    return False


def credits():
    return json.loads(api('/v1/user/subscription'))['character_count']


def log_cost(step, used, note=''):
    p = ep / 'costs.json'
    rows = json.loads(p.read_text()) if p.exists() else []
    rows.append({'step': step, 'credits': used, 'note': note, 'time': time.strftime('%Y-%m-%d %H:%M')})
    p.write_text(json.dumps(rows, indent=2))
    print(f'{step}: {used} ElevenLabs credits ({note}); episode total {sum(r["credits"] for r in rows)}')


# ---------------------------------------------------------------- audio io

def decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def write(path, x):
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-i', '-', str(path)],
                   input=np.clip(x, -1, 1).astype(np.float32).tobytes(), check=True)


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)


def db(g):
    return 10 ** (g / 20)


# ---------------------------------------------------------------- steps

def voice():
    V = {'id': 'TX3LPaxmHKxFdv7VOQHJ', 'model': 'eleven_multilingual_v2',
         'settings': {'stability': 0.55, 'similarity_boost': 0.8, 'style': 0.15, 'use_speaker_boost': True}}
    V.update(E.get('voice', {}))
    text = E['script'].strip()
    before = credits()
    res = json.loads(api(f'/v1/text-to-speech/{V["id"]}/with-timestamps?output_format=mp3_44100_128',
                         {'text': text, 'model_id': V['model'], 'voice_settings': V['settings']}))
    (A / 'voice.mp3').write_bytes(base64.b64decode(res['audio_base64']))
    al = res['alignment']
    words, cur = [], None
    for ch, s, e in zip(al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']):
        if re.match(r"[\w'’-]", ch):
            if cur is None:
                cur = {'w': '', 's': s}
            cur['w'] += ch
            cur['e'] = e
        elif cur:
            words.append(cur)
            cur = None
    if cur:
        words.append(cur)
    write(A / 'voice.wav', decode(A / 'voice.mp3'))
    save_words(words)
    log_cost('voice', credits() - before, f'{len(text)} characters')


def save_words(words):
    (ep / 'words.json').write_text(json.dumps(words, indent=1))
    write_srt(words)
    dur = words[-1]['e'] if words else 0
    print(f'{len(words)} words in {dur:.1f} s = {len(words) / max(dur, 0.1):.2f} words/s -> words.json, captions.srt')


SMALL = {'a', 'an', 'the', 'of', 'to', 'in', 'on', 'at', 'and', 'or', 'but', 'your', 'my', 'is', 'are', 'for', 'with',
         'from', 'by', 'as', 'that', 'it', 'its', 'this', 'these', 'those', 'if', 'you', 'can', 'will'}


def cues(words, most=4):
    """2-4 word caption cues, broken at punctuation and at pauses over 0.25 s."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        small = re.sub(r'\W', '', w['w']).lower() in SMALL           # never leave "of" / "the" hanging at a cue's end
        nxt_small = nxt is not None and re.sub(r'\W', '', nxt['w']).lower() in SMALL
        end = (re.search(r'[.,!?;:]$', w['w']) or nxt is None or
               (not small and (len(cur) >= most or nxt['s'] - w['e'] > 0.25 or (len(cur) >= most - 1 and nxt_small)))
               or len(cur) >= most + 2)
        if end and (len(cur) >= 2 or nxt is None or re.search(r'[.!?]$', w['w'])):
            out.append({'text': ' '.join(x['w'] for x in cur), 's': cur[0]['s'], 'e': max(cur[-1]['e'], cur[0]['s'] + 0.4)})
            cur = []
    return out


def write_srt(words):
    t = lambda x: f'{int(x // 3600):02d}:{int(x // 60 % 60):02d}:{int(x % 60):02d},{int(round(x % 1 * 1000)) % 1000:03d}'
    cs = cues(words)
    (ep / 'captions.srt').write_text(''.join(f'{i}\n{t(c["s"])} --> {t(c["e"])}\n{c["text"]}\n\n' for i, c in enumerate(cs, 1)),
                                     encoding='utf-8')


def script_words():
    return re.findall(r"[\w'’-]+[.,!?;:]?", E['script'])


def captions():
    """No voice: time the script at a steady pace, so the picture, captions and a voice recorded later all agree."""
    wps = E.get('wps', 2.8)
    pause = {'.': 0.35, '!': 0.35, '?': 0.45, ',': 0.15, ';': 0.2, ':': 0.2}
    t, words = E.get('lead_in', 0.3), []
    for w in script_words():
        d = max(0.18, (len(re.sub(r'\W', '', w)) / 5.0) / wps)        # longer words take longer
        words.append({'w': w, 's': round(t, 3), 'e': round(t + d * 0.9, 3)})
        t += d + pause.get(w[-1], 0)
    save_words(words)
    print('No voice.wav: the mix will be music + effects only. Tell the user to record against captions.srt.')


def own(path):
    """The user's recording: clean it to voice.wav, then word times."""
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(path), '-af', 'highpass=f=70,loudnorm=I=-16:TP=-1.5',
                    '-ac', '2', '-ar', str(SR), str(A / 'voice.wav')], check=True)
    words = None
    try:
        from faster_whisper import WhisperModel
        segs, _ = WhisperModel('small', compute_type='int8').transcribe(str(A / 'voice.wav'), word_timestamps=True)
        words = [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3)} for s in segs for w in s.words]
        print('word times: faster-whisper')
    except ImportError:
        pass
    if words is None and has_key():
        before = credits()
        res = json.loads(api_form('/v1/speech-to-text', {'model_id': 'scribe_v1', 'timestamps_granularity': 'word'},
                                  [('file', A / 'voice.wav')]))
        words = [{'w': x['text'].strip(), 's': x['start'], 'e': x['end']} for x in res.get('words', []) if x.get('type', 'word') == 'word']
        log_cost('speech-to-text', credits() - before, 'word times of the user recording')
        print('word times: ElevenLabs speech-to-text')
    if words is None:
        words = spread(decode(A / 'voice.wav'))
        print('word times: estimated from silences (install faster-whisper for exact times)')
    save_words(words)


def spread(x):
    """Fallback: script words spread over the voiced stretches, proportional to their length."""
    env = np.abs(x).max(1)
    hop = SR // 100
    voiced = np.array([env[i:i + hop].max() > 0.02 for i in range(0, len(env), hop)])
    times = np.flatnonzero(voiced) / 100
    ws = script_words()
    lens = np.cumsum([0] + [len(w) for w in ws]) / max(1, sum(len(w) for w in ws))
    at = lambda f: float(times[min(len(times) - 1, int(f * (len(times) - 1)))]) if len(times) else f
    return [{'w': w, 's': round(at(lens[i]), 3), 'e': round(at(lens[i + 1]), 3)} for i, w in enumerate(ws)]


def clone(samples):
    """Instant voice clone. Only ever the user's own voice (or one they have written consent for)."""
    name = sys.argv[sys.argv.index('--name') + 1] if '--name' in sys.argv else f'{ep.name} voice'
    before = credits()
    res = json.loads(api_form('/v1/voices/add', {'name': name, 'remove_background_noise': 'true'}, [('files', s) for s in samples]))
    E.setdefault('voice', {})['id'] = res['voice_id']
    (ep / 'episode.json').write_text(json.dumps(E, indent=2), encoding='utf-8')
    print(f'cloned "{name}" -> voice id {res["voice_id"]} (saved in episode.json; reuse it for every episode)')
    log_cost('clone', credits() - before, f'{len(samples)} samples')


def clip(name):
    return A / 'sfx' / f'{name}.mp3'


def sfx():
    items = E.get('sfx', []) + E.get('beds', [])
    missing = [s for s in items if not clip(s['name']).exists()]
    print(f'{len(items)} clips, {len(missing)} to generate: {", ".join(s["name"] for s in missing) or "none"}')
    if not missing or '--dry' in sys.argv:
        return
    before = credits()
    for s in missing:
        clip(s['name']).write_bytes(api('/v1/sound-generation?output_format=mp3_44100_128',
                                        {'text': s['prompt'], 'duration_seconds': s.get('secs', 2), 'prompt_influence': 0.45}))
        print('  generated', s['name'])
    log_cost('sfx', credits() - before, f'{len(missing)} clips')


def word_time(cue, words):
    if isinstance(cue, (int, float)):
        return cue / FPS
    w, _, n = str(cue).partition('#')
    hits = [x for x in words if re.sub(r'\W', '', x['w']).lower() == re.sub(r'\W', '', w).lower()]
    if not hits:
        sys.exit(f'cue word "{w}" is not in the script')
    return hits[int(n or 1) - 1]['s']


def mix():
    words = json.loads((ep / 'words.json').read_text())
    v = decode(A / 'voice.wav') if (A / 'voice.wav').exists() else np.zeros((int((words[-1]['e'] if words else 1) * SR), 2), np.float32)
    total = len(v) + SR
    if E.get('seconds'):
        total = max(total, int(E['seconds'] * SR))
    out = np.zeros((total, 2), np.float32)
    out[:len(v)] += v
    loud = v[np.abs(v).max(1) > 0.01]
    vref = rms_db(loud) if len(loud) else -20                    # no voice: levels as if a voice sat at -20 dB
    for b in E.get('beds', []):
        x = decode(clip(b['name']))
        a, z = int(b.get('from', 0) * SR), int(b.get('to', total / SR) * SR)
        x = np.tile(x, (int(np.ceil((z - a) / len(x))), 1))[:z - a]
        fade = np.minimum(1, np.minimum(np.arange(len(x)), np.arange(len(x))[::-1]) / (0.3 * SR))[:, None]
        out[a:a + len(x)] += x / max(1e-9, np.abs(x).max()) * fade * db(b.get('db', -24))
    for s in E.get('sfx', []):
        x = decode(clip(s['name']))
        x = x / max(1e-9, np.abs(x).max())
        onset = int(np.argmax(np.abs(x).max(1) > 0.2))          # align the hit, not the clip's silent head
        at = int((word_time(s['at'], words) - s.get('lead', 2) / FPS) * SR) - onset
        a = max(0, at)
        x = x[a - at:][:total - a]
        out[a:a + len(x)] += x * db(s.get('db', -6))             # effects at half
    if E.get('music'):
        m = decode(Path(E['music']) if Path(E['music']).is_absolute() else ep / E['music'])
        m = np.tile(m, (int(np.ceil(total / len(m))), 1))[:total]
        m *= db(vref - 18 + 3 - rms_db(m))                       # default bed 18 dB under the voice, +3 dB rule
        out += m
    write(A / 'mix_pre.wav', out)
    target = E.get('target_lufs', -14)
    st = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(A / 'mix_pre.wav'), '-af',
                         f'loudnorm=I={target}:TP=-1:LRA=7:print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
    j = json.loads(st[st.rfind('{'):st.rfind('}') + 1])
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(A / 'mix_pre.wav'), '-af',
                    f"loudnorm=I={target}:TP=-1:LRA=7:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
                    f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true",
                    '-ar', str(SR), str(A / 'mix.wav')], check=True)
    print(f'mix -> {A / "mix.wav"} ({target} LUFS target, was {j["input_i"]})')


files, rest = [], iter(sys.argv[3:])
for a in rest:
    if a == '--name':
        next(rest, None)
    elif not a.startswith('--'):
        files.append(a)
{'voice': voice, 'sfx': sfx, 'mix': mix, 'captions': captions,
 'own': lambda: own(files[0]), 'clone': lambda: clone(files)}[mode]()

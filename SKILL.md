---
name: blender-3d-short
description: Make a realistic 3D explainer short (30-60 s, vertical 1080x1920) in real Blender, the "realistic human on a flat signature backdrop, camera dollies inside the body" genre. Starts by asking the user the voice (ElevenLabs voice, a clone of their own voice, their own recording, or no voice with burned-in captions), the look, the main character (their own rigged file, one made in Blender, a free downloaded one, or none), the render engine and the length. Measures reference shorts frame by frame, writes an original fact-checked script, builds the scene in Blender with Python (one-axis eased dolly camera, Khronos PBR Neutral, real downloaded assets, our own host), has a separate agent judge the stills to 8.5/10, renders with EEVEE fast (Cycles fast for skin, clouds, glass) with a live progress bar, mixes the sound and finishes with a real-camera layer and optional captions. Use when the user asks for a realistic 3D short, a Blender short, "a short like the stitches / blood vessels video", a body or how-things-work 3D explainer, or says "use the 3D short skill".
---

# Realistic 3D short (Blender + Python)

Every frame is a real Blender render of a scene Claude builds in Python. No AI image or video model.
Final output: 1080x1920, 30 fps, H.264 capped at 30 Mbps. Paths: `<skill>` = this folder. Episodes live in
`<project>/blender-shorts/<slug>/`, downloaded assets in `<project>/blender-shorts/assets/`, channel choices in
`<project>/blender-shorts/brand.json`. Run scripts with `python <skill>/scripts/<name>.py`.

Read first: `references/style.md` (the rules), `references/traps.md` (before inventing any fix).

## Setup (once per PC)
- Blender 5.x (found automatically under Program Files; else set `BLENDER=<path to blender.exe>`).
- `python -m pip install numpy opencv-python-headless pillow`; ffmpeg on PATH.
- Proof the pipeline works: copy `examples/test-cell/` to `blender-shorts/test-cell/`, then build, still, frames,
  finish. On an RTX 3080 Laptop, EEVEE fast renders its 90 frames at 1080x1920 in about 2 minutes.

## Step 0: kick-off questions (always, before any work)

Ask with the AskUserQuestion tool, in two rounds of up to four questions, then a third round that depends on the
voice answer. **If `blender-shorts/brand.json` exists, first ask one question: "Same settings as last time?"
(show them in one line) with "Yes" / "Change some". On "Yes" skip to round 3's topic-specific parts.**
Recommended option first. Save every answer to `brand.json` (channel-wide) and the episode's `episode.json`.

**Round 1: what and how it speaks**
1. *Topic*: "Suggest 3 for me" / "I have one" (they type it under Other). Suggestions: body or how-things-work
   questions that are pictures, checked on YouTube for originality of angle.
2. *Voice*:
   - **ElevenLabs voice** (recommended): a stock voice, generated from the script with exact word timings.
   - **Clone my voice (ElevenLabs)**: they upload 1-3 min of clean speech once; every episode then speaks in their
     voice. Only ever their own voice, or one they have written consent for.
   - **I'll record it myself**: they record the script; Claude cleans it, finds the word timings, builds the picture to it.
   - **No voice, captions only**: the script is timed at a steady 2.8 words/s, captions are burned in, and a
     `captions.srt` lets them record or add a voice later in their editor at exactly that timing.
3. *Length*: 30 s (recommended for a first one) / 45 s / 60 s. At 2.8 words/s that is ~80 / 120 / 165 words.
4. *Reference videos*: "No, use the built-in style rules" (recommended) / "Yes, I'll give files or links" (measured
   with `measure.py`, private study only).

**Round 2: the look**
1. *Look*: **Studio backdrop** (recommended: one signature colour behind everything, the genre's look) / Real-world
   photo backplates (stadium, street, sky behind the 3D) / Mix (backdrop, with real places for "where" beats).
2. *Backdrop colour* (skip if not using a backdrop): Peach `#F2D7C9` (ours so far) / Mint `#CFE8DF` / Deep navy
   `#1F2A44` / Custom (hex). Never the reference channel's colour.
3. *Main character*: "Is there a main character?" (`references/characters.md`)
   - **I'll provide a rigged character**: their .blend / .fbx / .glb file (Mixamo, Character Creator, a store).
   - **Make one for me** (recommended if they have none): built in Blender with MPFB, no accounts, our logo on the shirt.
   - **Download a free rigged one**: Claude proposes 2-3 candidates (source, licence, look); on sites that need an
     account (Mixamo, Renderpeople, Sketchfab) the user downloads it and gives the path.
   - **No character**: objects, body parts and places only.
   Once a main character exists (`assets/host/host.blend`), this question becomes "Use <name> again?".
4. *Render engine*:
   - **Auto** (recommended): EEVEE fast everywhere, Cycles fast only for shots that fail the judge on skin close-ups,
     clouds, glass or hair.
   - **EEVEE fast only**: the quickest, ~1 s a frame.
   - **Cycles fast only**: about 2x slower, softer and more natural light.
   - **High quality**: the `high` presets, about 2-3x slower than fast.

**Round 3: depends on the voice answer**
- ElevenLabs or clone: **the key.** Check for `ELEVENLABS_API_KEY=` in a `.env` in the project or above (never print
  it). If it is there, say "Found your ElevenLabs key" and do not ask. If not, ask:
  "Add your key: paste it here and I'll save it to `.env`, or add the line `ELEVENLABS_API_KEY=...` to `.env`
  yourself (keeps it out of the chat)". Save a pasted key to `<project>/.env` only, never echo it, never put it in
  any other file, commit or log.
- ElevenLabs: *Voice*: Calm narrator (default id in `sound.py`) / "Pick from my ElevenLabs library" (list with
  `GET /v1/voices`, show names only) / Voice ID (they type it). *Voice model*: **eleven_multilingual_v2**
  (recommended: steady, best word timings) / eleven_v3 (more expressive, less predictable).
- Clone: ask for the sample files (paths), then `sound.py <ep> clone <files> --name "<their name> voice"`; the
  voice id is saved and reused by every later episode.
- Own recording: tell them to wait until the script is approved, then record it in one take, phone at arm's length,
  quiet room, and give the file path. (Recording to the approved script is what keeps picture and voice in sync.)
- Main character, by the round 2 answer:
  - Provide: ask for the file path (and the texture folder if separate).
  - Make one: ask age range, build, and hair and clothing style (plain words); then ask to install MPFB.
  - Download: show the 2-3 candidates as options (name, look, licence, account needed) and let them pick.
- Every voice option: *Captions burned in?* Yes / No (no-voice always gets captions).
- Every option: *Music*: None, effects and room tone only (recommended for a first one) / My own track (file path,
  they confirm they have the rights) / YouTube Audio Library track (they download it and give the path).

Do not ask about anything else; everything below has a default. "Specific model" questions: there is no AI image
or video model in this pipeline. The choices that act like one are the render engine (round 2), the ElevenLabs
voice model (round 3), and the Claude model running the skill: Opus at high effort works best.

## Engine presets (the user's chosen settings, keep them)
- **EEVEE fast** (default, `b3d.EEVEE_PRESETS['fast']`): 16 samples, half-res ray tracing and GI, 1 shadow ray.
  ~0.9-1.2 s a frame at 1080p on the 3080, 99-99.9% similar to `high`.
- **Cycles fast** (`b3d.CYCLES_PRESETS['fast']`): 32 samples, 1 s time limit, OptiX denoiser, 2-3 bounces, Fast GI
  approximation, Persistent Data. ~1.7 s a frame. If the denoiser smear shows on a close-up, give that shot a 2 s limit.
- `--quality draft | fast | high` at render time, no rebuild. Engine per scene: `setup_render(engine=...)`, or
  `B3D_ENGINE=CYCLES python render.py <ep> build` to A/B without editing. Mixed engines in one short are fine (render
  each shot's frame range from its own .blend) if backdrop and grade match.

## Pipeline (save after every step; show the user stills, not walls of text)

1. **Topic and facts.** Work out every number and write it with its source in `episode.json` `science`. Shaky
   famous numbers get "Scientists estimate". The same topic as a big channel is fine, their words are not.
2. **Measure the reference** (only if round 1 said yes): `measure.py <folder> --out <ep>/reference.json`. Otherwise
   the defaults in style.md.
3. **Script** in `episode.json` (`examples/episode.template.json`): second person, ~2.8 words/s, the chosen length,
   the beat shape in style.md. Show it and wait for an OK. After the OK, "just do it" until the stills.
4. **Voice and timing**, by the round 1 answer:
   - ElevenLabs / clone: `sound.py <ep> voice` -> `audio/voice.wav`, `words.json`, `captions.srt`.
   - Own recording: wait for their file, then `sound.py <ep> own <file>` (word times: faster-whisper if installed,
     else ElevenLabs speech-to-text if there is a key, else estimated from silences; offer
     `pip install faster-whisper` if the estimate is off).
   - No voice: `sound.py <ep> captions` -> `words.json` + `captions.srt` at `"wps"` (2.8).
   Then write `shots.md`: per beat, the frame range (from the word times), the camera move (dolly in / hold+creep /
   pull out / fly-through) and what keeps moving during each hold. Max one hard cut per ~7 transitions.
5. **The 9-second test first.** One beat at full pipeline before the whole short: `scene.py` with `b3d` helpers.
   Render, finish, `measure.py`, and `compare.py reference.json ours.json` if there is a reference. **The delta is
   the to-do list.** Fix the camera until jerk and lateral drift match (one axis, eased keys).
6. **World and character.** Character first, by its path in `references/characters.md`, always through
   `b3d.import_character(path, height=1.75)`: it scales it to real height with the feet on the floor, drops stray
   cameras and lights, binds weighted parts to the rig and prints a report (rig type, parts not following the rig,
   face shapes x/52, missing textures). Fix every item in the report, then a turnaround still, then save
   `assets/host/host.blend`. World from `references/assets.md` (list downloads, source + licence + size, ask once).
   Rule: if a real one exists, download it, never model it.
7. **Stills and the judge.** `render.py <ep> still <frames...> --pct 50` for every beat. Then spawn a **separate
   agent** (Agent tool) with the stills and `references/realism.md`; it scores out of 10 and names the three worst
   giveaways. Fix, re-render, re-judge. **Render only at 8.5+.** Show the user the stills and the score. On "Auto"
   engine, a shot that fails on an EEVEE shortcut moves to Cycles fast here.
8. **Render.** Run `render.py <ep> frames` in the user's Terminal panel (run_in_terminal) so they watch the live
   bar (frames done, s per frame, ETA); read `<ep>/progress.json` to answer "how far is it?". Resumable. Then
   `render.py <ep> times`; if too slow, work down `references/render-speed.md` on the slowest frames.
9. **Sound.** `beds` (a room tone per world) and `sfx` (each on its word: "bone knock" on "bones") in
   `episode.json`, then `sound.py <ep> sfx` (needs a key; without one, skip effects or use files the user provides
   in `audio/sfx/<name>.mp3`) and `sound.py <ep> mix`. Mix rule: music +3 dB, effects at half, voice unchanged.
10. **Finish.** `finish.py <ep> --audio <ep>/audio/mix.wav [--captions]` -> `out/<slug>-final.mp4`. Watch it at
    phone size. No-voice episodes: also hand over `captions.srt` and say the voice goes in at those times.
11. **Report**: the final path, the judge's last score, render minutes, ElevenLabs credits (`costs.json`), and the
    credits text for the description (assets.md licences). Never claim the reference channel uses any tool.

## Scripts

| Script | Runs in | Does |
|---|---|---|
| `b3d.py` | Blender | render setup + presets (EEVEE/Cycles, GPU, look), backdrop + HDRI, shadow catcher (real on Cycles, faked on EEVEE), lights, one-axis eased dolly camera, materials, `import_character` (any rigged .blend/.fbx/.glb, scaled, bound, reported), `parent_to_bone`, shape keys, compositor, stopwatch |
| `render.py` | shell | `build`, `still`, `frames` (live progress bar, `progress.json`, resumable), `times`; `--quality` |
| `sound.py` | shell | `voice` (ElevenLabs), `clone`, `own` (user recording), `captions` (no voice), `sfx`, `mix`; every voice mode writes `captions.srt` |
| `finish.py` | shell | frames + mix -> 1080x1920 mp4, real-camera layer, `--captions` burn-in |
| `measure.py` / `compare.py` | shell | frame-by-frame metrics of any video; reference vs ours with a TO DO list |

`scene.py` is called as `blender -b --factory-startup --python scene.py -- <skill>/scripts <ep>/scene.blend`;
start from `examples/test-cell/scene.py` (call `shadow_catcher` after the lights).

# The style: realistic 3D explainer shorts

The genre: one realistic human (or body part, object, planet) on a flat signature backdrop, a calm voice explaining
what happens inside, real 3D rendered in Blender. Numbers below are the public figures Mr omi reported after
measuring the biggest channel in the genre frame by frame (video `_fIoJ_ywGfY`, 2026-11-03). Use them as defaults;
when the user hands you reference videos, run `scripts/measure.py` on them and trust your own numbers instead.

## Measured rules (the defaults)

| What | Rule |
|---|---|
| Camera | **The camera is the whole trick.** One continuous shot for a whole beat (31 s with zero cuts in a top short). Straight dolly IN to explain, a HOLD while the subject keeps moving, a slow creep, an eased pull OUT to resolve. **Zero lateral motion: no pans, no orbit.** |
| Camera smoothness | Every move eased. Jerk (3rd derivative of position) is the number to beat; our first try had 8x the reference's jerk. |
| Transitions | Hard cuts only ~1 in 7. The rest are motion transitions: the camera flies straight into the next scene (zoom-through), or a whip. |
| Micro-motion | Something always moves during a hold: a new stitch lands every 6-8 frames, a thread draws itself along its path, blood flows, the subject breathes. |
| Speech | Median **2.77 words per second**: calm, slower than cartoon shorts (~3.7). |
| Opening line | Second person hypothetical: "If you ...", "What happens if you ...", "How long are your ...?". 16 of the top 50 open the same way. |
| Backdrop | One flat, saturated signature colour behind everything (measure its exact RGB). |
| Sound | Loud, dense mix with almost no dynamic range (the reference sits near -5 LUFS). A room-tone bed, stacked hits on every big moment, reverb that follows the camera. 19 tracks for a 9 s test was normal. |
| Length | 30-60 s (the user picks 30 / 45 / 60 in step 0). |

## Ours, not theirs (non-negotiable)

- **Our own signature backdrop colour**, decided once per channel and written in `brand.json` (the test uses
  peach `#F2D7C9`). Not the reference's blue.
- **Our own host character**, built once (`references/characters.md`), with our logo on the shirt. Never a scan
  with someone else's logo, never a likeness of a real person.
- **Same topic is fine, never their words.** Write the script ourselves and fact-check it (`episode.json`
  `science`). When a famous number is shaky, say "Scientists estimate" (the "100,000 km of blood vessels" figure
  has a weak original source).
- Never copy a reference's shot order beat for beat for publishing. "Recreate it beat for beat" is only for a
  private side-by-side test.
- Never say a channel's name in the voice-over or description, never claim a channel is made with any tool.

## Beat shape of a 30 s short

1. Hook (0-3 s): the hypothetical, camera already moving in.
2. Inside (3-20 s): dolly in to the mechanism, hold, creep while it plays out; 2-3 motion transitions between
   scales (body -> organ -> cell).
3. Number (20-26 s): one real, sourced number on a picture that makes it physical (vessels wrapped round the Earth).
4. Resolve (26-30 s): eased pull-out to the whole person, a last line that lands on the final frame.

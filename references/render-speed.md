# Render speed: from 11 hours to about 1

Rule: **keep only what looks identical.** Before and after every speed change, render the same still and diff it
(`ffmpeg -i a.png -i b.png -lavfi ssim -f null -`; keep the change if SSIM > 0.985 and it looks the same at phone
size). Start from numbers: `render.py frames` writes `stopwatch.jsonl`, `render.py <ep> times` lists the slowest
frames. Speed work goes to the slowest frames first.

| Step | Typical gain | How |
|---|---|---|
| EEVEE instead of Cycles | ~7x | the default (`setup_render(engine='EEVEE')`): test cell 2.7 s/frame at 1080x1920 vs ~20 s in Cycles. Cycles only for shots that fail on EEVEE. |
| EEVEE `fast` preset | 2.3x more | the default (`b3d.EEVEE_PRESETS`): 16 samples, half-res ray tracing and GI, 1 shadow ray. 2.7 -> 1.2 s/frame, SSIM 0.990-0.999 vs `high`; a faint speckle in dark glossy areas at 100 % crop, hidden by the finish grain. |
| Final size 1080x1920 | - | the user's choice: no 2K render, no upscale. |
| Persistent Data | big on static worlds | `render.use_persistent_data` (on in `setup_render`). Without it every building, tree and car is rebuilt into the light/BVH lists every frame: city frames went 19 s -> 8 s. |
| Haze is not a light | big | A world/scene volume used as haze gets sampled like a light. Prefer compositor mist (Mist pass) for haze; if it must be a volume, keep it out of the light tree and give it few bounces. |
| Volume step rate honoured | big on clouds | Check the volume settings actually apply in your Blender's volume mode (one newer mode ignored the step-rate setting: 40 s -> 14 s once fixed). Measure a cloud frame before and after. |
| Adaptive sampling + denoise | 1.5-2x | on in `setup_render` (threshold 0.02, OptiX denoiser on RTX). |
| Fewer bounces | 1.2x | 8 total, 3 diffuse, 3 glossy, caustics off (defaults in `setup_render`). |
| Two Blenders at once | 1.3-1.8x wall | `render.py frames --jobs 2` (each renders every 2nd frame). Watch VRAM on 8 GB cards. |
| Instancing | memory, speed | trees, cars, AC units as collection instances / geometry nodes, never copies. |

Stop when the next gain would cost quality (it stopped at 61 minutes; "under 50" was only possible by losing
quality, so it was refused).

On this PC (RTX 3080 Laptop, 8 GB), test cell: EEVEE fast 1.2 s/frame, high 2.7 s/frame at 1080x1920 (first frame
12-27 s: shader compile); Cycles 5.5 s/frame at 540x960. Persistent Data, light tree, volume step rate and `--jobs` are Cycles
settings; on EEVEE the levers are `taa_render_samples`, ray-tracing resolution and shadow rays. A process without
the GPU enabled falls back to the CPU (~40 s/frame): `render.py` calls `b3d.gpu()` for you.

## What the EEVEE benchmark showed (test cell, 1080x1920, one setting changed at a time)

| Setting | s/frame | Similarity to high | Verdict |
|---|---|---|---|
| high (64 samples) | 3.45 | 1.000 | baseline |
| 16 samples | 1.64 | 0.9955 | **the lever**: in `fast` |
| 8 samples | 1.34 | 0.990 | `draft` |
| 1 sample | 1.44 | 0.915 | visibly noisy, no faster: ~1.3 s/frame is fixed overhead |
| ray tracing half res | 3.40 | - | no gain alone; cheap insurance in heavy scenes, in `fast` |
| ray tracing off / PROBE | 3.61 / 8.56 | 0.994 | slower: keep SCREEN |
| shadow resolution 0.5 | 7.56 | - | SLOWER: keep 1.0 |
| motion blur off | 3.73 | - | no gain: keep it on |
| compositor on GPU | 4.15 | - | no gain: keep CPU |

Timings on this laptop GPU swing up to 2x between runs (power and heat states): only trust differences bigger
than that, and re-measure on heavy scenes (volumes, a city) where shadows and volumetrics start to cost.

## EEVEE fast vs Cycles fast (5 s test cell, 150 frames, 1080x1920, 2026-11-03)

| | EEVEE `fast` | Cycles `fast` (32 samples, 1 s limit, OptiX, 2-3 bounces, Fast GI, Persistent Data) |
|---|---|---|
| s per frame | 0.9 | 1.7 (the 1 s limit stopped it at ~17/32 samples) |
| 5 s clip | 2.1 GPU-min | 4.3 GPU-min |
| Look | crisp, faint speckle in dark glossy areas | softer, the denoiser smears the dimple and leaves a pale rim on edges; more natural floor shadow |

Verdict: EEVEE fast stays the default. Cycles fast is only 2x slower, so it is a cheap switch for the shots that
need real light (skin, clouds, glass). Give those shots `time_limit` 2 s if the 1 s smear shows.

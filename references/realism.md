# Realism: the still checklist and the "real camera" layer

## The judge (step 7 of SKILL.md)

After every fix, a **separate agent** judges the stills: one that did not build them and is not told what was
just fixed. Give it the stills (phone size, 540x960 is enough), this checklist and the reference stills if any.
It returns a score out of 10 and the three worst problems, ranked. **Render only at 8.5 or above.**
(The sequence that worked: 7, 7.5, 8.5, render.)

Brief it like this:
> You are a viewer scrolling Shorts on a phone. Score these stills out of 10 for "this is real footage, not CGI".
> Use the checklist. Name the three things that give it away first, each with where in the frame. Do not be kind.

1. **Silhouette reads at phone size** in under a second (what is it, where is it).
2. **Skin is matte with pores** and light glows through thin parts (ears, fingers, nostrils). No wax, no plastic.
3. **Nothing floats**: contact shadows under feet, objects, decals sit IN the surface (no bright strip).
4. **Bounce light is plausible**: a green field tints chins green; a backdrop tints the rim. Before changing a
   material colour, turn off the suspect bounce source and look again.
5. **Highlights roll off** (no flat-white patches); the backdrop stays saturated.
6. **The lens is imperfect**: soft corners, bloom on bright spots, vignette, fine grain. A tack-sharp, noise-free
   frame reads as CGI.
7. **Scale cues are right**: hair thickness, pore size, depth of field shallow on close-ups, deep on the wide.
8. **Real-world assets are real**: photo backplate, scanned facades, NASA Earth, scanned bones. Nothing that has
   a real version is hand-modelled.
9. **No CG regularity**: tiles, trees, cars, clouds vary (scale, rotation, tint); no visible repeats.
10. **One idea per frame**: the thing the voice is talking about is the brightest, sharpest thing in frame.
11. **Brand**: our backdrop colour, our character, our logo; no third-party logos anywhere.

## The real-camera layer (where each piece lives)

| Imperfection | Where | Default |
|---|---|---|
| Motion blur on fast moves | EEVEE or Cycles (`setup_render(motion_blur=True)`) | shutter 0.5 |
| Depth of field on close-ups | camera (`dolly_camera(dof=2.8)`) | f/2.8 close, off on wides |
| Bloom / glow round bright spots | Blender compositor (`b3d.compositor(bloom=)`) | 0.5-0.7 |
| Slight lens dispersion | Blender compositor | 0.004 |
| Softer lens | `finish.py --soft` | 0.6 px gaussian at 1080p |
| Vignette | `finish.py --vignette` | 0.22 rad (0.35 reads as a filter) |
| Film grain | `finish.py --grain` | 7, temporal |
| View transform | `b3d.set_look` | Khronos PBR Neutral |

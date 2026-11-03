# Traps (read before inventing a fix)

Each one cost a day somewhere. Symptom -> cause -> fix.

## Characters
- **Need bare skin, the scan wears trousers.** A 3D scan is one solid surface; there is no leg under the
  trousers. Pick the character for the shot (bare forearm for stitches) or use a parametric character
  (characters.md), never "just delete the clothes".
- **Scan face looks stiff.** A scan's face rig is a jaw and a few bones. A scan is not built for acting. Use a
  character with face shape keys (52 ARKit-style shapes: browInnerUp, eyeWide, jawOpen, ...).
- **MetaHuman is a dead end here.** Its add-on needs an Epic account and an access token (Claude may not create
  accounts), and the public code lacks Epic's compiled rig library. Use the open-source path in characters.md.
- **Eyes, teeth, hair, shirt float away when he moves.** They were never bound to the armature.
  `b3d.bind_to_armature(rig)` and re-check a still at the most extreme pose.
- **Shirt has someone else's logo.** Replace the texture with ours before any still is shown.
- **Looks like a video game character** (waxy skin, heavy lips, bowl cut): matte skin with pores and subsurface
  scattering (`b3d.skin`), a real hair style, smaller lips via shape keys. Judge it at phone size.

## Surfaces and decals
- **Bright strip inside a wound/decal.** The decal floats 0.25 mm above the skin, but at render time Blender
  triangulates the skin along the other diagonal and the skin pokes through. Triangulate the skin first
  (Triangulate modifier, same as render), build the decal from those exact triangles, and bind it with Surface
  Deform so it moves with every step.
- **Wound interior is flat red.** Poly Haven has no flesh textures (all 869 checked). A scanned sponge texture,
  tinted, reads as flesh.
- **Teeth look green.** Not the teeth: green bounce light from the grass below. Check bounce before editing a
  material; the fix was deleting the fix (an "ivory" tint had turned the whole mouth beige).

## World
- **3D grass renders almost black.** Use a real stadium/landscape photo as a backplate, with an invisible
  shadow-catcher floor (`b3d.shadow_catcher`): the photo gives the grass and the mowing stripes, the 3D field
  only catches the shadows.
- **Hand-built stadium looks like AI slop.** Look at what the reference actually shows (a field floating in light
  colour, no stadium). Rule: **if a real one exists, download it; never build it by hand** (assets.md).
- **Clouds are solid blobs.** Use volumetric clouds (Principled Volume with noise density) that scatter light
  and cast shadows.
- **Every piece is real but the whole still looks fake: too perfect.** Real cameras are not perfect: softer lens,
  bloom, vignette, grain, motion blur on fast moves (realism.md, finish.py).

## Colour
- **Signature backdrop looks muted.** The view transform desaturates bright colours (AgX).
- **Swapping to Standard clips the highlights** to flat white. Use **Khronos PBR Neutral** (`b3d.set_look`): it
  keeps the backdrop saturated and rolls highlights off.

## Render
- **EEVEE has no shadow catcher.** `b3d.shadow_catcher` fakes one on EEVEE: the floor takes the backdrop colour
  times its own lighting and fades into the backdrop 1-3 m from the centre (`fade=`). Call it AFTER the lights. A
  dark band or ring on the floor = the fade starts too far out; a lighter patch = raise `lit`. Big subjects need a
  bigger `fade`.
- **EEVEE shortcuts that read as CG:** subsurface on skin close-ups, volumetric clouds, coloured bounce, glass.
  Those shots go to Cycles.
- **11 hours.** See render-speed.md. Biggest wins: Persistent Data (the BVH was rebuilt every frame), haze not
  counted as a light, the volume step rate actually honoured, EEVEE for most shots, two Blenders at once (Cycles).
- **"3000x faster" tutorials.** Keep only settings whose stills look identical to the slow render (diff them).

## Sound
- **Effect too loud** (said by ear). Measure it and pull it down by the measured amount (one stitch hit was 11 LU
  too hot). Then the user rule: music +3 dB, effects at half (-6 dB).

## Measuring
- **Backdrop measures darker than the colour you set.** Two causes: Khronos PBR Neutral renders a set sRGB colour
  about 8 levels darker (242,215,201 came out 234,207,193), and the finish vignette darkens the border that
  `measure.py` samples. Compare backdrops on raw frames, or the reference against our *finished* file only.
- **hold_share is 0 on our render.** Correct when there is creep: the camera never fully stops. Tracked points on
  a subject that fills the frame also count its own rotation as camera motion; judge holds on wides.

## Imported characters
- **Character is 180 m tall / tiny.** FBX is usually in centimetres. `b3d.import_character(height=1.75)` rescales
  from the real mesh bounds; never type a scale by hand.
- **A stray "Icosphere" in a glTF import.** The importer's bone display shape. `import_character` hides it and
  leaves it out of the height measurement.
- **Parts jump when bound.** Re-parenting without keeping the world matrix moves them. `bind_to_armature` only
  adds the Armature modifier; `parent_to_bone` keeps the world matrix.

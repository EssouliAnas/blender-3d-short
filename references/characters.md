# The main character: ask, then build or bring it in once

One main character per channel (or per series), saved as `blender-shorts/assets/host/host.blend` and imported into
every episode with `b3d.import_character`. That is why he never drifts between shorts. Step 0 asks which path.

## The four answers to "Is there a main character?"

| Answer | What happens | Claude can do it alone? |
|---|---|---|
| **No character** | Objects, body parts, places only. Skip this file. | yes |
| **I'll provide a rigged character** | The user gives a `.blend`, `.fbx`, `.glb`/`.gltf` (or `.obj`, unrigged). Imported and checked (below). | yes, from their file |
| **Make one for me** | Built with MPFB inside Blender, no accounts (below). | yes, after the user OKs installing MPFB |
| **Download a free rigged one** | Claude proposes 2-3 candidates with source, licence, look and download steps; the user picks. | only from no-login sources; sites that need an account, the user downloads and gives the path |

Whichever path: never a likeness of a real person, never a famous or trademarked character, never someone else's
logo on the clothes. Our logo goes on the shirt (`assets/host/shirt_logo.png`).

## Path 1: the user's own rigged character

1. Ask for the file path (and the texture folder if separate). FBX from Mixamo, Character Creator, Daz exports,
   Renderpeople, a `.blend` from Blender Market etc. all work. VRM needs the VRM add-on: ask, or have them export FBX.
2. `root, rig, rep = b3d.import_character(path, height=1.75)` in a test scene, and read the printed report:
   - `rig_type` (mixamo / rigify / mpfb / other) and `bones`: no rig = it cannot walk; offer Mixamo auto-rig (path 3).
   - `not_following_rig`: parts that will float away on the first move. Weighted ones are bound automatically;
     unweighted ones (eyes, teeth, hats) go on the head bone with `b3d.parent_to_bone(obj, rig, '<head bone>')`.
   - `arkit_face_shapes` (x/52): 52 = full face capture set, expressions are easy; 0 = only jaw/bone face, keep
     him to neutral faces or add MPFB face shapes.
   - `missing_textures`: ask for the texture folder before any still.
   - `textures`: look for third-party logos.
   - `height_m_before`: 180 means centimetres (normal for FBX), already rescaled.
3. Render a turnaround still (front, 3/4, side, face close-up) and the most extreme pose of the episode. Judge with
   realism.md. Then save `assets/host/host.blend`.

## Path 2: make one (MPFB)

1. **MPFB** (the MakeHuman plugin for Blender) from Blender's official extension site (Edit > Preferences > Get
   Extensions, search "MPFB"). Free, no account, runs locally. Ask before installing it.
2. New human: body proportions (not a likeness of anyone), the default or game-engine rig, a real hair style (no
   bowl cut), eyebrows, eyelashes, teeth, tongue. Ask the user 3 things: age range, build, hair and clothing style.
3. Face: add MPFB's face rig / expression shape keys. If this MPFB version offers ARKit-compatible face shape keys,
   use them; write the list it provides into this file.
4. Clothes with our logo; `b3d.skin()` look (matte, pores, subsurface); eyes with a wet cornea (rough 0.05,
   IOR 1.376); teeth judged under neutral light first (traps.md: green teeth were bounce light).
5. Run it through `import_character` once anyway (it binds and reports), turnaround still, save `host.blend`.

## Path 3: download a free rigged one

Propose 2-3 options in one message (name, look, licence, size, what account it needs) and let the user pick:

| Source | Look | Licence | Account |
|---|---|---|---|
| Mixamo (Adobe) | semi-realistic people, plus auto-rigging of any humanoid mesh, plus walk/idle animations | free to use in videos | Adobe account: **the user downloads** (FBX, "with skin"), gives the path |
| Renderpeople free rigged samples | photoreal scanned people | free samples, check the sample licence | account: the user downloads |
| Sketchfab (filter: downloadable, rigged, CC-BY or CC0) | anything | per model, credit CC-BY authors | account: the user downloads |
| Quaternius / Kenney | stylised, low-poly | CC0 | none: Claude may download after the user's OK |
| Poly Haven | no characters (props, HDRIs only) | CC0 | none |

Rules: Claude never creates accounts or signs in; it gives the user the exact page and steps. Before downloading
anything itself it states filename, source, licence and size and waits for an OK. Credit CC-BY authors in the
description (`episode.json` `credits`). Downloads go to `blender-shorts/assets/<source>/`; nothing in them is run.
Then path 1 from step 2.

## In an episode

```python
root, rig, rep = b3d.import_character(r'.../blender-shorts/assets/host/host.blend', height=1.75, location=(0, 0, 0))
```

Characters barely move (a walk cycle, breathing, one expression per beat). The camera and the inside-the-body
animation carry the life. Mixamo animations (walk, idle, surprised) retarget onto a Mixamo rig directly.

## When the shot needs the inside of the body

Hide or fade the skin (alpha or a cut-away on the shot side only) and show the system: bones from BodyParts3D,
vessels from a generator (branching curves from the heart, bright red arteries out, darker veins back, denser near
the skin so the silhouette still reads).

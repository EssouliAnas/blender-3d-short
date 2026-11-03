# Assets: if a real one exists, download it

Never hand-model something that exists as a scan, a photo or a dataset. Before downloading, list every file
(source, licence, size) for the user and get one OK per episode. Keep a `credits` list in `episode.json` and
paste it into the YouTube description. Downloads go in `assets/<source>/` beside the episodes (outside the skill),
one folder per source; never run anything that comes with them.

| Need | Source | Licence | Notes |
|---|---|---|---|
| HDRIs, textures, simple models | Poly Haven (polyhaven.com, API `api.polyhaven.com/files/<id>`) | CC0 | No flesh textures: use a scanned sponge for wound interiors. |
| Photo backplates (stadium, street, sky) | Poly Haven HDRIs (use a crop as plate), Wikimedia Commons, Unsplash | CC0 / per file | Plate + `b3d.shadow_catcher` = real grass and stripes for free. |
| Bones, organs | BodyParts3D, Database Center for Life Science, Japan | CC BY-SA 2.1 JP | Credit it. Humerus, radius, ulna etc. as OBJ. |
| Earth, clouds, city lights | NASA Visible Earth: Blue Marble, Earth's City Lights | NASA imagery, credit "NASA" | Sphere + day map + cloud layer + night lights on the dark side + thin atmosphere that fades with altitude. |
| Buildings, city | CC0 modular facade kits (Kenney, Quaternius, Poly Haven) | CC0 | 440 buildings from one scanned facade kit (walls, windows, shop fronts, roof edges), instanced. |
| Field / sports markings | Wikimedia Commons diagrams | CC BY-SA (credit the author) | Project onto a plane. |
| Humans | MPFB (characters.md) | Generated models are CC0 | No accounts. |
| Music | A licensed track the user owns, or YouTube Audio Library | per track | Credit as the track asks. |
| Sound effects | ElevenLabs sound generation (`sound.py sfx`) | per ElevenLabs plan | Credits logged in `costs.json`. |

Things Claude does not do: create accounts, accept licence terms on someone's behalf, use assets that need a
login token (MetaHuman, Sketchfab downloads, Renderpeople full scans). Ask the user to download those themselves.

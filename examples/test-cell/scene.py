"""Pipeline test: a red blood cell on the signature backdrop. Dolly in, hold with a creep, eased pull-out.
Built by: python <skill>/scripts/render.py <this folder> build   (Blender passes the skill scripts dir and blend path)
"""
import math, sys

skill_scripts, blend_path = sys.argv[sys.argv.index('--') + 1:][:2]
sys.path.insert(0, skill_scripts)
import bpy
import b3d

b3d.clean()
s = b3d.setup_render(fps=30, res=(1080, 1920), samples=64)
s.frame_start, s.frame_end = 1, 90
b3d.backdrop((242, 215, 201), light_strength=0.6)     # our signature backdrop (peach), not the reference's

# The cell: a flattened sphere with a dimple on both sides (biconcave disc), wet tissue look.
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1, location=(0, 0, 1.2))
cell = bpy.context.object
cell.name = 'Cell'
for v in cell.data.vertices:
    r = math.hypot(v.co.x, v.co.y)
    r = min(r, 1.0)
    v.co.z = math.copysign((0.06 + 0.55 * r * r) * math.sqrt(max(0.0, 1 - r * r)), v.co.z)   # thin middle, thick rim
bpy.ops.object.shade_smooth()
cell.modifiers.new('Sub', 'SUBSURF').levels = 1
cell.rotation_euler = (math.radians(62), 0, math.radians(20))
m = b3d.principled('Cell', (0.48, 0.04, 0.05), rough=0.42, sss=0.6, sss_radius=(1.0, 0.15, 0.1), coat=0.2, bump=(60, 0.12))
b3d.give(cell, m)
cell.keyframe_insert('rotation_euler', frame=1)
cell.rotation_euler.z += math.radians(25)            # the subject keeps moving while the camera holds
cell.keyframe_insert('rotation_euler', frame=90)

b3d.studio_lights(target=(0, 0, 1.2), scale=1.2)
b3d.shadow_catcher(z=0)                           # after the lights: on EEVEE it measures them
b3d.dolly_camera(start=(0, -9, 2.2), target=(0, 0, 1.2), lens=50, creep=0.15,
                 keys=[(1, 0), (30, 4.5), (60, 4.5), (90, 1.0)])
b3d.compositor(bloom=0.5)
print('ENGINE', s.render.engine, 'LOOK', s.view_settings.view_transform)
b3d.save(blend_path)

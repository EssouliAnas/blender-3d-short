"""Blender-side helpers for realistic 3D shorts. Runs INSIDE Blender (5.x):

    import sys; sys.path.insert(0, r'<skill>/scripts'); import b3d

Every episode's scene.py builds its world with these, so every short gets the same camera grammar, look and speed
settings. Units are metres, frames are at the scene fps.
"""
import json, math, os, time

import bpy
from mathutils import Vector


# ---------------------------------------------------------------- render setup

def setup_render(fps=30, res=(1080, 1920), samples=96, device='OPTIX', motion_blur=True, engine='EEVEE', quality='fast'):
    """engine='EEVEE' (default): ~2 s a frame at 1080p, good for most shots. engine='CYCLES': path tracing on the GPU
    for the shots EEVEE fakes badly (skin close-ups, volumetric clouds, strong bounce light); see render-speed.md.
    quality (EEVEE): 'fast' (default, watchable), 'draft' (previews), 'high' (the old settings); see EEVEE_PRESETS.
    `samples` only applies to Cycles."""
    s = bpy.context.scene
    s.render.fps = fps
    engine = os.environ.get('B3D_ENGINE', engine)      # B3D_ENGINE=CYCLES python render.py ... build: A/B any scene
    if engine.upper().startswith('EEVEE'):
        setup_eevee(s, fps, res, motion_blur)
        eevee_quality(os.environ.get('B3D_QUALITY', quality))
        return s
    s.render.engine = 'CYCLES'
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.use_persistent_data = True          # keep the BVH between frames: the big one for static worlds
    s.render.use_motion_blur = motion_blur
    s.render.motion_blur_shutter = 0.5
    s.render.film_transparent = False
    c = s.cycles
    backend = gpu(device)
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    try:
        c.denoiser = 'OPTIX' if backend == 'OPTIX' else 'OPENIMAGEDENOISE'
    except TypeError:
        pass
    c.caustics_reflective = c.caustics_refractive = False
    c.blur_glossy = 1.0
    c.volume_step_rate = 4.0                     # check it is honoured: traps.md "volumes ignore the step rate"
    s.render.image_settings.file_format = 'PNG'
    s.render.image_settings.color_depth = '8'
    set_look()
    cycles_quality(os.environ.get('B3D_QUALITY', quality), samples if samples != 96 else None)
    return s


# The "fast Cycles" recipe: few samples, a hard time limit per frame, the OptiX denoiser on the GPU's tensor cores,
# 2-3 bounces, Fast GI approximation instead of full indirect light, Persistent Data (set in setup_render).
CYCLES_PRESETS = {
    'draft': {'samples': 16, 'time_limit': 0.5, 'adaptive_threshold': 0.1, 'max_bounces': 2, 'diffuse_bounces': 2,
              'glossy_bounces': 2, 'transmission_bounces': 2, 'volume_bounces': 0, 'transparent_max_bounces': 4,
              'use_fast_gi': True},
    'fast': {'samples': 32, 'time_limit': 1.0, 'adaptive_threshold': 0.05, 'max_bounces': 3, 'diffuse_bounces': 2,
             'glossy_bounces': 3, 'transmission_bounces': 3, 'volume_bounces': 0, 'transparent_max_bounces': 4,
             'use_fast_gi': True},
    'high': {'samples': 256, 'time_limit': 0.0, 'adaptive_threshold': 0.02, 'max_bounces': 8, 'diffuse_bounces': 3,
             'glossy_bounces': 3, 'transmission_bounces': 6, 'volume_bounces': 1, 'transparent_max_bounces': 8,
             'use_fast_gi': False},
}


def cycles_quality(name='fast', samples=None):
    """Apply a Cycles preset. time_limit (s) stops sampling and hands the frame to the denoiser."""
    backend = gpu()
    for sc in bpy.data.scenes:
        c = sc.cycles
        for k, v in CYCLES_PRESETS[name].items():
            if hasattr(c, k):
                setattr(c, k, v)
        if samples:
            c.samples = samples
        c.fast_gi_method = 'REPLACE'             # AO-style approximation replaces the slow indirect bounces
        c.ao_bounces_render = 1
        if sc.world:
            sc.world.light_settings.distance = 2.0
        c.use_denoising = True
        try:
            c.denoiser = 'OPTIX' if backend == 'OPTIX' else 'OPENIMAGEDENOISE'
        except TypeError:
            pass
        c.denoising_use_gpu = True
        c.preview_denoising_start_sample = 1     # viewport only; the final render denoises once at the end
        sc.render.use_persistent_data = True
    return name


def apply_quality(name='fast'):
    """render.py --quality <name>: the preset of whichever engine the scene uses, at render time."""
    return eevee_quality(name) if is_eevee() else cycles_quality(name)


def setup_eevee(s, fps, res, motion_blur):
    """EEVEE with ray-traced reflections/GI and soft ray-traced shadows. eevee_quality() then sets the cost."""
    for e in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):   # 5.x name first, 4.2-4.5 name second
        try:
            s.render.engine = e
            break
        except TypeError:
            continue
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.use_motion_blur = motion_blur
    s.render.motion_blur_shutter = 0.5
    ev = s.eevee
    ev.use_raytracing = True
    ev.ray_tracing_method = 'SCREEN'            # PROBE was 4x slower and no better
    ev.ray_tracing_options.use_denoise = True
    ev.use_fast_gi = True
    ev.fast_gi_method = 'GLOBAL_ILLUMINATION'
    ev.use_shadows = True
    ev.shadow_resolution_scale = 1.0            # 0.5 was SLOWER in the benchmark, keep 1.0
    ev.use_volumetric_shadows = True
    s.render.image_settings.file_format = 'PNG'
    s.render.image_settings.color_depth = '8'
    s.render.image_settings.compression = 15
    set_look()
    return s


# Measured on the test cell, RTX 3080 Laptop, 1080x1920 (references/render-speed.md). Samples are the only big
# lever: 64 -> 16 halved the frame time at 99.6% similarity (SSIM 0.9955); ~1.3 s per frame is fixed overhead
# (scene sync, compositor, PNG write) that no setting removes. The rest only matters in heavy scenes (volumes,
# many lights), so 'fast' trims it where it is invisible at phone size.
EEVEE_PRESETS = {
    'draft': {'taa_render_samples': 8, 'rt.resolution_scale': '2', 'shadow_ray_count': 1, 'shadow_step_count': 4,
              'fast_gi_resolution': '2', 'fast_gi_step_count': 4, 'volumetric_tile_size': '16', 'volumetric_samples': 16,
              'volumetric_shadow_samples': 8},                                     # SSIM 0.990: previews, stills
    'fast': {'taa_render_samples': 16, 'rt.resolution_scale': '2', 'shadow_ray_count': 1, 'shadow_step_count': 6,
             'fast_gi_resolution': '2', 'fast_gi_step_count': 6, 'volumetric_tile_size': '8', 'volumetric_samples': 32,
             'volumetric_shadow_samples': 12},                                     # SSIM 0.995: the default
    'high': {'taa_render_samples': 64, 'rt.resolution_scale': '1', 'shadow_ray_count': 2, 'shadow_step_count': 8,
             'fast_gi_resolution': '1', 'fast_gi_step_count': 8, 'volumetric_tile_size': '4', 'volumetric_samples': 64,
             'volumetric_shadow_samples': 16},                                     # the old settings, 2x the time
}


def eevee_quality(name='fast'):
    """Apply an EEVEE preset to every scene. render.py --quality <name> calls it at render time, so the same
    .blend renders draft stills and fast finals without a rebuild."""
    for sc in bpy.data.scenes:
        ev = sc.eevee
        for k, v in EEVEE_PRESETS[name].items():
            obj, attr = (ev.ray_tracing_options, k[3:]) if k.startswith('rt.') else (ev, k)
            if hasattr(obj, attr):
                setattr(obj, attr, v)
    return name


def is_eevee():
    return 'EEVEE' in bpy.context.scene.render.engine


def gpu(device='OPTIX'):
    """The device list lives in Blender's preferences, not in the .blend: every render process must call this, or
    Cycles silently falls back to the CPU (render.py does). Returns the backend in use."""
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for t in (device, 'OPTIX', 'CUDA', 'METAL', 'HIP', 'NONE'):
        try:
            prefs.compute_device_type = t
            prefs.get_devices()
            if t == 'NONE' or any(d.type == t for d in prefs.devices):
                break
        except Exception:
            continue
    on = False
    for d in prefs.devices:
        d.use = d.type == prefs.compute_device_type
        on |= d.use
    for sc in bpy.data.scenes:
        sc.cycles.device = 'GPU' if on else 'CPU'
    return prefs.compute_device_type if on else 'CPU'


def set_look(exposure=0.0, look_contrast='Medium High Contrast'):
    """Khronos PBR Neutral keeps a saturated backdrop saturated without burning highlights to flat white.
    Standard clips, AgX desaturates bright colours (the 'muted backdrop' trap). Falls back to AgX."""
    v = bpy.context.scene.view_settings
    for vt in ('Khronos PBR Neutral', 'AgX', 'Filmic', 'Standard'):
        try:
            v.view_transform = vt
            break
        except TypeError:
            continue
    try:
        v.look = look_contrast if v.view_transform != 'Khronos PBR Neutral' else 'None'
    except TypeError:
        v.look = 'None'
    v.exposure = exposure
    return v.view_transform


# ---------------------------------------------------------------- world

def backdrop(color, light_strength=1.0, hdri=None, hdri_strength=1.0):
    """Camera sees one flat signature colour; objects are lit by an HDRI (or the colour) behind it."""
    BACKDROP.update(color=color, strength=hdri_strength if hdri else light_strength)
    w = bpy.context.scene.world or bpy.data.worlds.new('World')
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    cam_bg = nt.nodes.new('ShaderNodeBackground')
    cam_bg.inputs['Color'].default_value = (*srgb_to_linear(color), 1)
    cam_bg.inputs['Strength'].default_value = 1.0
    light = nt.nodes.new('ShaderNodeBackground')
    light.inputs['Strength'].default_value = hdri_strength if hdri else light_strength
    if hdri:
        env = nt.nodes.new('ShaderNodeTexEnvironment')
        env.image = bpy.data.images.load(hdri, check_existing=True)
        nt.links.new(env.outputs['Color'], light.inputs['Color'])
    else:
        light.inputs['Color'].default_value = (*srgb_to_linear(color), 1)
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(light.outputs['Background'], mix.inputs[1])
    nt.links.new(cam_bg.outputs['Background'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return w


def shadow_catcher(size=40, z=0.0, color=None, lit=None, fade=(1.0, 3.0)):
    """Invisible floor that only keeps shadows: objects sit on the backdrop or on a photo backplate.
    Cycles: a real shadow catcher. EEVEE has none, so the floor shows the backdrop colour times its own lighting
    (Shader to RGB / its unshadowed brightness `lit`): shadows darken it, everywhere else matches the backdrop.
    `lit` is measured automatically from the lights if not given; raise it if the floor shows as a lighter patch.
    `fade` (metres from the floor centre): the EEVEE floor blends fully into the backdrop between these radii, so
    light falloff far from the lamps never shows as a darker band or a horizon line."""
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    p = bpy.context.object
    p.name = 'ShadowCatcher'
    if not is_eevee():
        p.is_shadow_catcher = True
        return p
    color = color or BACKDROP.get('color', (1, 1, 1))
    m = bpy.data.materials.new('ShadowCatcherEevee')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    dif = nt.nodes.new('ShaderNodeBsdfDiffuse')
    dif.inputs['Color'].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new('ShaderNodeShaderToRGB')
    norm = nt.nodes.new('ShaderNodeMath')
    norm.operation = 'DIVIDE'
    norm.use_clamp = True
    norm.inputs[1].default_value = lit or floor_light(z)
    tint = nt.nodes.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    tint.blend_type = 'MULTIPLY'
    tint.inputs['Factor'].default_value = 1.0
    tint.inputs[6].default_value = (*srgb_to_linear(color), 1)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    dist = nt.nodes.new('ShaderNodeVectorMath')
    dist.operation = 'LENGTH'
    ramp = nt.nodes.new('ShaderNodeMapRange')
    ramp.interpolation_type = 'SMOOTHSTEP'
    ramp.inputs['From Min'].default_value, ramp.inputs['From Max'].default_value = fade
    edge = nt.nodes.new('ShaderNodeMix')
    edge.data_type = 'RGBA'
    edge.inputs[7].default_value = (*srgb_to_linear(color), 1)
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs['Color'], norm.inputs[0])
    nt.links.new(norm.outputs[0], tint.inputs[7])
    nt.links.new(tc.outputs['Object'], dist.inputs[0])
    nt.links.new(dist.outputs['Value'], ramp.inputs['Value'])
    nt.links.new(ramp.outputs['Result'], edge.inputs['Factor'])
    nt.links.new(tint.outputs[2], edge.inputs[6])
    nt.links.new(edge.outputs[2], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    give(p, m)
    return p


def floor_light(z=0.0):
    """Rough irradiance of a white diffuse floor at the origin from the area lights + world (for the EEVEE catcher)."""
    total = BACKDROP.get('strength', 1.0)
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and o.data.type == 'AREA':
            d = o.location - Vector((0, 0, z))
            facing = max(0.0, -(o.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized().dot(-d.normalized()))
            total += o.data.energy * facing * max(0.0, d.normalized().z) / (math.pi * 4 * d.length_squared)
    return max(total, 1e-3)


BACKDROP = {}


def area_light(name, loc, target, power, size=2.0, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, 'AREA')
    d.energy, d.size, d.color = power, size, color
    o = bpy.data.objects.new(name, d)
    bpy.context.collection.objects.link(o)
    o.location = loc
    aim(o, target)
    return o


def studio_lights(target=(0, 0, 1), scale=1.0):
    """Key from front-left above, cool rim from behind, soft fill. Every light should be motivated in a real
    world shot; on the flat backdrop this is the standard three-point."""
    t = Vector(target)
    return [area_light('Key', t + Vector((-2.5, -3.0, 2.5)) * scale, t, 600 * scale ** 2, 2.5, (1, 0.96, 0.9)),
            area_light('Rim', t + Vector((2.0, 3.0, 2.0)) * scale, t, 400 * scale ** 2, 1.5, (0.85, 0.92, 1)),
            area_light('Fill', t + Vector((3.0, -2.0, 0.5)) * scale, t, 120 * scale ** 2, 4.0)]


# ---------------------------------------------------------------- camera grammar

def aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def dolly_camera(start, target, keys, lens=50, name='Cam', creep=0.0, dof=None):
    """The genre's camera: ONE axis, no pan, no orbit. It moves along the line start->target only.

    keys: [(frame, metres_travelled_towards_target), ...] e.g. [(1,0),(40,2.2),(120,2.2),(170,0.4)]
          = dolly in to explain, hold, pull back out to resolve. Every key is eased (no linear moves, no jerk).
    creep: metres of slow forward drift added across every hold, so nothing is ever frozen.
    dof:   None or f-stop (focus distance follows the target)."""
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start, cd.clip_end = 0.01, 5000
    cam = bpy.data.objects.new(name, cd)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    start, target = Vector(start), Vector(target)
    axis = (target - start).normalized()
    cam.location = start
    aim(cam, target)
    prev = None
    for i, (f, d) in enumerate(keys):
        if prev is not None and creep and abs(d - prev[1]) < 1e-6:
            d = prev[1] + creep
            keys[i] = (f, d)
        cam.location = start + axis * d
        cam.keyframe_insert('location', frame=f)
        prev = (f, d)
    ease(cam)
    if dof:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = dof
        foc = bpy.data.objects.new(name + '_focus', None)
        bpy.context.collection.objects.link(foc)
        foc.location = target
        cd.dof.focus_object = foc
    return cam


def ease(obj):
    """Bezier with flat tangents on every key: ease-in-out everywhere, zero velocity at holds."""
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    for fc in fcurves(ad.action):
        for k in fc.keyframe_points:
            k.interpolation = 'BEZIER'
            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'


def fcurves(action):
    """Blender 4.4+ layered actions keep fcurves in channelbags; older ones on the action."""
    if hasattr(action, 'fcurves') and len(action.fcurves):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                out += list(bag.fcurves)
    return out


# ---------------------------------------------------------------- materials

def principled(name, color, rough=0.5, metal=0.0, sss=0.0, sss_radius=(1.0, 0.35, 0.2), coat=0.0, bump=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*srgb_to_linear(color), 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss
        b.inputs['Subsurface Radius'].default_value = sss_radius
    if coat:
        b.inputs['Coat Weight'].default_value = coat
    if bump:
        add_noise_bump(m, b, *bump)
    return m


def add_noise_bump(m, bsdf, scale=400.0, strength=0.15):
    """Pores / micro surface: a real surface is never perfectly smooth."""
    nt = m.node_tree
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = 8
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = strength
    nt.links.new(n.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], bsdf.inputs['Normal'])


def skin(name='Skin', tone=(0.80, 0.60, 0.50)):
    """Matte skin with pores and subsurface scattering (light glows through ears and fingers)."""
    return principled(name, tone, rough=0.55, sss=0.25, sss_radius=(1.0, 0.4, 0.25), bump=(600, 0.08))


def wet_tissue(name='Tissue', color=(0.55, 0.08, 0.08)):
    return principled(name, color, rough=0.25, sss=0.5, sss_radius=(1.0, 0.2, 0.1), coat=0.6, bump=(120, 0.25))


def bone(name='Bone'):
    return principled(name, (0.86, 0.80, 0.68), rough=0.6, sss=0.1, bump=(90, 0.3))


def image_material(name, path, emission=False):
    """A real photo/texture on a surface (backplates, NASA Earth maps, scanned decals)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(path, check_existing=True)
    b = nt.nodes['Principled BSDF']
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    if emission:
        nt.links.new(tex.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = 1.0
    return m


def give(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


# ---------------------------------------------------------------- characters

def bind_to_armature(armature, objects=None):
    """Eyes, teeth, hair, brows and clothes must follow the rig, or they float off on the first move (traps.md)."""
    objects = objects or [o for o in bpy.data.objects if o.type == 'MESH']
    bones = {b.name for b in armature.data.bones}
    fixed = []
    for o in objects:
        if o.type != 'MESH' or o.parent_type == 'BONE':
            continue
        mods = [m for m in o.modifiers if m.type == 'ARMATURE']
        if any(m.object for m in mods):
            continue                              # already follows a rig
        if not bones & {g.name for g in o.vertex_groups}:
            continue                              # no weights for this rig: parent it to the head bone by hand
        (mods[0] if mods else o.modifiers.new('Armature', 'ARMATURE')).object = armature
        fixed.append(o.name)                      # no re-parenting: the mesh stays exactly where it is
    return fixed


def parent_to_bone(obj, armature, bone):
    """Unweighted parts (eyes, teeth, a hat) ride on one bone, usually the head, keeping their place."""
    mw = obj.matrix_world.copy()
    obj.parent, obj.parent_type, obj.parent_bone = armature, 'BONE', bone
    bpy.context.view_layer.update()
    obj.matrix_world = mw


def shape_key(obj, name, frames_values):
    """Animate a face shape key (ARKit names: browInnerUp, eyeWideLeft, jawOpen, ...): [(frame, 0..1), ...]."""
    kb = obj.data.shape_keys.key_blocks[name]
    for f, v in frames_values:
        kb.value = v
        kb.keyframe_insert('value', frame=f)
    ease(obj.data.shape_keys)


ARKIT = ['browDownLeft', 'browDownRight', 'browInnerUp', 'browOuterUpLeft', 'browOuterUpRight', 'cheekPuff',
         'cheekSquintLeft', 'cheekSquintRight', 'eyeBlinkLeft', 'eyeBlinkRight', 'eyeLookDownLeft', 'eyeLookDownRight',
         'eyeLookInLeft', 'eyeLookInRight', 'eyeLookOutLeft', 'eyeLookOutRight', 'eyeLookUpLeft', 'eyeLookUpRight',
         'eyeSquintLeft', 'eyeSquintRight', 'eyeWideLeft', 'eyeWideRight', 'jawForward', 'jawLeft', 'jawOpen', 'jawRight',
         'mouthClose', 'mouthDimpleLeft', 'mouthDimpleRight', 'mouthFrownLeft', 'mouthFrownRight', 'mouthFunnel',
         'mouthLeft', 'mouthLowerDownLeft', 'mouthLowerDownRight', 'mouthPressLeft', 'mouthPressRight', 'mouthPucker',
         'mouthRight', 'mouthRollLower', 'mouthRollUpper', 'mouthShrugLower', 'mouthShrugUpper', 'mouthSmileLeft',
         'mouthSmileRight', 'mouthStretchLeft', 'mouthStretchRight', 'mouthUpperUpLeft', 'mouthUpperUpRight',
         'noseSneerLeft', 'noseSneerRight', 'tongueOut']


def import_character(path, height=1.75, location=(0, 0, 0), name='Character'):
    """Bring any rigged character into the scene, ready to use: .blend (appends every object), .fbx (Mixamo and most
    stores), .glb/.gltf, .obj (no rig). Drops imported cameras and lights, puts everything under one root empty,
    scales it to `height` metres (None = keep) with the feet on the floor at `location`, binds weighted meshes that
    are not following the rig. Returns (root, rig or None, report) and prints the report: read it before any still.
    """
    path = os.path.abspath(path)
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext == '.blend':
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = list(src.objects)
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
        for o in dst.objects:
            if o is not None:
                coll.objects.link(o)
    elif ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=True)
    elif ext in ('.glb', '.gltf'):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == '.obj':
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise ValueError(f'{ext}: convert it to .fbx or .glb first (VRM needs the VRM add-on, ask the user)')
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.type in ('CAMERA', 'LIGHT')]:
        bpy.data.objects.remove(o)
    new = [o for o in bpy.data.objects if o not in before]
    rigs = sorted([o for o in new if o.type == 'ARMATURE'], key=lambda o: -len(o.data.bones))
    rig = rigs[0] if rigs else None
    shapes = {pb.custom_shape for r in rigs for pb in r.pose.bones if pb.custom_shape}
    for o in [o for o in new if o in shapes]:          # bone display widgets (the glTF importer's "Icosphere")
        o.hide_render = o.hide_viewport = True
    meshes = [o for o in new if o.type == 'MESH' and o not in shapes]

    root = bpy.data.objects.new(name + 'Root', None)
    bpy.context.scene.collection.objects.link(root)
    for o in new:
        if o.parent is None:
            mw = o.matrix_world.copy()
            o.parent = root
            o.matrix_world = mw
    bound = bind_to_armature(rig, meshes) if rig else []
    unbound = [o.name for o in meshes if rig and not any(m.type == 'ARMATURE' and m.object for m in o.modifiers)
               and o.parent_type != 'BONE']

    bpy.context.view_layer.update()
    lo, hi = bbox(meshes)
    measured = hi.z - lo.z
    if height and measured > 1e-6:
        root.scale = [height / measured] * 3
    bpy.context.view_layer.update()
    lo, hi = bbox(meshes)
    root.location += Vector(location) - Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))

    keys = sorted({k.name for o in meshes if o.data.shape_keys for k in o.data.shape_keys.key_blocks[1:]})
    bones = [b.name for b in rig.data.bones] if rig else []
    images = sorted({i.name for i in bpy.data.images if i.source == 'FILE' and (i.users and not i.has_data and not i.packed_file)
                     and not os.path.exists(bpy.path.abspath(i.filepath))})
    report = {
        'file': os.path.basename(path), 'rig': rig.name if rig else None, 'bones': len(bones),
        'rig_type': ('mixamo' if any(b.startswith('mixamorig') for b in bones) else
                     'rigify' if any(b.startswith(('DEF-', 'ORG-')) for b in bones) else
                     'mpfb/makehuman' if 'spine01' in bones or 'upperarm01.L' in bones else 'other' if bones else 'none'),
        'meshes': [o.name for o in meshes], 'bound_now': bound, 'not_following_rig': unbound,
        'height_m_before': round(measured, 3), 'height_m': height,
        'shape_keys': len(keys), 'arkit_face_shapes': f'{sum(k in keys for k in ARKIT)}/52',
        'actions': [a.name for a in bpy.data.actions if a.users],
        'missing_textures': images,
        'textures': sorted(i.name for i in bpy.data.images if i.source == 'FILE')[:40],
    }
    print('CHARACTER', json.dumps(report))
    return root, rig, report


def bbox(objs):
    """World-space bounds of the evaluated meshes (modifiers and the rig pose applied)."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        ev = o.evaluated_get(dg)
        pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    if not pts:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


# ---------------------------------------------------------------- post (inside Blender)

def compositor(bloom=0.6, dispersion=0.004, distortion=-0.006):
    """Bloom around bright spots + a little lens dispersion. Vignette, grain and softness are added in finish.py
    (ffmpeg), so they stay adjustable without re-rendering."""
    s = bpy.context.scene
    ng = bpy.data.node_groups.new('Lens', 'CompositorNodeTree')
    if hasattr(s, 'compositing_node_group'):
        s.compositing_node_group = ng
        out = ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        go = ng.nodes.new('NodeGroupOutput')
        sink = go.inputs[0]
    else:
        s.use_nodes = True
        ng = s.node_tree
        ng.nodes.clear()
        sink = ng.nodes.new('CompositorNodeComposite').inputs[0]
    rl = ng.nodes.new('CompositorNodeRLayers')
    glare = ng.nodes.new('CompositorNodeGlare')
    set_input_or_attr(glare, 'Type', 'glare_type', 'Bloom')
    set_input_or_attr(glare, 'Quality', 'quality', 'High')
    set_input_or_attr(glare, 'Threshold', 'threshold', 1.0)
    set_input_or_attr(glare, 'Strength', 'mix', bloom)
    lens = ng.nodes.new('CompositorNodeLensdist')
    set_input_or_attr(lens, 'Dispersion', 'dispersion', dispersion)
    set_input_or_attr(lens, 'Distortion', 'distortion', distortion)
    ng.links.new(rl.outputs['Image'], glare.inputs['Image'])
    ng.links.new(glare.outputs['Image'], lens.inputs['Image'])
    ng.links.new(lens.outputs['Image'], sink)
    return ng


def set_input_or_attr(node, socket, attr, value):
    """Blender 4.x keeps node options as attributes, 5.x as input sockets (menus take the label)."""
    if socket in node.inputs:
        try:
            node.inputs[socket].default_value = value
            return
        except (TypeError, ValueError):
            pass
    if hasattr(node, attr):
        try:
            setattr(node, attr, value.upper() if isinstance(value, str) else value)
        except TypeError:
            setattr(node, attr, value)


# ---------------------------------------------------------------- the stopwatch

def stopwatch(log_path):
    """Per-frame render time to a JSONL file, so render-speed work starts from numbers (render.py adds it)."""
    state = {}

    def pre(scene, *_):
        state['t'] = time.time()

    def post(scene, *_):
        with open(log_path, 'a') as f:
            f.write(json.dumps({'frame': scene.frame_current, 'sec': round(time.time() - state.get('t', time.time()), 2)}) + '\n')

    bpy.app.handlers.render_pre.append(pre)
    bpy.app.handlers.render_post.append(post)


# ---------------------------------------------------------------- misc

def srgb_to_linear(c):
    c = [x / 255 if max(c) > 1 else x for x in c]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def clean():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def save(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    s = bpy.context.scene
    with open(os.path.join(os.path.dirname(path), 'scene.json'), 'w') as f:      # render.py's progress bar reads it
        json.dump({'frame_start': s.frame_start, 'frame_end': s.frame_end, 'fps': s.render.fps,
                   'engine': s.render.engine, 'res': [s.render.resolution_x, s.render.resolution_y]}, f)

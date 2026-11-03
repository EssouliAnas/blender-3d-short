"""The delta between the reference and our render is the to-do list.

python compare.py <reference measure.json> <ours measure.json>
Either file may be a single-video report or a folder report (its 'summary' is used). Prints every metric side by
side and a TO DO line for each one that is off by more than its tolerance.
"""
import json, sys

# metric: (tolerance, kind, what to do when ours is too high, too low)
RULES = {
    ('camera', 'lateral_speed'): (0.02, 'abs', 'camera drifts sideways: lock the move to one dolly axis (b3d.dolly_camera), no orbit', None),
    ('camera', 'vertical_speed'): (0.02, 'abs', 'camera bobs vertically: keep the dolly line level or aim it straight at the subject', None),
    ('camera', 'zoom_speed'): (0.35, 'rel', 'dolly moves are faster than the reference: lengthen them', 'dolly moves are slower: shorten them or travel further'),
    ('camera', 'hold_share'): (0.35, 'rel', 'too many dead holds: add creep or keep the subject moving', 'never settles: add holds while the explanation lands'),
    ('camera', 'jerk_lateral'): (0.5, 'rel', 'sideways jerk: ease every key (b3d.ease), remove orbit/shake', None),
    ('camera', 'jerk_zoom'): (0.5, 'rel', 'zoom jerk: longer eases, fewer keys, no linear segments', None),
    ('cuts', 'per_minute'): (0.3, 'rel', 'too many hard cuts: turn most into motion transitions (fly-through, whip)', 'too few cuts for the reference pace'),
    ('light', 'luma'): (0.12, 'rel', 'brighter than the reference: lower exposure', 'darker than the reference: raise exposure or the backdrop'),
    ('light', 'contrast'): (0.2, 'rel', 'more contrast than the reference: softer key, more fill', 'flatter than the reference: stronger key, deeper shadows'),
    ('light', 'saturation'): (0.2, 'rel', 'over-saturated: check the view transform and the backdrop colour', 'muted: view transform desaturates (use Khronos PBR Neutral), or the grade is too grey'),
    ('sound', 'lufs'): (2.0, 'abs', 'mix louder than the target', 'mix quieter than the target: raise the master'),
    ('sound', 'lra'): (2.0, 'abs', 'too dynamic: compress the mix, raise the room tone', None),
    ('speech', 'words_per_second'): (0.15, 'rel', 'speech faster than the reference: cut words or slow the voice', 'speech slower: tighten pauses'),
}


def load(p):
    j = json.load(open(p))
    return j.get('summary', j)


ref, ours = load(sys.argv[1]), load(sys.argv[2])
todo = []
print(f'{"metric":28s} {"reference":>11s} {"ours":>11s}')
for sec in ('camera', 'cuts', 'light', 'sound', 'speech'):
    for k in sorted(set(ref.get(sec, {})) | set(ours.get(sec, {}))):
        a, b = ref.get(sec, {}).get(k), ours.get(sec, {}).get(k)
        print(f'{sec + "." + k:28s} {str(a):>11s} {str(b):>11s}')
        rule = RULES.get((sec, k))
        if not rule or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            continue
        tol, kind, high, low = rule
        d = b - a
        off = abs(d) > (tol if kind == 'abs' else tol * max(abs(a), 1e-6))
        if off and (high if d > 0 else low):
            todo.append(f'{sec}.{k}: {a} -> {b}. {high if d > 0 else low}')
print('\nTO DO' if todo else '\nNothing off by more than its tolerance.')
for t in todo:
    print(' -', t)

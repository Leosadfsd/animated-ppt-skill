#!/usr/bin/env python3
"""Validate a portable scene, bind exported objects, group complete units and add timing."""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET
import animate

SCRIPTS = Path(__file__).resolve().parent


def known_fields(value, allowed, label):
    unknown = set(value) - set(allowed.split())
    if unknown:
        raise ValueError(label + ' has unknown fields: ' + ', '.join(sorted(unknown)))


def load_scene(path):
    path = Path(path).resolve()
    scene = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(scene, dict) or scene.get('version') != 1:
        raise ValueError('Scene must be an object with version 1')
    known_fields(scene, 'version title width height font background color slides', 'Scene')
    for key in ('width', 'height'):
        value = scene.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(key + ' must be a finite positive number')
    if not isinstance(scene.get('font'), str) or not scene['font'].strip():
        raise ValueError('Declare a font explicitly')
    if not isinstance(scene.get('slides'), list) or not scene['slides']:
        raise ValueError('Scene needs nonempty slides')
    plan = {'version': 1, 'slides': []}
    for number, page in enumerate(scene['slides'], 1):
        if not isinstance(page, dict) or not isinstance(page.get('units'), list) or not page['units']:
            raise ValueError('Each slide needs nonempty units')
        known_fields(page, 'title background notes sources units', 'Slide')
        if not isinstance(page.get('notes', ''), str):
            raise ValueError('notes must be text')
        if not isinstance(page.get('sources', []), list) or any(not isinstance(source, str) for source in page.get('sources', [])):
            raise ValueError('sources must be an array of strings')
        names, motions = set(), []
        for unit in page['units']:
            if not isinstance(unit, dict):
                raise ValueError('Each unit must be an object')
            known_fields(unit, 'name beat cue from delay_ms duration_ms elements', 'Unit')
            name = unit.get('name')
            if not isinstance(name, str) or not name or '__' in name or name in names:
                raise ValueError('Unit names must be unique, nonempty and cannot contain __')
            names.add(name)
            animate.integer(unit.get('beat'), -1, 'beat')
            if not isinstance(unit.get('cue', ''), str):
                raise ValueError('cue must be text')
            elements = unit.get('elements')
            if not isinstance(elements, list) or not elements:
                raise ValueError('Each unit needs nonempty elements')
            for item in elements:
                if not isinstance(item, dict) or item.get('type') not in ('text', 'image'):
                    raise ValueError('Elements must be text or image objects')
                known_fields(item, 'type frame rotation text size font color bold italic align' if item['type'] == 'text' else 'type frame rotation src fit', 'Element')
                frame = item.get('frame')
                if not isinstance(frame, list) or len(frame) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in frame):
                    raise ValueError('frame needs four finite numbers [x,y,width,height]')
                x, y, w, h = frame
                if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > scene['width'] + .01 or y + h > scene['height'] + .01:
                    raise ValueError('Element frame is outside the slide: ' + name)
                rotation = item.get('rotation', 0)
                if type(rotation) not in (int, float) or not math.isfinite(rotation):
                    raise ValueError('rotation must be finite')
                if item['type'] == 'text':
                    if not isinstance(item.get('text'), str) or not item['text']:
                        raise ValueError('Text elements need nonempty text')
                    size = item.get('size', 42)
                    if type(size) not in (int, float) or not math.isfinite(size) or size <= 0:
                        raise ValueError('Text size must be positive')
                    if 'font' in item and (not isinstance(item['font'], str) or not item['font'].strip()):
                        raise ValueError('Element font must be nonempty text')
                else:
                    source = item.get('src')
                    if not isinstance(source, str) or not source or Path(source).is_absolute() or ':' in source or '\\' in source:
                        raise ValueError('Image src must be a portable relative path')
                    full = (path.parent / source).resolve()
                    if not full.is_relative_to(path.parent) or not full.is_file():
                        raise ValueError('Missing image or path outside scene directory: ' + source)
                    if full.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
                        raise ValueError('Scene image format must be PNG or JPEG')
                    if item.get('fit', 'contain') not in ('contain', 'cover'):
                        raise ValueError('Image fit must be contain or cover')
            if unit['beat'] >= 0:
                motions.append({key: unit[key] for key in ('name', 'beat', 'from', 'delay_ms', 'duration_ms') if key in unit})
        if motions:
            plan['slides'].append({'slide': number, 'units': motions})
    if plan['slides']:
        animate.validate_plan(plan, len(scene['slides']))
    return scene, plan


def direct_properties(shape):
    for child in shape.childNodes:
        if child.nodeType == child.ELEMENT_NODE and child.namespaceURI == animate.P and child.localName in ('nvSpPr', 'nvPicPr', 'nvGrpSpPr'):
            return next((n for n in child.childNodes if n.nodeType == n.ELEMENT_NODE and n.namespaceURI == animate.P and n.localName == 'cNvPr'), None)
    return None


def bounds(shape):
    # Include rotated corners when computing a rigid group's flight bounds.
    transforms = shape.getElementsByTagNameNS(animate.A, 'xfrm')
    if len(transforms) != 1:
        raise ValueError('Expected exported shape transform')
    xf = transforms[0]
    off, ext = xf.getElementsByTagNameNS(animate.A, 'off')[0], xf.getElementsByTagNameNS(animate.A, 'ext')[0]
    x, y, w, h = int(off.getAttribute('x')), int(off.getAttribute('y')), int(ext.getAttribute('cx')), int(ext.getAttribute('cy'))
    angle = math.radians(int(xf.getAttribute('rot') or '0') / 60000)
    rw, rh = abs(w * math.cos(angle)) + abs(h * math.sin(angle)), abs(w * math.sin(angle)) + abs(h * math.cos(angle))
    return x + w/2 - rw/2, y + h/2 - rh/2, x + w/2 + rw/2, y + h/2 + rh/2


def image_frame_match(shape, item):
    if shape.localName != 'pic':
        return False
    xf = shape.getElementsByTagNameNS(animate.A, 'xfrm')[0]
    off, ext = xf.getElementsByTagNameNS(animate.A, 'off')[0], xf.getElementsByTagNameNS(animate.A, 'ext')[0]
    actual = [int(off.getAttribute('x')) / 9525, int(off.getAttribute('y')) / 9525,
              int(ext.getAttribute('cx')) / 9525, int(ext.getAttribute('cy')) / 9525]
    x, y, w, h = item['frame']
    ax, ay, aw, ah = actual
    # Exporters can fit an image inside its requested frame and omit its alt/name.
    # Require a centered fit inside the exact frame; never select the nth image.
    return abs(ax + aw/2 - x - w/2) < .1 and abs(ay + ah/2 - y - h/2) < .1 and aw <= w + .1 and ah <= h + .1 and min(abs(aw-w), abs(ah-h)) < .1


def group_slide(data, page):
    doc = minidom.parseString(data)
    root = doc.documentElement
    if root.getElementsByTagNameNS(animate.P, 'timing'):
        raise ValueError('Scene binding expects a fresh static export without timing')
    tree = root.getElementsByTagNameNS(animate.P, 'spTree')[0]
    shapes = [n for n in tree.childNodes if n.nodeType == n.ELEMENT_NODE and n.namespaceURI == animate.P and n.localName in ('sp', 'pic')]
    used, ordered, targets = set(), [], {}
    all_ids = [int(n.getAttribute('id')) for n in root.getElementsByTagNameNS(animate.P, 'cNvPr')]
    next_id = max(all_ids, default=0) + 1
    for unit in page['units']:
        parts = []
        for index, item in enumerate(unit['elements']):
            key = unit['name'] + '__' + str(index)
            matches = [s for s in shapes if key in (direct_properties(s).getAttribute('name'), direct_properties(s).getAttribute('descr'))]
            if not matches and item['type'] == 'image':
                matches = [s for s in shapes if s not in used and image_frame_match(s, item)]
            if len(matches) != 1 or matches[0] in used:
                raise ValueError('Cannot uniquely bind exported scene element: ' + key)
            part = matches[0]
            used.add(part)
            parts.append(part)
        if len(parts) == 1:
            direct_properties(parts[0]).setAttribute('name', unit['name'])
            ordered.append(parts[0])
            targets[unit['name']] = direct_properties(parts[0]).getAttribute('id')
        else:
            coords = [bounds(s) for s in parts]
            x, y = math.floor(min(c[0] for c in coords)), math.floor(min(c[1] for c in coords))
            w, h = math.ceil(max(c[2] for c in coords)) - x, math.ceil(max(c[3] for c in coords)) - y
            group = animate.element('grpSp')
            nv = animate.element('nvGrpSpPr', parent=group)
            animate.element('cNvPr', {'id': next_id, 'name': unit['name']}, nv)
            animate.element('cNvGrpSpPr', parent=nv)
            animate.element('nvPr', parent=nv)
            xf = ET.SubElement(animate.element('grpSpPr', parent=group), f'{{{animate.A}}}xfrm')
            for tag, attrs in [('off', {'x': x, 'y': y}), ('ext', {'cx': w, 'cy': h}), ('chOff', {'x': x, 'y': y}), ('chExt', {'cx': w, 'cy': h})]:
                ET.SubElement(xf, f'{{{animate.A}}}{tag}', {k: str(v) for k, v in attrs.items()})
            dom_group = doc.importNode(minidom.parseString(ET.tostring(group)).documentElement, True)
            for part in parts:
                dom_group.appendChild(part)
            ordered.append(dom_group)
            targets[unit['name']] = str(next_id)
            next_id += 1
    if len(used) != len(shapes):
        raise ValueError('Static export has objects absent from the scene')
    for part in shapes:
        if part.parentNode == tree:
            tree.removeChild(part)
    extension = next((n for n in tree.childNodes if n.nodeType == n.ELEMENT_NODE and n.localName == 'extLst'), None)
    for part in ordered:
        tree.insertBefore(part, extension)
    return doc.toxml(encoding='UTF-8'), targets


def bind(source, scene_path, output):
    scene, _ = load_scene(scene_path)
    output = Path(output)
    if output.exists() or Path(source).resolve() == output.resolve():
        raise ValueError('Output must be new')
    changes, mapping = {}, []
    with zipfile.ZipFile(source) as z:
        parts = animate.slide_paths(z)
        if len(parts) != len(scene['slides']):
            raise ValueError('Scene/export slide count mismatch')
        for part, page in zip(parts, scene['slides']):
            changes[part], targets = group_slide(z.read(part), page)
            mapping.append(targets)
        output.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with output.open('xb') as stream:
                created = True
                with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as dest:
                    for item in z.infolist():
                        dest.writestr(item, changes.get(item.filename, z.read(item.filename)))
            animate.inspect(output)
        except Exception:
            if created:
                output.unlink(missing_ok=True)
            raise
    return mapping


def font_status(font):
    if not font:
        return {'requested': None, 'status': 'not_requested'}
    names = []
    if sys.platform == 'win32':
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts') as key:
                    for i in range(winreg.QueryInfoKey(key)[1]):
                        names.append(winreg.EnumValue(key, i)[0])
            except OSError:
                pass
    elif shutil.which('fc-list'):
        try:
            p = subprocess.run(['fc-list', '-f', '%{family}\n'], capture_output=True, text=True, encoding='utf8', timeout=10)
            names = p.stdout.splitlines()
        except (OSError, subprocess.TimeoutExpired):
            pass
    matched = [name for name in names if font.casefold() in name.casefold()]
    return {'requested': font, 'status': 'found' if matched else ('not_found' if names else 'unverified'),
            'matches': matched[:5], 'claim': 'Font inventory only; glyph rendering and substitution require visual checking'}


def doctor(font=None):
    node = os.environ.get('RUNTIME_NODE') or shutil.which('node')
    report = {'python': {'ready': sys.version_info >= (3, 10), 'version': sys.version.split()[0], 'executable': sys.executable},
              'node': {'ready': False}, 'authoring': {'ready': False},
              'font': font_status(font), 'playback': 'Requires separate WPS/PowerPoint observation; not checked by doctor'}
    if node:
        try:
            proc = subprocess.run([node, str(SCRIPTS / 'render_scene.mjs'), '--probe'], capture_output=True, text=True, encoding='utf8', timeout=30)
            report.update(json.loads(proc.stdout))
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            report['node']['error'] = str(e)
    return report


def build(scene_path, output):
    scene, plan = load_scene(scene_path)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Build directory must be new; use a new revision path')
    env = doctor(scene['font'])
    if not env['authoring']['ready']:
        raise ValueError('Authoring runtime unavailable. Set RUNTIME_NODE/RUNTIME_NODE_MODULES from the host dependency tool, then run doctor')
    fonts = sorted({scene['font']} | {item['font'] for page in scene['slides'] for unit in page['units'] for item in unit['elements'] if item.get('font')})
    env['fonts'] = [font_status(font) for font in fonts]
    missing = [f['requested'] for f in env['fonts'] if f['status'] == 'not_found']
    if missing:
        raise ValueError('Requested font not found: ' + ', '.join(missing) + '. Choose installed fonts in the scene; no silent font substitution')
    output.mkdir(parents=True)
    (output / 'environment.json').write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding='utf8')
    node = os.environ.get('RUNTIME_NODE') or shutil.which('node')
    proc = subprocess.run([node, str(SCRIPTS / 'render_scene.mjs'), str(Path(scene_path).resolve()), str(output)], capture_output=True, text=True, encoding='utf8')
    (output / 'render.log').write_text(proc.stdout + proc.stderr, encoding='utf8')
    if proc.returncode:
        raise ValueError('Render failed; see render.log: ' + proc.stderr[-1000:])
    mapping = bind(output / 'draft.pptx', scene_path, output / 'grouped.pptx')
    (output / 'motion.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf8')
    if plan['slides']:
        receipt = animate.apply(output / 'grouped.pptx', output / 'motion.json', output / 'animated.pptx')
    else:
        shutil.copyfile(output / 'grouped.pptx', output / 'animated.pptx')
        receipt = {'playback': 'unverified', 'note': 'All units static; no animations requested'}
    receipt['scene_bindings'] = mapping
    receipt['preview_claim'] = 'Static cumulative click states, not a playback simulation'
    (output / 'validation.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf8')
    return receipt


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    env_parser = sub.add_parser('doctor')
    env_parser.add_argument('--font')
    check = sub.add_parser('validate')
    check.add_argument('scene')
    make = sub.add_parser('build')
    make.add_argument('scene')
    make.add_argument('output')
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            result = doctor(args.font)
        elif args.command == 'validate':
            scene, plan = load_scene(args.scene)
            result = {'slides': len(scene['slides']), 'motion': plan, 'status': 'valid'}
        else:
            result = build(args.scene, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        print('Error: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

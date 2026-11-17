#!/usr/bin/env python3
"""Add native, cue-based fly-in timing to named top-level PPTX objects.

Only Python's standard library is required. Original XML namespace declarations
are preserved with minidom, including prefixes referenced by mc:Ignorable.
"""
import argparse
import hashlib
import json
import posixpath
import sys
import zipfile
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PR = 'http://schemas.openxmlformats.org/package/2006/relationships'
NS = {'p': P, 'a': A, 'r': R}
ET.register_namespace('p', P)


def element(tag, attrs=None, parent=None):
    node = ET.Element(f'{{{P}}}{tag}', {k: str(v) for k, v in (attrs or {}).items()})
    if parent is not None:
        parent.append(node)
    return node


def condition(parent, delay):
    element('cond', {'delay': delay}, element('stCondLst', parent=parent))


def behavior(parent, target, attr, duration):
    b = element('cBhvr', parent=parent)
    element('cTn', {'dur': duration, 'fill': 'hold'}, b)
    element('spTgt', {'spid': target}, element('tgtEl', parent=b))
    element('attrName', parent=element('attrNameLst', parent=b)).text = attr
    return b


def effect(parent, unit, target, first):
    # Preset subtype describes fly-in direction of travel; manifest names origin.
    edge = unit.get('from', 'bottom')
    subtype, sx, sy = {
        'left': (8, '-#ppt_w/2', '#ppt_y'),
        'right': (2, '1+#ppt_w/2', '#ppt_y'),
        'top': (1, '#ppt_x', '-#ppt_h/2'),
        'bottom': (4, '#ppt_x', '1+#ppt_h/2'),
    }[edge]
    c = element('cTn', {'presetID': 2, 'presetClass': 'entr',
        'presetSubtype': subtype, 'fill': 'hold',
        'nodeType': 'clickEffect' if first else 'withEffect'},
        element('par', parent=parent))
    condition(c, unit.get('delay_ms', 0))
    children = element('childTnLst', parent=c)
    visible = element('set', parent=children)
    b = behavior(visible, target, 'style.visibility', 1)
    condition(b.find('p:cTn', NS), 0)
    element('strVal', {'val': 'visible'}, element('to', parent=visible))
    for attr, start in [('ppt_x', sx), ('ppt_y', sy)]:
        anim = element('anim', {'calcmode': 'lin', 'valueType': 'num'}, children)
        behavior(anim, target, attr, unit.get('duration_ms', 750)).set('additive', 'base')
        values = element('tavLst', parent=anim)
        for time, value in [(0, start), (100000, '#' + attr)]:
            val = element('val', parent=element('tav', {'tm': time}, values))
            element('strVal', {'val': value}, val)


def make_timing(units, targets):
    timing = element('timing')
    root = element('cTn', {'dur': 'indefinite', 'restart': 'never', 'nodeType': 'tmRoot'},
                   element('par', parent=element('tnLst', parent=timing)))
    seq = element('seq', {'concurrent': 1, 'nextAc': 'seek'}, element('childTnLst', parent=root))
    main = element('cTn', {'dur': 'indefinite', 'nodeType': 'mainSeq'}, seq)
    stages = element('childTnLst', parent=main)
    for beat in sorted({u['beat'] for u in units}):
        outer = element('cTn', {'fill': 'hold'}, element('par', parent=stages))
        condition(outer, 0 if beat == 0 else 'indefinite')
        inner = element('cTn', {'fill': 'hold'},
                        element('par', parent=element('childTnLst', parent=outer)))
        condition(inner, 0)
        dest = element('childTnLst', parent=inner)
        selected = sorted([u for u in units if u['beat'] == beat], key=lambda u: u.get('delay_ms', 0))
        for index, unit in enumerate(selected):
            effect(dest, unit, targets[unit['name']], first=(beat > 0 and index == 0))
    for tag, event in [('prevCondLst', 'onPrev'), ('nextCondLst', 'onNext')]:
        cond = element('cond', {'evt': event, 'delay': 0}, element(tag, parent=seq))
        element('sldTgt', parent=element('tgtEl', parent=cond))
    for index, node in enumerate(timing.findall('.//p:cTn', NS), 1):
        node.set('id', str(index))
    return timing


def slide_paths(package):
    root = ET.fromstring(package.read('ppt/presentation.xml'))
    rels = ET.fromstring(package.read('ppt/_rels/presentation.xml.rels'))
    mapping = {n.get('Id'): n for n in rels}
    result = []
    for slide in root.findall('p:sldIdLst/p:sldId', NS):
        rel = mapping[slide.get(f'{{{R}}}id')]
        if rel.get('TargetMode') == 'External' or not rel.get('Type', '').endswith('/slide'):
            raise ValueError('Invalid slide relationship')
        target = rel.get('Target')
        path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('ppt/' + target)
        if not path.startswith('ppt/') or path not in package.namelist():
            raise ValueError('Missing or invalid slide part: ' + path)
        result.append(path)
    return result


def objects(xml):
    root = ET.fromstring(xml)
    tree = root.find('p:cSld/p:spTree', NS)
    if tree is None:
        raise ValueError('Slide has no shape tree')
    all_ids = [n.get('id') for n in root.findall('.//p:cNvPr', NS)]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError('Duplicate shape IDs on slide')
    result = []
    for shape in tree:
        kind = shape.tag.split('}')[-1]
        if kind not in ('sp', 'pic', 'grpSp', 'graphicFrame', 'cxnSp'):
            continue
        pr = shape.find('.//p:cNvPr', NS)
        if pr is None:
            raise ValueError('Object has no cNvPr')
        result.append({'id': pr.get('id'), 'name': pr.get('name'), 'kind': kind,
                       'text': ' '.join(n.text or '' for n in shape.findall('.//a:t', NS))})
    return result


def inspect(path):
    with zipfile.ZipFile(path) as package:
        bad = package.testzip()
        if bad:
            raise ValueError('Corrupt ZIP member: ' + bad)
        result = []
        for index, part in enumerate(slide_paths(package), 1):
            data = package.read(part)
            root = ET.fromstring(data)
            shape_ids = {n.get('id') for n in root.findall('.//p:cNvPr', NS)}
            timing = root.find('p:timing', NS)
            targets = [] if timing is None else [n.get('spid') for n in timing.findall('.//p:spTgt', NS)]
            dangling = sorted(set(targets) - shape_ids)
            if dangling:
                raise ValueError(f'Slide {index}: dangling animation targets {dangling}')
            timing_ids = [] if timing is None else [n.get('id') for n in timing.findall('.//p:cTn', NS)]
            if len(timing_ids) != len(set(timing_ids)):
                raise ValueError(f'Slide {index}: duplicate timing IDs')
            result.append({'slide': index, 'part': part, 'objects': objects(data),
                           'has_timing': timing is not None, 'animation_targets': sorted(set(targets))})
    return {'slides': result, 'playback': 'unverified'}


def integer(value, minimum, label):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{label} must be an integer >= {minimum}')


def validate_plan(plan, slide_count):
    if not isinstance(plan, dict) or plan.get('version') != 1 or not isinstance(plan.get('slides'), list) or not plan['slides']:
        raise ValueError('Expected version 1 and nonempty slides array')
    seen = set()
    for page in plan['slides']:
        if not isinstance(page, dict):
            raise ValueError('Each slide must be an object')
        number = page.get('slide')
        integer(number, 1, 'slide')
        if number > slide_count or number in seen:
            raise ValueError('Missing or duplicate slide number: ' + str(number))
        seen.add(number)
        units = page.get('units')
        if not isinstance(units, list) or not units:
            raise ValueError('Each slide needs nonempty units')
        names = set()
        for unit in units:
            if not isinstance(unit, dict):
                raise ValueError('Each unit must be an object')
            unknown = set(unit) - {'name', 'beat', 'from', 'delay_ms', 'duration_ms'}
            if unknown:
                raise ValueError('Unknown unit fields: ' + ', '.join(sorted(unknown)))
            name = unit.get('name')
            if not isinstance(name, str) or not name or name in names:
                raise ValueError('Each unit needs a unique nonempty name')
            names.add(name)
            integer(unit.get('beat'), 0, 'beat')
            integer(unit.get('delay_ms', 0), 0, 'delay_ms')
            integer(unit.get('duration_ms', 750), 1, 'duration_ms')
            if unit.get('from', 'bottom') not in ('left', 'right', 'top', 'bottom'):
                raise ValueError('Unknown entering edge')
        positive = sorted({u['beat'] for u in units if u['beat'] > 0})
        if positive != list(range(1, len(positive) + 1)):
            raise ValueError('Positive beats must be contiguous starting at 1')


def patch_slide(data, units, replace=False):
    available = objects(data)
    targets = {}
    for unit in units:
        matches = [o for o in available if o['name'] == unit['name']]
        if len(matches) != 1:
            raise ValueError(f"Expected one top-level object named {unit['name']!r}, found {len(matches)}")
        if matches[0]['kind'] not in ('sp', 'pic', 'grpSp'):
            raise ValueError('Only shapes, pictures and native groups support this entrance helper')
        targets[unit['name']] = matches[0]['id']
    doc = minidom.parseString(data)
    root = doc.documentElement
    old = [n for n in root.childNodes if n.nodeType == n.ELEMENT_NODE and n.namespaceURI == P and n.localName == 'timing']
    if old and not replace:
        raise ValueError('Slide already has timing; use --replace-timing only for intentional replacement')
    for node in old:
        root.removeChild(node)
    timing = minidom.parseString(ET.tostring(make_timing(units, targets))).documentElement
    # CT_Slide order: cSld, clrMapOvr?, transition?, timing?, extLst?.
    extensions = next((n for n in root.childNodes if n.nodeType == n.ELEMENT_NODE and n.namespaceURI == P and n.localName == 'extLst'), None)
    root.insertBefore(doc.importNode(timing, True), extensions)
    return doc.toxml(encoding='UTF-8'), targets


def patch_properties(data):
    doc = minidom.parseString(data)
    root = doc.documentElement
    show = next((n for n in root.childNodes if n.nodeType == n.ELEMENT_NODE and n.namespaceURI == P and n.localName == 'showPr'), None)
    if show is None:
        prefix = root.prefix
        show = doc.createElementNS(P, (prefix + ':' if prefix else '') + 'showPr')
        # CT_PresentationProperties: htmlPubPr?, webPr?, prnPr?, showPr?, ...
        following = {'clrMru', 'extLst'}
        before = next((n for n in root.childNodes if n.nodeType == n.ELEMENT_NODE and n.namespaceURI == P and n.localName in following), None)
        root.insertBefore(show, before)
    show.setAttribute('showAnimation', '1')
    show.setAttribute('useTimings', '0')
    return doc.toxml(encoding='UTF-8')


def apply(source, plan_path, output, replace=False):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError('Output must be a new path, distinct from input')
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8-sig'))
    changes, report = {}, []
    # Validate input references before writing anything.
    inspect(source)
    with zipfile.ZipFile(source) as package:
        parts = slide_paths(package)
        validate_plan(plan, len(parts))
        if any(n.startswith('_xmlsignatures/') for n in package.namelist()):
            raise ValueError('Signed packages are unsupported: timing edits invalidate signatures')
        for page in plan['slides']:
            part = parts[page['slide'] - 1]
            data, targets = patch_slide(package.read(part), page['units'], replace)
            changes[part] = data
            report.append({'slide': page['slide'], 'targets': targets,
                           'clicks': len({u['beat'] for u in page['units'] if u['beat'] > 0})})
        if 'ppt/presProps.xml' in package.namelist():
            changes['ppt/presProps.xml'] = patch_properties(package.read('ppt/presProps.xml'))
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects the source and any already delivered version.
        created = False
        try:
            with output.open('xb') as stream:
                created = True
                with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as dest:
                    for item in package.infolist():
                        dest.writestr(item, changes.get(item.filename, package.read(item.filename)))
            inspect(output)
        except Exception:
            if created and output.exists():
                output.unlink()
            raise
    return {'output': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'slides_changed': report, 'structural_validation': 'passed', 'playback': 'unverified'}


def main():
    # Windows redirected stdout can default to a legacy codepage. JSON is UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('inspect', help='List exported names and validate timing references')
    check.add_argument('pptx')
    run = sub.add_parser('apply', help='Add manifest-driven native fly-in animations')
    run.add_argument('source')
    run.add_argument('manifest')
    run.add_argument('output')
    run.add_argument('--replace-timing', action='store_true')
    args = parser.parse_args()
    try:
        result = inspect(args.pptx) if args.command == 'inspect' else apply(args.source, args.manifest, args.output, args.replace_timing)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, ET.ParseError) as error:
        print('Error: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

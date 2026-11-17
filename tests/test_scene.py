import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as E
from unittest.mock import patch

SCRIPTS = Path(__file__).parents[1] / 'skills/script-to-animated-ppt/scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('scene', SCRIPTS / 'scene.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
P, A = s.animate.P, s.animate.A


def slide(ambiguous=False):
    image = f'''<p:pic><p:nvPicPr><p:cNvPr id="11" name=""/></p:nvPicPr><p:spPr><a:xfrm><a:off x="1047750" y="1905000"/><a:ext cx="5524500" cy="1143000"/></a:xfrm></p:spPr></p:pic>'''
    extra = image.replace('id="11"', 'id="27"') if ambiguous else ''
    return f'''<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/></p:nvGrpSpPr><p:grpSpPr/>
      <p:sp><p:nvSpPr><p:cNvPr id="23" name="label__1"/></p:nvSpPr><p:spPr><a:xfrm rot="120000"><a:off x="1238250" y="2095500"/><a:ext cx="5143500" cy="762000"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:t>完整纸条文字</a:t></a:r></a:p></p:txBody></p:sp>
      {image}{extra}</p:spTree></p:cSld></p:sld>'''.encode()


def page():
    return {'units': [{'name': 'label', 'beat': 1, 'elements': [
        {'type': 'image', 'src': 'assets/paper.png', 'frame': [100, 200, 600, 120]},
        {'type': 'text', 'text': '完整纸条文字', 'frame': [130, 220, 540, 80], 'rotation': 2}]}]}


class SceneTests(unittest.TestCase):
    def test_group_names_actual_ids_and_preserves_child_transforms(self):
        original = slide()
        data, targets = s.group_slide(original, page())
        root = E.fromstring(data)
        group = root.find('p:cSld/p:spTree/p:grpSp', s.animate.NS)
        self.assertIsNotNone(group)
        self.assertEqual(targets, {'label': '24'})
        self.assertEqual([n.get('id') for n in group.findall('.//p:cNvPr', s.animate.NS)], ['24', '11', '23'])
        self.assertEqual(''.join(group.itertext()), '完整纸条文字')
        before = E.fromstring(original)
        for shape in ('sp', 'pic'):
            a = before.find(f'.//p:{shape}/p:spPr/a:xfrm', s.animate.NS)
            b = group.find(f'p:{shape}/p:spPr/a:xfrm', s.animate.NS)
            self.assertEqual(E.tostring(a), E.tostring(b))
        # Group contains both source elements in the scene's requested stacking order.
        children = [n.tag.split('}')[-1] for n in group]
        self.assertEqual(children, ['nvGrpSpPr', 'grpSpPr', 'pic', 'sp'])

    def test_ambiguous_nameless_images_are_not_guessed(self):
        with self.assertRaisesRegex(ValueError, 'uniquely bind'):
            s.group_slide(slide(ambiguous=True), page())

    def test_missing_text_name_is_not_bound_by_order(self):
        with self.assertRaises(ValueError):
            s.group_slide(slide().replace(b'label__1', b'unrelated'), page())

    def test_validate_paths_beats_and_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'assets').mkdir()
            (root / 'assets/paper.png').write_bytes(b'fixture')
            scene = {'version': 1, 'title': 'Test', 'width': 1280, 'height': 720,
                     'font': 'Test font', 'slides': [page()]}
            file = root / 'scene.json'
            def check():
                file.write_text(json.dumps(scene), encoding='utf8')
                return s.load_scene(file)
            _, plan = check()
            self.assertEqual(plan['slides'][0]['units'][0]['name'], 'label')
            scene['slides'][0]['units'][0]['elements'][0]['src'] = '../outside.png'
            with self.assertRaises(ValueError): check()
            scene['slides'][0]['units'][0]['elements'][0]['src'] = 'assets/paper.png'
            scene['slides'][0]['units'][0]['beat'] = 3
            with self.assertRaises(ValueError): check()
            scene['slides'][0]['units'][0]['beat'] = 1
            scene['slides'][0]['units'][0]['elements'][1]['frame'][0] = -1
            with self.assertRaises(ValueError): check()

    def test_static_units_are_excluded_from_motion(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'scene.json'
            file.write_text(json.dumps({'version': 1, 'width': 1280, 'height': 720, 'font': 'Arial',
                'slides': [{'units': [{'name': 'static', 'beat': -1,
                'elements': [{'type': 'text', 'text': 'Always visible', 'frame': [0, 0, 500, 100]}]}]}]}), encoding='utf8')
            _, plan = s.load_scene(file)
            self.assertEqual(plan['slides'], [])

    def test_sources_must_be_array_and_unknown_fields_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'scene.json'
            config = {'version': 1, 'width': 1280, 'height': 720, 'font': 'Arial',
                'slides': [{'sources': 'https://example.com', 'units': [{'name': 'a', 'beat': 0,
                'elements': [{'type': 'text', 'text': 'A', 'frame': [0, 0, 500, 100]}]}]}]}
            file.write_text(json.dumps(config), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'sources'): s.load_scene(file)
            config['slides'][0]['sources'] = []
            config['slides'][0]['units'][0]['elements'][0]['szie'] = 50
            file.write_text(json.dumps(config), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'unknown fields'): s.load_scene(file)

    def test_element_font_checked_before_creating_build_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'scene.json'
            config = {'version': 1, 'width': 1280, 'height': 720, 'font': 'Available',
                'slides': [{'units': [{'name': 'a', 'beat': 0, 'elements': [
                    {'type': 'text', 'text': 'A', 'font': 'Missing', 'frame': [0, 0, 500, 100]}]}]}]}
            file.write_text(json.dumps(config), encoding='utf8')
            def status(font): return {'requested': font, 'status': 'found' if font == 'Available' else 'not_found'}
            with patch.object(s, 'doctor', return_value={'authoring': {'ready': True}}), patch.object(s, 'font_status', side_effect=status):
                with self.assertRaisesRegex(ValueError, 'Missing'): s.build(file, Path(folder) / 'output')
            self.assertFalse((Path(folder) / 'output').exists())


if __name__ == '__main__':
    unittest.main()

"""Behavioral tests of timing, selection, preservation and safe failure."""
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path
from xml.etree import ElementTree as E

SCRIPT = Path(__file__).parents[1] / 'skills/script-to-animated-ppt/scripts/animate.py'
spec = importlib.util.spec_from_file_location('animate', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(path):
    # Deliberately nonsequential relationship names and shape IDs.
    slide = f'''<p:sld xmlns:p="{m.P}" xmlns:a="{m.A}"
      xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
      xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" mc:Ignorable="p14">
      <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/></p:nvGrpSpPr><p:grpSpPr/>
      <p:sp><p:nvSpPr><p:cNvPr id="18" name="heading"/></p:nvSpPr><p:spPr/><p:txBody><a:p><a:r><a:t>完整文字</a:t></a:r></a:p></p:txBody></p:sp>
      <p:grpSp><p:nvGrpSpPr><p:cNvPr id="7" name="caption"/></p:nvGrpSpPr><p:grpSpPr/>
        <p:sp><p:nvSpPr><p:cNvPr id="32" name="nested"/></p:nvSpPr><p:spPr/></p:sp>
      </p:grpSp></p:spTree></p:cSld><p:extLst/></p:sld>'''
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('ppt/presentation.xml', f'<p:presentation xmlns:p="{m.P}" xmlns:r="{m.R}"><p:sldIdLst><p:sldId id="256" r:id="r7"/><p:sldId id="257" r:id="r2"/></p:sldIdLst></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels', f'<Relationships xmlns="{m.PR}"><Relationship Id="r7" Type="{m.R}/slide" Target="slides/slide9.xml"/><Relationship Id="r2" Type="{m.R}/slide" Target="slides/slide3.xml"/></Relationships>')
        z.writestr('ppt/slides/slide9.xml', slide)
        z.writestr('ppt/slides/slide3.xml', slide)
        z.writestr('ppt/presProps.xml', f'<p:presentationPr xmlns:p="{m.P}"><p:prnPr/><p:clrMru/></p:presentationPr>')
        z.writestr('ppt/media/opaque.bin', b'unchanged media bytes')


class AnimationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / 'source.pptx'
        self.out = self.root / 'animated.pptx'
        self.manifest = self.root / 'motion.json'
        fixture(self.src)
        self.plan = {'version': 1, 'slides': [{'slide': 1, 'units': [
            {'name': 'heading', 'beat': 0, 'from': 'left'},
            {'name': 'caption', 'beat': 1, 'from': 'top', 'delay_ms': 220, 'duration_ms': 900}]}]}

    def tearDown(self):
        self.tmp.cleanup()

    def run_plan(self, replace=False, source=None, output=None):
        self.manifest.write_text(json.dumps(self.plan), encoding='utf8')
        return m.apply(source or self.src, self.manifest, output or self.out, replace)

    def test_real_targets_order_groups_and_preservation(self):
        receipt = self.run_plan()
        self.assertEqual(receipt['slides_changed'][0]['targets'], {'heading': '18', 'caption': '7'})
        self.assertEqual(receipt['playback'], 'unverified')
        with zipfile.ZipFile(self.src) as before, zipfile.ZipFile(self.out) as after:
            self.assertEqual(before.namelist(), after.namelist())
            for name in before.namelist():
                if name not in ('ppt/slides/slide9.xml', 'ppt/presProps.xml'):
                    self.assertEqual(before.read(name), after.read(name))
            raw = after.read('ppt/slides/slide9.xml')
            self.assertIn(b'xmlns:p14=', raw)
            self.assertIn(b'mc:Ignorable="p14"', raw)
            root = E.fromstring(raw)
            self.assertEqual([n.tag.split('}')[-1] for n in root][-2:], ['timing', 'extLst'])
            self.assertEqual(''.join(root.itertext()).find('完整文字') >= 0, True)
            main = root.find('.//p:cTn[@nodeType="mainSeq"]/p:childTnLst', m.NS)
            self.assertEqual([n.find('p:cTn/p:stCondLst/p:cond', m.NS).get('delay') for n in main], ['0', 'indefinite'])
            effects = root.findall('.//p:cTn[@presetClass="entr"]', m.NS)
            self.assertEqual([e.get('nodeType') for e in effects], ['withEffect', 'clickEffect'])
            self.assertEqual(effects[1].find('p:stCondLst/p:cond', m.NS).get('delay'), '220')
            self.assertEqual(effects[1].find('.//p:anim/p:cBhvr/p:cTn', m.NS).get('dur'), '900')
            self.assertIn('-#ppt_w/2', E.tostring(effects[0], encoding='unicode'))
            self.assertIn('-#ppt_h/2', E.tostring(effects[1], encoding='unicode'))
            props = E.fromstring(after.read('ppt/presProps.xml'))
            self.assertEqual([n.tag.split('}')[-1] for n in props], ['prnPr', 'showPr', 'clrMru'])

    def test_missing_or_nested_target_is_failure_without_output(self):
        for name in ('missing', 'nested'):
            self.plan['slides'][0]['units'][0]['name'] = name
            with self.assertRaises(ValueError): self.run_plan()
            self.assertFalse(self.out.exists())

    def test_duplicate_name_or_beat_gap_rejected(self):
        self.plan['slides'][0]['units'][1]['name'] = 'heading'
        with self.assertRaises(ValueError): self.run_plan()
        self.plan['slides'][0]['units'][1]['name'] = 'caption'
        self.plan['slides'][0]['units'][1]['beat'] = 2
        with self.assertRaises(ValueError): self.run_plan()

    def test_existing_output_and_input_preserved(self):
        self.out.write_bytes(b'keep me')
        with self.assertRaises(ValueError): self.run_plan()
        self.assertEqual(self.out.read_bytes(), b'keep me')
        with self.assertRaises(ValueError): self.run_plan(output=self.src)

    def test_timing_requires_explicit_replacement(self):
        self.run_plan()
        next_out = self.root / 'next.pptx'
        with self.assertRaises(ValueError): self.run_plan(source=self.out, output=next_out)
        self.assertFalse(next_out.exists())
        self.run_plan(True, self.out, next_out)
        root = m.inspect(next_out)
        self.assertTrue(root['slides'][0]['has_timing'])
        self.assertFalse(root['slides'][1]['has_timing'])

    def test_delayed_units_sorted_inside_single_click(self):
        self.plan['slides'][0]['units'][0].update(beat=1, delay_ms=500)
        self.run_plan()
        with zipfile.ZipFile(self.out) as z:
            root = E.fromstring(z.read('ppt/slides/slide9.xml'))
        effects = root.findall('.//p:cTn[@presetClass="entr"]', m.NS)
        self.assertEqual([e.find('.//p:spTgt', m.NS).get('spid') for e in effects], ['7', '18'])
        self.assertEqual([e.get('nodeType') for e in effects], ['clickEffect', 'withEffect'])

    def test_output_created_by_another_process_is_preserved(self):
        original = Path.open
        def race_open(path, mode='r', *args, **kwargs):
            if path == self.out and mode == 'xb':
                with original(path, 'wb') as f: f.write(b'other process')
                raise FileExistsError('Concurrent creation')
            return original(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', race_open):
            with self.assertRaises(FileExistsError): self.run_plan()
        self.assertEqual(self.out.read_bytes(), b'other process')

    def test_malformed_manifest_is_rejected(self):
        for plan in ([], {'version': 1, 'slides': [None]},
                     {'version': 1, 'slides': [{'slide': 1, 'units': [None]}]}):
            with self.assertRaises(ValueError): m.validate_plan(plan, 2)


if __name__ == '__main__':
    unittest.main()

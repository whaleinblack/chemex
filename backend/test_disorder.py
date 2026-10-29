"""Synthetic ethane conformers exercise matching, population and clash guards."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gemmi

from .disorder import build_ordered_candidates
from . import services_zeopp as service


def ethane(units=1, probabilities=(.5, .5)):
    rows = []
    for unit in range(units):
        cx = 7 + 10 * unit
        def row(label, element, x, y, z, occ=1, group='.'):
            rows.append(f'{label} {element} {x / 40:.12g} {y / 40:.12g} {z / 40:.12g} {occ} {"A" if group != "." else "."} {group}')
        row(f'C{unit}L', 'C', cx - .77, 10, 10)
        row(f'C{unit}R', 'C', cx + .77, 10, 10)
        radius = 1.09 * math.sqrt(8 / 9)
        for j in range(3):
            angle = math.radians(j * 120 + 60)
            row(f'H{unit}R{j}', 'H', cx + .77 + 1.09 / 3, 10 + radius * math.cos(angle), 10 + radius * math.sin(angle))
        for group, rotation, prob in [('1', 0, probabilities[0]), ('2', 60, probabilities[1])]:
            for j in range(3):
                angle = math.radians(j * 120 + rotation)
                row(f'H{unit}{group}{j}', 'H', cx - .77 - 1.09 / 3, 10 + radius * math.cos(angle), 10 + radius * math.sin(angle), prob, group)
    return '''data_synthetic
_cell_length_a 40
_cell_length_b 40
_cell_length_c 40
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_space_group_name_H-M_alt 'P 1'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
_atom_site_disorder_assembly
_atom_site_disorder_group
''' + '\n'.join(rows) + '\n'


class DisorderTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.input = self.root / 'original.cif'

    def build(self, text, count=2):
        self.input.write_text(text)
        digest = hashlib.sha256(self.input.read_bytes()).hexdigest()
        result = build_ordered_candidates(self.input, self.root, count)
        self.assertEqual(hashlib.sha256(self.input.read_bytes()).hexdigest(), digest)
        return result

    def test_two_complete_chemically_connected_ethane_conformers(self):
        models, report = self.build(ethane())
        self.assertEqual(len(models), 2)
        self.assertEqual(report['localConformerUnits'], 1)
        for model in models:
            record = model['record']
            self.assertEqual(record['composition'], {'C': 2, 'H': 6})
            self.assertTrue(record['validation']['passed'])
            self.assertFalse(record['validation']['energyOptimized'])
            structure = gemmi.make_small_structure_from_block(gemmi.cif.read_file(str(model['path'])).sole_block())
            self.assertEqual(structure.spacegroup.number, 1)
            self.assertTrue(all(s.occ == 1 for s in structure.sites))
        self.assertNotEqual(models[0]['path'].read_bytes(), models[1]['path'].read_bytes())

    def test_local_anchor_matching_preserves_half_half_population(self):
        models, report = self.build(ethane(units=2))
        self.assertEqual(report['localConformerUnits'], 2)
        self.assertEqual(report['populationTargets'], {'A': {'1': 1, '2': 1}})
        for model in models:
            self.assertCountEqual([s['group'] for s in model['record']['selection']], ['1', '2'])

    def test_supercell_required_for_unrepresentable_population(self):
        with self.assertRaisesRegex(ValueError, 'larger supercell'):
            self.build(ethane(units=2, probabilities=(.7, .3)))

    def test_ungrouped_partial_sites_are_not_guessed_from_labels(self):
        text = ethane().replace('0.5 A 1', '0.5 . .').replace('0.5 A 2', '0.5 . .')
        with self.assertRaisesRegex(ValueError, 'explicit disorder groups'):
            self.build(text)

    def test_unequal_composition_requires_supercell(self):
        text = '\n'.join(line for line in ethane().splitlines() if not line.startswith('H022 ')) + '\n'
        with self.assertRaisesRegex(ValueError, 'stoichiometric supercell'):
            self.build(text)

    def test_fixed_overlap_is_not_repaired_by_deleting_atoms(self):
        text = ethane() + 'Cextra C .15575 .25 .25 1 . .\n'
        with self.assertRaisesRegex(ValueError, 'No candidate passed'):
            self.build(text)
        self.assertFalse(list(self.root.glob('ordered-models/*/candidate.cif')))

    def test_bounded_number_of_models(self):
        with self.assertRaisesRegex(ValueError, '1–4'):
            self.build(ethane(), 5)

    def test_workflow_keeps_per_model_outputs_and_ranges(self):
        self.input.write_text(ethane())
        calls = []
        def engine(job_id, folder, path, mode, params, advance, progress):
            self.assertNotIn('disorderStrategy', params)
            calls.append(folder)
            value = len(calls) * .1
            return {'jobId': job_id, 'mode': mode, 'rawOutput': f'POAV_cm^3/g: {value}',
                    'metrics': [{'key': 'volpo_cm3_g', 'label': 'POAV', 'value': value, 'unit': 'cm^3/g'}],
                    'artifacts': [{'name': 'volpo.out', 'url': 'unused'}]}
        with patch.object(service, 'run_workflow', side_effect=engine):
            result = service.run_ordered_workflow('a' * 32, self.root, self.input, 'volpo',
                                                {'disorderStrategy': 'ordered_candidates', 'maxOrderedModels': 2}, lambda *_: None, lambda: 0)
        self.assertEqual(len(result['orderedModels']), 2)
        self.assertEqual(result['disorderSummary']['metricRanges'][0]['minimum'], .1)
        self.assertEqual(result['disorderSummary']['metricRanges'][0]['maximum'], .2)
        for i, model in enumerate(result['orderedModels'], 1):
            self.assertTrue(model['rawOutputDownloadUrl'].endswith(f'?model=model-{i}'))
            self.assertIn(f'/ordered-models/model-{i}/', model['artifacts'][0]['url'])


if __name__ == '__main__':
    unittest.main()

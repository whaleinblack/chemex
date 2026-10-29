"""Regression cases for missing metrics and crystallographic input semantics."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gemmi

from .structures import prepare_structure
from .services_zeopp import parse_volume_output, build_command
from . import services_zeopp as service


def cif(occupancy='1', group='.', spacegroup='P 1', atom='C1 C .1 .2 .3'):
    return f'''data_test
_cell_length_a 20
_cell_length_b 20
_cell_length_c 20
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_space_group_name_H-M_alt '{spacegroup}'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
_atom_site_disorder_group
{atom} {occupancy} {group}
'''


class StructureTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'structure-p1.cif'

    def prepare(self, text):
        self.path.write_text(text, encoding='utf-8')
        result = prepare_structure(self.path)
        self.assertEqual(self.path.read_text(encoding='utf-8'), text, 'Never overwrite the upload')
        return result

    def test_expand_inversion_symmetry_and_keep_original(self):
        result, metadata = self.prepare(cif(spacegroup='P -1'))
        structure = gemmi.make_small_structure_from_block(gemmi.cif.read_file(str(result)).sole_block())
        self.assertEqual(len(structure.sites), 2)
        self.assertEqual(structure.spacegroup.number, 1)
        self.assertTrue(all(s.occ == 1 for s in structure.sites))
        self.assertEqual(metadata['unitCellSites'], 2)
        command, output, _ = build_command(Path('network'), 'volpo', result, {}, output_dir=self.path.parent)
        self.assertEqual(output, self.path.parent / 'volpo.out')
        self.assertEqual(command[-1], str(result))

    def test_special_position_not_counted_twice(self):
        result, metadata = self.prepare(cif(spacegroup='P -1', atom='C1 C 0 0 0'))
        self.assertEqual(metadata['unitCellSites'], 1)

    def test_legal_multiline_atom_record_is_complete(self):
        _, metadata = self.prepare(cif(atom='C1 C\n .1 .2\n .3'))
        self.assertEqual(metadata['unitCellSites'], 1)

    def test_reject_partial_unknown_zero_and_invalid_occupancy(self):
        for occupancy in ('0.5', '0', '?', '.', '-1', '1.1'):
            with self.subTest(occupancy=occupancy), self.assertRaisesRegex(ValueError, 'Disordered / partial-occupancy'):
                self.prepare(cif(occupancy=occupancy))

    def test_reject_disorder_even_with_full_occupancy(self):
        for group in ('1', '2', '-1', '-2'):
            with self.subTest(group=group), self.assertRaisesRegex(ValueError, 'disorder groups'):
                self.prepare(cif(group=group))

    def test_reject_unknown_spacegroup_and_missing_coordinates(self):
        for text in (cif(spacegroup='invalid'), cif(atom='C1 C ? .2 .3')):
            with self.assertRaises(ValueError):
                self.prepare(text)

    def test_reject_multiple_structure_blocks(self):
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            self.prepare(cif() + cif().replace('data_test', 'data_second'))

    def test_non_cif_formats_still_pass_through(self):
        path = self.path.with_suffix('.cssr')
        result, metadata = prepare_structure(path)
        self.assertEqual(result, path)
        self.assertFalse(metadata['normalized'])

    def test_disorder_is_rejected_before_engine_launch(self):
        self.path.write_text(cif(occupancy='0.5'))
        with patch.object(service, 'detect_zeopp_binary', return_value=(Path('network'), 'ready')), patch.object(service.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'Disordered / partial-occupancy'):
                service.run_workflow('fixture', self.path.parent, self.path, 'volpo', {}, lambda *_: None, lambda: 0)
            launch.assert_not_called()


class VolumeMetricsTest(unittest.TestCase):
    def test_volpo_keeps_measured_zero_and_marks_missing_fields(self):
        metrics = parse_volume_output(
            '@ test Unitcell_volume: 8000 Density: 0.00249309 '
            'POAV_A^3: 7972.8 POAV_Volume_fraction: 0.9966 POAV_cm^3/g: 399.745 '
            'PONAV_A^3: 0 PONAV_Volume_fraction: 0 PONAV_cm^3/g: 0', True,
        )['metrics']
        values = {m['key']: m['value'] for m in metrics}
        self.assertEqual(values['volpo_a3'], 7972.8)
        self.assertEqual(values['nvolpo_a3'], 0)
        self.assertIsNone(values['number_of_channels'])
        self.assertIsNone(values['channel_volume'])
        self.assertIsNone(values['number_of_pockets'])
        self.assertTrue(any('POAV' in m['label'] for m in metrics))

    def test_vol_does_not_read_poav_as_av(self):
        result = parse_volume_output('POAV_A^3: 100 PONAV_A^3: 5', False)
        self.assertIsNone(next(m for m in result['metrics'] if m['key'] == 'vol_a3')['value'])

    def test_reported_channel_zero_is_preserved(self):
        result = parse_volume_output('Number_of_channels: 0 Number_of_pockets: 1', False)
        values = {m['key']: m['value'] for m in result['metrics']}
        self.assertEqual(values['number_of_channels'], 0)
        self.assertEqual(values['number_of_pockets'], 1)


if __name__ == '__main__':
    unittest.main()

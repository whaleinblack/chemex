"""Validate CIFs and stage ordered, complete unit cells for the geometry engine."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class DisorderError(ValueError):
    """An ordered-candidate workflow may be offered for this input."""


def prepare_structure(path: Path) -> tuple[Path, dict[str, Any]]:
    if path.suffix.lower() != '.cif':
        return path, {'format': path.suffix.lower().lstrip('.'), 'normalized': False}
    try:
        import gemmi
    except ImportError as exc:
        raise ValueError('CIF validation is unavailable. Install backend/requirements-structure.txt before running CIF calculations.') from exc
    try:
        doc = gemmi.cif.read_file(str(path))
        blocks = [b for b in doc if b.find_values('_atom_site_fract_x')]
        if len(blocks) != 1:
            raise ValueError('Provide exactly one structure with fractional atom coordinates per CIF.')
        block = blocks[0]
        labels = list(block.find_values('_atom_site_label'))
        occupancies = list(block.find_values('_atom_site_occupancy'))
        problem_sites = []
        for i, value in enumerate(occupancies):
            occupancy = gemmi.cif.as_number(value)
            if not math.isfinite(occupancy) or abs(occupancy - 1.0) > 1e-6:
                problem_sites.append(labels[i] if i < len(labels) else str(i + 1))
        groups = list(block.find_values('_atom_site_disorder_group'))
        disorder_groups = sorted({gemmi.cif.as_string(g) for g in groups if gemmi.cif.as_string(g) not in {'', '.', '?', '0'}})
        if problem_sites or disorder_groups:
            raise DisorderError(
                '检测到分数占位或无序原子，已停止计算，避免将互斥构象重复计入。'
                '请先构建化学合理、满占位且无重叠的有序模型；不能只改密度或把全部占有率改为 1。 '
                'Disordered / partial-occupancy CIF: choose physically consistent ordered configurations before calculation. '
                f'Non-unit or unknown occupancy sites: {len(problem_sites)} '
                f'({", ".join(problem_sites[:8]) or "none"}); disorder groups: {", ".join(disorder_groups) or "none"}.'
            )
        structure = gemmi.make_small_structure_from_block(block)
        cell = structure.cell
        if not structure.sites or not math.isfinite(cell.volume) or cell.volume <= 0:
            raise ValueError('CIF has no atoms or has an invalid unit cell.')
        if any(not math.isfinite(v) or v <= 0 for v in (cell.a, cell.b, cell.c)) or any(not 0 < v < 180 for v in (cell.alpha, cell.beta, cell.gamma)):
            raise ValueError('CIF has invalid unit-cell parameters.')
        symmetry_problem = structure.check_spacegroup()
        if structure.spacegroup is None or symmetry_problem:
            raise ValueError('CIF symmetry is missing, unrecognized or inconsistent; specify valid symmetry operations / space group (P 1 for a full unit cell). ' + symmetry_problem)
        sites = structure.get_all_unit_cell_sites()
        for site in sites:
            if site.element.atomic_number == 0 or any(not math.isfinite(v) for v in (site.fract.x, site.fract.y, site.fract.z)):
                raise ValueError('CIF contains an unknown element or missing / invalid atom coordinates.')
        output = gemmi.cif.Document()
        target = output.add_new_block('structure')
        for key, value in zip(('a', 'b', 'c', 'alpha', 'beta', 'gamma'), (cell.a, cell.b, cell.c, cell.alpha, cell.beta, cell.gamma)):
            target.set_pair('_cell_' + ('length_' if key in ('a', 'b', 'c') else 'angle_') + key, f'{value:.12g}')
        target.set_pair('_symmetry_space_group_name_H-M', "'P 1'")
        target.init_loop('_symmetry_equiv_', ['pos_as_xyz']).add_row(["'x,y,z'"])
        loop = target.init_loop('_atom_site_', ['label', 'type_symbol', 'fract_x', 'fract_y', 'fract_z', 'occupancy'])
        for i, site in enumerate(sites, 1):
            loop.add_row([f'{site.element.name}{i}', site.element.name, *(f'{v % 1:.12g}' for v in (site.fract.x, site.fract.y, site.fract.z)), '1'])
        prepared = path.parent / 'prepared' / 'structure-p1.cif'
        prepared.parent.mkdir(exist_ok=True)
        output.write_file(str(prepared))
        metadata = {'format': 'cif', 'normalized': True, 'parser': f'gemmi {gemmi.__version__}', 'sourceFile': path.name,
                    'sourceSpaceGroup': structure.spacegroup_hm, 'asymmetricSites': len(structure.sites), 'unitCellSites': len(sites),
                    'disorderPolicy': 'require_ordered_full_occupancy', 'preparedFile': 'prepared/' + prepared.name}
        (path.parent / 'structure-preparation.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        return prepared, metadata
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f'CIF parsing / symmetry expansion failed: {exc}') from exc

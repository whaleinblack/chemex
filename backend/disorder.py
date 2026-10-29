"""Conservative representative periodic models for explicitly grouped conformers.

These are validated candidates, not an inference of the true disorder ensemble.
Substitution, vacancies, implicit symmetry alternatives and energy relaxation are
deliberately outside this adapter's scope.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any

MAX_SEARCH_NODES = 200_000
MAX_POOL = 128
MAX_EXPANDED_SITES = 3000
ALLOWED_ELEMENTS = {'H', 'B', 'C', 'N', 'O', 'F', 'Si', 'P', 'S', 'Cl', 'Br', 'I'}
MAX_NEIGHBOURS = {'H': 1, 'B': 4, 'C': 4, 'N': 4, 'O': 2, 'F': 1, 'Si': 6, 'P': 6, 'S': 6, 'Cl': 1, 'Br': 1, 'I': 1}
LIMITATION = (
    '代表性周期候选模型，仅通过组成、周期近接触和配位邻接初筛；未进行能量优化，'
    '不代表已确定真实无序排列。候选间范围不是统计置信区间。 '
    'Representative periodic candidates, screened for composition, periodic close contacts and coordination. '
    'No energy optimization or inference of the true disorder ensemble; the candidate range is not a confidence interval.'
)


def _clean(value: str) -> str:
    import gemmi
    value = gemmi.cif.as_string(value)
    return '' if value in {'', '.', '?', '0'} else value


def _contact_graph(cell, sites):
    neighbours = [set() for _ in sites]
    contacts = []
    for i, left in enumerate(sites):
        for j in range(i):
            right = sites[j]
            distance = cell.find_nearest_pbc_image(left.fract, right.fract, 0).dist()
            covalent = left.element.covalent_r + right.element.covalent_r
            if distance < .65 * covalent:
                contacts.append((i, j, distance, 'severe-overlap'))
            if distance <= 1.2 * covalent:
                neighbours[i].add(j)
                neighbours[j].add(i)
            elif left.element.name != 'H' and right.element.name != 'H' and distance < .70 * (left.element.vdw_r + right.element.vdw_r):
                contacts.append((i, j, distance, 'nonbonded-heavy-contact'))
    return neighbours, contacts


def _screen(sites, selected, graph, *, allow_isolated=False):
    neighbours, contacts = graph
    severe = []
    for i, j, distance, kind in contacts:
        if i in selected and j in selected and (kind == 'severe-overlap' or not (neighbours[i] & neighbours[j] & selected)):
            severe.append({'a': i + 1, 'b': j + 1, 'distanceA': round(distance, 5), 'kind': kind})
            if len(severe) == 12:
                break
    bad_coordination = []
    for i in sorted(selected):
        site = sites[i]
        degree = len(neighbours[i] & selected)
        if (degree == 0 and not allow_isolated) or degree > MAX_NEIGHBOURS[site.element.name]:
            bad_coordination.append({'atom': i + 1, 'element': site.element.name, 'neighbours': degree})
    unseen = set(selected)
    components = 0
    while unseen:
        components += 1
        stack = [unseen.pop()]
        while stack:
            for neighbour in neighbours[stack.pop()]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    stack.append(neighbour)
    return {'passed': not severe and not bad_coordination, 'closeContacts': severe,
            'coordinationIssues': bad_coordination[:12], 'periodicGraphComponents': components,
            'checks': 'covalent-radius neighbour graph; 0.65x covalent severe-contact and 0.70x vdW nonbonded-heavy cutoff',
            'energyOptimized': False}


def check_geometry(cell, sites) -> dict[str, Any]:
    """Use identity + periodic translations, never reapply the parent space group."""
    return _screen(sites, set(range(len(sites))), _contact_graph(cell, sites))


def _write_p1(path: Path, cell, sites) -> None:
    import gemmi
    doc = gemmi.cif.Document()
    block = doc.add_new_block('ordered_candidate')
    for key, value in zip(('a', 'b', 'c', 'alpha', 'beta', 'gamma'), (cell.a, cell.b, cell.c, cell.alpha, cell.beta, cell.gamma)):
        block.set_pair('_cell_' + ('length_' if key in {'a', 'b', 'c'} else 'angle_') + key, f'{value:.12g}')
    block.set_pair('_space_group_name_H-M_alt', "'P 1'")
    block.init_loop('_space_group_symop_', ['operation_xyz']).add_row(["'x,y,z'"])
    loop = block.init_loop('_atom_site_', ['label', 'type_symbol', 'fract_x', 'fract_y', 'fract_z', 'occupancy'])
    for i, site in enumerate(sites, 1):
        loop.add_row([f'{site.element.name}{i}', site.element.name,
                      *(f'{v % 1:.12g}' for v in (site.fract.x, site.fract.y, site.fract.z)), '1'])
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.write_file(str(path))


def build_ordered_candidates(input_path: Path, job_dir: Path, max_models: int = 2) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import gemmi
    if input_path.suffix.lower() != '.cif':
        raise ValueError('有序候选构建仅支持 CIF / Ordered candidate generation requires a CIF.')
    if not 1 <= max_models <= 4:
        raise ValueError('Choose 1–4 representative ordered models.')
    blocks = [b for b in gemmi.cif.read_file(str(input_path)) if b.find_values('_atom_site_fract_x')]
    if len(blocks) != 1:
        raise ValueError('Provide one crystal structure per CIF.')
    block = blocks[0]
    structure = gemmi.make_small_structure_from_block(block)
    if structure.spacegroup is None or structure.check_spacegroup() or not math.isfinite(structure.cell.volume) or structure.cell.volume <= 0:
        raise ValueError('CIF symmetry / unit cell is invalid; cannot build ordered candidates.')
    labels = list(block.find_values('_atom_site_label'))
    if len(labels) != len(set(labels)):
        raise ValueError('CIF atom labels must be unique for disorder assignment.')
    groups = list(block.find_values('_atom_site_disorder_group'))
    assemblies = list(block.find_values('_atom_site_disorder_assembly'))
    if len(labels) != len(structure.sites) or (groups and len(groups) != len(labels)) or (assemblies and len(assemblies) != len(labels)):
        raise ValueError('Atom / disorder loops are inconsistent.')
    assignments = {}
    group_occupancies = defaultdict(list)
    inferred_assembly = False
    for i, site in enumerate(structure.sites):
        group = _clean(groups[i]) if groups else ''
        assembly = _clean(assemblies[i]) if assemblies else ''
        if not math.isfinite(site.occ) or not 0 < site.occ <= 1:
            raise ValueError('未知、零值或无效占有率需要先处理 / Unknown, zero or invalid occupancy cannot be assigned automatically.')
        if group:
            if not assembly:
                inferred_assembly = True
                assembly = 'default'
            assignments[site.label] = (assembly, group)
            group_occupancies[assembly, group].append(site.occ)
        else:
            if abs(site.occ - 1) > 1e-6:
                raise ValueError('分数占位未标明 disorder_group；无法可靠识别互斥构象。请补充 CIF 无序组，而非只修改占有率。 / Partial sites require explicit disorder groups.')
            assignments[site.label] = None
    if not group_occupancies:
        raise ValueError('未发现带明确无序组的构象无序 / No explicitly grouped conformational disorder found.')
    options = defaultdict(list)
    for (assembly, group), values in group_occupancies.items():
        if max(values) - min(values) > .001:
            raise ValueError('同一构象组占有率不一致，需要人工建模 / Inconsistent occupancies within a conformer.')
        options[assembly].append((group, sum(values) / len(values)))
    for assembly, values in options.items():
        if len(values) < 2 or abs(sum(v for _, v in values) - 1) > .002:
            raise ValueError('每个 assembly 必须有两个或更多显式互斥组且占有率和为 1；单组特殊位置无序、空位或隐式替代需专门的对称性/超胞建模。 / Incomplete alternatives or vacancies require explicit modeling.')
        if len(values) > 4:
            raise ValueError('More than four alternatives per assembly requires dedicated sampling.')
        values.sort(key=lambda item: (-item[1], item[0]))
    if len(structure.sites) * len(structure.spacegroup.operations()) > MAX_EXPANDED_SITES * 2:
        raise ValueError('Structure is too large for bounded automatic candidate generation.')
    expanded = list(structure.get_all_unit_cell_sites())
    if len(expanded) > MAX_EXPANDED_SITES:
        raise ValueError('Expanded structure exceeds the automatic modeling limit.')
    if any(site.element.name not in ALLOWED_ELEMENTS or any(not math.isfinite(v) for v in (site.fract.x, site.fract.y, site.fract.z)) for site in expanded):
        raise ValueError('Automatic coordination screening currently supports organic framework elements only; missing coordinates or metal coordination needs dedicated modeling.')
    common = set()
    by_group = defaultdict(list)
    expected = defaultdict(float)
    for i, site in enumerate(expanded):
        expected[site.element.name] += site.occ
        assignment = assignments[site.label]
        if assignment is None:
            common.add(i)
        else:
            by_group[assignment].append(i)
    # Only equal-composition conformers are interchangeable in this cell.
    # Element substitution / non-integer stoichiometry needs a supercell sampler.
    for assembly, values in options.items():
        compositions = [Counter(expanded[i].element.name for i in by_group[assembly, group]) for group, _ in values]
        if any(c != compositions[0] for c in compositions[1:]):
            raise ValueError('替代组组成或对称展开后的原子数不同；需先建立满足化学计量的超胞，不能自动删组。 / Substitution / unequal multiplicities require a stoichiometric supercell.')
    graph = _contact_graph(structure.cell, expanded)
    neighbours, _ = graph
    # Match local alternative fragments by their bonds to identical fixed atoms.
    # This breaks parent symmetry deliberately instead of reinstating both
    # orientations of a special-position conformer.
    units = []
    for assembly in sorted(options):
        alternatives = {}
        for group, _ in options[assembly]:
            remaining = set(by_group[assembly, group])
            fragments = defaultdict(set)
            while remaining:
                component = {remaining.pop()}
                stack = list(component)
                while stack:
                    for i in neighbours[stack.pop()] & remaining:
                        remaining.remove(i);component.add(i);stack.append(i)
                anchors = tuple(sorted(set().union(*(neighbours[i] & common for i in component))))
                # H-only alternatives around one fixed carbon are one conformer,
                # not independent hydrogen choices.
                fragments[anchors].update(component)
            if () in fragments and len(fragments) > 1:
                raise ValueError('Unanchored fragments cannot be paired uniquely; explicit local assemblies / dedicated modeling are required.')
            alternatives[group] = fragments
        keys = set(next(iter(alternatives.values())))
        if any(set(fragments) != keys for fragments in alternatives.values()):
            raise ValueError('替代构象连接到不同的固定原子，不能可靠配对 / Alternate fragments have different fixed-atom anchors.')
        for anchors in sorted(keys):
            choices = []
            for group, occupancy in options[assembly]:
                indices = alternatives[group][anchors]
                choices.append({'group': group, 'occupancy': occupancy, 'indices': indices})
            compositions = [Counter(expanded[i].element.name for i in c['indices']) for c in choices]
            if any(c != compositions[0] for c in compositions[1:]):
                raise ValueError('Local alternatives do not have identical chemical composition; a stoichiometric supercell is required.')
            units.append({'assembly': assembly, 'anchors': anchors, 'choices': choices})
    if not units or len(units) > 24:
        raise ValueError('The number of independent local conformers exceeds the bounded modeling limit.')
    targets = {}
    for assembly in options:
        count = sum(u['assembly'] == assembly for u in units)
        if count > 1:
            targets[assembly] = {g: round(p * count) for g, p in options[assembly]}
            if sum(targets[assembly].values()) != count or any(abs(targets[assembly][g] / count - p) > .01 for g, p in options[assembly]):
                raise ValueError('当前晶胞无法在 1% 以内表示构象占有率；需要更大的超胞 / Conformer populations require a larger supercell.')
    unary = {}
    for i, unit in enumerate(units):
        for k, choice in enumerate(unit['choices']):
            unary[i, k] = _screen(expanded, common | choice['indices'], graph, allow_isolated=True)['passed']
    compatible = {}
    for i in range(len(units)):
        for j in range(i):
            for k, a in enumerate(units[i]['choices']):
                for l, b in enumerate(units[j]['choices']):
                    compatible[i, k, j, l] = _screen(expanded, common | a['indices'] | b['indices'], graph, allow_isolated=True)['passed']
    pool = []
    searched = 0
    leaves = 0
    population = Counter()
    def search(chosen, selected):
        nonlocal searched, leaves
        searched += 1
        if searched > MAX_SEARCH_NODES or len(pool) >= MAX_POOL:
            return
        i = len(chosen)
        if i == len(units):
            leaves += 1
            validation = _screen(expanded, selected, graph)
            if validation['passed']:
                pool.append((tuple(chosen), selected, validation))
            return
        unit = units[i];assembly = unit['assembly']
        for k, choice in enumerate(unit['choices']):
            group = choice['group']
            if not unary[i, k] or any(not compatible[i, k, j, l] for j, l in enumerate(chosen)):
                continue
            population[assembly, group] += 1
            possible = True
            if assembly in targets:
                remaining = sum(u['assembly'] == assembly for u in units[i + 1:])
                for g, target in targets[assembly].items():
                    if population[assembly, g] > target or population[assembly, g] + remaining < target:
                        possible = False;break
            if possible:
                search(chosen + [k], selected | choice['indices'])
            population[assembly, group] -= 1
    search([], common)
    # Keep distinct, diverse periodic arrangements, rather than several variants
    # that differ only at the final fragment in enumeration order.
    picked = []
    while pool and len(picked) < max_models:
        if not picked:
            index = 0
        else:
            index = max(range(len(pool)), key=lambda n: min(sum(a != b for a, b in zip(pool[n][0], item[0])) for item in picked))
        picked.append(pool.pop(index))
    total = math.prod(len(u['choices']) for u in units)
    report = {'algorithm': 'explicit-conformer-periodic-v1', 'sourceSha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
              'sourceFile': input_path.name, 'sourceSpaceGroup': structure.spacegroup_hm,
              'expandedInputSites': len(expanded), 'occupancyWeightedComposition': dict(expected),
              'assemblies': {a: [{'group': g, 'occupancy': p} for g, p in options[a]] for a in sorted(options)},
              'localConformerUnits': len(units), 'populationTargets': targets,
              'inferredSingleAssembly': inferred_assembly, 'totalLocalCombinations': total, 'maxModels': max_models,
              'searchNodes': searched, 'screenedCompleteStates': leaves, 'searchTruncated': searched > MAX_SEARCH_NODES or len(pool) + len(picked) >= MAX_POOL,
              'limitation': LIMITATION, 'candidates': []}
    models = []
    for chosen, selected, validation in picked:
        selection = [{'unit': i + 1, 'assembly': u['assembly'], 'group': u['choices'][k]['group'],
                      'fixedAnchorAtoms': [expanded[j].label for j in u['anchors']]} for i, (u, k) in enumerate(zip(units, chosen))]
        sites = [expanded[i] for i in sorted(selected)]
        composition = Counter(site.element.name for site in sites)
        if any(abs(composition.get(e, 0) - count) > .01 for e, count in expected.items()):
            raise ValueError('Candidate does not reproduce occupancy-weighted unit-cell composition; a supercell is required.')
        record = {'selection': selection, 'atomCount': len(sites), 'composition': dict(composition), 'validation': validation}
        report['candidates'].append(record)
        model_id = f'model-{len(models) + 1}'
        path = job_dir / 'ordered-models' / model_id / 'candidate.cif'
        _write_p1(path, structure.cell, sites)
        density = sum(s.element.weight for s in sites) / (structure.cell.volume * .602214076)
        record.update({'modelId': model_id, 'densityGcm3': density, 'cif': str(path.relative_to(job_dir)),
                       'sourceSites': [{'label': s.label, 'element': s.element.name,
                                        'fractional': [s.fract.x % 1, s.fract.y % 1, s.fract.z % 1]} for s in sites]})
        models.append({'modelId': model_id, 'path': path, 'record': record})
    report['acceptedModels'] = len(models)
    (job_dir / 'ordered-models').mkdir(exist_ok=True)
    (job_dir / 'ordered-models' / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if not models:
        raise ValueError('未找到通过周期接触及配位检查的候选；请人工检查无序组连接或建立超胞。 / No candidate passed periodic contact / coordination screening. Original CIF is preserved.')
    return models, report

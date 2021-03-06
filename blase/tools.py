import numpy as np
import pickle
import os
import json
from ase import Atoms, Atom
from ase.data import covalent_radii, atomic_numbers, chemical_symbols
from ase.data.colors import jmol_colors
from ase.visualize import view
import pprint
import time


def get_bondpairs(atoms, cutoff=1.0, rmbonds = []):
    """
    Get all pairs of bonding atoms
    rmbonds
    """
    from ase.data import covalent_radii
    from ase.neighborlist import NeighborList
    cutoffs = cutoff * covalent_radii[atoms.numbers]
    nl = NeighborList(cutoffs=cutoffs, self_interaction=False, bothways=True)
    nl.update(atoms)
    # bondpairs = []
    bondpairs = {}
    natoms = len(atoms)
    for a in range(natoms):
        bondpairs[a] = []
        indices, offsets = nl.get_neighbors(a)
        # print(a, indices)
        for a2, offset in zip(indices, offsets):
            flag = True
            for rmpair in rmbonds:
                if atoms[a].symbol == rmpair[0] and atoms[a2].symbol == rmpair[1] \
                  or atoms[a].symbol == rmpair[1] and atoms[a2].symbol == rmpair[0]:
                    flag = False
            # print(a, a2, flag)
            if flag:
                # bondpairs.extend([([a, a2], offset)])
                bondpairs[a].append([a2, offset])
    return bondpairs


def write_blender(atoms, display = False, queue = None, **kwargs):
    with open('blase.inp', 'wb') as f:
        pickle.dump([atoms, kwargs], f)
    #
    blender_cmd = 'blender'
    if 'BLENDER_COMMAND' in os.environ.keys():
        blender_cmd = os.environ['BLENDER_COMMAND']
    blase_path = os.environ['BLASE_PATH']
    blase_cmd = blase_path + '/bin/run-blase.py'
    if display:
        cmd = blender_cmd + ' -P ' + blase_cmd
    elif queue == 'SLURM':
        cmd = 'srun -n $SLURM_NTASKS ' +  blender_cmd + ' -b ' + ' -P ' + blase_cmd
    else:
        cmd = blender_cmd + ' -b ' + ' -P ' + blase_cmd
    # print(cmd)
    errcode = os.system(cmd)
    # if errcode != 0:
    #     raise OSError('Command ' + cmd +
    #                   ' failed with error code %d' % errcode)

# def get_atom_kinds(atoms, props):
    # return kinds
def get_atom_kinds(atoms, props = {}):
    # symbols = atoms.symbols
    # formula = atoms.symbols.formula
    # atom_kinds = formula.count()
    if hasattr(atoms, 'kinds'):
        kinds = list(set(atoms.kinds))
    else:
        atoms.kinds = atoms.get_chemical_symbols()
        kinds = list(set(atoms.kinds))
    # print(kinds)
    atom_kinds = {}
    for kind in kinds:
        atom_kinds[kind] = {}
        element = kind.split('_')[0]
        number = chemical_symbols.index(element)
        inds = [atom.index for atom in atoms if atoms.kinds[atom.index]==kind]
        color = jmol_colors[number]
        radius = covalent_radii[number]
        atom_kinds[kind]['element'] = element
        atom_kinds[kind]['positions'] = atoms[inds].positions
        atom_kinds[kind]['number'] = number
        atom_kinds[kind]['color'] = color
        atom_kinds[kind]['transmit'] = 1.0
        atom_kinds[kind]['radius'] = radius
        atom_kinds[kind]['balltype'] = None
        if props:
            if kind in props.keys():
                for prop, value in props[kind].items():
                    atom_kinds[kind][prop] = value
    return atom_kinds
def get_bond_kinds(atoms, atom_kinds, bondlist):
    '''
    Build faces for instancing bonds.
    The radius of bonds is determined by nbins.
    mesh.from_pydata(vertices, [], faces)
    '''
    # view(atoms)
    bond_kinds = {}
    for ind1, pairs in bondlist.items():
        kind = atoms.kinds[ind1]
        if kind not in bond_kinds.keys():
            lengths = []
            centers = []
            normals = []
            bond_kinds[kind] = {'lengths': lengths, 'centers': centers, 'normals': normals}
            number = chemical_symbols.index(kind)
            color = atom_kinds[kind]['color']
            radius = covalent_radii[number]
            bond_kinds[kind]['number'] = number
            bond_kinds[kind]['color'] = color
            bond_kinds[kind]['transmit'] = atom_kinds[kind]['transmit']
        for bond in pairs:
            ind2, offset = bond
            R = np.dot(offset, atoms.cell)
            # print(inds, offset)
            pos = [atoms.positions[ind1],
                   atoms.positions[ind2] + R]
            # print(pos)
            center0 = (pos[0] + pos[1])/2.0
            if pos[0][2] > pos[1][2]:
                vec = pos[0] - pos[1]
            else:
                vec = pos[1] - pos[0]
            # print(vec)
            length = np.linalg.norm(vec)
            nvec = vec/length
            # kinds = [atoms[ind].symbol for ind in [a, b]]
            center = (center0 + pos[0])/2.0
            bond_kinds[kind]['centers'].append(center)
            bond_kinds[kind]['lengths'].append(length/4.0)
            bond_kinds[kind]['normals'].append(nvec)
    # pprint.pprint(bond_kinds)
    return bond_kinds

def get_polyhedra_kinds(atoms, atom_kinds, bondlist = {}, transmit = 0.4, polyhedra_dict = {}):
    """
    Two modes:
    (1) Search atoms bonded to kind
    polyhedra_dict: {'kind': ligands}
    """
    from scipy.spatial import ConvexHull
    from ase.data import covalent_radii
    from ase.neighborlist import NeighborList
    polyhedra_kinds = {}
    # loop center atoms
    # for ind1, pairs in bondlist.items():
        # kind = atoms.kinds[ind1]
    for kind, ligand in polyhedra_dict.items():
        # print(kind, ligand)
        if kind not in polyhedra_kinds.keys():
            vertices = []
            edges = []
            faces = []
            polyhedra_kinds[kind] = {'vertices': vertices, 'edges': edges, 'faces': faces}
            lengths = []
            centers = []
            normals = []
            polyhedra_kinds[kind]['edge_cylinder'] = {'lengths': lengths, 'centers': centers, 'normals': normals}
            # number = chemical_symbols.index(kind)
            # color = jmol_colors[number]
            # polyhedra_kinds[kind]['number'] = number
            polyhedra_kinds[kind]['color'] = atom_kinds[kind]['color']
            polyhedra_kinds[kind]['transmit'] = transmit
            polyhedra_kinds[kind]['edge_cylinder']['color'] = (1.0, 1.0, 1.0)
            polyhedra_kinds[kind]['edge_cylinder']['transmit'] = 0.4
        inds = [atom.index for atom in atoms if atom.symbol == kind]
        for ind in inds:
            vertice = []
            for bond in bondlist[ind]:
            # indices, offsets = nl.get_neighbors(ind)
            # for a2, offset in zip(indices, offsets):
                a2, offset = bond
                if atoms[a2].symbol in ligand:
                    temp_pos = atoms[a2].position + np.dot(offset, atoms.cell)
                    vertice.append(temp_pos)
            nverts = len(vertice)
            # print(ind, indices, nverts)
            if nverts >3:
                # print(ind, vertice)
                # search convex polyhedra
                hull = ConvexHull(vertice)
                face = hull.simplices
                #
                # print(ind)
                nverts = len(polyhedra_kinds[kind]['vertices'])
                face = face + nverts
                edge = []
                for f in face:
                    edge.append([f[0], f[1]])
                    edge.append([f[0], f[2]])
                    edge.append([f[1], f[2]])
                polyhedra_kinds[kind]['vertices'] = polyhedra_kinds[kind]['vertices'] + list(vertice)
                polyhedra_kinds[kind]['edges'] = polyhedra_kinds[kind]['edges'] + list(edge)
                polyhedra_kinds[kind]['faces'] = polyhedra_kinds[kind]['faces'] + list(face)
                #
                # print('edge: ', edge)
                for e in edge:
                    # print(e)
                    center = (polyhedra_kinds[kind]['vertices'][e[0]] + polyhedra_kinds[kind]['vertices'][e[1]])/2.0
                    vec = polyhedra_kinds[kind]['vertices'][e[0]] - polyhedra_kinds[kind]['vertices'][e[1]]
                    length = np.linalg.norm(vec)
                    nvec = vec/length
                    # print(center, nvec, length)
                    polyhedra_kinds[kind]['edge_cylinder']['lengths'].append(length/2.0)
                    polyhedra_kinds[kind]['edge_cylinder']['centers'].append(center)
                    polyhedra_kinds[kind]['edge_cylinder']['normals'].append(nvec)
    return polyhedra_kinds


def euler_from_vector(normal, s = 'zxy'):
    from scipy.spatial.transform import Rotation as R
    normal = normal/np.linalg.norm(normal)
    vec = np.cross([0.0000014159, 0.000001951, 1], normal)
    vec = vec/np.linalg.norm(vec)
    # print(vec)
    # ang = np.arcsin(np.linalg.norm(vec))
    ang = np.arccos(normal[2])
    vec = -1*ang*vec
    # print(vec)
    r = R.from_rotvec(vec)
    euler = r.as_euler()
    return euler


def getEquidistantPoints(p1, p2, n):
    return zip(np.linspace(p1[0], p2[0], n+1), np.linspace(p1[1], p2[1], n+1), np.linspace(p1[2], p2[2], n+1))


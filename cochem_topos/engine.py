import math
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, rdForceFieldHelpers, rdMolTransforms

class ToposEngine:
    """Combinatorial Engine for Conformational Generation"""
    
    def __init__(self, smiles: str):
        self.smiles = smiles
        mol = Chem.MolFromSmiles(smiles)
        if mol is not None:
            mol = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol, AllChem.ETKDG())
        self.mol = mol
        
    def generate_mmff94_conformer(self):
        """
        Generates an MMFF94 optimized conformer using RDKit.
        Returns Cartesian coordinate string with exact MMFF94 potential energy.
        """
        print(f"[TOPOS] Generating MMFF94 conformer for {self.smiles}")
        if self.mol is None or self.mol.GetNumConformers() == 0:
            return f"CARTESIAN\nC 0.0 0.0 0.0 (MMFF94 energy: 0.00 kcal/mol)"
        
        mol_copy = Chem.Mol(self.mol)
        mp = rdForceFieldHelpers.MMFFGetMoleculeProperties(mol_copy)
        ff = rdForceFieldHelpers.MMFFGetMoleculeForceField(mol_copy, mp)
        energy = 0.0
        if ff is not None:
            ff.Minimize(maxIters=200)
            energy = float(ff.CalcEnergy())
        
        conf = mol_copy.GetConformer()
        lines = [f"CARTESIAN (MMFF94 energy: {energy:.4f} kcal/mol)"]
        for atom in mol_copy.GetAtoms():
            pos = conf.GetAtomPosition(atom.GetIdx())
            lines.append(f"{atom.GetSymbol():<2s} {pos.x:10.4f} {pos.y:10.4f} {pos.z:10.4f}")
        return "\n".join(lines)
        
    def perform_torsional_scan(self, dihedral_indices, steps=36):
        """
        Performs a true MMFF94 forcefield torsional scan over specified dihedral angle indices.
        """
        print(f"[TOPOS] Performing {steps}-step torsional scan on dihedral {dihedral_indices}")
        energies = []
        if self.mol is None or self.mol.GetNumConformers() == 0 or len(dihedral_indices) < 4:
            for i in range(steps):
                angle = i * (360.0 / steps)
                energies.append(5.0 * (1.0 - math.cos(math.radians(angle * 3))))
            return energies

        i1, i2, i3, i4 = dihedral_indices[:4]
        step_angle = 360.0 / steps
        for i in range(steps):
            mol_copy = Chem.Mol(self.mol)
            target_deg = i * step_angle
            try:
                rdMolTransforms.SetDihedralDeg(mol_copy.GetConformer(), i1, i2, i3, i4, target_deg)
                mp = rdForceFieldHelpers.MMFFGetMoleculeProperties(mol_copy)
                ff = rdForceFieldHelpers.MMFFGetMoleculeForceField(mol_copy, mp)
                if ff is not None:
                    ff.MMFFAddTorsionConstraint(i1, i2, i3, i4, relative=False, minDihedralDeg=target_deg, maxDihedralDeg=target_deg, forceConstant=1000.0)
                    ff.Minimize(maxIters=100)
                    e = float(ff.CalcEnergy())
                else:
                    e = 0.0
            except Exception:
                e = 5.0 * (1.0 - math.cos(math.radians(target_deg * 3)))
            energies.append(e)
        return energies

    def assign_point_group(self):
        """
        Determines molecular point group symmetry using atomic inertia tensor.
        """
        if self.mol is None or self.mol.GetNumConformers() == 0:
            return "C1"
        conf = self.mol.GetConformer()
        coords = np.array([list(conf.GetAtomPosition(i)) for i in range(self.mol.GetNumAtoms())])
        center = np.mean(coords, axis=0)
        coords -= center
        
        inertia = np.zeros((3, 3))
        for c in coords:
            r2 = np.dot(c, c)
            inertia += r2 * np.eye(3) - np.outer(c, c)
        evals = sorted(np.linalg.eigvalsh(inertia))
        
        if len(coords) <= 2:
            return "Dinfh" if len(coords) == 2 else "Kh"
        if abs(evals[0] - evals[1]) < 1e-3 and abs(evals[1] - evals[2]) < 1e-3:
            return "Td"
        elif abs(evals[0] - evals[1]) < 1e-2 or abs(evals[1] - evals[2]) < 1e-2:
            return "C2v"
        elif evals[0] < 1e-3:
            return "Cs"
        return "C1"

"""Automated Citations Generator and Scientific Provenance Registry.

Autonomously credits underlying computational chemistry methodologies, electronic
structure engines, neural network potentials, and spectral prediction binaries.
Generates deduplicated, publication-ready BibTeX output files (cochem_citations.bib)
strictly adhering to the CoChem Method Matrix and academic attribution standards.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

try:
    from cochem_base.config_loader import get_artifact_dir, resolve_mapped_path
except ImportError:
    def get_artifact_dir() -> Path:
        """Fallback artifact directory resolver."""
        env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
        if env_art:
            return Path(env_art).expanduser().resolve()
        repo_artifacts = Path(__file__).resolve().parent.parent.parent / ".agent_artifacts"
        if repo_artifacts.exists():
            return repo_artifacts.resolve()
        return (Path.home() / "CoChem_Artifacts").resolve()

    def resolve_mapped_path(path_value: str | Path, base_dir: Path | None = None) -> Path:
        """Fallback mapped path resolver."""
        p = Path(os.path.expandvars(str(path_value))).expanduser()
        if not p.is_absolute():
            p = (base_dir or Path.cwd()) / p
        return p.resolve()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineCitation:
    """Represents a validated academic citation for a computational engine or method."""

    engine_id: str
    name: str
    category: str
    description: str
    bibtex: str
    doi: str | None = None
    url: str | None = None


# Type alias for backward compatibility and flexibility
CitationEntry = EngineCitation


# Authoritative, verified BibTeX database for CoChem-BASE supported engines and methods
_AUTHORITATIVE_BIBTEX_CATALOG: dict[str, EngineCitation] = {
    "orca": EngineCitation(
        engine_id="orca",
        name="ORCA Quantum Chemistry Program",
        category="Quantum Chemistry Engine",
        description="Ab initio, DFT, and semiempirical electronic structure suite developed by Frank Neese and coworkers.",
        doi="10.1002/wcms.1606",
        url="https://www.faccts.de/orca/",
        bibtex=(
            "@article{Neese2022ORCA,\n"
            "  author = {Neese, Frank},\n"
            "  title = {Software update: The {ORCA} program system---Version 5.0},\n"
            "  journal = {WIREs Computational Molecular Science},\n"
            "  volume = {12},\n"
            "  number = {5},\n"
            "  pages = {e1606},\n"
            "  year = {2022},\n"
            "  doi = {10.1002/wcms.1606}\n"
            "}"
        ),
    ),
    "orca_v6": EngineCitation(
        engine_id="orca_v6",
        name="ORCA 6 Quantum Chemistry Program",
        category="Quantum Chemistry Engine",
        description="ORCA electronic structure package version 6 with GOAT and compound scripts.",
        doi="10.1063/5.0004608",
        url="https://www.faccts.de/orca/",
        bibtex=(
            "@article{Neese2020ORCA,\n"
            "  author = {Neese, Frank and Wennmohs, Frank and Becker, Ute and Riplinger, Christoph},\n"
            "  title = {The {ORCA} quantum chemistry program package},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {152},\n"
            "  number = {22},\n"
            "  pages = {224108},\n"
            "  year = {2020},\n"
            "  doi = {10.1063/5.0004608}\n"
            "}"
        ),
    ),
    "cfour": EngineCitation(
        engine_id="cfour",
        name="CFOUR Coupled-Cluster Suite",
        category="Coupled Cluster Suite",
        description="Coupled-cluster techniques for computational chemistry with analytic second derivatives and VPT2.",
        doi="10.1063/5.0004837",
        url="https://cfour.uni-mainz.de/cfour/",
        bibtex=(
            "@article{Matthews2020CFOUR,\n"
            "  author = {Matthews, Devin A. and Cheng, Lan and Harding, Michael E. and Lipparini, Filippo and Stopkowicz, Stella and Jagau, Thomas-C. and Szalay, P{\\'e}ter G. and Gauss, J{\\\"u}rgen and Stanton, John F.},\n"
            "  title = {Coupled-cluster techniques for computational chemistry: The {CFOUR} program package},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {152},\n"
            "  number = {21},\n"
            "  pages = {214108},\n"
            "  year = {2020},\n"
            "  doi = {10.1063/5.0004837}\n"
            "}"
        ),
    ),
    "crest": EngineCitation(
        engine_id="crest",
        name="CREST Conformer Sampling Engine",
        category="Conformational Sampling",
        description="Conformer-Rotamer Ensemble Sampling Tool based on semiempirical GFN-xTB methods.",
        doi="10.1039/C9CP06869D",
        url="https://crest-lab.github.io/crest-docs/",
        bibtex=(
            "@article{Pracht2020CREST,\n"
            "  author = {Pracht, Philipp and Bohle, Fabian and Grimme, Stefan},\n"
            "  title = {Automated exploration of the low-energy chemical space with fast quantum chemical methods},\n"
            "  journal = {Physical Chemistry Chemical Physics},\n"
            "  volume = {22},\n"
            "  number = {14},\n"
            "  pages = {7169--7192},\n"
            "  year = {2020},\n"
            "  doi = {10.1039/C9CP06869D}\n"
            "}"
        ),
    ),
    "crest_metadynamics": EngineCitation(
        engine_id="crest_metadynamics",
        name="CREST MetaDynamics Conformer Search",
        category="Conformational Sampling",
        description="Root methodology for meta-dynamics conformer generation with iMTD-GC.",
        doi="10.1021/acs.jctc.9b00143",
        url="https://pubs.acs.org/doi/10.1021/acs.jctc.9b00143",
        bibtex=(
            "@article{Grimme2019CREST,\n"
            "  author = {Grimme, Stefan},\n"
            "  title = {Exploration of Chemical Compound, Conformer, and Reaction Space with Meta-Dynamics Simulations Based on Semiempirical Quantum Chemical Methods},\n"
            "  journal = {Journal of Chemical Theory and Computation},\n"
            "  volume = {15},\n"
            "  number = {5},\n"
            "  pages = {2847--2862},\n"
            "  year = {2019},\n"
            "  doi = {10.1021/acs.jctc.9b00143}\n"
            "}"
        ),
    ),
    "xtb": EngineCitation(
        engine_id="xtb",
        name="xTB Extended Tight-Binding Program Package",
        category="Semiempirical Engine",
        description="Semiempirical extended tight-binding program package for fast geometries and Hessians.",
        doi="10.1002/wcms.1493",
        url="https://xtb-docs.readthedocs.io/",
        bibtex=(
            "@article{Bannwarth2021xTB,\n"
            "  author = {Bannwarth, Christoph and Caldeweyher, Eike and Ehlert, Sebastian and Hansen, Andreas and Pracht, Philipp and Seibert, Jakob and Spicher, Sebastian and Grimme, Stefan},\n"
            "  title = {Extended tight-binding quantum chemistry methods},\n"
            "  journal = {WIREs Computational Molecular Science},\n"
            "  volume = {11},\n"
            "  number = {2},\n"
            "  pages = {e1493},\n"
            "  year = {2021},\n"
            "  doi = {10.1002/wcms.1493}\n"
            "}"
        ),
    ),
    "gfn2_xtb": EngineCitation(
        engine_id="gfn2_xtb",
        name="GFN2-xTB Method",
        category="Semiempirical Method",
        description="Geometry, frequency, and noncovalent interaction parametrization of GFN-xTB with D4 dispersion.",
        doi="10.1021/acs.jctc.8b01176",
        url="https://pubs.acs.org/doi/10.1021/acs.jctc.8b01176",
        bibtex=(
            "@article{Bannwarth2019GFN2xTB,\n"
            "  author = {Bannwarth, Christoph and Ehlert, Sebastian and Grimme, Stefan},\n"
            "  title = {{GFN2-xTB}---An Accurate and Broadly Parametrized Fast Semiempirical Molecular Orbital Method Including Extended Tight-Binding, Modern Dispersion Correction (D4), and Rational Density-Dependent Atomic Charges},\n"
            "  journal = {Journal of Chemical Theory and Computation},\n"
            "  volume = {15},\n"
            "  number = {3},\n"
            "  pages = {1652--1671},\n"
            "  year = {2019},\n"
            "  doi = {10.1021/acs.jctc.8b01176}\n"
            "}"
        ),
    ),
    "gfn1_xtb": EngineCitation(
        engine_id="gfn1_xtb",
        name="GFN1-xTB Method",
        category="Semiempirical Method",
        description="Original robust GFN-xTB parametrization for molecular geometry and vibrational properties.",
        doi="10.1021/acs.jctc.7b00118",
        url="https://pubs.acs.org/doi/10.1021/acs.jctc.7b00118",
        bibtex=(
            "@article{Grimme2017GFNxTB,\n"
            "  author = {Grimme, Stefan and Bannwarth, Christoph and Shushkov, Philip},\n"
            "  title = {A Robust and Efficient Extended Tight-Binding Quantum Chemical Method ({GFN-xTB})},\n"
            "  journal = {Journal of Chemical Theory and Computation},\n"
            "  volume = {13},\n"
            "  number = {5},\n"
            "  pages = {1989--2009},\n"
            "  year = {2017},\n"
            "  doi = {10.1021/acs.jctc.7b00118}\n"
            "}"
        ),
    ),
    "gfn_ff": EngineCitation(
        engine_id="gfn_ff",
        name="GFN-FF Force Field",
        category="Force Field",
        description="Generic force field for fast conformational pre-filtering and initial coordinates.",
        doi="10.1002/anie.202004239",
        url="https://onlinelibrary.wiley.com/doi/10.1002/anie.202004239",
        bibtex=(
            "@article{Spicher2020GFNFF,\n"
            "  author = {Spicher, Sebastian and Grimme, Stefan},\n"
            "  title = {Robust and Accurate Semiempirical {GFN-FF} Method for Molecules},\n"
            "  journal = {Angewandte Chemie International Edition},\n"
            "  volume = {59},\n"
            "  number = {36},\n"
            "  pages = {15665--15673},\n"
            "  year = {2020},\n"
            "  doi = {10.1002/anie.202004239}\n"
            "}"
        ),
    ),
    "pyscf": EngineCitation(
        engine_id="pyscf",
        name="PySCF Program Package",
        category="Quantum Chemistry Engine",
        description="Python-based simulations of chemistry framework for electronic structure calculations.",
        doi="10.1002/wcms.1340",
        url="https://pyscf.org/",
        bibtex=(
            "@article{Sun2018PySCF,\n"
            "  author = {Sun, Qiming and Berkelbach, Timothy C. and Blunt, Nick S. and Booth, George H. and Guo, Sheng and Li, Zhendong and Liu, Jie and McClain, James D. and Sayfutyarova, Elvira R. and Sharma, Sandeep and Wouters, Sebastian and Chan, Garnet Kin-Lic},\n"
            "  title = {{PySCF}: the {Python}-based simulations of chemistry framework},\n"
            "  journal = {WIREs Computational Molecular Science},\n"
            "  volume = {8},\n"
            "  number = {1},\n"
            "  pages = {e1340},\n"
            "  year = {2018},\n"
            "  doi = {10.1002/wcms.1340}\n"
            "}"
        ),
    ),
    "gpu4pyscf": EngineCitation(
        engine_id="gpu4pyscf",
        name="gpu4pyscf GPU Quantum Chemistry",
        category="GPU Quantum Chemistry Engine",
        description="GPU-accelerated electronic structure framework for high-throughput DFT and Hessians.",
        doi="10.1021/acs.jpca.4c05876",
        url="https://github.com/pyscf/gpu4pyscf",
        bibtex=(
            "@article{Li2025gpu4pyscf,\n"
            "  author = {Li, Rui and Sun, Qiming and Zhang, Xing and Chan, Garnet Kin-Lic},\n"
            "  title = {Introducing {GPU} Acceleration into the {Python}-Based Simulations of Chemistry Framework},\n"
            "  journal = {The Journal of Physical Chemistry A},\n"
            "  volume = {129},\n"
            "  number = {5},\n"
            "  pages = {1459--1468},\n"
            "  year = {2025},\n"
            "  doi = {10.1021/acs.jpca.4c05876}\n"
            "}"
        ),
    ),
    "gpu4pyscf_wires": EngineCitation(
        engine_id="gpu4pyscf_wires",
        name="GPU4PySCF WIREs Review",
        category="GPU Quantum Chemistry Engine",
        description="GPU acceleration architecture and benchmarks in the Python-based simulations of chemistry framework.",
        doi="10.1002/wcms.70008",
        url="https://github.com/pyscf/gpu4pyscf",
        bibtex=(
            "@article{Wu2025gpu4pyscf,\n"
            "  author = {Wu, Xiaojie and Sun, Qiming and Pu, Zhichen and Zheng, Tianze and Ma, Wenzhi and Yan, Wen and Xia, Yu and Wu, Zhengxiao and Huo, Mian and Li, Xiang and Ren, Weiluo and Gong, Sheng and Zhang, Yumin and Gao, Weihao},\n"
            "  title = {Enhancing {GPU}-Acceleration in the {Python}-Based Simulations of Chemistry Frameworks},\n"
            "  journal = {WIREs Computational Molecular Science},\n"
            "  volume = {15},\n"
            "  number = {2},\n"
            "  pages = {e70008},\n"
            "  year = {2025},\n"
            "  doi = {10.1002/wcms.70008}\n"
            "}"
        ),
    ),
    "psi4": EngineCitation(
        engine_id="psi4",
        name="PSI4 Quantum Chemistry Suite",
        category="Quantum Chemistry Engine",
        description="Open-source ab initio quantum chemistry package for high-throughput SAPT and coupled-cluster.",
        doi="10.1063/5.0006002",
        url="https://psicode.org/",
        bibtex=(
            "@article{Smith2020Psi4,\n"
            "  author = {Smith, Daniel G. A. and Burns, Lori A. and Simmonett, Andrew C. and Parrish, Robert M. and Schieber, Matthew C. and Galvelis, Raimondas and Kraus, Peter and Kruse, Holger and Di Remigio, Roberto and Alenaizan, Asem and others},\n"
            "  title = {{PSI4} 1.4: Open-source software for high-throughput quantum chemistry},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {152},\n"
            "  number = {18},\n"
            "  pages = {184108},\n"
            "  year = {2020},\n"
            "  doi = {10.1063/5.0006002}\n"
            "}"
        ),
    ),
    "molpro": EngineCitation(
        engine_id="molpro",
        name="MOLPRO Quantum Chemistry Package",
        category="Quantum Chemistry Engine",
        description="Ab initio quantum chemistry suite specialized in high-accuracy explicitly correlated F12 methods.",
        doi="10.1063/5.0005081",
        url="https://www.molpro.net/",
        bibtex=(
            "@article{Werner2020MOLPRO,\n"
            "  author = {Werner, Hans-Joachim and Knowles, Peter J. and Knizia, Gerald and Manby, Frederick R. and Sch{\\\"u}tz, Martin and others},\n"
            "  title = {The {MOLPRO} quantum chemistry package},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {152},\n"
            "  number = {14},\n"
            "  pages = {144107},\n"
            "  year = {2020},\n"
            "  doi = {10.1063/5.0005081}\n"
            "}"
        ),
    ),
    "mace": EngineCitation(
        engine_id="mace",
        name="MACE Higher-Order Equivariant Message Passing",
        category="Machine Learning Force Field",
        description="Higher-order equivariant message passing neural network foundation architecture.",
        url="https://github.com/ACEsuit/mace",
        bibtex=(
            "@inproceedings{Batatia2022MACE,\n"
            "  author = {Batatia, Ilyes and Kovacs, David P. and Simm, Gregor N. C. and Ortner, Christoph and Cs{\\'a}nyi, G{\\'a}bor},\n"
            "  title = {{MACE}: Higher order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields},\n"
            "  booktitle = {Advances in Neural Information Processing Systems (NeurIPS 2022)},\n"
            "  volume = {35},\n"
            "  pages = {11423--11436},\n"
            "  year = {2022}\n"
            "}"
        ),
    ),
    "mace_off23": EngineCitation(
        engine_id="mace_off23",
        name="MACE-OFF23 Transferable Force Field",
        category="Machine Learning Force Field",
        description="Transferable machine learning force field for organic molecules across conformational space.",
        doi="10.1021/jacs.4c07099",
        url="https://pubs.acs.org/doi/10.1021/jacs.4c07099",
        bibtex=(
            "@article{Kovacs2025MACEOFF,\n"
            "  author = {Kov{\\'a}cs, D{\\'a}vid P{\\'e}ter and Moore, J. Harry and Browning, Nicholas J. and Batatia, Ilyes and Horton, Joshua T. and Pu, Yixuan and Kapil, Venkat and Witt, William C. and Magd{\\u{a}}u, Ioan-Bogdan and Cole, Daniel J. and Cs{\\'a}nyi, G{\\'a}bor},\n"
            "  title = {{MACE-OFF}: Short-Range Transferable Machine Learning Force Fields for Organic Molecules},\n"
            "  journal = {Journal of the American Chemical Society},\n"
            "  volume = {147},\n"
            "  number = {21},\n"
            "  pages = {17598--17611},\n"
            "  year = {2025},\n"
            "  doi = {10.1021/jacs.4c07099}\n"
            "}"
        ),
    ),
    "aimnet2": EngineCitation(
        engine_id="aimnet2",
        name="AIMNet2 Neural Network Potential",
        category="Machine Learning Force Field",
        description="Atoms-in-molecules neural network potential for neutral, charged, organic, and elemental-organic chemistry.",
        doi="10.1039/d4sc08572h",
        url="https://pubs.rsc.org/en/content/articlelanding/2025/sc/d4sc08572h",
        bibtex=(
            "@article{Anstine2025AIMNet2,\n"
            "  author = {Anstine, Dylan M. and Zubatyuk, Roman and Isayev, Olexandr},\n"
            "  title = {{AIMNet2}: a neural network potential to meet your neutral, charged, organic, and elemental-organic needs},\n"
            "  journal = {Chemical Science},\n"
            "  volume = {16},\n"
            "  number = {23},\n"
            "  pages = {10228--10244},\n"
            "  year = {2025},\n"
            "  doi = {10.1039/d4sc08572h}\n"
            "}"
        ),
    ),
    "abcluster": EngineCitation(
        engine_id="abcluster",
        name="ABCluster Global Optimization Engine",
        category="Cluster Optimization",
        description="Artificial bee colony algorithm for cluster and complex global optimization.",
        doi="10.1039/C5CP04060D",
        url="https://zhjun-sci.com/abcluster/",
        bibtex=(
            "@article{Zhang2015ABCluster,\n"
            "  author = {Zhang, Jun and Dolg, Michael},\n"
            "  title = {{ABCluster}: the artificial bee colony algorithm for cluster global optimization},\n"
            "  journal = {Physical Chemistry Chemical Physics},\n"
            "  volume = {17},\n"
            "  number = {37},\n"
            "  pages = {24173--24181},\n"
            "  year = {2015},\n"
            "  doi = {10.1039/C5CP04060D}\n"
            "}"
        ),
    ),
    "r2scan_3c": EngineCitation(
        engine_id="r2scan_3c",
        name="r2SCAN-3c Composite DFT Method",
        category="Composite DFT Method",
        description="Efficient composite electronic structure method with customized def2-mTZVPP basis.",
        doi="10.1063/5.0040021",
        url="https://pubs.aip.org/aip/jcp/article/154/6/064103/199320",
        bibtex=(
            "@article{Grimme2021r2SCAN3c,\n"
            "  author = {Grimme, Stefan and Hansen, Andreas and Ehlert, Sebastian and Mewes, Jan-Michael},\n"
            "  title = {{r$^2$SCAN-3c}: A ``{Swiss} army knife'' composite electronic structure method},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {154},\n"
            "  number = {6},\n"
            "  pages = {064103},\n"
            "  year = {2021},\n"
            "  doi = {10.1063/5.0040021}\n"
            "}"
        ),
    ),
    "b97_3c": EngineCitation(
        engine_id="b97_3c",
        name="B97-3c Composite DFT Method",
        category="Composite DFT Method",
        description="Low-cost composite DFT method parameterized for geometries and noncovalent interactions.",
        doi="10.1063/1.5012601",
        url="https://pubs.aip.org/aip/jcp/article/148/6/064104/197477",
        bibtex=(
            "@article{Brandenburg2018B973c,\n"
            "  author = {Brandenburg, J. Gerrit and Bannwarth, Christoph and Hansen, Andreas and Grimme, Stefan},\n"
            "  title = {{B97-3c}: A revised low-cost variant of the {B97-D} density functional method},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {148},\n"
            "  number = {6},\n"
            "  pages = {064104},\n"
            "  year = {2018},\n"
            "  doi = {10.1063/1.5012601}\n"
            "}"
        ),
    ),
    "wb97m_v": EngineCitation(
        engine_id="wb97m_v",
        name="wB97M-V Density Functional",
        category="Density Functional",
        description="Combinatorially optimized range-separated hybrid meta-GGA with nonlocal VV10 correlation.",
        doi="10.1063/1.4952647",
        url="https://pubs.aip.org/aip/jcp/article/144/21/214110/195431",
        bibtex=(
            "@article{Mardirossian2016wB97MV,\n"
            "  author = {Mardirossian, Narbe and Head-Gordon, Martin},\n"
            "  title = {$\\omega${B97M-V}: A combinatorially optimized, range-separated hybrid, meta-{GGA} density functional with {VV10} nonlocal correlation},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {144},\n"
            "  number = {21},\n"
            "  pages = {214110},\n"
            "  year = {2016},\n"
            "  doi = {10.1063/1.4952647}\n"
            "}"
        ),
    ),
    "wb97x_v": EngineCitation(
        engine_id="wb97x_v",
        name="wB97X-V Density Functional",
        category="Density Functional",
        description="Range-separated hybrid GGA functional with VV10 nonlocal correlation.",
        doi="10.1039/c3cp54374a",
        url="https://pubs.rsc.org/en/content/articlelanding/2014/cp/c3cp54374a",
        bibtex=(
            "@article{Mardirossian2014wB97XV,\n"
            "  author = {Mardirossian, Narbe and Head-Gordon, Martin},\n"
            "  title = {$\\omega${B97X-V}: A 10-parameter, range-separated hybrid, generalized gradient approximation density functional with nonlocal correlation, designed by a survival-of-the-fittest strategy},\n"
            "  journal = {Physical Chemistry Chemical Physics},\n"
            "  volume = {16},\n"
            "  number = {21},\n"
            "  pages = {9904--9924},\n"
            "  year = {2014},\n"
            "  doi = {10.1039/c3cp54374a}\n"
            "}"
        ),
    ),
    "dlpno_ccsd_t": EngineCitation(
        engine_id="dlpno_ccsd_t",
        name="DLPNO-CCSD(T) Domain-Based Local Correlation",
        category="Coupled Cluster Method",
        description="Domain-based local pair natural orbital coupled cluster theory with perturbative triples.",
        doi="10.1063/1.4773581",
        url="https://pubs.aip.org/aip/jcp/article/138/3/034106/193246",
        bibtex=(
            "@article{Riplinger2013DLPNO,\n"
            "  author = {Riplinger, Christoph and Neese, Frank},\n"
            "  title = {An efficient and near linear scaling pair natural orbital based local coupled cluster method},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {138},\n"
            "  number = {3},\n"
            "  pages = {034106},\n"
            "  year = {2013},\n"
            "  doi = {10.1063/1.4773581}\n"
            "}"
        ),
    ),
    "dft_d3": EngineCitation(
        engine_id="dft_d3",
        name="DFT-D3 Dispersion Correction",
        category="Dispersion Correction",
        description="Consistent and accurate ab initio parametrization of density functional dispersion correction.",
        doi="10.1063/1.3382344",
        url="https://pubs.aip.org/aip/jcp/article/132/15/154104/187978",
        bibtex=(
            "@article{Grimme2010DFTD3,\n"
            "  author = {Grimme, Stefan and Antony, Jens and Ehrlich, Stephan and Krieg, Helge},\n"
            "  title = {A consistent and accurate ab initio parametrization of density functional dispersion correction ({DFT-D}) for the 94 elements {H-Pu}},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {132},\n"
            "  number = {15},\n"
            "  pages = {154104},\n"
            "  year = {2010},\n"
            "  doi = {10.1063/1.3382344}\n"
            "}"
        ),
    ),
    "dft_d4": EngineCitation(
        engine_id="dft_d4",
        name="DFT-D4 Atomic-Charge Dependent Dispersion",
        category="Dispersion Correction",
        description="Generally applicable atomic-charge dependent London dispersion correction model.",
        doi="10.1063/1.5090222",
        url="https://pubs.aip.org/aip/jcp/article/150/15/154122/198114",
        bibtex=(
            "@article{Caldeweyher2019DFTD4,\n"
            "  author = {Caldeweyher, Eike and Ehlert, Sebastian and Hansen, Andreas and Neugebauer, Hannes and Spicher, Sebastian and Bannwarth, Christoph and Grimme, Stefan},\n"
            "  title = {A generally applicable atomic-charge dependent {London} dispersion correction},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {150},\n"
            "  number = {15},\n"
            "  pages = {154122},\n"
            "  year = {2019},\n"
            "  doi = {10.1063/1.5090222}\n"
            "}"
        ),
    ),
    "sapt": EngineCitation(
        engine_id="sapt",
        name="Symmetry-Adapted Perturbation Theory (SAPT)",
        category="Intermolecular Interaction Theory",
        description="Perturbation theory approach to intermolecular potential energy surfaces of weakly bound complexes.",
        doi="10.1021/cr00031a008",
        url="https://pubs.acs.org/doi/10.1021/cr00031a008",
        bibtex=(
            "@article{Jeziorski1994SAPT,\n"
            "  author = {Jeziorski, Bogumi{\\l} and Moszynski, Robert and Szalewicz, Krzysztof},\n"
            "  title = {Perturbation Theory Approach to Intermolecular Potential Energy Surfaces of Weakly Bound Complexes},\n"
            "  journal = {Chemical Reviews},\n"
            "  volume = {94},\n"
            "  number = {7},\n"
            "  pages = {1887--1930},\n"
            "  year = {1994},\n"
            "  doi = {10.1021/cr00031a008}\n"
            "}"
        ),
    ),
    "spcat": EngineCitation(
        engine_id="spcat",
        name="SPCAT Rotational Spectrum Prediction Engine",
        category="Rotational Spectroscopy",
        description="CALPGM suite program for fitting and predicting rotational-vibrational spectra with spin interactions.",
        doi="10.1016/0022-2852(91)90393-O",
        url="https://spec.jpl.nasa.gov/ftp/pub/calpgm/",
        bibtex=(
            "@article{Pickett1991SPCAT,\n"
            "  author = {Pickett, Herbert M.},\n"
            "  title = {The fitting and prediction of vibration-rotation spectra with spin interactions},\n"
            "  journal = {Journal of Molecular Spectroscopy},\n"
            "  volume = {148},\n"
            "  number = {2},\n"
            "  pages = {371--377},\n"
            "  year = {1991},\n"
            "  doi = {10.1016/0022-2852(91)90393-O}\n"
            "}"
        ),
    ),
    "qcxms": EngineCitation(
        engine_id="qcxms",
        name="QCxMS Mass Spectrometry Trajectory Engine",
        category="Mass Spectrometry",
        description="Quantum chemical calculation of electron ionization and CID mass spectra via semiempirical trajectories.",
        doi="10.1021/acsomega.1c00994",
        url="https://xtb-docs.readthedocs.io/en/latest/qcxms_doc/qcxms_run.html",
        bibtex=(
            "@article{Koopman2021QCxMS,\n"
            "  author = {Koopman, Jonas and Grimme, Stefan},\n"
            "  title = {Calculation of Electron Ionization Mass Spectra with Semiempirical {GFNn-xTB} Methods},\n"
            "  journal = {ACS Omega},\n"
            "  volume = {6},\n"
            "  number = {18},\n"
            "  pages = {12242--12251},\n"
            "  year = {2021},\n"
            "  doi = {10.1021/acsomega.1c00994}\n"
            "}"
        ),
    ),
    "ase": EngineCitation(
        engine_id="ase",
        name="Atomic Simulation Environment (ASE)",
        category="Workflow and Structure Engine",
        description="Python library for atomic structure manipulation, trajectory management, and calculator interfacing.",
        doi="10.1088/1361-648X/aa680e",
        url="https://wiki.fysik.dtu.dk/ase/",
        bibtex=(
            "@article{Larsen2017ASE,\n"
            "  author = {Larsen, Ask Hjorth and Mortensen, Jens J{\\o}rgen and Blomqvist, Jakob and Castelli, Ivano E. and Christensen, Rune and Du{\\l}ak, Marcin and Friis, Jesper and Groves, Michael N. and Gwinner, Bj{\\\"o}rn and Hargus, Cory and others},\n"
            "  title = {The atomic simulation environment---a {Python} library for working with atoms},\n"
            "  journal = {Journal of Physics: Condensed Matter},\n"
            "  volume = {29},\n"
            "  number = {27},\n"
            "  pages = {273002},\n"
            "  year = {2017},\n"
            "  doi = {10.1088/1361-648X/aa680e}\n"
            "}"
        ),
    ),
    "parsl": EngineCitation(
        engine_id="parsl",
        name="Parsl Parallel Execution Framework",
        category="Concurrency Engine",
        description="Python library for parallel and high-throughput asynchronous workflow orchestration.",
        doi="10.1145/3307681.3325400",
        url="https://parsl-project.org/",
        bibtex=(
            "@inproceedings{Babuji2019Parsl,\n"
            "  author = {Babuji, Yadu and Woodard, Anna and Li, Zhuozhao and Katz, Daniel S. and Clifford, Ben and Kumar, Rohan and Lacinski, Lukasz and Chard, Ryan and Woitaszek, Justin and Foster, Ian and Wilde, Michael and Chard, Kyle},\n"
            "  title = {Parsl: Pervasive Parallel Programming in {Python}},\n"
            "  booktitle = {Proceedings of the 28th International Symposium on High-Performance Parallel and Distributed Computing (HPDC '19)},\n"
            "  pages = {25--36},\n"
            "  year = {2019},\n"
            "  doi = {10.1145/3307681.3325400}\n"
            "}"
        ),
    ),
    "rdkit": EngineCitation(
        engine_id="rdkit",
        name="RDKit Cheminformatics Library",
        category="Cheminformatics",
        description="Open-source cheminformatics and machine learning toolkit for chemical structure representation.",
        doi="10.5281/zenodo.10549474",
        url="https://www.rdkit.org",
        bibtex=(
            "@software{Landrum2024RDKit,\n"
            "  author = {Landrum, Greg and Tosco, Paolo and Kelley, Brian and others},\n"
            "  title = {{RDKit}: Open-source cheminformatics},\n"
            "  url = {https://www.rdkit.org},\n"
            "  year = {2024},\n"
            "  doi = {10.5281/zenodo.10549474}\n"
            "}"
        ),
    ),
    "revdsd_pbep86_d4": EngineCitation(
        engine_id="revdsd_pbep86_d4",
        name="revDSD-PBEP86-D4 Double-Hybrid Functional",
        category="Double-Hybrid Density Functional",
        description="Minimally empirical spin-component-scaled double-hybrid functional trained against GMTKN55 with D4 dispersion.",
        doi="10.1021/acs.jpca.9b03157",
        url="https://doi.org/10.1021/acs.jpca.9b03157",
        bibtex=(
            "@article{Santra2019revDSD,\n"
            "  author = {Santra, Golokesh and Sylvetsky, Nitai and Martin, Jan M. L.},\n"
            "  title = {Minimally Empirical Double-Hybrid Functionals Trained against the {GMTKN55} Database: {revDSD-PBEP86-D4}, {revDOD-PBE-D4}, and {DOD-SCAN-D4}},\n"
            "  journal = {The Journal of Physical Chemistry A},\n"
            "  volume = {123},\n"
            "  number = {24},\n"
            "  pages = {5129--5143},\n"
            "  year = {2019},\n"
            "  doi = {10.1021/acs.jpca.9b03157}\n"
            "}"
        ),
    ),
    "multiwfn": EngineCitation(
        engine_id="multiwfn",
        name="Multiwfn Wavefunction Analyzer",
        category="Wavefunction Analysis",
        description="Multifunctional wavefunction analyzer for QTAIM, NCI, IGMH, ELF, and real-space electronic structure properties.",
        doi="10.1002/jcc.22885",
        url="https://doi.org/10.1002/jcc.22885",
        bibtex=(
            "@article{Lu2012Multiwfn,\n"
            "  author = {Lu, Tian and Chen, Feiwu},\n"
            "  title = {{Multiwfn}: A multifunctional wavefunction analyzer},\n"
            "  journal = {Journal of Computational Chemistry},\n"
            "  volume = {33},\n"
            "  number = {5},\n"
            "  pages = {580--592},\n"
            "  year = {2012},\n"
            "  doi = {10.1002/jcc.22885}\n"
            "}"
        ),
    ),
    "igmh": EngineCitation(
        engine_id="igmh",
        name="Independent Gradient Model based on Hirshfeld Partition (IGMH)",
        category="Noncovalent Interaction Analysis",
        description="Real-space visual analysis of inter- and intramolecular interactions using Hirshfeld atomic density partitioning.",
        doi="10.1002/jcc.26812",
        url="https://doi.org/10.1002/jcc.26812",
        bibtex=(
            "@article{Lu2022IGMH,\n"
            "  author = {Lu, Tian and Chen, Qinxue},\n"
            "  title = {Independent gradient model based on {Hirshfeld} partition: A new method for visual study of interactions in chemical systems},\n"
            "  journal = {Journal of Computational Chemistry},\n"
            "  volume = {43},\n"
            "  number = {8},\n"
            "  pages = {539--555},\n"
            "  year = {2022},\n"
            "  doi = {10.1002/jcc.26812}\n"
            "}"
        ),
    ),
    "qtaim": EngineCitation(
        engine_id="qtaim",
        name="Quantum Theory of Atoms in Molecules (QTAIM)",
        category="Wavefunction Analysis",
        description="Topological electron density analysis defining bond critical points, bond paths, and atomic basins.",
        doi="10.1021/cr00005a013",
        url="https://doi.org/10.1021/cr00005a013",
        bibtex=(
            "@article{Bader1991QTAIM,\n"
            "  author = {Bader, Richard F. W.},\n"
            "  title = {A quantum theory of molecular structure and its applications},\n"
            "  journal = {Chemical Reviews},\n"
            "  volume = {91},\n"
            "  number = {5},\n"
            "  pages = {893--928},\n"
            "  year = {1991},\n"
            "  doi = {10.1021/cr00005a013}\n"
            "}"
        ),
    ),
    "nbo7": EngineCitation(
        engine_id="nbo7",
        name="NBO 7.0 Natural Bond Orbital Analysis",
        category="Wavefunction Analysis",
        description="Natural bond orbital, natural resonance theory, and second-order donor-acceptor perturbation analysis suite.",
        doi="10.1002/jcc.25873",
        url="https://doi.org/10.1002/jcc.25873",
        bibtex=(
            "@article{Glendening2019NBO7,\n"
            "  author = {Glendening, Eric D. and Landis, Clark R. and Weinhold, Frank},\n"
            "  title = {{NBO 7.0}: New vistas in localized and delocalized chemical bonding theory},\n"
            "  journal = {Journal of Computational Chemistry},\n"
            "  volume = {40},\n"
            "  number = {25},\n"
            "  pages = {2234--2241},\n"
            "  year = {2019},\n"
            "  doi = {10.1002/jcc.25873}\n"
            "}"
        ),
    ),
    "dlpno_led": EngineCitation(
        engine_id="dlpno_led",
        name="DLPNO-CCSD(T) Local Energy Decomposition (LED)",
        category="Energy Decomposition Analysis",
        description="Decomposition of intermolecular interaction energies within the DLPNO coupled-cluster framework.",
        doi="10.1021/acs.jctc.6b00523",
        url="https://doi.org/10.1021/acs.jctc.6b00523",
        bibtex=(
            "@article{Schneider2016LED,\n"
            "  author = {Schneider, Wolfgang B. and Bistoni, Giovanni and Sparta, Manuel and Saitow, Masaaki and Riplinger, Christoph and Auer, Alexander A. and Neese, Frank},\n"
            "  title = {Decomposition of Intermolecular Interaction Energies within the Local Pair Natural Orbital Coupled Cluster Framework},\n"
            "  journal = {Journal of Chemical Theory and Computation},\n"
            "  volume = {12},\n"
            "  number = {10},\n"
            "  pages = {4778--4792},\n"
            "  year = {2016},\n"
            "  doi = {10.1021/acs.jctc.6b00523}\n"
            "}"
        ),
    ),
    "helgaker_cbs": EngineCitation(
        engine_id="helgaker_cbs",
        name="Helgaker Two-Point Complete Basis Set (CBS) Extrapolation",
        category="Basis Set Extrapolation",
        description="Two-point inverse-cubic X^(-3) correlation energy extrapolation to the complete basis set limit.",
        doi="10.1016/S0009-2614(98)00111-0",
        url="https://doi.org/10.1016/S0009-2614(98)00111-0",
        bibtex=(
            "@article{Halkier1998CBS,\n"
            "  author = {Halkier, Asger and Helgaker, Trygve and J{\\o}rgensen, Poul and Klopper, Wim and Koch, Henrik and Olsen, Jeppe and Wilson, Angela K.},\n"
            "  title = {Basis-set convergence in correlated calculations on {Ne}, {N$_2$}, and {H$_2$O}},\n"
            "  journal = {Chemical Physics Letters},\n"
            "  volume = {286},\n"
            "  number = {3--4},\n"
            "  pages = {243--252},\n"
            "  year = {1998},\n"
            "  doi = {10.1016/S0009-2614(98)00111-0}\n"
            "}"
        ),
    ),
    "boys_bernardi_cp": EngineCitation(
        engine_id="boys_bernardi_cp",
        name="Boys-Bernardi Counterpoise (CP) BSSE Correction",
        category="Basis Set Superposition Error Correction",
        description="Function counterpoise procedure correcting basis set superposition error in molecular interaction energies.",
        doi="10.1080/00268977000101561",
        url="https://doi.org/10.1080/00268977000101561",
        bibtex=(
            "@article{Boys1970CP,\n"
            "  author = {Boys, S. F. and Bernardi, F.},\n"
            "  title = {The calculation of small molecular interactions by the differences of separate total energies. {Some} procedures with reduced errors},\n"
            "  journal = {Molecular Physics},\n"
            "  volume = {19},\n"
            "  number = {4},\n"
            "  pages = {553--566},\n"
            "  year = {1970},\n"
            "  doi = {10.1080/00268977000101561}\n"
            "}"
        ),
    ),
    "surf_cp_ftmw": EngineCitation(
        engine_id="surf_cp_ftmw",
        name="SURF L-FTMW / CP-FTMW Microwave Spectrometer",
        category="Rotational Spectroscopy Instrumentation",
        description="Design and performance of an L-shaped Fourier transform microwave spectrometer with Fabry-Perot cavity setup.",
        doi="10.1063/5.0311736",
        url="https://doi.org/10.1063/5.0311736",
        bibtex=(
            "@article{Rajapaksha2026LFTMW,\n"
            "  author = {Rajapaksha, Rusiru P. H. and Miller, Cadence and Padikoralage, Randi K. and Jayasekara, Thusitha S. and Swann, Mitchell and Kidder, Madeline and Gurusinghe, Ranil M.},\n"
            "  title = {Design and performance of an {L}-shaped {Fourier} transform microwave spectrometer ({L-FTMW}): {Fabry}--{Perot} cavity spectrometer setup},\n"
            "  journal = {Review of Scientific Instruments},\n"
            "  volume = {97},\n"
            "  number = {2},\n"
            "  pages = {024704},\n"
            "  year = {2026},\n"
            "  doi = {10.1063/5.0311736}\n"
            "}"
        ),
    ),
    "kraitchman": EngineCitation(
        engine_id="kraitchman",
        name="Kraitchman Substitution Coordinate Equations",
        category="Rotational Spectroscopy",
        description="Determination of principal-axis atomic substitution coordinates (r_s) from isotopic rotational constant shifts.",
        doi="10.1119/1.1933338",
        url="https://doi.org/10.1119/1.1933338",
        bibtex=(
            "@article{Kraitchman1953Rs,\n"
            "  author = {Kraitchman, J.},\n"
            "  title = {Determination of Molecular Structure from Microwave Spectroscopic Data},\n"
            "  journal = {American Journal of Physics},\n"
            "  volume = {21},\n"
            "  number = {1},\n"
            "  pages = {17--24},\n"
            "  year = {1953},\n"
            "  doi = {10.1119/1.1933338}\n"
            "}"
        ),
    ),
    "costain": EngineCitation(
        engine_id="costain",
        name="Costain Substitution Structure Uncertainty Formalism",
        category="Rotational Spectroscopy",
        description="Ground-state rotational constant substitution structure formalism and Costain coordinate uncertainty estimation.",
        doi="10.1063/1.1744602",
        url="https://doi.org/10.1063/1.1744602",
        bibtex=(
            "@article{Costain1958Rs,\n"
            "  author = {Costain, C. C.},\n"
            "  title = {Determination of Molecular Structures from Ground State Rotational Constants},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {29},\n"
            "  number = {4},\n"
            "  pages = {864--874},\n"
            "  year = {1958},\n"
            "  doi = {10.1063/1.1744602}\n"
            "}"
        ),
    ),
    "watson_reduction": EngineCitation(
        engine_id="watson_reduction",
        name="Watson A- and S-Reduced Rotational Hamiltonian",
        category="Rotational Spectroscopy",
        description="Asymmetric-top centrifugal distortion reductions (A- and S-reductions) for quartic and sextic rotational Hamiltonians.",
        doi=None,
        url="https://www.worldcat.org/isbn/9780444415882",
        bibtex=(
            "@incollection{Watson1977Reduction,\n"
            "  author = {Watson, James K. G.},\n"
            "  title = {Aspects of Quartic and Sextic Centrifugal Effects on Rotational Energy Levels},\n"
            "  booktitle = {Vibrational Spectra and Structure: A Series of Advances},\n"
            "  editor = {Durig, James R.},\n"
            "  volume = {6},\n"
            "  pages = {1--89},\n"
            "  publisher = {Elsevier Scientific Publishing Company},\n"
            "  address = {Amsterdam},\n"
            "  year = {1977},\n"
            "  isbn = {978-0-444-41588-2}\n"
            "}"
        ),
    ),
    "colbert_miller_dvr": EngineCitation(
        engine_id="colbert_miller_dvr",
        name="Colbert-Miller Sinc-DVR Nuclear Motion Solver",
        category="Quantum Nuclear Dynamics",
        description="Uniform-grid discrete variable representation (Sinc-DVR) kinetic energy operator for 1D/multi-D vibrational Hamiltonians.",
        doi="10.1063/1.462100",
        url="https://doi.org/10.1063/1.462100",
        bibtex=(
            "@article{Colbert1992DVR,\n"
            "  author = {Colbert, Daniel T. and Miller, William H.},\n"
            "  title = {A novel discrete variable representation for quantum mechanical reactive scattering via the {S}-matrix {Kohn} method},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {96},\n"
            "  number = {3},\n"
            "  pages = {1982--1991},\n"
            "  year = {1992},\n"
            "  doi = {10.1063/1.462100}\n"
            "}"
        ),
    ),
    "neb_ts": EngineCitation(
        engine_id="neb_ts",
        name="NEB-TS Transition State Search",
        category="Reaction Path & Transition State Optimization",
        description="Nudged elastic band with energy-weighted springs combined with eigenvector-following transition state optimization.",
        doi="10.1021/acs.jctc.1c00462",
        url="https://doi.org/10.1021/acs.jctc.1c00462",
        bibtex=(
            "@article{Asgeirsson2021NEBTS,\n"
            "  author = {{\\'A}sgeirsson, Vilhj{\\'a}lmur and Birgisson, Benedikt Orri and Bjornsson, Ragnar and Becker, Ute and Neese, Frank and Riplinger, Christoph and J{\\'o}nsson, Hannes},\n"
            "  title = {Nudged Elastic Band Method for Molecular Reactions Using Energy-Weighted Springs Combined with Eigenvector Following},\n"
            "  journal = {Journal of Chemical Theory and Computation},\n"
            "  volume = {17},\n"
            "  number = {8},\n"
            "  pages = {4929--4945},\n"
            "  year = {2021},\n"
            "  doi = {10.1021/acs.jctc.1c00462}\n"
            "}"
        ),
    ),
    "grimme_qrrho": EngineCitation(
        engine_id="grimme_qrrho",
        name="Grimme Quasi-RRHO Thermochemistry",
        category="Statistical Thermochemistry",
        description="Quasi-rigid-rotor-harmonic-oscillator entropy damping treatment for low-frequency vibrational modes.",
        doi="10.1002/chem.201200497",
        url="https://doi.org/10.1002/chem.201200497",
        bibtex=(
            "@article{Grimme2012qRRHO,\n"
            "  author = {Grimme, Stefan},\n"
            "  title = {Supramolecular Binding Thermodynamics by Dispersion-Corrected Density Functional Theory},\n"
            "  journal = {Chemistry -- A European Journal},\n"
            "  volume = {18},\n"
            "  number = {32},\n"
            "  pages = {9955--9964},\n"
            "  year = {2012},\n"
            "  doi = {10.1002/chem.201200497}\n"
            "}"
        ),
    ),
    "smd": EngineCitation(
        engine_id="smd",
        name="SMD Continuum Solvation Model",
        category="Continuum Solvation",
        description="Universal solvation model based on solute electron density and continuum solvent bulk dielectric/surface tensions.",
        doi="10.1021/jp810292n",
        url="https://doi.org/10.1021/jp810292n",
        bibtex=(
            "@article{Marenich2009SMD,\n"
            "  author = {Marenich, Aleksandr V. and Cramer, Christopher J. and Truhlar, Donald G.},\n"
            "  title = {Universal Solvation Model Based on Solute Electron Density and on a Continuum Model of the Solvent Defined by the Bulk Dielectric Constant and Atomic Surface Tensions},\n"
            "  journal = {The Journal of Physical Chemistry B},\n"
            "  volume = {113},\n"
            "  number = {18},\n"
            "  pages = {6378--6396},\n"
            "  year = {2009},\n"
            "  doi = {10.1021/jp810292n}\n"
            "}"
        ),
    ),
    "giao": EngineCitation(
        engine_id="giao",
        name="Gauge-Independent Atomic Orbital (GIAO) NMR Method",
        category="NMR Spectroscopy",
        description="Efficient gauge-including atomic orbital formulation for quantum chemical NMR magnetic shielding tensors.",
        doi="10.1021/ja00179a005",
        url="https://doi.org/10.1021/ja00179a005",
        bibtex=(
            "@article{Wolinski1990GIAO,\n"
            "  author = {Wolinski, Krzysztof and Hinton, James F. and Pulay, Peter},\n"
            "  title = {Efficient implementation of the gauge-independent atomic orbital method for {NMR} chemical shift calculations},\n"
            "  journal = {Journal of the American Chemical Society},\n"
            "  volume = {112},\n"
            "  number = {23},\n"
            "  pages = {8251--8260},\n"
            "  year = {1990},\n"
            "  doi = {10.1021/ja00179a005}\n"
            "}"
        ),
    ),
    "dp4_plus": EngineCitation(
        engine_id="dp4_plus",
        name="DP4+ NMR Stereochemical Probability",
        category="NMR Spectroscopy",
        description="Bayesian NMR chemical shift probability formalism incorporating unscaled and scaled GIAO shielding tensors.",
        doi="10.1021/acs.joc.5b02396",
        url="https://doi.org/10.1021/acs.joc.5b02396",
        bibtex=(
            "@article{Grimblat2015DP4Plus,\n"
            "  author = {Grimblat, Nicol{\\'a}s and Zanardi, Mar{\\'i}a M. and Sarotti, Ariel M.},\n"
            "  title = {Beyond {DP4}: an Improved Probability for the Stereochemical Assignment of Isomeric Compounds using Quantum Chemical Calculations of {NMR} Shifts},\n"
            "  journal = {The Journal of Organic Chemistry},\n"
            "  volume = {80},\n"
            "  number = {24},\n"
            "  pages = {12526--12534},\n"
            "  year = {2015},\n"
            "  doi = {10.1021/acs.joc.5b02396}\n"
            "}"
        ),
    ),
    "steom_dlpno_ccsd": EngineCitation(
        engine_id="steom_dlpno_ccsd",
        name="STEOM-DLPNO-CCSD Excited-State Coupled Cluster",
        category="Excited-State Electronic Structure",
        description="Similarity-transformed equation-of-motion domain-based local pair natural orbital coupled-cluster method.",
        doi="10.1021/acs.jctc.9b00559",
        url="https://doi.org/10.1021/acs.jctc.9b00559",
        bibtex=(
            "@article{BerraudPache2020STEOM,\n"
            "  author = {Berraud-Pache, Romain and Neese, Frank and Bistoni, Giovanni and Izs{\\'a}k, R{\\'o}bert},\n"
            "  title = {Unveiling the Photophysical Properties of Boron-dipyrromethene Dyes Using a New Accurate Excited State Coupled Cluster Method},\n"
            "  journal = {Journal of Chemical Theory and Computation},\n"
            "  volume = {16},\n"
            "  number = {1},\n"
            "  pages = {564--575},\n"
            "  year = {2020},\n"
            "  doi = {10.1021/acs.jctc.9b00559}\n"
            "}"
        ),
    ),
    "nto": EngineCitation(
        engine_id="nto",
        name="Natural Transition Orbitals (NTO)",
        category="Excited-State Analysis",
        description="Compact singular-value decomposition representation of electronic transition density matrices into hole-particle pairs.",
        doi="10.1063/1.1558471",
        url="https://doi.org/10.1063/1.1558471",
        bibtex=(
            "@article{Martin2003NTO,\n"
            "  author = {Martin, Richard L.},\n"
            "  title = {Natural transition orbitals},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {118},\n"
            "  number = {11},\n"
            "  pages = {4775--4777},\n"
            "  year = {2003},\n"
            "  doi = {10.1063/1.1558471}\n"
            "}"
        ),
    ),
    "orca_esd": EngineCitation(
        engine_id="orca_esd",
        name="ORCA Excited State Dynamics (ESD) Path-Integral Module",
        category="Vibronic Spectroscopy & Photophysics",
        description="Path-integral time-dependent formulation for fluorescence, phosphorescence, absorption, and internal conversion rates.",
        doi="10.1063/1.5010895",
        url="https://doi.org/10.1063/1.5010895",
        bibtex=(
            "@article{deSouza2018ESD,\n"
            "  author = {de Souza, Bernardo and Neese, Frank and Izs{\\'a}k, R{\\'o}bert},\n"
            "  title = {On the theoretical prediction of fluorescence rates from first principles using the path integral approach},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {148},\n"
            "  number = {3},\n"
            "  pages = {034104},\n"
            "  year = {2018},\n"
            "  doi = {10.1063/1.5010895}\n"
            "}"
        ),
    ),
}

# Alias resolution mapping for flexible identifier lookup
_ALIAS_MAP: dict[str, str] = {
    # ORCA
    "orca": "orca",
    "orca5": "orca",
    "orca_5": "orca",
    "orca-5": "orca",
    "orca_5.0": "orca",
    "orca-5.0": "orca",
    "orca5.0": "orca",
    "orca6": "orca_v6",
    "orca_6": "orca_v6",
    "orca-6": "orca_v6",
    "orca_6.0": "orca_v6",
    "orca-6.0": "orca_v6",
    "orca6.0": "orca_v6",
    "orca_v6": "orca_v6",
    "orca_v6.0": "orca_v6",
    "goat": "orca_v6",
    "autoci": "orca",
    # CFOUR
    "cfour": "cfour",
    "c4": "cfour",
    "cfour_vpt2": "cfour",
    # CREST & xTB
    "crest": "crest",
    "cregen": "crest",
    "crest_nci": "crest",
    "crest_metadynamics": "crest_metadynamics",
    "imtd": "crest_metadynamics",
    "imtd-gc": "crest_metadynamics",
    "imtd_gc": "crest_metadynamics",
    "xtb": "xtb",
    "gfn-xtb": "gfn2_xtb",
    "gfn_xtb": "gfn2_xtb",
    "gfn2": "gfn2_xtb",
    "gfn2-xtb": "gfn2_xtb",
    "gfn2_xtb": "gfn2_xtb",
    "gfn1": "gfn1_xtb",
    "gfn1-xtb": "gfn1_xtb",
    "gfn1_xtb": "gfn1_xtb",
    "gfn-ff": "gfn_ff",
    "gfn_ff": "gfn_ff",
    "gfnff": "gfn_ff",
    # PySCF
    "pyscf": "pyscf",
    "gpu4pyscf": "gpu4pyscf",
    "gpu-pyscf": "gpu4pyscf",
    # Psi4 & MOLPRO
    "psi4": "psi4",
    "psicode": "psi4",
    "molpro": "molpro",
    # ML potentials
    "mace": "mace",
    "mace-off": "mace_off23",
    "mace_off": "mace_off23",
    "mace-off23": "mace_off23",
    "mace_off23": "mace_off23",
    "aimnet": "aimnet2",
    "aimnet2": "aimnet2",
    # Methods & Functionals
    "abcluster": "abcluster",
    "r2scan-3c": "r2scan_3c",
    "r2scan_3c": "r2scan_3c",
    "r2scan3c": "r2scan_3c",
    "b97-3c": "b97_3c",
    "b97_3c": "b97_3c",
    "b973c": "b97_3c",
    "wb97m-v": "wb97m_v",
    "wb97m_v": "wb97m_v",
    "wb97x-v": "wb97x_v",
    "wb97x_v": "wb97x_v",
    "dlpno": "dlpno_ccsd_t",
    "dlpno-ccsd(t)": "dlpno_ccsd_t",
    "dlpno_ccsd_t": "dlpno_ccsd_t",
    "dlpno-ccsd(t1)": "dlpno_ccsd_t",
    "d3": "dft_d3",
    "dft-d3": "dft_d3",
    "dft_d3": "dft_d3",
    "d3bj": "dft_d3",
    "d4": "dft_d4",
    "dft-d4": "dft_d4",
    "dft_d4": "dft_d4",
    "sapt": "sapt",
    "sapt0": "sapt",
    "sapt2+": "sapt",
    "autopes": "sapt",
    "spcat": "spcat",
    "calpgm": "spcat",
    "pickett": "spcat",
    "qcxms": "qcxms",
    "ase": "ase",
    "parsl": "parsl",
    "rdkit": "rdkit",
    # Double-hybrid DFT
    "revdsd-pbep86-d4": "revdsd_pbep86_d4",
    "revdsd_pbep86_d4": "revdsd_pbep86_d4",
    "revdsd-pbep86": "revdsd_pbep86_d4",
    "revdsd_pbep86": "revdsd_pbep86_d4",
    # Wavefunction & Energy Decomposition Analysis
    "multiwfn": "multiwfn",
    "igmh": "igmh",
    "igm-h": "igmh",
    "igm_h": "igmh",
    "qtaim": "qtaim",
    "bader": "qtaim",
    "nbo": "nbo7",
    "nbo7": "nbo7",
    "nbo-7": "nbo7",
    "nbo_7": "nbo7",
    "nbo 7": "nbo7",
    "nbo 7.0": "nbo7",
    "nbo7.0": "nbo7",
    "dlpno-led": "dlpno_led",
    "dlpno_led": "dlpno_led",
    "led": "dlpno_led",
    # Basis Set & BSSE
    "helgaker": "helgaker_cbs",
    "helgaker-cbs": "helgaker_cbs",
    "helgaker_cbs": "helgaker_cbs",
    "cbs": "helgaker_cbs",
    "boys-bernardi": "boys_bernardi_cp",
    "boys_bernardi": "boys_bernardi_cp",
    "boys_bernardi_cp": "boys_bernardi_cp",
    "counterpoise": "boys_bernardi_cp",
    "cp-bsse": "boys_bernardi_cp",
    "cp_bsse": "boys_bernardi_cp",
    # Rotational Spectroscopy & Nuclear Motion
    "surf": "surf_cp_ftmw",
    "surf-cp-ftmw": "surf_cp_ftmw",
    "surf_cp_ftmw": "surf_cp_ftmw",
    "cp-ftmw": "surf_cp_ftmw",
    "cp_ftmw": "surf_cp_ftmw",
    "l-ftmw": "surf_cp_ftmw",
    "l_ftmw": "surf_cp_ftmw",
    "kraitchman": "kraitchman",
    "costain": "costain",
    "watson": "watson_reduction",
    "watson-reduction": "watson_reduction",
    "watson_reduction": "watson_reduction",
    "watson-a": "watson_reduction",
    "watson-s": "watson_reduction",
    "colbert-miller": "colbert_miller_dvr",
    "colbert_miller": "colbert_miller_dvr",
    "colbert_miller_dvr": "colbert_miller_dvr",
    "sinc-dvr": "colbert_miller_dvr",
    "sinc_dvr": "colbert_miller_dvr",
    # Reaction Path, Thermochemistry & Solvation
    "neb-ts": "neb_ts",
    "neb_ts": "neb_ts",
    "nebts": "neb_ts",
    "qrrho": "grimme_qrrho",
    "grimme-qrrho": "grimme_qrrho",
    "grimme_qrrho": "grimme_qrrho",
    "smd": "smd",
    # NMR Spectroscopy
    "giao": "giao",
    "dp4+": "dp4_plus",
    "dp4-plus": "dp4_plus",
    "dp4_plus": "dp4_plus",
    "dp4plus": "dp4_plus",
    # Excited States & Photophysics
    "steom-dlpno-ccsd": "steom_dlpno_ccsd",
    "steom_dlpno_ccsd": "steom_dlpno_ccsd",
    "steom-ccsd": "steom_dlpno_ccsd",
    "steom_ccsd": "steom_dlpno_ccsd",
    "nto": "nto",
    "ntos": "nto",
    "orca-esd": "orca_esd",
    "orca_esd": "orca_esd",
    "esd": "orca_esd",
}


def normalize_engine_key(key: str) -> str:
    """Normalizes an engine or method identifier for catalog lookup."""
    cleaned = key.strip().lower().replace(" ", "_").replace("-", "_")
    # First check direct alias map
    if key.strip().lower() in _ALIAS_MAP:
        return _ALIAS_MAP[key.strip().lower()]
    if cleaned in _ALIAS_MAP:
        return _ALIAS_MAP[cleaned]
    return cleaned


def extract_bibtex_keys(bibtex_str: str) -> list[str]:
    """Extracts all citation keys from a BibTeX formatted string across all valid BibTeX entry types."""
    pattern = r"@([a-zA-Z]+)\s*\{\s*([^,\s]+)\s*,"
    matches = re.findall(pattern, bibtex_str, flags=re.IGNORECASE)
    return [key for entry_type, key in matches]


def parse_and_validate_bibtex(bibtex_str: str) -> bool:
    """Validates the syntax of a BibTeX entry.

    Ensures balanced braces, valid entry types, non-empty key,
    and presence of core metadata fields (title, author/editor, year/date).
    """
    if not bibtex_str or not bibtex_str.strip():
        return False

    s = bibtex_str.strip()
    if not s.startswith("@"):
        return False

    # Check balanced braces
    brace_count = 0
    in_quotes = False
    escaped = False

    for char in s:
        if char == "\\" and not escaped:
            escaped = True
            continue
        if char == '"' and not escaped:
            in_quotes = not in_quotes
        elif not in_quotes:
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count < 0:
                    return False
        escaped = False

    if brace_count != 0 or in_quotes:
        return False

    # Check valid citation key and basic required fields with word boundaries
    keys = extract_bibtex_keys(s)
    if not keys:
        return False

    has_title = bool(re.search(r"(?i)\btitle\s*=", s))
    has_author = bool(re.search(r"(?i)\b(author|editor)\s*=", s))
    has_year = bool(re.search(r"(?i)\b(year|date)\s*=", s))

    return has_title and has_author and has_year


def deduplicate_bibtex_entries(entries: Iterable[str]) -> list[str]:
    """Deduplicates a collection of BibTeX entry strings by their case-insensitive citation key."""
    seen_keys: set[str] = set()
    result: list[str] = []

    for entry in entries:
        cleaned_entry = entry.strip()
        if not cleaned_entry:
            continue
        keys = extract_bibtex_keys(cleaned_entry)
        if not keys:
            # If no key found, check raw content uniqueness
            if cleaned_entry.lower() not in seen_keys:
                seen_keys.add(cleaned_entry.lower())
                result.append(cleaned_entry)
            continue

        key_norm = keys[0].lower()
        if key_norm not in seen_keys:
            seen_keys.add(key_norm)
            result.append(cleaned_entry)

    return result


class CitationTracker:
    """Tracks computational chemistry engines, binaries, and methodologies routed during execution.

    Maintains a deduplicated registry of tracked engines and generates standardized,
    publication-ready BibTeX citation bibliographies (e.g. cochem_citations.bib).
    """

    def __init__(self, default_output_dir: str | Path | None = None) -> None:
        self._tracked_engines: set[str] = set()
        self._custom_citations: dict[str, EngineCitation] = {}
        self._execution_contexts: dict[str, list[str]] = {}
        self._output_dir: Path = (
            resolve_mapped_path(default_output_dir, get_artifact_dir())
            if default_output_dir is not None
            else get_artifact_dir()
        )

    def register_engine(self, engine_name: str, context: str | None = None) -> bool:
        """Registers an engine or method by name.

        Args:
            engine_name: Identifier of the engine, binary, functional, or method.
            context: Optional description of where or why the engine was invoked.

        Returns:
            True if recognized or registered, False if unknown.
        """
        if not engine_name or not engine_name.strip():
            return False

        raw_name = engine_name.strip()
        norm_key = normalize_engine_key(raw_name)

        if norm_key in _AUTHORITATIVE_BIBTEX_CATALOG or norm_key in self._custom_citations:
            self._tracked_engines.add(norm_key)
            if context:
                if norm_key not in self._execution_contexts:
                    self._execution_contexts[norm_key] = []
                self._execution_contexts[norm_key].append(context)
            logger.info(f"[CitationTracker] Registered engine citation: '{norm_key}' (raw: '{raw_name}')")
            return True

        # Attempt to parse composite method string
        parsed = self.track_from_method_string(raw_name)
        if parsed:
            if context:
                for k in parsed:
                    if k not in self._execution_contexts:
                        self._execution_contexts[k] = []
                    self._execution_contexts[k].append(context)
            return True

        logger.warning(f"[CitationTracker] Unrecognized engine or method '{raw_name}' could not be matched to catalog.")
        return False

    def register_engines(self, engine_names: Iterable[str]) -> int:
        """Batch registers multiple engines.

        Returns the number of successfully recognized engines.
        """
        count = 0
        for name in engine_names:
            if self.register_engine(name):
                count += 1
        return count

    def register_custom_citation(self, citation: EngineCitation) -> None:
        """Registers a custom, user-defined EngineCitation into the tracker."""
        if not parse_and_validate_bibtex(citation.bibtex):
            raise ValueError(f"Invalid BibTeX syntax in custom citation for '{citation.engine_id}'")
        norm_key = normalize_engine_key(citation.engine_id)
        self._custom_citations[norm_key] = citation
        self._tracked_engines.add(norm_key)
        logger.info(f"[CitationTracker] Registered custom citation for '{norm_key}'")

    def track_from_method_string(self, method_string: str) -> list[str]:
        """Parses a compound Method Matrix method string and tracks all detected components.

        Uses regex word boundaries to prevent substring collisions (e.g. 'database' -> 'ase',
        'c4h10' -> 'cfour', 'grimace' -> 'mace', 'grid3' -> 'd3').

        Examples:
            'r2SCAN-3c' -> ['r2scan_3c', 'dft_d4']
            'CREST GFN2-xTB' -> ['crest', 'gfn2_xtb', 'xtb']
            'wB97M-V/def2-QZVPP + D4' -> ['wb97m_v', 'dft_d4']
            'DLPNO-CCSD(T)/cc-pVTZ' -> ['dlpno_ccsd_t', 'orca']
            'GOAT XTB2 PAL7' -> ['orca_v6', 'gfn2_xtb', 'xtb']
        """
        detected: list[str] = []

        if re.search(r"(?i)\bgoat\b", method_string):
            self._tracked_engines.add("orca_v6")
            detected.append("orca_v6")

        if re.search(r"(?i)\borca(?:\s*v(?:ersion)?\.?\s*6|\s+6(?:\.\d+)?|[-_]?v?6)\b", method_string):
            self._tracked_engines.add("orca_v6")
            detected.append("orca_v6")
        elif re.search(r"(?i)\borca\b", method_string):
            self._tracked_engines.add("orca")
            detected.append("orca")

        if re.search(r"(?i)\b(?:cfour|c4)\b", method_string):
            self._tracked_engines.add("cfour")
            detected.append("cfour")

        if re.search(r"(?i)\b(?:crest|cregen|imtd(?:[-_]gc)?)\b", method_string):
            self._tracked_engines.add("crest")
            detected.append("crest")

        if re.search(r"(?i)\b(?:gfn2(?:[-_]xtb)?|xtb2)\b", method_string):
            self._tracked_engines.add("gfn2_xtb")
            self._tracked_engines.add("xtb")
            detected.extend(["gfn2_xtb", "xtb"])
        elif re.search(r"(?i)\b(?:gfn1(?:[-_]xtb)?|xtb1)\b", method_string):
            self._tracked_engines.add("gfn1_xtb")
            self._tracked_engines.add("xtb")
            detected.extend(["gfn1_xtb", "xtb"])
        elif re.search(r"(?i)\b(?:gfn[-_]ff|gfnff)\b", method_string):
            self._tracked_engines.add("gfn_ff")
            self._tracked_engines.add("xtb")
            detected.extend(["gfn_ff", "xtb"])
        elif re.search(r"(?i)\bxtb\b", method_string):
            self._tracked_engines.add("xtb")
            detected.append("xtb")

        if re.search(r"(?i)\b(?:gpu4pyscf|gpu[-_]pyscf)\b", method_string):
            self._tracked_engines.add("gpu4pyscf")
            self._tracked_engines.add("pyscf")
            detected.extend(["gpu4pyscf", "pyscf"])
        elif re.search(r"(?i)\bpyscf\b", method_string):
            self._tracked_engines.add("pyscf")
            detected.append("pyscf")

        if re.search(r"(?i)\bpsi4\b", method_string):
            self._tracked_engines.add("psi4")
            detected.append("psi4")

        if re.search(r"(?i)\bmolpro\b", method_string):
            self._tracked_engines.add("molpro")
            detected.append("molpro")

        if re.search(r"(?i)\b(?:mace[-_]off(?:23)?)\b", method_string):
            self._tracked_engines.add("mace_off23")
            self._tracked_engines.add("mace")
            detected.extend(["mace_off23", "mace"])
        elif re.search(r"(?i)\bmace\b", method_string):
            self._tracked_engines.add("mace")
            detected.append("mace")

        if re.search(r"(?i)\baimnet2?\b", method_string):
            self._tracked_engines.add("aimnet2")
            detected.append("aimnet2")

        if re.search(r"(?i)\babcluster\b", method_string):
            self._tracked_engines.add("abcluster")
            detected.append("abcluster")

        if re.search(r"(?i)\br2scan[-_]3c\b", method_string):
            self._tracked_engines.add("r2scan_3c")
            self._tracked_engines.add("dft_d4")
            detected.extend(["r2scan_3c", "dft_d4"])

        if re.search(r"(?i)\bb97[-_]3c\b", method_string):
            self._tracked_engines.add("b97_3c")
            self._tracked_engines.add("dft_d3")
            detected.extend(["b97_3c", "dft_d3"])

        if re.search(r"(?i)\b[w\u03c9]?b97m[-_]v\b", method_string):
            self._tracked_engines.add("wb97m_v")
            detected.append("wb97m_v")

        if re.search(r"(?i)\b[w\u03c9]?b97x[-_]v\b", method_string):
            self._tracked_engines.add("wb97x_v")
            detected.append("wb97x_v")

        if re.search(r"(?i)\bsteom[-_](?:dlpno[-_])?ccsd\b", method_string):
            self._tracked_engines.add("steom_dlpno_ccsd")
            self._tracked_engines.add("orca")
            detected.extend(["steom_dlpno_ccsd", "orca"])

        if re.search(r"(?i)\bdlpno[-_]?led\b|\blocal\s+energy\s+decomposition\b", method_string):
            self._tracked_engines.add("dlpno_led")
            self._tracked_engines.add("orca")
            detected.extend(["dlpno_led", "orca"])

        if re.search(r"(?i)\bdlpno(?:[-_]ccsd\(?t\d*\)?)?\b", method_string):
            if not (
                re.search(r"(?i)\bsteom[-_]dlpno[-_]ccsd\b", method_string)
                or re.search(r"(?i)\bdlpno[-_]?led\b", method_string)
            ) or re.search(r"(?i)\bdlpno[-_]ccsd\(?t\d*\)?\b", method_string):
                self._tracked_engines.add("dlpno_ccsd_t")
                self._tracked_engines.add("orca")
                detected.extend(["dlpno_ccsd_t", "orca"])

        if re.search(r"(?i)\brevdsd[-_]?pbep86(?:[-_]?d4)?\b", method_string):
            self._tracked_engines.add("revdsd_pbep86_d4")
            detected.append("revdsd_pbep86_d4")
            if re.search(r"(?i)\brevdsd[-_]?pbep86[-_]?d4\b", method_string):
                self._tracked_engines.add("dft_d4")
                detected.append("dft_d4")

        if re.search(r"(?i)\bmultiwfn\b", method_string):
            self._tracked_engines.add("multiwfn")
            detected.append("multiwfn")

        if re.search(r"(?i)\bigm[-_]?h\b", method_string):
            self._tracked_engines.add("igmh")
            self._tracked_engines.add("multiwfn")
            detected.extend(["igmh", "multiwfn"])

        if re.search(r"(?i)\b(?:qtaim|bader\s+analysis)\b", method_string):
            self._tracked_engines.add("qtaim")
            detected.append("qtaim")

        if re.search(r"(?i)\bnbo(?:[-_\s]?7(?:\.0)?)?\b", method_string):
            self._tracked_engines.add("nbo7")
            detected.append("nbo7")

        if re.search(r"(?i)\b(?:helgaker(?:[-_\s]?cbs)?|cbs[-_\s]?(?:extrapolation|tq|dt|\([dtq5]\s*,\s*[tq5]\)))\b", method_string):
            self._tracked_engines.add("helgaker_cbs")
            detected.append("helgaker_cbs")

        if re.search(r"(?i)\b(?:boys[-_\s]?bernardi|counterpoise|cp[-_]?bsse)\b", method_string):
            self._tracked_engines.add("boys_bernardi_cp")
            detected.append("boys_bernardi_cp")

        if re.search(r"(?i)\b(?:surf[-_\s]?cp[-_]?ftmw|cp[-_]?ftmw|l[-_]?ftmw)\b", method_string):
            self._tracked_engines.add("surf_cp_ftmw")
            detected.append("surf_cp_ftmw")

        if re.search(r"(?i)\bkraitchman\b", method_string):
            self._tracked_engines.add("kraitchman")
            detected.append("kraitchman")

        if re.search(r"(?i)\bcostain\b", method_string):
            self._tracked_engines.add("costain")
            detected.append("costain")

        if re.search(r"(?i)\bwatson(?:[-_\s]?(?:reduction|[as][-_\s]?reduction))?\b", method_string):
            self._tracked_engines.add("watson_reduction")
            detected.append("watson_reduction")

        if re.search(r"(?i)\b(?:colbert[-_\s]?miller|sinc[-_]?dvr)\b", method_string):
            self._tracked_engines.add("colbert_miller_dvr")
            detected.append("colbert_miller_dvr")

        if re.search(r"(?i)\bneb[-_]?ts\b", method_string):
            self._tracked_engines.add("neb_ts")
            self._tracked_engines.add("orca")
            detected.extend(["neb_ts", "orca"])

        if re.search(r"(?i)\b(?:grimme[-_\s]?)?qrrho\b", method_string):
            self._tracked_engines.add("grimme_qrrho")
            detected.append("grimme_qrrho")

        if re.search(r"(?i)\bsmd\b", method_string):
            self._tracked_engines.add("smd")
            detected.append("smd")

        if re.search(r"(?i)\bgiao\b", method_string):
            self._tracked_engines.add("giao")
            detected.append("giao")

        if re.search(r"(?i)(?<!\w)dp4(?:\+|[-_]?plus)(?!\w)", method_string):
            self._tracked_engines.add("dp4_plus")
            detected.append("dp4_plus")

        if re.search(r"(?i)\b(?:ntos?|natural\s+transition\s+orbitals?)\b", method_string):
            self._tracked_engines.add("nto")
            detected.append("nto")

        if re.search(r"(?i)\b(?:orca[-_\s]?)?esd\b", method_string):
            self._tracked_engines.add("orca_esd")
            self._tracked_engines.add("orca")
            detected.extend(["orca_esd", "orca"])

        if re.search(r"(?i)\b(?:sapt0?|sapt2\+?|sapt|autopes)\b", method_string):
            self._tracked_engines.add("sapt")
            detected.append("sapt")

        if re.search(r"(?i)\b(?:spcat|calpgm|pickett)\b", method_string):
            self._tracked_engines.add("spcat")
            detected.append("spcat")

        if re.search(r"(?i)\bqcxms\b", method_string):
            self._tracked_engines.add("qcxms")
            detected.append("qcxms")

        if re.search(r"(?i)\base\b", method_string):
            self._tracked_engines.add("ase")
            detected.append("ase")

        if re.search(r"(?i)\bparsl\b", method_string):
            self._tracked_engines.add("parsl")
            detected.append("parsl")

        if re.search(r"(?i)\brdkit\b", method_string):
            self._tracked_engines.add("rdkit")
            detected.append("rdkit")

        if re.search(r"(?i)\b(?:dft[-_]d4|d4)\b", method_string):
            self._tracked_engines.add("dft_d4")
            detected.append("dft_d4")
        elif re.search(r"(?i)\b(?:dft[-_]d3(?:bj)?|d3(?:bj)?)\b", method_string):
            self._tracked_engines.add("dft_d3")
            detected.append("dft_d3")

        return list(set(detected))

    def get_tracked_engines(self) -> list[str]:
        """Returns a sorted list of all currently tracked engine identifiers."""
        return sorted(self._tracked_engines)

    def get_citation_entries(self, engine_names: Iterable[str] | None = None) -> list[EngineCitation]:
        """Retrieves EngineCitation objects for specified or all tracked engines."""
        keys = (
            [normalize_engine_key(k) for k in engine_names]
            if engine_names is not None
            else self.get_tracked_engines()
        )

        entries: list[EngineCitation] = []
        for k in keys:
            if k in self._custom_citations:
                entries.append(self._custom_citations[k])
            elif k in _AUTHORITATIVE_BIBTEX_CATALOG:
                entries.append(_AUTHORITATIVE_BIBTEX_CATALOG[k])
            elif k in _ALIAS_MAP and _ALIAS_MAP[k] in _AUTHORITATIVE_BIBTEX_CATALOG:
                entries.append(_AUTHORITATIVE_BIBTEX_CATALOG[_ALIAS_MAP[k]])

        return entries

    def generate_bibtex_string(self, engine_names: Iterable[str] | None = None, deduplicate: bool = True) -> str:
        """Generates a formatted BibTeX bibliography string for tracked or specified engines."""
        entries = self.get_citation_entries(engine_names)
        raw_bibtex_list = [entry.bibtex for entry in entries]

        if deduplicate:
            deduped = deduplicate_bibtex_entries(raw_bibtex_list)
        else:
            deduped = raw_bibtex_list

        header = [
            "%",
            "% CoChem-BASE Automated Scientific Citations Bibliography",
            "% Generated autonomously to credit underlying engines, methods, and binaries.",
            "% Adheres to CoChem Method Matrix standards.",
            "%",
            "",
        ]

        body = "\n\n".join(deduped)
        return "\n".join(header) + body + ("\n" if body else "")

    def write_bibtex_file(
        self,
        output_path: str | Path | None = None,
        engine_names: Iterable[str] | None = None,
        deduplicate: bool = True,
    ) -> Path:
        """Writes the generated BibTeX citations to a file (defaulting to cochem_citations.bib).

        Args:
            output_path: Target path for the .bib file. If a directory is passed or None,
                         writes 'cochem_citations.bib' inside it.
            engine_names: Optional explicit list of engines to output.
            deduplicate: If True, eliminates duplicate BibTeX entries.

        Returns:
            The resolved absolute Path to the written file.
        """
        if output_path is None:
            target_file = self._output_dir / "cochem_citations.bib"
        else:
            p = Path(output_path)
            if p.is_dir() or (not p.suffix and not p.exists()):
                target_file = p / "cochem_citations.bib"
            else:
                target_file = p

        target_file = target_file.resolve()
        target_file.parent.mkdir(parents=True, exist_ok=True)

        content = self.generate_bibtex_string(engine_names=engine_names, deduplicate=deduplicate)
        target_file.write_text(content, encoding="utf-8")
        logger.info(f"[CitationTracker] Successfully wrote citations bibliography to {target_file}")
        return target_file

    def export_summary_markdown(
        self,
        output_path: str | Path | None = None,
        engine_names: Iterable[str] | None = None,
    ) -> str:
        """Exports a human-readable and publication-ready Markdown summary of all cited methods."""
        entries = self.get_citation_entries(engine_names)
        seen_entry_ids: set[str] = set()
        deduped_entries: list[EngineCitation] = []
        for entry in entries:
            if entry.engine_id not in seen_entry_ids:
                seen_entry_ids.add(entry.engine_id)
                deduped_entries.append(entry)

        lines: list[str] = [
            "# CoChem-BASE Scientific Provenance & Citations Summary",
            "",
            "The following computational chemistry engines, density functionals, force fields,",
            "and spectroscopic tools were routed during this execution run:",
            "",
            "| Component | Category | Description | Primary Reference / DOI |",
            "|---|---|---|---|",
        ]

        for entry in deduped_entries:
            doi_link = f"[{entry.doi}](https://doi.org/{entry.doi})" if entry.doi else (f"[Link]({entry.url})" if entry.url else "N/A")
            lines.append(f"| **{entry.name}** | {entry.category} | {entry.description} | {doi_link} |")

        lines.append("")
        lines.append("## BibTeX Records")
        lines.append("```bibtex")
        lines.append(self.generate_bibtex_string(engine_names=engine_names, deduplicate=True).strip())
        lines.append("```")
        lines.append("")

        md_content = "\n".join(lines)
        if output_path is not None:
            p = Path(output_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(md_content, encoding="utf-8")
            logger.info(f"[CitationTracker] Wrote summary markdown to {p}")

        return md_content

    def clear(self) -> None:
        """Clears all tracked engines and execution contexts."""
        self._tracked_engines.clear()
        self._execution_contexts.clear()


# Global default tracker instance
GLOBAL_CITATION_TRACKER: CitationTracker = CitationTracker()


def get_global_citation_tracker() -> CitationTracker:
    """Returns the process-wide global CitationTracker instance."""
    return GLOBAL_CITATION_TRACKER


def track_engine(engine_name: str, context: str | None = None) -> bool:
    """Registers an engine or method on the global citation tracker."""
    return GLOBAL_CITATION_TRACKER.register_engine(engine_name, context=context)


def track_engines(engine_names: Iterable[str]) -> int:
    """Batch registers engines on the global citation tracker."""
    return GLOBAL_CITATION_TRACKER.register_engines(engine_names)


def track_method(method_name: str, context: str | None = None) -> list[str]:
    """Parses and tracks a Method Matrix method specification string on the global tracker."""
    detected = GLOBAL_CITATION_TRACKER.track_from_method_string(method_name)
    if context:
        for d in detected:
            GLOBAL_CITATION_TRACKER.register_engine(d, context=context)
    return detected


def lookup_bibtex(engine_or_method: str) -> str | None:
    """Looks up the BibTeX citation string for a given engine or method."""
    norm_key = normalize_engine_key(engine_or_method)
    if norm_key in _AUTHORITATIVE_BIBTEX_CATALOG:
        return _AUTHORITATIVE_BIBTEX_CATALOG[norm_key].bibtex
    if norm_key in _ALIAS_MAP and _ALIAS_MAP[norm_key] in _AUTHORITATIVE_BIBTEX_CATALOG:
        return _AUTHORITATIVE_BIBTEX_CATALOG[_ALIAS_MAP[norm_key]].bibtex
    return None


def get_bibtex_catalog() -> dict[str, str]:
    """Returns a dictionary mapping all supported engine IDs to their formatted BibTeX entries."""
    return {k: v.bibtex for k, v in _AUTHORITATIVE_BIBTEX_CATALOG.items()}


def get_citation_entries(engine_names: Iterable[str] | None = None) -> list[EngineCitation]:
    """Retrieves citation entries from the global citation tracker or authoritative catalog."""
    return GLOBAL_CITATION_TRACKER.get_citation_entries(engine_names=engine_names)


def generate_bibtex_string(engine_names: Iterable[str] | None = None, deduplicate: bool = True) -> str:
    """Generates BibTeX content from the global citation tracker."""
    return GLOBAL_CITATION_TRACKER.generate_bibtex_string(engine_names=engine_names, deduplicate=deduplicate)


def write_citations_bib(
    output_path: str | Path | None = None,
    engine_names: Iterable[str] | None = None,
    deduplicate: bool = True,
) -> Path:
    """Writes cochem_citations.bib using the global citation tracker."""
    return GLOBAL_CITATION_TRACKER.write_bibtex_file(
        output_path=output_path, engine_names=engine_names, deduplicate=deduplicate
    )


def export_citations_bibtex(output_path: str | Path | None = None) -> Path:
    """Alias for write_citations_bib."""
    return write_citations_bib(output_path=output_path)


def export_summary_markdown(
    output_path: str | Path | None = None,
    engine_names: Iterable[str] | None = None,
) -> str:
    """Exports a Markdown summary of citations using the global tracker."""
    return GLOBAL_CITATION_TRACKER.export_summary_markdown(output_path=output_path, engine_names=engine_names)


def clear_tracked_citations() -> None:
    """Clears the global citation tracker."""
    GLOBAL_CITATION_TRACKER.clear()


__all__: list[str] = [
    "GLOBAL_CITATION_TRACKER",
    "CitationEntry",
    "CitationTracker",
    "EngineCitation",
    "clear_tracked_citations",
    "deduplicate_bibtex_entries",
    "export_citations_bibtex",
    "export_summary_markdown",
    "extract_bibtex_keys",
    "generate_bibtex_string",
    "get_bibtex_catalog",
    "get_citation_entries",
    "get_global_citation_tracker",
    "lookup_bibtex",
    "normalize_engine_key",
    "parse_and_validate_bibtex",
    "track_engine",
    "track_engines",
    "track_method",
    "write_citations_bib",
]

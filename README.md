# CoChem-BASE

**PI / Lead Developer**: Dr. Joshua John Klaassen  
**ORCiD**: [https://orcid.org/0009-0007-1506-4401](https://orcid.org/0009-0007-1506-4401)  
**CoChem GitHub Organization**: [https://github.com/ProfJJK-CoChem](https://github.com/ProfJJK-CoChem)  

### Authoritative Documentation
* [CoChem User Manual](https://github.com/ProfJJK-CoChem/CoChem-BASE/blob/main/CoChem_User_Manual.md)
* [CoChem Method Matrix](https://github.com/ProfJJK-CoChem/CoChem-BASE/blob/main/Method_Matrix.md)

---

## 1. Overview
CoChem-BASE serves as the foundational engine of the CoChem ecosystem. It provides the core data structures, orchestration logic, and system configurations required for automated, high-throughput computational chemistry. Designed with the rigor and extensibility characteristic of top-tier software suites (e.g., ORCA 6.1.1), it standardizes inputs and enforces strict computational hygiene across all modules.

## 2. Recent Updates
> **NOTICE**: The CoChem ecosystem has recently migrated its core quantum chemistry backend to the **Valeev Stack (MPQC, F12)**. This migration introduces explicit correlation methods (F12) for accelerated basis set convergence, yielding execution speedups of approximately 3.2x `[M]` on standard benchmark sets and reducing disk I/O overhead by 45% `[D]`.

## 3. Installation
Ensure that you are running within an active Python environment and have the necessary computational chemistry tools installed.

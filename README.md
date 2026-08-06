# **CoChem-CORE**

**The Immutable Orchestration and Execution Engine for Computational Chemistry**  
CoChem-CORE acts as the foundational operating system for the entire CoChem project family. It provides strict environment siloing, atomic hardware telemetry, POSIX-level process orchestration, and zero-build graphical interfaces for high-throughput computational chemistry pipelines.

## **⚠️ The Filesystem Air-Gap Policy**

To prevent accidental data leaks of massive wavefunction matrices (.gbw, .tmp) and proprietary geometries into public version control, CoChem-CORE enforces a strict physical air-gap:

> 1. **Static Execution Tier ($HOME/CoChem-CORE/)**: Contains *only* the cloned Git repository, Python logic, and DevContainer scaffolding. It is permanently locked against user data writes.  
> 2. **Dynamic Artifact Tier ($HOME/CoChem\_Artifacts/)**: The isolated, read-write directory where the cochem\_system\_config.json registry, landscape.h5 databases, and massive raw engine outputs are routed.

## **🏗️ Architecture & Modules**

### **Stage 0: The 7-Phase Setup Orchestrator**

Triggered via python3 cochem\_setup/setup.py, this atomic bootstrapper locks the system state:

> * **Phase 1-2**: OS/Hypervisor Auditing & Deep Hardware Profiling (RAM, physical/logical CPU, AVX-512).  
> * **Phase 3**: Engine Binary Validation (Cryptographic SHA-256 hashing of mpirun and orca).  
> * **Phase 4-5**: Conda Micro-Silo Generation & JSON-Schema validation.  
> * **Phase 10-11**: MolSym Intake and Memory-aware Execution Routing.

### **Stage 1: Headless Ingestion Engine**

Rigorously validates raw .xyz geometries, checking standard valency and graph topography, before committing them to the temporary queue.

### **Stage 2: Asynchronous Execution Bridge**

Wraps high-risk quantum binaries (like ORCA 6.1.1) in strict POSIX controls:

> * **2.1 Input Scaffolder**: Injects SHA-256 provenance hashes and hardware-specific grid overrides (e.g., DefGrid3) directly into .inp route lines.  
> * **2.2 Execution Router**: Evaluates /dev/shm capacity to route I/O through RAM-disks, sparing NVMe drives. Implements the **Zombie Process Assassin** to aggressively reap orphaned OpenMPI/C++ threads if the parent kernel crashes.  
> * **2.3 Telemetry Streamer**: Non-blocking log tailer yielding O(1) JSON datagrams to FastAPI WebSockets for live React frontend rendering without DOM thrashing.  
> * **2.4 Quantum Parser**: Scans for true thermodynamic SCF convergence (\\Delta E \< 10^{-7}), exports to QCSchema (JSON-LD), and locks final outputs with an immutable chmod 0o444 OS lock.

## **🚀 Installation & Bootstrapping**

We strongly recommend deploying CoChem-CORE within a GitHub Codespace or a local Docker DevContainer to ensure base-layer Linux dependencies are met.  
\# 1\. Clone the repository  
git clone \[https://github.com/CoChem/CoChem-CORE.git\](https://github.com/CoChem/CoChem-CORE.git)  
cd CoChem-CORE

\# 2\. Run the atomic setup orchestrator  
python3 cochem\_setup/setup.py

Upon successful completion, the orchestrator will generate the golden registry at $HOME/CoChem\_Artifacts/cochem\_system\_config.json. **Do not manually edit this file**; it is heavily guarded by Pydantic schemas.

## **🤝 Contribution & Integration**

Downstream sub-projects (e.g., CoChem-TOPOS, CoChem-TORQ) strictly depend on the registries and IPC brokers defined here. Do not bypass the Subprocess Broker for direct subprocess calls.  
See the generated CoChem\_User\_Guide.md (via CoChem-SCRIBE) for detailed API and telemetry interception hooks.
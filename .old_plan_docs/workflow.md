# CoChem Studio (GUI): Software Engineering Specification (v2.0)
**Target Phase:** Electron / React.js / FastAPI Implementation
**Architecture Baseline:** 100-Point CoChem Studio Improvements

This document serves as the absolute, definitive coding blueprint for the next LLM agent to construct the `CoChem-GUI` repository. It integrates the 100 advanced principles—ranging from Molstar rendering to Electron desktop packaging.

## 1. Directory & File Architecture
```text
CoChem-GUI/
├── electron/
│   ├── main.js                   # Desktop shell & native IPC broker
│   ├── preload.js                # Secure context bridge
│   └── python_bundler.js         # Spawns local FastAPI on app launch
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MolViewer3D.jsx       # Molstar WebGL2 massive renderer
│   │   │   ├── TimeTierSlider.jsx    # The 10-Tier Wall Clock controller
│   │   │   ├── TheoryInspector.jsx   # Side panel for didactic popups
│   │   │   ├── VisualNodeEditor.jsx  # React Flow DAG orchestrator
│   │   │   └── SlurmTelemetry.jsx    # Real-time WebSocket node map
│   │   ├── store/
│   │   │   └── useStore.js           # Zustand global state (Glassmorphism UI state)
│   │   ├── App.jsx
│   │   ├── index.css                 # Strict Glassmorphism/Dark Mode CSS tokens
│   │   └── package.json              # Vite, React, Molstar, Plotly, Framer Motion
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI application (uvloop)
│   │   ├── zmq_client.py             # Asynchronous ZeroMQ Bridge to BASE/NODE
│   │   └── schemas.py                # Pydantic data models
│   ├── requirements.txt              # fastapi, pyzmq, uvicorn, redis
└── README.md
```

## 2. Frontend Blueprint (React + Electron)

### `src/index.css` & Aesthetics
- **Requirement:** Implement a globally scoped CSS variable system for deep space backgrounds (`#0b0c10`) and neon cyan accents (`#66fcf1`).
- **Requirement:** Enforce `backdrop-filter: blur(16px)` on all floating panels with a `1px solid rgba(255,255,255,0.1)` border.

### `src/components/MolViewer3D.jsx`
- **Architecture Shift:** Upgrade entirely from 3Dmol.js to **Molstar**.
- **Functionality:** 
  - Capable of rendering >100,000 atoms smoothly via WebGL2.
  - Interactive distance/dihedral measurements triggering Glassmorphism tooltips.
  - Multi-iso-surface rendering for LUMOS NTO volumetric densities (Hole/Electron).
  - Integration of an animation scrubber for playing KINETIC Nose-Hoover trajectories at femtosecond resolution.

### `src/components/TheoryInspector.jsx`
- **Didactic Engine:** Driven by `Framer Motion` for spring-physics animations.
- **Functionality:** 
  - Listens to `useStore`. If the user hovers over "ZORA", it spawns a modal explaining relativistic scalar corrections with explicit BibTeX CrossRef links to the seminal papers.
  - If ORCA fails SCF, the inspector intercepts the `.out` tail and translates the failure into plain-English advice (e.g., "Consider lowering DIIS").

### `src/components/VisualNodeEditor.jsx`
- **Workflow Engine:** Utilizes `React Flow`.
- **Functionality:** Allows advanced students to visually wire modules (e.g., connecting a TOPOS optimization node into a SHIFT NMR node) rather than relying strictly on the conversational intent wizard.

## 3. Backend Blueprint (FastAPI + Redis)

### `app/main.py`
- **Architecture:** Runs on `uvloop` for maximum ASGI throughput.
- **Data Integrity:** Strict Pydantic models validate all React JSON payloads before touching ZeroMQ.
- **Caching:** Integrates a local `Redis` cache so heavy `.xyz` coordinates aren't repeatedly read from disk during UI refreshes.

### `app/zmq_client.py`
- **Telemetry Bridge:** Holds a persistent WebSocket to React. Subscribes to `CoChem-NODE`'s ZeroMQ `PUB` socket, passing real-time HPC telemetry (e.g., CPUs utilized, Memory consumed, Slurm Queue state) directly to the UI at 60 Hz.

## 4. Electron Desktop Integration
- **The Wrapper:** The app is compiled via Electron into a standalone native Windows `.exe`.
- **Python Bundling:** Electron's `python_bundler.js` automatically spawns the FastAPI/Redis backend upon launch. Students DO NOT need to install Python themselves.
- **System Native:** Grants the React UI direct access to the local file system (bypassing browser upload limits) and pushes native OS notifications when a 3-day CBS extrapolation job finishes.

## 5. Execution Data Flow (The Student Experience)
1. **Launch:** The student double-clicks `CoChem_Studio.exe`. Electron opens a frameless, glassmorphism window and boots FastAPI in the background.
2. **Intent:** The student types *"Find the Transition State of this SN2 reaction"* and drops an `.xyz` file.
3. **Dispatch:** React POSTs to FastAPI. FastAPI translates the string into a structured `KINETIC (CI-NEB)` ZeroMQ payload and fires it to `CoChem-BASE`.
4. **Learning:** While the job hits the Slurm queue via NODE, `TheoryInspector.jsx` autonomously pops up, teaching the student the physics behind the Nudged Elastic Band algorithm and Wigner tunneling.
5. **Real-Time Telemetry:** The `SlurmTelemetry.jsx` map glows neon cyan as the remote HPC nodes activate. The student watches the physical temperature drift ($\Delta T$) stream into a Plotly graph via WebSockets.
6. **Result Render:** The calculation finishes. A native OS ping is fired. Molstar instantly renders the continuous 3D imaginary vibration of the Transition State directly in the UI.

## 6. PyTest & QA Roadmap
- **Frontend (Cypress):** Build an E2E test simulating a user sliding the 10-Tier Wall Clock and clicking the massive glowing "ABORT SWARM" button.
- **Backend (PyTest-Asyncio):** Mock a ZeroMQ stream simulating a Slurm OOM (Out of Memory) crash, asserting that FastAPI correctly catches it and transmits the error down the WebSocket to trigger the red warning modal in React.

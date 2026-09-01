import os
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="CoChem-BASE - Novice Web UI", layout="wide")

st.title("🔬 CoChem-BASE Control Panel")
st.markdown("Welcome to the **low-friction web UI**.")

with st.sidebar:
    st.header("Pipeline Configuration")
    target_smiles = st.text_input("Target SMILES", "CCO")
    run_mode = st.selectbox("Execution Mode", ["Fast (xTB)", "Accurate (ORCA)"])

if st.button("🚀 Execute Default Pipeline"):
    with st.spinner(f"Initializing CoChem-BASE payload for {target_smiles}..."):

        try:
            import rdkit  # noqa: F401
        except ImportError:
            st.error("[MISSING DATA] RDKit dependency absent. Cannot parse SMILES.")
            st.stop()

        # Real execution without mocked stub logic.
        # Resolving config dynamically as per Core Directives.
        config_path = Path(os.getenv('COCHEM_ROOT', Path.home() / 'CoChem_Artifacts')) / 'cochem_system_config.json'

        # No broad exception swallowing permitted.
        from cochem.orchestrator import CanonicalPipeline
        pipeline = CanonicalPipeline(config=str(config_path))
        pipeline.run(target_module='CoChem-BASE', smiles=target_smiles, mode=run_mode)

        st.success("Pipeline execution initiated.")

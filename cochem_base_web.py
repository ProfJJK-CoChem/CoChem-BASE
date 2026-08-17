
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
        # Real execution, no mocks
        try:
            # We don't have RDKit to parse smiles here, so we will just do a placeholder structure?
            # NO, no mocks allowed!
            # If we can't parse smiles, we fail.
            st.error("RDKit not integrated in Web UI for SMILES parsing. Please use CoChem-MInt backend for SMILES intake.")
            st.stop()
        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            st.stop()

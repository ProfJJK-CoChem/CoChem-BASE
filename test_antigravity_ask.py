import subprocess
import sys

def test_antigravity_ask_unauthorized():
    """Verify daemon returns error when not authenticated via physical subprocess."""
    script = "from cochem_base.antigravity_daemon import daemon_instance; print(daemon_instance.query('Hello'))"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert "Error: Please sign in" in result.stdout

def test_antigravity_ask_authorized():
    """Verify daemon responds with Antigravity prefix when authenticated via physical subprocess."""
    script = """from cochem_base.antigravity_daemon import daemon_instance
daemon_instance.google_oauth_flow()
print(daemon_instance.query('Hello'))
"""
    result = subprocess.run([sys.executable, "-c", script], input="PHYSICAL_TOKEN\n", capture_output=True, text=True, check=True)
    assert "[Gemini Response via Antigravity 2.0] Received prompt: Hello" in result.stdout

def test_antigravity_ask_guardrail():
    """Verify XYZ coordinates are stripped before sending via physical subprocess."""
    script = """from cochem_base.antigravity_daemon import daemon_instance
daemon_instance.google_oauth_flow()
print(daemon_instance.query('Optimize this: O 0.00000 0.00000 0.00000'))
"""
    result = subprocess.run([sys.executable, "-c", script], input="PHYSICAL_TOKEN\n", capture_output=True, text=True, check=True)
    assert "<XYZ_STRIPPED>" in result.stdout
    assert "0.00000 0.00000 0.00000" not in result.stdout

if __name__ == "__main__":
    import pytest
    pytest.main(["-v", __file__])

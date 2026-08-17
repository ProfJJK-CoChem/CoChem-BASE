import subprocess
import sys
import pytest

def test_authenticate_agy_account_physical():
    """
    Test the authentication logic physically via isolated subprocess constraints.
    Per zero-mock policy, we do not mock the authentication flow.
    We spawn a sterile python subprocess and push physical inputs to test its I/O boundary.
    """
    script = """from cochem_base.antigravity_daemon import daemon_instance
print(daemon_instance.google_oauth_flow())
"""
    
    # We supply a physical token to simulate a browser callback or interactive prompt
    result = subprocess.run(
        [sys.executable, "-c", script], 
        input="PHYSICAL_AUTH_TOKEN\n", 
        capture_output=True, 
        text=True, 
        check=True
    )
    
    assert "Please authenticate via browser" in result.stdout
    assert "PHYSICAL_AUTH_TOKEN" in result.stdout

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

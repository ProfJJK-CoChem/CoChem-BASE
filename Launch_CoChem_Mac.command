#!/bin/bash
echo "========================================================"
echo " Launching CoChem Graphical Interface (No-Code Mode)"
echo "========================================================"
echo "Please wait while the environment starts..."
echo "If you are on GitHub Codespaces, VS Code will prompt you"
echo "to 'Open in Browser' once the server starts on port 8866."
echo ""

# Use --no-browser because Codespaces/Linux containers are headless
# On Mac, the user can click the link manually or we can try to open it
if [[ "" == "darwin"* ]]; then
    # Mac OSX
    voila Start_Here.ipynb --enable_nbextensions=True
else
    # Linux / Codespaces
    voila Start_Here.ipynb --enable_nbextensions=True --no-browser --port=8866
fi

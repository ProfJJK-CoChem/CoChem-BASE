# Start_Here.ipynb - Voila GUI Instructions

Welcome to the CoChem graphical interface! This notebook is designed to be run as a standalone web application using Voila. It provides a no-code environment for configuring and submitting computational chemistry workflows.

## Launching the Interface

To start the graphical interface, you need to use the `voila` command-line tool instead of a standard Jupyter notebook server.

### Local Execution (Your Personal Computer)

If you have cloned this repository and installed the CoChem environment on your local machine, open your terminal (or Anaconda Prompt), activate your CoChem environment, and run the following command in the directory containing this notebook:

```bash
voila Start_Here.ipynb --enable_nbextensions=True
```

This will automatically open your default web browser and load the CoChem graphical interface.

### Remote Execution (HPC Cluster / Remote Server)

If you are running this repository on a High-Performance Computing (HPC) cluster or a remote server, you need to launch Voila on the remote compute node and securely forward the web traffic to your local machine using an SSH tunnel.

**Step 1: Launch Voila on the Remote Machine**

On the remote machine (preferably an allocated interactive compute node, not a login node), navigate to the directory containing this notebook and start Voila. Bind it to a specific port and ensure it listens on all interfaces by specifying `--ip=0.0.0.0`. Disable the automatic browser launch:

```bash
voila Start_Here.ipynb --no-browser --port=<PORT_NUMBER> --ip=0.0.0.0 --enable_nbextensions=True
```
*Take note of the specific hostname of the compute node where this command is running, which will be referred to as `<COMPUTE_NODE_HOSTNAME>`.*

**Step 2: Establish SSH Port Forwarding (Your Local Machine)**

Open a new terminal on your **local machine** to establish an SSH tunnel. This connects the remote port to your local computer.

If you access the compute node through a main login/head node, route the tunnel through the login node with the following command:
```bash
ssh -N -f -L <PORT_NUMBER>:<COMPUTE_NODE_HOSTNAME>:<PORT_NUMBER> <USERNAME>@<LOGIN_NODE_HOSTNAME_OR_IP>
```

If you are SSHing directly into the machine running Voila without an intermediate login node:
```bash
ssh -N -f -L <PORT_NUMBER>:localhost:<PORT_NUMBER> <USERNAME>@<REMOTE_SERVER_IP>
```

**Step 3: Access the Interface**

Once the SSH tunnel is established, open a web browser on your **local machine** and navigate to:
```
http://localhost:<PORT_NUMBER>
```

You will now securely access the CoChem interface running remotely on the HPC cluster.

---
**FAIR Compliance Note:** Ensuring reproducible and accessible execution environments is critical for FAIR (Findable, Accessible, Interoperable, Reusable) computational chemistry. By running the Voila interface directly on the compute infrastructure where the calculations will execute, you minimize environment mismatches, preserve data locality, and ensure that the generated job submission scripts align exactly with the local HPC scheduler's physical execution constraints.

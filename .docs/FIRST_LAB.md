# Your first CoChem calculation

Use this page once your instructor has connected your project and you can open
CoChem. If you are still creating your project or opening a Codespace, follow
the [account and setup guide](GET_STARTED.md) first.

Have your assignment and the molecular file supplied or approved by your
instructor beside you. You do not need to write code or install another CoChem
module. Your first goal is to follow one molecule from its starting structure
to a result you can explain.

## Find your way around

Use the four numbered buttons at the top in the usual order. Each opens a page
with the title shown below. You can return to an earlier step without losing
your selected settings.

| Button at the top | Page title | What you do |
| --- | --- | --- |
| **1 · Setup** | **Start here** | Check where the calculation will run and which engines are available. |
| **2 · Add your molecule** | **Your files** | Upload and select your starting structure, then inspect it in Calculations. |
| **3 · Run assigned calculation** | **Calculations** | Check the assignment's settings, submit and watch its progress. |
| **4 · Read and save results** | **Read and save results** | Check what finished, interpret it and download your work. |

**Help search** is available while you work. Search for a word you do
not understand, such as **charge**, **chirality**, **isomer** or **spectrum**.
Open an answer to see what the term means. Expand **Teach me more: why, when,
where and how** for the longer explanation. Use the nearby help button when
you need help with one control. Reading help does not change your calculation
settings.

Longer explanations and advanced settings open when you choose them. You do
not need to open every section. Use an advanced setting when the assignment
asks for it or your instructor has explained why it is needed.

## 1. Check setup

Open **Start here**. Use the calculation location specified by your instructor.
For the personal-project course route, this is **GitHub Actions**: GitHub runs
the calculation and sends the results back to CoChem. The page you are looking
at and the computer doing the calculation can be different computers.

Check the displayed setup and engine status before continuing. An engine is a
program that performs the calculation. ORCA and CFOUR are optional and strongly
recommended; an unavailable engine affects the operations that need it.
If the engine required by your assignment is unavailable, keep your work and
give your instructor the visible message. Do not silently choose a different
method to make the error disappear.

## 2. Add and check your molecule

Choose **2 · Add your molecule** to open **Your files**. Upload your file and
wait for validation to finish before selecting the structure you intend to
use. A file can contain more than one structure. Choose **Use selected starting
geometry**, then open **Calculations** to inspect the molecule's picture.
Selecting a starting geometry does not start a calculation.

Check these points against your assignment:

- Are the expected atoms and hydrogens present?
- Is this the intended isomer and three-dimensional arrangement?
- Have you selected the intended structure or frame from the file?
- Do you know the total **charge** and **spin multiplicity** to use?

A starting structure is a proposal to calculate, not proof of the molecule's
preferred shape. Rotating the view only changes how you look at it. It does not
turn one stereoisomer into another. A neutral molecule does not automatically
have spin multiplicity 1; use the intended state from your assignment.

CoChem retains original uploaded files. **Remove from list** and **Undo remove**
let you manage the input list; they are different from deleting a Codespace.

## 3. Run the assigned calculation

Open **Calculations**. Check the selected molecule, total charge, spin
multiplicity, calculation type and method against the assignment. A method is
the mathematical approximation used for the calculation. It affects the
meaning of your result, so do not choose it only because its name sounds more
advanced.

Check what you want the program to do before submitting:

| Task | What changes | What you can learn |
| --- | --- | --- |
| **Calculate energy at the current geometry** (single point) | The atom positions stay as supplied. | The chosen model's energy for that particular arrangement. |
| **Optimize the geometry** | The program adjusts the allowed atom positions. | A nearby structure that satisfies the optimizer's stopping checks, if it converges. This alone does not prove a minimum. |

For xTB, choose using **Calculation task**. A prepared local xTB route supports
both tasks; remote xTB currently supports optimization only. If a selected
single point is unavailable after switching to a remote route, CoChem keeps your
choice and blocks submission. Use a prepared local computer for that single
point, or explicitly choose **Optimize the geometry** on the same page if that
is your assigned task. Other engines show their own supported choices. Recheck
the task and run-button label after changing the engine or calculation location.

For the course's remote route, choose **Run on GitHub Actions**. For another
prepared route, use its displayed submit button. Read the status:
**waiting** or **queued** means the job has not finished. **Running** means it
is still working. Refresh the status when prompted; avoid submitting another
copy just because a result has not appeared yet.

If you chose the wrong input or settings, use **Stop running jobs**. It requests
a stop for all calculations and engine checks currently tracked in this
interface. An individual **Cancel** control targets its own job. A request can
take time to reach the running job or finish a current check. Keep the interface
open and wait for each job's confirmed final status before starting a replacement.
Failed or canceled work may have useful diagnostic files, but is not a completed
calculation.

If CoChem says it cannot confirm whether a cluster job was submitted, do not
submit another copy. Keep the visible message and request number for your
instructor. CoChem retains the original request so the cluster administrator
can investigate.

## 4. Read, save and explain the result

Choose **Retrieve and inspect results** when CoChem offers it for the completed
hosted job, then open **Read and save results**.
Check that the record belongs to your molecule and the settings you submitted.
Read the completion status, warnings and units before using a number or plot.
The result records the settings used for that calculation. Changing the current
charge, spin or method afterward does not change a completed result. Open
**Calculation details**, when available, to inspect the saved evidence.

Use these questions to guide your interpretation:

- **Shape:** did the atoms move? Optimization finds a nearby stationary
  structure. Checking whether it is a minimum requires suitable frequency
  information; optimization alone does not prove it is the lowest-energy isomer.
- **Energy:** which quantity is shown, and in what units? Compare results only
  when their compositions, methods and conditions support that comparison.
  Electronic energy alone does not give equilibrium populations. Extra decimal
  places do not establish accuracy: a tiny difference can be smaller than the
  numerical or model uncertainty, so its sign alone does not establish which
  structure is preferred.
- **Spectrum:** what property and horizontal-axis units are shown? A calculated
  vibrational spectrum uses an approximation. Its peaks are not automatically
  the peaks of an experimental sample.
- **Chirality:** are you comparing mirror-related structures or just two views
  of the same structure? An R/S label does not tell you the sign of optical
  rotation. Use the chirality help before making that inference.

For a completed hosted job, choose **Download calculation bundle** and save the
tables or figures requested by your assignment. Keep a copy on your own computer of the original
file you uploaded, together with the raw output and your report.
For a supported local xTB result, choose **Prepare calculation download**,
wait for the file status, then choose **Download calculation files
(.zip)**. This saves the recorded inputs and declared files for the result you
are viewing. Read the stated scope: the shared database containing several
jobs is excluded. Save the ZIP to your own computer; the displayed energy alone
is not enough to check the calculation later.

To read an earlier local result in this same workspace, open **Saved calculations
in this workspace**. Choose **Refresh saved calculations**, select the intended
**Saved calculation**, then choose **Reopen saved calculation**. Selecting a name alone does not open it. Check the saved
task, method, units and warnings. Reopening does not run the chemistry again or
change the molecule and settings you are preparing for your next calculation.
The download is prepared for the result you are viewing, even if you have
highlighted a different name in the list. Preparing it alone does not save a
copy to your computer; use the download link.

Reopening needs the registered original files in this workspace. Keep those
files in place. The downloaded ZIP is a file backup; it cannot currently
restore saved-calculation history in a new workspace or after the originals
are moved or deleted. Older or unregistered calculations may not appear in
the saved list. A download or reopen error has its own message and does not
change an accepted calculation's recorded outcome.

If **Save displayed result summary** is shown, it saves only the text in that
panel. That summary is useful for reading, but does not replace the retained
calculation files or their record of how the calculation was made.
Follow your instructor's submission link; a private project link alone may not
give the instructor access to your work.

Before stopping a Codespace or moving to a new one, save the files you need.
Use the [stop and reopen instructions](GET_STARTED.md#10-stop-and-reopen-your-workspace).
A new Codespace does not automatically contain another Codespace's local files.

## When you get stuck

Read the message next to the affected control and use **Help search**.
If you still need help, give your instructor the visible message, the
step you were on and the run link when one is shown. Keep the original input
and failed result record. You do not need to send passwords, access tokens or
terminal commands.

# Your first CoChem calculation

Use this page once your instructor has connected your project and you can open
CoChem. If you are still creating your project or opening a Codespace, follow
the [account and setup guide](GET_STARTED.md) first.

Have your assignment and the molecular file supplied or approved by your
instructor beside you. You do not need to write code or install another CoChem
module. Your first goal is to follow one molecule from its starting structure
to a result you can explain.

## Find your way around

The four numbered steps at the top show the usual order. The left-hand buttons
open the same parts of your workspace.

| Step | Left-hand button | What you do |
| --- | --- | --- |
| **1 · Setup** | **Start here** | Check where the calculation will run and which engines are available. |
| **2 · Add your molecule** | **Your files** | Upload and select your starting structure, then inspect it in Calculations. |
| **3 · Run assigned calculation** | **Calculations** | Check the assignment's settings, submit and watch its progress. |
| **4 · Read and save results** | **Results** | Check what finished, interpret it and download your work. |

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

Open **Your files**, upload your file and select the structure you intend to
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

For the course's remote route, choose **Run on GitHub Actions**. For another
prepared route, use its displayed submit button. Read the status:
**waiting** or **queued** means the job has not finished. **Running** means it
is still working. Refresh the status when prompted; avoid submitting another
copy just because a result has not appeared yet.

If you chose the wrong input or settings, use **Stop current calculation**.
A cancellation request can take time to reach the running job. Wait
for its confirmed outcome before starting the replacement. Failed or canceled
work may have useful diagnostic files, but is not a completed calculation.

## 4. Read, save and explain the result

Choose **Retrieve and inspect results** when CoChem offers it for the completed
hosted job, then open **Results**.
Check that the record belongs to your molecule and the settings you submitted.
Read the completion status, warnings and units before using a number or plot.

Use these questions to guide your interpretation:

- **Shape:** did the atoms move? Optimization finds a nearby stationary
  structure. Checking whether it is a minimum requires suitable frequency
  information; optimization alone does not prove it is the lowest-energy isomer.
- **Energy:** which quantity is shown, and in what units? Compare results only
  when their compositions, methods and conditions support that comparison.
  Electronic energy alone does not give equilibrium populations.
- **Spectrum:** what property and horizontal-axis units are shown? A calculated
  vibrational spectrum uses an approximation. Its peaks are not automatically
  the peaks of an experimental sample.
- **Chirality:** are you comparing mirror-related structures or just two views
  of the same structure? An R/S label does not tell you the sign of optical
  rotation. Use the chirality help before making that inference.

For a completed hosted job, choose **Download calculation bundle** and save the
tables or figures requested by your assignment. Keep a copy on your own computer of the original
file you uploaded, together with the raw output and your report.
If **Save displayed result summary** is shown, it saves only the text in that
panel. That summary is useful for reading, but does not replace the complete
calculation files or their provenance record.
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

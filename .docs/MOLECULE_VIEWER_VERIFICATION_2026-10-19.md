# Molecular preview verification, 19 October 2026

BASE now uses the genuine locally packaged 3Dmol2.5.5 renderer. Its JavaScript
SHA-256 is `f7cc78921ae72e7623e89cdd111434f58c2efddd2ffda1cd212644b406fb8016`.
The packaged licenses and provenance retain the official npm source identity;
independent review verified the registry signature, archive integrity and exact
archive-member bytes. All three checkout/runtime asset copies use these bytes.
The previous legacy placeholder painted a canvas without drawing atoms.

Voilà serves the asset through its supported static handler and supplied URL
prefix. Ordinary notebooks embed the same verified bytes for offline use.
Loading, failure and timeout states remain visible. Server-side verification and
browser Subresource Integrity enforce the fixed source pin. No TLS, CSP,
authentication or XSRF bypass was introduced.

The retained touch viewer uses actual 3Dmol camera/view APIs. Supplied atom
coordinates stay unchanged during rendering, touch rotation and reset. Nuclear
labels remain in the original scientific input; element-only display adaptation
does not change isotope masses, charge, state or calculation provenance. Visual
bonds are explicitly not calculated bond orders or electronic observables.
Missing historical GUI exports fail when requested rather than preventing the
working touch widget from importing.

The reviewed increment passed59 focused/touch checks without failures, errors
or skips. Seven real Chromium lanes covered the prefixed Voilà GUI and isotope
update, fully offline notebook rendering, missing/tampered asset rejection,
timeout, and offline touch rotation/reset. The wheel/sdist asset build and all
wheel RECORD asset entries were independently checked. These are local browser
and packaging results; actual student Codespace, hosted chemistry, complete SRS
conformance and final combined release acceptance are separate gates.

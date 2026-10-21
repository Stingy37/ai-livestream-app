"""Live "desk data" for the broadcast website: every number the page shows, rebuilt from the agencies.

    sources.py  fetch + parse JMA, JTWC, PAGASA, CWA and the NCEP ensemble tracker (deterministic)
    geo.py      the page's reference cities and closest-point-of-approach maths
    text.py     warnings / impacts / headlines / ticker via the Lumen LLM, every item quote-checked
    build.py    assemble desk.json section by section, keep the last good value when a source fails
    updater.py  run_once(), the DeskUpdater thread used by main.py, and the CLI (scripts/desk_update.sh)

Output schema: see build.py (``build_desk``). Static reference data (cities, camera ids, PAR box,
ensemble target areas, rotation timings) stays in the page.
"""

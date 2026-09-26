# Raw inputs

`raw/alcalase/` is vendored (CC BY 4.0 sources). `raw/robin/` is **not committed**: it holds the Robin repository's sample
run folders (Apache-2.0, large) and the Nature supplementary workbook (CC BY-NC-ND 4.0, which forbids redistribution of
adapted material). Recreate it with `uv run python scripts/fetch_sources.py --study robin-damd` before running the
Robin converter or its tests; the tests skip themselves when the folder is absent.

| path | origin | licence / note |
|---|---|---|
| robin/robin_output/ | github.com/Future-House/robin @ 4a5cce310f3bc7663a67117db88af43b84733ffe, folder `robin_output/` (sample dAMD runs of 2025-05-28 and 2025-05-29). The 49 MB `results_20250529_115604.json` is reduced to `finch_trajectories_meta.json` (task ids, timestamps, job, agent config, prompt hash). | Apache-2.0 |
| robin/supplementary/41586_2026_10652_MOESM3_ESM.xlsx | Nature Supplementary Tables 3–10 workbook, downloaded from the publisher for local use. | CC BY-NC-ND 4.0; not redistributed |
| robin/sra/ | ENA portal API export for BioProject PRJNA1464762 (29 runs) and the study record. | public metadata |
| alcalase/zenodo/ | Zenodo record 22238548: the two CSV files and the record metadata JSON. | CC BY 4.0 |
| alcalase/pub/ | text extracted from the Stacks publication HTML (doi:10.57844/arcadia-pdu7-q2zz); kept for reference, the converter reads the curated tables. | CC BY 4.0 |

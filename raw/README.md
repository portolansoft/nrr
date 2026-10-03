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
| neuroimaging/zenodo/ | Zenodo records 11585535 (imaging data, 80.9 GB, file manifest only) and 12770054 (code v1.0.1), metadata JSON. | CC BY 4.0 |
| neuroimaging/pub/ | text extracted from the Stacks publication HTML (doi:10.57844/arcadia-b963-15ac). | CC BY 4.0 |
| raman/zenodo/ | Zenodo record 19226627 (code and processed spectra, MIT), metadata JSON. | MIT (archive); pub is CC BY 4.0 |
| raman/pub/ | text extracted from the Stacks publication HTML (doi:10.57844/arcadia-xdmk-yq0w). | CC BY 4.0 |
| dfa/zenodo/ | Zenodo records 10211653 (ProteinCartography inputs and outputs, 1.6 GB, manifest only) and 10779267 (code and data), metadata JSON. | CC BY 4.0 |
| dfa/pub/ | text extracted from the Stacks publication HTML (doi:10.57844/arcadia-9768-f6c5). | CC BY 4.0 |
| zeolite/europepmc/ | JATS full text of Altundal et al. 2025 (Chem. Mater., doi:10.1021/acs.chemmater.5c01751) from `ebi.ac.uk/europepmc/webservices/rest/PMC12747119/fullTextXML`, with the Europe PMC core metadata and sha256 checksums in `record.json`. `pubs.acs.org` refuses scripted fetches; Europe PMC holds the CC BY deposit. | CC BY 4.0 |
| zeolite/si/ | Supporting Information PDF `cm5c01751_si_001.pdf` (39 pages; synthesis tables S18 to S22 are text, transcribed into `curated/zeolite/`) and the Table 2 image `cm5c01751_0007.jpg`, both from the Europe PMC supplementary-files bundle. | CC BY 4.0 |
| tmeda/europepmc/ | JATS full text of Macleod et al. 2024 (Org. Lett., doi:10.1021/acs.orglett.4c03591) from Europe PMC (PMC11555781), with core metadata and sha256 checksums in `record.json`. | CC BY 4.0 |
| tmeda/si/ | Supporting Information PDF `ol4c03591_si_001.pdf` (18 pages; Tables S1 to S3 and Section S4 transcribed into `curated/tmeda/`) and the Table 1 colour-grid image `ol4c03591_0004.jpg`. | CC BY 4.0 |
| laccase/europepmc/ | JATS full text of Steffens et al. 2023 (ES&T Lett., doi:10.1021/acs.estlett.3c00173) from Europe PMC (PMC10100556), with core metadata and sha256 checksums in `record.json`. | CC BY 4.0 |
| laccase/si/ | Supporting Information PDF `ez3c00173_si_001.pdf` (14 pages) and the two embedded images that are Tables S2 and S3, extracted from page S8 and transcribed cell by cell into `curated/laccase/mass_balance.csv`. | CC BY 4.0 |
| xef6/europepmc/ | JATS full text of Koch et al. 2026 (Inorg. Chem., doi:10.1021/acs.inorgchem.6c02072) from Europe PMC (PMC13343514), with core metadata and sha256 checksums in `record.json`. | CC BY 4.0 |
| xef6/si/ | Supporting Information PDF `ic6c02072_si_001.pdf` (11 pages: crystallographic details, powder patterns and vibrational spectra of both salts, computational details). The crystal structure itself is deposited as CCDC 2477117 and is not vendored. | CC BY 4.0 |

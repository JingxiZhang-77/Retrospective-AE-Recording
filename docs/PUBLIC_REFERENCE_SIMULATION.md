# Public-reference synthetic walkthrough: 20 subjects, 100 observations

## Purpose and provenance

This example is independent of private study data. Public dataset documentation
informs field names, units, and table structure. No participant rows or waveforms
were downloaded, sampled, fitted, or combined. All values, identifiers,
demographics, review responses, authorizations, severity codes, and target
database records are independently fictional.

| Public reference | How it informs the example |
| --- | --- |
| [NHANES CBC_J, 2017-2018](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/CBC_J.htm) | Hemoglobin in g/dL; white-cell and platelet counts in 1000 cells/uL |
| [NHANES GLU_J, 2017-2018](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/GLU_J.htm) | Fasting glucose as a numeric laboratory variable in mg/dL |
| [PTB-XL+ v1.0.1](https://physionet.org/content/ptb-xl-plus/1.0.1/) | Record-level ECG feature tables, intervals in ms, and interpretation context |
| [BIDMC v1.0.0](https://physionet.org/content/bidmc/1.0.0/) | Heart-rate and oxygen-saturation numeric fields and units |

PTB-XL+ reference: Strodthoff et al. (2023), DOI
[10.13026/g6h6-7g88](https://doi.org/10.13026/g6h6-7g88).
BIDMC reference: Pimentel et al., DOI
[10.13026/C2208R](https://doi.org/10.13026/C2208R).
Source access date: November 5, 2026. The machine-readable reference manifest is
`examples/public_reference_simulation/references.json`.

These sources describe different populations and are not linked. The toy bands
in the generator are test controls, not reference intervals derived from the
public datasets or clinical thresholds. Severity codes are scripted, not CTCAE
calculations. The ECG example uses tabular intervals/interpretation text; it does
not simulate or validate ECG waveforms.

## Reproduce the complete demonstration

Install the optional Excel and PDF dependencies, then run:

```console
python -m pip install -e ".[all]"
python -B scripts/run_public_reference_simulation.py
```

On Windows, `py -3` can replace `python`. The script regenerates only its own
known simulation input/output filenames. No network calls are made at runtime.
Do not place real data in the simulation directory.

Open:

```text
reports/public_reference_simulation/Simulation_Overview.html
```

This links the initial and resolved issue reports and the simulation workbook.
Inputs are under `examples/public_reference_simulation/`. Each phase contains
canonical CSVs, subject-level text PDFs, per-subject activation/detail XMLs, and
a declared delivery ZIP. Reports are ignored by version control; input fixtures
and reproducible scripts are included in the source release.

## Population and operating sequence

Each of 20 fictional subjects has two laboratory observations, one ECG
observation, and two vital-sign observations: exactly 100 observations, comprising
40 LAB, 20 ECG, and 40 VS rows. Subject identifiers are `SYN-001` to `SYN-020`.
The deterministic seed is 20261105.

1. Generate numeric and qualitative observations with preserved units/context.
2. Apply explicitly fictional candidate bands and a missing-result scenario.
3. Request scripted review for 65 observations; 66 observations are in scope,
   including one excluded missing-result observation.
4. Generate synthetic PI assessments and recording decisions.
5. Assign 60 automated records, two manual entries, one existing-AE link, and
   37 exclusions. These are route counts over the same 100 source observations.
6. Assemble 27-field AE references, listing snapshots, 18 subject PDFs, XML
   activation/detail files, and a local simulated EDC download with 63 AE rows.
7. Run initial verification with deliberately injected defects.
8. Apply the predefined synthetic resolutions and regenerate the affected files.
9. Repeat verification and compare with the prior reference.

Both phases use the same source observations. The changed review, decision, and
output snapshots illustrate the downstream resolution process. The script does
not contact real investigators or perform a live EDC upload.

## Negative controls and results

`scenario_cases.csv` defines 14 intentional issue scenarios. They include missing
review, conflicting responses, unsupported management comments, an unapplied
grade override, an untransferred reviewed term, overlength text, lost unitless
interpretation text, missing manual-entry evidence, missing/extra stored records,
an omitted null item, incorrect target metadata, an incorrect activation value,
and stale package members.

The initial run detects 62 error items and one warning across those scenarios.
One scenario can affect several handoffs, so error items are not a count of
distinct clinical events. The resolved run has zero errors and zero warnings,
with all 14 verification areas executed. Its 17 information items record allowed
representation differences, an authorized scripted interpretation, and baseline
changes; they are not unresolved blocking issues.

`scenario_detection.csv` records whether each intended scenario was detected.
Every scenario is asserted by the runner, and the resolved acceptance condition
is asserted rather than presumed. Clinical validity and real-world production
performance are not established by this controlled demonstration.

## Files to inspect

- `source_observations.csv`: all 100 generated observations and public-reference IDs.
- `synthetic_subjects.csv`: 20 fictional demographic rows.
- `01_initial/`: deliberately incomplete/inconsistent workflow snapshots.
- `02_resolved/`: snapshots after scripted resolution.
- `Simulation_Overview.html`: before/after summary and links.
- Each phase's `report.html`, `report.xlsx`, `issues.csv`, and `lineage.csv`.
- Each phase's `Simulation_Data.xlsx`: subjects, references, source findings,
  review, decisions, AE data, listing values, EDC records, and baseline.


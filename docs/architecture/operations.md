# Operational architecture

The editable source is [operations.drawio](operations.drawio). The SVG exports and paged HTML
come from that XML via `python tools/export_architecture.py`. This small exporter supports this
document's rectangular cells, labels, directed edges and embedded image; it is not a general
draw.io renderer. Open the source in diagrams.net for editing, then inspect the exported pages.

| Page | Question |
|---|---|
| [D01](D01.svg) | What research, audit and batch paths already exist? |
| [D02](D02.svg) | Where do measurement and durable human review fit? |
| [D03](D03.svg) | Which bytes, protocols and quality boundaries are preserved? |
| [D04](D04.svg) | Which event context feeds the unchanged rules? |
| [D05](D05.svg) | What are the operational table grains and keys? |
| [D06](D06.svg) | How is frozen research reconstructed in memory? |
| [D07](D07.svg) | How do cases and append-only human history relate to signals? |
| [D08](D08.svg) | What persists before and after a process exit? |
| [D09](D09.svg) | Where do throughput, latency and RSS measurements begin/end? |
| [D10](D10.svg) | How is installation separated from offline verification? |
| [D11](D11.svg) | What would the blocked GCP staging and export path contain? |
| [D12](D12.svg) | What measured requirements would justify later expansion? |
| [D13](D13.svg) | How do domain, application, adapters and CLI separate responsibility? |
| [D14](D14.svg) | Where are untrusted inputs validated and local OS trust assumed? |
| [D15](D15.svg) | How are SQL contracts partitioned into exactly one owner document? |
| [D16](D16.svg) | Where do PUBG calculations end and external resources begin? |
| [D17](D17.svg) | Who owns read snapshot lifetime, and which reads can a future UI reuse? |
| [D18](D18.svg) | How are frozen research, collection ledgers and independent audits connected? |
| [D19](D19.svg) | What changes identity, and how do existing DBs and cross-version comparisons work? |
| [D20](D20.svg) | Which executable gates keep architecture, SQL and evidence consistent? |

Solid cells denote existing implementation or frozen research. Dashed cells also carry explicit
PLANNED/BLOCKED/CONDITIONAL labels. The review workflow and local offline gate are implemented;
the remote CI run is unverified. GCP is a proposed single VM, not a deployed service.
The supplied Google icon guide is dated May 2026. [Icon provenance](icon-provenance.json) records
the selected core Compute Engine SVG and SHA; the legacy ZIP is not used. The unused Cloud SQL,
BigQuery and other Google services are not pictured as active dependencies.

The table contracts live in [DESIGN §12](../../DESIGN.md#12-로컬-배치-운영-계약) and the
[SQL inventory](../sql/README.md). Diagrams summarize those contracts and do not redefine them.
The GCP account/project and blocker evidence stay in local `private/` records.

The [20-page PDF](operations.pdf) is exported from [operations-print.html](operations-print.html).
To regenerate it after the SVG export, run Chrome headless against that local file with
`--no-pdf-header-footer --print-to-pdf=<destination>`. Check all pages for labels, fonts,
overlap and clipping. The exporter validates IDs, bounds, colors and a restricted embedded SVG
grammar; it rejects active content and external resources. Source and export use the same cells.

The [security review](../security/operations.md), [SQL owner tree](../sql/README.md) and
[implemented code boundaries](clean-architecture.md) explain D13–D20. The
[refactoring record](../maintenance/refactoring-plan.md) separates implementation from final
verification and the already blocked cloud work.

D17 was updated on 2026-10-29 for [ADR 024](../adr/024-owned-read-snapshots.md): queries close
only the snapshot they start, report shares it with status, and caller transactions stay open.
Its verification is recorded in [read snapshot validation](../maintenance/read-snapshot-validation.md).

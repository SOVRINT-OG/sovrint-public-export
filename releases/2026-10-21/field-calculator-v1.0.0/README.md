# SOVRINT™ Field Calculator — Public Research Prototype v1.0.0

**Release date:** October 21, 2026  
**Research author:** Katrina Pietroniro  
**Artifact:** SOVRINT-FIELD-CALC-001  
**Release class:** public, reproducible research-software prototype  
**Rights:** © Katrina Pietroniro. All rights reserved; see [repository notice](../../../SOVRINT_LICENSE.md). This publication does not grant an open-source license.  
**Scientific status:** proposed, non-validated dimensionless indices.

The Field Calculator implements the original SOVRINT canonical-draft six-index state vector:

`F_t = [EAS, TSS, HLI, OC, IR, FCS]`

The scores summarize user-supplied normalized environmental disturbance, technical stability, human-load, observability and interpretation ratings. **They do not establish a physical "field", causation, psychological status, disease, intentional interference, or the safety of any real-world environment.** Software testing is not empirical validation of these interpretations.

## Live public demonstration

**[Field Calculator public site](https://calculator.sovrint.ca/)**  
**[Synthetic schema endpoint](https://calculator.sovrint.ca/api/multilayer/schema)**  
**[Self-test endpoint](https://calculator.sovrint.ca/api/multilayer/selftest)**

Cloudflare identifies the Worker as `pietroniro-field-calculator`, serving `calculator.sovrint.ca`, Worker release `0.4.1`. A deployed, unauthenticated demonstration endpoint exists, but browser/MCP client functionality and third-party accessibility require independent confirmation.

**Do not enter personal health data, confidential location information, credentials, private logs, or other sensitive data into a public endpoint.** The offline Python reference can be used to avoid submitting observations over a network.

## Offline reproducibility

From **this release directory** (Python 3.11+, no third-party dependencies):

```bash
python examples/make_synthetic_input.py --output synthetic_input.json
python field_calculator.py --input synthetic_input.json --output synthetic_report.json
python -m unittest discover -v -s tests -p 'test_*.py'
```

Expected synthetic test: each of the six scores is **50**, classification `MIXED_TRANSITIONAL`.

Cross-language parity (Node.js 20+, Python in PATH):

```bash
node --test cloudflare/field-state.test.mjs
```

Inputs require all **26** fields, a declared evidence class, UTC timestamp, and provenance metadata. The program rejects missing/non-finite/out-of-range observations. All symbolic notes are separate and do not contribute to scores. The output includes normalized inputs, effective weights, per-observation attribution and SHA-256 digests.

### Included files

- `CALCULATION_SPEC_v1.yaml` — original draft equations and weights, included **unchanged**.
- `field_calculator.py` — deterministic Python offline implementation.
- `cloudflare/field-state.mjs` — JavaScript/Worker parity **model module** (not the complete deployed Worker).
- `tests/`, `cloudflare/field-state.test.mjs` — unit and cross-language numerical verification.
- `examples/make_synthetic_input.py` — transparent demonstration fixture.
- `release.json` — metadata and review boundaries.

### Validation / provenance

Origin: private canonical repository `SOVRINT-OG/sovrint-core`, accepted PR #4, merge commit `7b7985234452229fa6b62a6f6ab7699fedc80ec1`. Earlier CI passed the deterministic Python and JS parity tests; source review and independent replication remain desirable. Cloudflare independently reports a live deployed Worker version `f1d28685-b0fc-4f14-845f-af1af13211b8`.

### Limitations and public-use boundaries

- No authenticated data feeds, calibration study, medical validation or external physical interpretation is supplied.
- Environmental terms are **operator-normalized ratings**, not verified measurements without independent instrumentation.
- HLI is not a medical instrument; use only synthetic data in this public example.
- `FCS` is a **weighted modeling composite**, not objective proof of coherence or integrity.
- No automatic high-impact decisions, forensic attribution, private journal or personal-data ingestion is included in this published snapshot.
- Source is public for inspection **under the repository's all-rights-reserved terms**, not as an open-source distribution.

No DOI, journal peer review, standards certification, scientific replication or production security audit is claimed.

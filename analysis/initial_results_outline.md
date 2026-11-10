# Initial Results — content outline

Structure only, no prose. Every leaf bullet names the exact table/figure file stem
(under `analysis/output/tables/` and `analysis/output/figures/`) that backs it, so
each claim in the written chapter is traceable back to `analyze_poc_results.py`.
Regenerate all numbers by running `python analysis/analyze_poc_results.py` — do not
hand-copy figures from an earlier run, they are pinned to the committed
`poc_response/` input and reproduce exactly.

Section numbers below are placeholders ("4.x") — renumber to fit the actual chapter.

## 4.1 What Was Executed

- The 10 named catalytic processes analyzed: Contact process, Fischer-Tropsch
  process, Fluid catalytic cracking, Haber-Bosch process, Hydroformylation,
  Methanation, Ostwald process, Selective catalytic reduction, Steam reforming,
  Water-gas shift reaction.
- The realized pipeline, one line each: Wikipedia lead paragraph as a seed
  "abstract" → LogicMill/PatSpecter similarity retrieval (top-10 candidates per
  process) → 4-source abstract enrichment chain (OpenAlex → Semantic Scholar →
  CrossRef → Semantic Scholar by title) → deterministic local-LLM extraction
  (`gemma3:4b` via Ollama, temperature=0, seed=42) constrained to a hand-written
  CoreMeta4Cat-subset Pydantic schema → field-level CURIE/IRI ontology mapping →
  `owlready2` OWL/RDF-XML knowledge-graph assembly.
- State explicitly: a 7th planned step (predefined SPARQL queries over the
  resulting graph) was **not** exercised in this PoC.
- Frame the chapter as a feasibility/workflow demonstration, not a benchmarked
  evaluation — set up §4.7.

## 4.2 Retrieved Corpus Characteristics

- Corpus size and composition: 90 documents retrieved (post-dedup) across the 10
  processes; article/book-chapter/review/other/dissertation/preprint breakdown —
  `document_type_distribution` / `fig_document_type_distribution`.
- Corpus recency: spans the 1920s–2020s (1 of 90 documents has no
  `publicationDate`) — `publication_year_distribution` /
  `fig_publication_year_distribution`.
- Retrieval similarity scores are uniformly high and narrow across the whole
  corpus (min 0.9787, max 0.9933, mean 0.9845) — `retrieval_score_summary`; flag
  this in one sentence as a forward reference for §4.6.3 (a high similarity score
  does not by itself indicate topical relevance).

## 4.3 Retrieval-to-Extraction Funnel

- Overall funnel: 90 retrieved → 66 with a usable abstract (73.3%) → 66
  successfully parsed into schema-conformant metadata — i.e. **every** document
  that cleared the abstract-quality gate was also successfully extracted, with no
  residual failures after the pipeline's one self-correction retry —
  `funnel_overall` / `fig_funnel`.
- Per-process completeness ranges from 100% (Haber-Bosch process, 8/8) to 44.4%
  (Steam reforming, 4/9) — `per_process_completeness` / `fig_per_process_completeness`.
  Note the entire gap is attributable to abstract availability (the 4-source
  enrichment chain not finding a valid abstract), not to LLM extraction failures —
  the abstract-obtained and metadata-extracted counts are identical in every one
  of the 10 processes.

## 4.4 Schema-Field Extraction Fidelity

- Reliably populated fields: `used_reactant` (87.9%), `generated_product`
  (86.4%), `used_catalyst` (57.6%) — `field_population` / `fig_field_population`.
- Rarely/never populated fields: `has_duration` (25.8%), `used_solvent` (6.1%),
  `has_temperature` (6.1%), `has_pressure` (6.1%), `used_starting_material` (0%),
  `has_yield` (0%), `catalyst_quantity` (0%) — same table/figure. Suggest a
  plausible reason: abstracts (as opposed to full methods sections) rarely state
  exact quantitative operating conditions cleanly — the schema's `Quantity.raw_text`
  fallback exists precisely for this difficulty.
- Notable asymmetry: `catalyst_type` is populated in 100% of extractions (0
  nulls) vs. `catalyst_form` at 80.3% (13/66 left null) — `field_population`; both
  enums' value breakdowns are in `catalyst_type_distribution` /
  `fig_catalyst_type_distribution` (heterogeneous 72.7%, homogeneous 13.6%, other
  10.6%, electro-/biocatalysis 1.5% each; photocatalysis/hybrid never assigned)
  and `catalyst_form_distribution` / `fig_catalyst_form_distribution` (other
  36.4%, supported 21.2%, null 19.7%, bulk 15.2%, powdered 6.1%, thin_film 1.5%;
  deposited_sample never assigned).
- Exclude `reaction_name` from this fidelity discussion — it is prompt-hardcoded
  to the queried process name (see the `field_population` table's footnote row) —
  and cross-reference forward to §4.6.3, where that same design choice is shown to
  have a concrete downstream cost.

## 4.5 Knowledge Graph Characterization

- Class/individual inventory: 5 classes, 304 individuals total (66 Publication,
  66 ReactionInstance, 10 CatalyticReaction, 108 ChemicalSpecies, 54 Catalyst) —
  `kg_class_individual_counts` / `fig_kg_class_sizes`.
- Property inventory and external-ontology grounding: 7 object properties, 19
  data properties, 1 annotation property; each domain property carries a
  `mappedConcept` annotation pointing into RO, RXNO, SIO, PROV-O, schema.org, or
  VOC4CAT/CoreMeta4Cat — `kg_property_inventory`. Note the one deliberate
  exception: `catalystForm`'s `mappedConcept` is the literal placeholder string
  `"TODO:catalyst_form"`, documented upstream as CoreMeta4Cat itself lacking a
  slot URI for this field — not a mapping bug introduced by this pipeline.
- Frame this section as demonstrating the graph is externally groundable to
  community ontologies, not just internally self-consistent.

## 4.6 Observed Failure Modes

*(First-class results — frame as findings about small-LLM/lightweight-pipeline
reliability, not as apologetic caveats.)*

### 4.6.1 Temperature/duration field confusion

- 7 of 66 extracted records (10.6%) place a Celsius-pattern temperature reading
  in `has_duration` while `has_temperature` is left empty —
  `duration_temperature_confusion`.
- Quote 2–3 concrete examples directly from the table with process attribution,
  e.g. `"410 degC"` filed as a duration (Contact process), `"100–150 °C"` filed as
  a duration (Haber-Bosch process), and `"538?℃"` filed as a duration (Fluid
  catalytic cracking) — the last using the single-character "℃" glyph rather than
  "°C", which is a useful illustration that a regex-based, reproducible detector
  catches variants a manual read-through can miss (an earlier manual pass over
  this corpus counted only 6; the script's exact, rerunnable count is 7).
- State the detection method in one line: a targeted regex over `has_duration`,
  gated on `has_temperature` being empty — fully mechanical, exact, and
  reproducible, not an estimate.

### 4.6.2 Chemical/catalyst entity fragmentation

- Exact, automatic statistic: naive lowercase/whitespace-only deduplication
  during knowledge-graph assembly leaves 8 clusters of near-duplicate labels
  among the 108 `ChemicalSpecies` individuals, covering 18 individuals (16.7%) —
  `fragmentation_summary_tier1` / `fragmentation_clusters_tier1`. Zero such
  clusters among the 54 `Catalyst` individuals under the same mechanical rule.
- Illustrative, human-reviewed examples (clearly labeled as such, not restated as
  the headline statistic): nitrogen fragments into 4 individuals (`nitrogen`,
  `N2`, `N 2`, `dinitrogen (N2)`); hydrogen into 3 (`hydrogen`, `H2`, `H 2`);
  additional catalyst-side example `Co`/`Cobalt` —
  `fragmentation_examples_tier2_curated`.
- One sentence on why this matters structurally: every fragment is a *separate*
  knowledge-graph node, so per-substance graph queries or statistics (e.g. "how
  many reactions use nitrogen") silently undercount unless a consumer already
  knows to merge these variants.

### 4.6.3 Retrieval-noise-propagated mislabeling

- One confirmed instance, found via manual review of `document_ledger` (state
  this limitation explicitly in-line — it is not a systematically counted rate):
  the LogicMill top-10 for "Contact process" includes a paper on regenerating an
  SCR (deNOx) catalyst (title "Insight into regeneration mechanism with sulfuric
  acid for arsenic poisoned commercial SCR catalyst", DOI
  `10.1016/j.joei.2019.02.002`), which the pipeline nonetheless force-labeled
  `reaction_name: "Contact process"` because that field is copied from the query
  term rather than topically verified.
- Sharpen the connection to §4.2: this document's similarity score (0.9795) is in
  fact the *maximum* score recorded among all Contact-process retrievals in this
  run — `retrieval_score_summary` — i.e. the single most-similar document by
  embedding score was the topically wrong one, showing that retrieval score alone
  cannot serve as a relevance filter.
- Connect to the prompt-hardcoded `reaction_name` design choice flagged in §4.4:
  an upstream retrieval-noise problem, combined with that design choice,
  propagates silently into a knowledge-graph-level labeling error.

## 4.7 Scope of the Present Results

*(Closing boundary statement — phrase as a natural forward-looking boundary, not
a buried admission.)*

- No ground-truth/gold-standard annotation exists for this corpus; nothing above
  measures extraction *accuracy* (whether populated values are factually
  correct) — only extraction *frequency* (whether a field was populated at all)
  and *internal-consistency* anomalies (§4.6.1, §4.6.2). A populated
  `has_temperature` value has not been checked against the source text for
  correctness.
- The fragmentation and mislabeling findings (§4.6.2, §4.6.3) are existence
  proofs — one from an exhaustive mechanical scan, one from a single manually
  confirmed case — not exhaustive audits; the true corpus-wide rate of either
  failure mode is unknown and would require a systematic annotation pass.
- Scale: 10 processes, 66 extracted records — a feasibility-scale sample, not a
  statistically powered study.
- The planned 7th pipeline step (SPARQL querying) remains unexercised; no
  query-level results are reported here.
- Close by stating what a follow-up evaluation would need to add (a
  gold-standard annotated subset, a defined accuracy metric) — framed as the
  natural next step this chapter's groundwork enables, not as an omission.

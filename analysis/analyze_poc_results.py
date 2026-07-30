"""Post-hoc analysis of poc_response/*.json and catalysis_kg.owl.

Reads only the already-generated PoC output -- no new LLM/API calls. Produces
the tables and figures cited in the "Initial Results" chapter outline (see
initial_results_outline.md), so every number in the chapter is reproducible
and traceable back to this script.

Usage:
    python analysis/analyze_poc_results.py [--poc-response-dir DIR] [--output-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from detectors import (
    CURATED_CATALYST_SYNONYMS,
    CURATED_CHEMICAL_SYNONYMS,
    curated_fragmentation_clusters,
    has_duration_temperature_confusion,
    mechanical_fragmentation_clusters,
    quantity_is_empty,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POC_RESPONSE_DIR = REPO_ROOT / "poc_response"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# The notebook's slug is `re.sub(r"[^\w]+", "_", key)`, which is lossy (hyphens,
# spaces and en-dashes all collapse to "_"), so it can't be reversed
# algorithmically -- hardcode the mapping instead.
PROCESS_DISPLAY_NAMES = {
    "Contact_process": "Contact process",
    "Fischer_Tropsch_process": "Fischer-Tropsch process",
    "Fluid_catalytic_cracking": "Fluid catalytic cracking",
    "Haber_Bosch_process": "Haber-Bosch process",
    "Hydroformylation": "Hydroformylation",
    "Methanation": "Methanation",
    "Ostwald_process": "Ostwald process",
    "Selective_catalytic_reduction": "Selective catalytic reduction",
    "Steam_reforming": "Steam reforming",
    "Water_gas_shift_reaction": "Water\u2013gas shift reaction",
}

LIST_FIELDS = ["used_starting_material", "used_reactant", "generated_product", "used_catalyst", "used_solvent"]
STR_FIELDS = ["has_duration"]
QUANTITY_FIELDS = ["has_temperature", "has_pressure", "has_yield", "catalyst_quantity"]
ENUM_FIELDS = ["catalyst_type", "catalyst_form"]
FIELD_ORDER = LIST_FIELDS + STR_FIELDS + QUANTITY_FIELDS + ENUM_FIELDS

DISPLAY_LABELS = {
    "used_starting_material": "Starting material",
    "used_reactant": "Reactant",
    "generated_product": "Product",
    "used_catalyst": "Catalyst",
    "used_solvent": "Solvent",
    "has_duration": "Duration",
    "has_temperature": "Temperature",
    "has_pressure": "Pressure",
    "has_yield": "Yield",
    "catalyst_quantity": "Catalyst quantity",
    "catalyst_type": "Catalyst type",
    "catalyst_form": "Catalyst form",
}

OWL_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
}
# The KG file's default (unprefixed) namespace -- used by e.g. <mappedConcept>.
MEX_NS = "https://w3id.org/nfdi4cat/metaextract4cat#"


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_all_documents(poc_response_dir: Path) -> list[dict]:
    """Glob response_*.json (sorted), flatten to one dict per document, each
    tagged with `process`/`slug`. PatspecterEmbedding is dropped (always []
    in this dataset)."""
    records: list[dict] = []
    for path in sorted(poc_response_dir.glob("response_*.json")):
        slug = path.stem[len("response_"):]
        process = PROCESS_DISPLAY_NAMES.get(slug, slug)
        with path.open(encoding="utf-8") as fh:
            entries = json.load(fh)
        for entry in entries:
            doc = dict(entry["document"])
            doc.pop("PatspecterEmbedding", None)
            doc["process"] = process
            doc["slug"] = slug
            doc["id"] = entry.get("id")
            doc["score"] = entry.get("score")
            records.append(doc)
    return records


# --------------------------------------------------------------------------
# Retrieval -> extraction funnel
# --------------------------------------------------------------------------

def compute_funnel(records: list[dict]) -> pd.DataFrame:
    n_retrieved = len(records)
    n_with_abstract = sum(1 for r in records if r.get("abstract"))
    n_extracted = sum(1 for r in records if r.get("extracted_metadata"))
    rows = [
        {"stage": "Retrieved", "n_documents": n_retrieved, "pct_of_retrieved": 100.0},
        {
            "stage": "Abstract obtained",
            "n_documents": n_with_abstract,
            "pct_of_retrieved": round(100 * n_with_abstract / n_retrieved, 1),
        },
        {
            "stage": "Metadata extracted",
            "n_documents": n_extracted,
            "pct_of_retrieved": round(100 * n_extracted / n_retrieved, 1),
        },
    ]
    return pd.DataFrame(rows)


def compute_per_process_completeness(records: list[dict]) -> pd.DataFrame:
    rows = []
    for process in sorted({r["process"] for r in records}):
        subset = [r for r in records if r["process"] == process]
        n_retrieved = len(subset)
        n_with_abstract = sum(1 for r in subset if r.get("abstract"))
        n_extracted = sum(1 for r in subset if r.get("extracted_metadata"))
        rows.append(
            {
                "process": process,
                "n_retrieved": n_retrieved,
                "n_with_abstract": n_with_abstract,
                "n_extracted": n_extracted,
                "pct_extracted": round(100 * n_extracted / n_retrieved, 1) if n_retrieved else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("pct_extracted", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Schema-field population
# --------------------------------------------------------------------------

def _field_kind(field: str) -> str:
    if field in LIST_FIELDS:
        return "list"
    if field in QUANTITY_FIELDS:
        return "quantity"
    if field in ENUM_FIELDS:
        return "enum"
    return "str"


def is_field_populated(value: object, kind: str) -> bool:
    if kind == "quantity":
        return not quantity_is_empty(value)
    if kind == "list":
        return isinstance(value, list) and len(value) > 0
    return value is not None


def compute_field_population(records: list[dict]) -> pd.DataFrame:
    extracted = [r["extracted_metadata"] for r in records if r.get("extracted_metadata")]
    n_total = len(extracted)
    rows = []
    for field in FIELD_ORDER:
        kind = _field_kind(field)
        n_populated = sum(1 for meta in extracted if is_field_populated(meta.get(field), kind))
        rows.append(
            {
                "field": field,
                "field_kind": kind,
                "n_populated": n_populated,
                "n_total": n_total,
                "pct_populated": round(100 * n_populated / n_total, 1) if n_total else 0.0,
                "note": "",
            }
        )
    rows.append(
        {
            "field": "reaction_name",
            "field_kind": "str",
            "n_populated": n_total,
            "n_total": n_total,
            "pct_populated": 100.0,
            "note": (
                "Prompt-hardcoded to the queried process name -- not an extraction-fidelity "
                "signal. See the retrieval-noise-propagated mislabeling failure mode."
            ),
        }
    )
    return pd.DataFrame(rows)


def compute_enum_distribution(records: list[dict], field_name: str) -> pd.DataFrame:
    extracted = [r["extracted_metadata"] for r in records if r.get("extracted_metadata")]
    n_total = len(extracted)
    counts: dict[str, int] = {}
    for meta in extracted:
        value = meta.get(field_name)
        key = value if value is not None else "(not stated)"
        counts[key] = counts.get(key, 0) + 1
    rows = [
        {field_name: key, "n": n, "pct_of_extracted": round(100 * n / n_total, 1) if n_total else 0.0}
        for key, n in counts.items()
    ]
    return pd.DataFrame(rows).sort_values("n", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Knowledge graph (OWL) parsing -- stdlib ElementTree, the file is flat
# RDF/XML with no imports/blank nodes/restrictions, so no reasoner is needed.
# --------------------------------------------------------------------------

def _local_name(uri_or_ref: str) -> str:
    if "#" in uri_or_ref:
        return uri_or_ref.rsplit("#", 1)[-1]
    return uri_or_ref.rsplit("/", 1)[-1]


def load_owl_root(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def count_individuals_by_class(root: ET.Element) -> pd.DataFrame:
    rdf_ns = OWL_NS["rdf"]
    counts: dict[str, int] = {}
    for individual in root.findall("owl:NamedIndividual", OWL_NS):
        type_el = individual.find("rdf:type", OWL_NS)
        if type_el is None:
            continue
        resource = type_el.get(f"{{{rdf_ns}}}resource")
        if not resource:
            continue
        class_name = _local_name(resource)
        counts[class_name] = counts.get(class_name, 0) + 1
    rows = [{"owl_class": name, "n_individuals": n} for name, n in counts.items()]
    df = pd.DataFrame(rows).sort_values("n_individuals", ascending=False).reset_index(drop=True)
    total = pd.DataFrame([{"owl_class": "Total", "n_individuals": int(df["n_individuals"].sum())}])
    return pd.concat([df, total], ignore_index=True)


def list_property_inventory(root: ET.Element) -> pd.DataFrame:
    rdf_ns = OWL_NS["rdf"]
    rows = []
    for kind, tag in (
        ("object", "ObjectProperty"),
        ("datatype", "DatatypeProperty"),
        ("annotation", "AnnotationProperty"),
    ):
        for prop in root.findall(f"owl:{tag}", OWL_NS):
            about = prop.get(f"{{{rdf_ns}}}about", "")
            name = _local_name(about)
            domain_el = prop.find("rdfs:domain", OWL_NS)
            range_el = prop.find("rdfs:range", OWL_NS)
            domain = _local_name(domain_el.get(f"{{{rdf_ns}}}resource", "")) if domain_el is not None else ""
            range_ = _local_name(range_el.get(f"{{{rdf_ns}}}resource", "")) if range_el is not None else ""
            mapped_el = prop.find(f"{{{MEX_NS}}}mappedConcept")
            mapped = mapped_el.text if mapped_el is not None and mapped_el.text else ""
            rows.append(
                {
                    "property_name": name,
                    "property_kind": kind,
                    "domain": domain,
                    "range": range_,
                    "mapped_concept_iri": mapped,
                }
            )
    return pd.DataFrame(rows)


def get_labels_for_class(root: ET.Element, class_local_name: str) -> list[str]:
    rdf_ns = OWL_NS["rdf"]
    labels = []
    for individual in root.findall("owl:NamedIndividual", OWL_NS):
        type_el = individual.find("rdf:type", OWL_NS)
        if type_el is None:
            continue
        resource = type_el.get(f"{{{rdf_ns}}}resource", "")
        if _local_name(resource) != class_local_name:
            continue
        label_el = individual.find("rdfs:label", OWL_NS)
        if label_el is not None and label_el.text:
            labels.append(label_el.text)
    return labels


# --------------------------------------------------------------------------
# Failure-mode reports (built on top of detectors.py)
# --------------------------------------------------------------------------

def report_duration_temperature_confusion(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        meta = r.get("extracted_metadata")
        if not meta:
            continue
        hit = has_duration_temperature_confusion(meta)
        if hit is None:
            continue
        rows.append(
            {
                "process": r["process"],
                "doi_or_id": r.get("doi") or r.get("id") or "",
                "title": r.get("title", ""),
                "has_duration_value": hit["has_duration_value"],
                "has_temperature_value": hit["has_temperature_value"],
            }
        )
    return pd.DataFrame(rows)


def report_fragmentation_summary(chem_labels: list[str], cat_labels: list[str]) -> pd.DataFrame:
    rows = []
    for entity_class, labels in (("ChemicalSpecies", chem_labels), ("Catalyst", cat_labels)):
        clusters = mechanical_fragmentation_clusters(labels)
        n_in_clusters = sum(len(c) for c in clusters)
        rows.append(
            {
                "entity_class": entity_class,
                "n_individuals_total": len(labels),
                "n_clusters_size_ge2": len(clusters),
                "n_individuals_in_clusters": n_in_clusters,
                "pct_individuals_in_clusters": round(100 * n_in_clusters / len(labels), 1) if labels else 0.0,
            }
        )
    return pd.DataFrame(rows)


def report_fragmentation_clusters(chem_labels: list[str], cat_labels: list[str]) -> pd.DataFrame:
    rows = []
    for entity_class, labels in (("ChemicalSpecies", chem_labels), ("Catalyst", cat_labels)):
        for i, cluster in enumerate(mechanical_fragmentation_clusters(labels), start=1):
            rows.append(
                {
                    "entity_class": entity_class,
                    "cluster_id": i,
                    "member_labels": "; ".join(cluster),
                    "cluster_size": len(cluster),
                }
            )
    return pd.DataFrame(rows)


def report_fragmentation_examples_curated(chem_labels: list[str], cat_labels: list[str]) -> pd.DataFrame:
    rows = []
    for entity_class, labels, synonyms in (
        ("ChemicalSpecies", chem_labels, CURATED_CHEMICAL_SYNONYMS),
        ("Catalyst", cat_labels, CURATED_CATALYST_SYNONYMS),
    ):
        for cluster in curated_fragmentation_clusters(labels, synonyms):
            canonical = next((synonyms[m.lower()] for m in cluster if m.lower() in synonyms), cluster[0].lower())
            rows.append(
                {
                    "entity_class": entity_class,
                    "canonical_concept": canonical,
                    "member_labels": "; ".join(cluster),
                    "cluster_size": len(cluster),
                    "note": "curated/illustrative (human-reviewed synonym table) -- not an automatically-discovered statistic",
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Bonus corpus-context tables
# --------------------------------------------------------------------------

def compute_document_type_distribution(records: list[dict]) -> pd.DataFrame:
    n_total = len(records)
    counts: dict[str, int] = {}
    for r in records:
        key = r.get("type") or "(unknown)"
        counts[key] = counts.get(key, 0) + 1
    rows = [{"document_type": k, "n": n, "pct_of_retrieved": round(100 * n / n_total, 1)} for k, n in counts.items()]
    return pd.DataFrame(rows).sort_values("n", ascending=False).reset_index(drop=True)


def compute_score_summary(records: list[dict]) -> pd.DataFrame:
    rows = []
    for process in sorted({r["process"] for r in records}):
        scores = pd.Series([r["score"] for r in records if r["process"] == process and r.get("score") is not None])
        rows.append(
            {
                "process": process,
                "n": len(scores),
                "score_min": round(scores.min(), 4),
                "score_max": round(scores.max(), 4),
                "score_mean": round(scores.mean(), 4),
                "score_median": round(scores.median(), 4),
            }
        )
    all_scores = pd.Series([r["score"] for r in records if r.get("score") is not None])
    rows.append(
        {
            "process": "All",
            "n": len(all_scores),
            "score_min": round(all_scores.min(), 4),
            "score_max": round(all_scores.max(), 4),
            "score_mean": round(all_scores.mean(), 4),
            "score_median": round(all_scores.median(), 4),
        }
    )
    return pd.DataFrame(rows)


def compute_publication_year_distribution(records: list[dict]) -> pd.DataFrame:
    counts: dict[str, int] = {}
    n_missing = 0
    for r in records:
        date = r.get("publicationDate")
        if not date or len(date) < 4 or not date[:4].isdigit():
            n_missing += 1
            continue
        year = int(date[:4])
        decade = f"{(year // 10) * 10}s"
        counts[decade] = counts.get(decade, 0) + 1
    rows = [{"decade": k, "n": v} for k, v in sorted(counts.items())]
    if n_missing:
        rows.append({"decade": "(no date)", "n": n_missing})
    return pd.DataFrame(rows)


def build_document_ledger(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        meta = r.get("extracted_metadata") or {}
        rows.append(
            {
                "process": r["process"],
                "title": r.get("title", ""),
                "doi": r.get("doi", ""),
                "openalex_id": r.get("id", ""),
                "type": r.get("type", ""),
                "publication_date": r.get("publicationDate", ""),
                "score": r.get("score"),
                "has_abstract": bool(r.get("abstract")),
                "has_extracted_metadata": bool(r.get("extracted_metadata")),
                "used_reactant": "; ".join(meta.get("used_reactant") or []),
                "generated_product": "; ".join(meta.get("generated_product") or []),
                "used_catalyst": "; ".join(meta.get("used_catalyst") or []),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Export helpers
# --------------------------------------------------------------------------

def df_to_markdown(df: pd.DataFrame) -> str:
    """Hand-rolled Markdown table writer (no `tabulate` dependency)."""

    def esc(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    headers = list(df.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(esc(row[h]) for h in headers) + " |")
    return "\n".join(lines)


def _format_floats_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Values are already rounded via Python round(), but to_latex()/a naive
    Markdown writer would otherwise apply their own default float formatting
    (e.g. "87.900000"). Render float columns as fixed-precision strings so
    .md/.tex show exactly the intended precision; .csv keeps raw numbers for
    downstream reuse. Percentage columns get 1dp, score columns get 4dp --
    the only two kinds of float column this script produces."""
    display_df = df.copy()
    for col in display_df.columns:
        if pd.api.types.is_float_dtype(display_df[col]):
            decimals = 4 if "score" in col else 1
            display_df[col] = display_df[col].map(lambda x, d=decimals: "" if pd.isna(x) else f"{x:.{d}f}")
    return display_df


def export_table(df: pd.DataFrame, name: str, out_dir: Path) -> None:
    tables_dir = out_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(tables_dir / f"{name}.csv", index=False)
    display_df = _format_floats_for_display(df)
    (tables_dir / f"{name}.md").write_text(df_to_markdown(display_df), encoding="utf-8")
    (tables_dir / f"{name}.tex").write_text(display_df.to_latex(index=False, escape=True), encoding="utf-8")


def save_chart(fig, name: str, out_dir: Path) -> None:
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(figures_dir / f"{name}.png", dpi=300)
    fig.savefig(figures_dir / f"{name}.svg")
    plt.close(fig)


# --------------------------------------------------------------------------
# Charts
#
# All charts here compare a single measure (a count or a %) across a nominal
# or ordered category -- i.e. every one is a "magnitude" job, never
# "identity" -- so each uses ONE hue for all bars (never a different color
# per bar/category) per the project's chart-design convention, with the
# exception of the funnel, which is an explicitly ordered progression and
# uses the matching 3-step ordinal ramp. Colors are the validated default
# palette's sequential-blue slot/ramp.
# --------------------------------------------------------------------------

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Arial"]

_SURFACE = "#fcfcfb"
_INK_PRIMARY = "#0b0b0b"
_INK_SECONDARY = "#52514e"
_GRIDLINE = "#e1e0d9"
_BASELINE = "#c3c2b7"
_BAR_HUE = "#2a78d6"
_ORDINAL_RAMP = ["#86b6ef", "#3987e5", "#1c5cab"]  # funnel stages, steps 250/400/550


def _style_axes(ax, horizontal: bool = False) -> None:
    ax.set_facecolor(_SURFACE)
    ax.figure.set_facecolor(_SURFACE)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(_BASELINE)
    ax.grid(axis="x" if horizontal else "y", color=_GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=_INK_SECONDARY, labelsize=9)
    ax.title.set_color(_INK_PRIMARY)
    ax.title.set_fontsize(11)
    ax.xaxis.label.set_color(_INK_SECONDARY)
    ax.yaxis.label.set_color(_INK_SECONDARY)


def chart_funnel(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(df["stage"], df["n_documents"], color=_ORDINAL_RAMP, width=0.6, zorder=3)
    ax.bar_label(bars, padding=3, color=_INK_SECONDARY, fontsize=9)
    ax.set_ylabel("Documents")
    ax.set_title("Retrieval-to-extraction funnel")
    ax.set_ylim(0, df["n_documents"].max() * 1.15)
    _style_axes(ax)
    return fig


def chart_per_process_completeness(df: pd.DataFrame):
    df = df.sort_values("pct_extracted")
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.barh(df["process"], df["pct_extracted"], color=_BAR_HUE, height=0.6, zorder=3)
    ax.bar_label(bars, padding=3, fmt="%.1f%%", color=_INK_SECONDARY, fontsize=9)
    ax.set_xlabel("% extracted")
    ax.set_title("Per-process extraction completeness")
    ax.set_xlim(0, 112)
    _style_axes(ax, horizontal=True)
    return fig


def chart_field_population(df: pd.DataFrame):
    df = df[df["field"] != "reaction_name"].copy()
    df["label"] = df["field"].map(lambda f: DISPLAY_LABELS.get(f, f))
    df = df.sort_values("pct_populated")
    fig, ax = plt.subplots(figsize=(7, 5.5))
    bars = ax.barh(df["label"], df["pct_populated"], color=_BAR_HUE, height=0.6, zorder=3)
    ax.bar_label(bars, padding=3, fmt="%.1f%%", color=_INK_SECONDARY, fontsize=9)
    ax.set_xlabel("% populated")
    ax.set_title("Schema-field population rate (n=66 extracted records)")
    ax.set_xlim(0, 112)
    _style_axes(ax, horizontal=True)
    return fig


def chart_enum_distribution(df: pd.DataFrame, value_column: str, title: str):
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    labels = df[value_column].astype(str)
    bars = ax.bar(labels, df["n"], color=_BAR_HUE, width=0.6, zorder=3)
    ax.bar_label(bars, padding=3, color=_INK_SECONDARY, fontsize=9)
    ax.set_ylabel("Count")
    ax.set_title(title)
    ax.set_ylim(0, df["n"].max() * 1.15)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    _style_axes(ax)
    return fig


def chart_kg_class_sizes(df: pd.DataFrame):
    df = df[df["owl_class"] != "Total"]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    bars = ax.bar(df["owl_class"], df["n_individuals"], color=_BAR_HUE, width=0.6, zorder=3)
    ax.bar_label(bars, padding=3, color=_INK_SECONDARY, fontsize=9)
    ax.set_ylabel("Individuals")
    ax.set_title("Knowledge graph class sizes")
    ax.set_ylim(0, df["n_individuals"].max() * 1.15)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    _style_axes(ax)
    return fig


def chart_publication_year_distribution(df: pd.DataFrame):
    plot_df = df[df["decade"] != "(no date)"]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(plot_df["decade"], plot_df["n"], color=_BAR_HUE, width=0.6, zorder=3)
    ax.bar_label(bars, padding=3, color=_INK_SECONDARY, fontsize=9)
    ax.set_ylabel("Documents")
    ax.set_title("Corpus publication decade")
    ax.set_ylim(0, plot_df["n"].max() * 1.15)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    _style_axes(ax)
    return fig


def chart_document_type_distribution(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6, 4.5))
    bars = ax.bar(df["document_type"], df["n"], color=_BAR_HUE, width=0.6, zorder=3)
    ax.bar_label(bars, padding=3, color=_INK_SECONDARY, fontsize=9)
    ax.set_ylabel("Documents")
    ax.set_title("Corpus document-type composition")
    ax.set_ylim(0, df["n"].max() * 1.15)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    _style_axes(ax)
    return fig


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poc-response-dir", type=Path, default=DEFAULT_POC_RESPONSE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    records = load_all_documents(args.poc_response_dir)
    owl_root = load_owl_root(args.poc_response_dir / "catalysis_kg.owl")

    funnel = compute_funnel(records)
    per_process = compute_per_process_completeness(records)
    field_pop = compute_field_population(records)
    catalyst_type_dist = compute_enum_distribution(records, "catalyst_type")
    catalyst_form_dist = compute_enum_distribution(records, "catalyst_form")

    kg_classes = count_individuals_by_class(owl_root)
    kg_properties = list_property_inventory(owl_root)
    chem_labels = get_labels_for_class(owl_root, "ChemicalSpecies")
    cat_labels = get_labels_for_class(owl_root, "Catalyst")

    frag_summary = report_fragmentation_summary(chem_labels, cat_labels)
    frag_clusters = report_fragmentation_clusters(chem_labels, cat_labels)
    frag_curated = report_fragmentation_examples_curated(chem_labels, cat_labels)
    duration_confusion = report_duration_temperature_confusion(records)

    doc_type_dist = compute_document_type_distribution(records)
    score_summary = compute_score_summary(records)
    year_dist = compute_publication_year_distribution(records)
    ledger = build_document_ledger(records)

    tables = {
        "funnel_overall": funnel,
        "per_process_completeness": per_process,
        "field_population": field_pop,
        "catalyst_type_distribution": catalyst_type_dist,
        "catalyst_form_distribution": catalyst_form_dist,
        "kg_class_individual_counts": kg_classes,
        "kg_property_inventory": kg_properties,
        "fragmentation_summary_tier1": frag_summary,
        "fragmentation_clusters_tier1": frag_clusters,
        "fragmentation_examples_tier2_curated": frag_curated,
        "duration_temperature_confusion": duration_confusion,
        "document_type_distribution": doc_type_dist,
        "retrieval_score_summary": score_summary,
        "publication_year_distribution": year_dist,
        "document_ledger": ledger,
    }
    for name, df in tables.items():
        export_table(df, name, args.output_dir)

    save_chart(chart_funnel(funnel), "fig_funnel", args.output_dir)
    save_chart(chart_per_process_completeness(per_process), "fig_per_process_completeness", args.output_dir)
    save_chart(chart_field_population(field_pop), "fig_field_population", args.output_dir)
    save_chart(
        chart_enum_distribution(catalyst_type_dist, "catalyst_type", "Catalyst type distribution"),
        "fig_catalyst_type_distribution",
        args.output_dir,
    )
    save_chart(
        chart_enum_distribution(catalyst_form_dist, "catalyst_form", "Catalyst form distribution"),
        "fig_catalyst_form_distribution",
        args.output_dir,
    )
    save_chart(chart_kg_class_sizes(kg_classes), "fig_kg_class_sizes", args.output_dir)
    save_chart(chart_publication_year_distribution(year_dist), "fig_publication_year_distribution", args.output_dir)
    save_chart(chart_document_type_distribution(doc_type_dist), "fig_document_type_distribution", args.output_dir)

    n_retrieved = len(records)
    n_extracted = sum(1 for r in records if r.get("extracted_metadata"))
    kg_total = int(kg_classes.loc[kg_classes["owl_class"] == "Total", "n_individuals"].iloc[0])
    chem_total = len(chem_labels)
    chem_clusters = int(frag_summary.loc[frag_summary["entity_class"] == "ChemicalSpecies", "n_clusters_size_ge2"].iloc[0])
    chem_in_clusters = int(
        frag_summary.loc[frag_summary["entity_class"] == "ChemicalSpecies", "n_individuals_in_clusters"].iloc[0]
    )

    print("=" * 60)
    print("PoC output analysis")
    print("=" * 60)
    print(f"Documents retrieved:             {n_retrieved}")
    print(f"Documents with metadata:         {n_extracted} ({100 * n_extracted / n_retrieved:.1f}%)")
    print(f"KG individuals total:            {kg_total}")
    print(
        f"Duration/temperature confusion:  {len(duration_confusion)}/{n_extracted} "
        f"({100 * len(duration_confusion) / n_extracted:.1f}%)"
    )
    print(
        f"ChemicalSpecies fragmentation:    {chem_in_clusters}/{chem_total} individuals in "
        f"{chem_clusters} clusters (mechanical, Tier 1)"
    )
    print()
    print("NOTE: no ground-truth/gold-standard annotation exists for this corpus.")
    print("The tables above report extraction FREQUENCY and internal-consistency")
    print("anomalies only -- no accuracy/precision/recall metric is computed anywhere")
    print("in this script, because nothing exists yet to compare extracted values against.")
    print()
    print(f"Tables written to:  {args.output_dir / 'tables'}")
    print(f"Figures written to: {args.output_dir / 'figures'}")


if __name__ == "__main__":
    main()

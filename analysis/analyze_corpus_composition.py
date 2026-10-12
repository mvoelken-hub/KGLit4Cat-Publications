"""Corpus composition of the retrieved documents and their path into extraction.

Reads only the already-generated PoC output (poc_response/response_*.json) -- no
new LLM/API calls. Complements analyze_poc_results.py, whose loader and table
export it reuses, with the corpus-level tables that script does not provide:

    corpus_summary             key counts and ranges in one place (control values)
    corpus_per_process         retrieved / usable abstract / extracted metadata per
                               process, alphabetical, with a Total row (same counts
                               as per_process_completeness)
    document_type_by_process   document types per process
    document_type_by_abstract  document types with and without a usable abstract
    abstract_gap_by_process_and_type
                               where the missing abstracts arise (process x type)
    other_category_documents   the documents the source database types as "other"
    preprint_crosscheck        closest title in the corpus for every preprint

A document counts as having a usable abstract if its `abstract` field is non-empty.
The notebook stores None when no source returned an abstract or when its validity
gate (`_is_valid_abstract`) rejected the text, so the two cases cannot be told
apart here.

Usage:
    python analysis/analyze_corpus_composition.py [--poc-response-dir DIR] [--output-dir DIR]
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from analyze_poc_results import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_POC_RESPONSE_DIR,
    export_table,
    load_all_documents,
)

# "Recent" means published in this year or later (the manuscript speaks of "the 2010s or 2020s").
RECENT_FROM_YEAR = 2010

# Mirrors the notebook's deduplicate() step: normalised titles at or above this ratio
# are treated as the same paper there.
TITLE_SIMILARITY_THRESHOLD = 0.95

OTHER_TYPE = "other"
PREPRINT_TYPE = "preprint"


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _has_usable_abstract(record: dict) -> bool:
    return bool(record.get("abstract"))


def _has_metadata(record: dict) -> bool:
    return bool(record.get("extracted_metadata"))


def _document_type(record: dict) -> str:
    return record.get("type") or "(unknown)"


def _publication_year(record: dict) -> int | None:
    date = record.get("publicationDate")
    if not date or len(date) < 4 or not date[:4].isdigit():
        return None
    return int(date[:4])


def _pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _normalize_title(title: str | None) -> str:
    """Same normalisation as the notebook's deduplicate() step."""
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"<[^>]+>", " ", t)  # HTML/XML tags, e.g. <sub>
    t = re.sub(r"&[a-z]+;", " ", t)  # HTML entities, e.g. &lt;
    t = re.sub(r"[^a-z0-9]+", " ", t)  # punctuation -> space
    return re.sub(r"\s+", " ", t).strip()


def _types_by_frequency(records: list[dict]) -> list[str]:
    counts = Counter(_document_type(r) for r in records)
    return sorted(counts, key=lambda t: (-counts[t], t))


def _append_total_row(df: pd.DataFrame, label_column: str) -> pd.DataFrame:
    total = {label_column: "Total", **{c: int(df[c].sum()) for c in df.columns if c != label_column}}
    return pd.concat([df, pd.DataFrame([total])], ignore_index=True)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

def compute_corpus_summary(records: list[dict]) -> pd.DataFrame:
    """Key counts and ranges in one place, so every number in the corpus
    description can be checked against a single table."""
    n = len(records)
    n_abstract = sum(_has_usable_abstract(r) for r in records)
    n_metadata = sum(_has_metadata(r) for r in records)
    n_abstract_only = sum(_has_usable_abstract(r) and not _has_metadata(r) for r in records)
    n_metadata_only = sum(_has_metadata(r) and not _has_usable_abstract(r) for r in records)
    per_process = Counter(r["process"] for r in records)
    years = [y for y in (_publication_year(r) for r in records) if y is not None]
    n_recent = sum(y >= RECENT_FROM_YEAR for y in years)
    scores = [r["score"] for r in records if r.get("score") is not None]

    rows = [
        ("documents_retrieved", n, "after per-process deduplication"),
        ("processes", len(per_process), "with at least one retrieved document"),
        ("documents_per_process_min", min(per_process.values(), default=0), ""),
        ("documents_per_process_max", max(per_process.values(), default=0), ""),
        (
            "distinct_openalex_ids",
            len({r.get("id") for r in records}),
            "equals documents_retrieved if no document appears under two processes",
        ),
        (
            "distinct_normalized_titles",
            len({_normalize_title(r.get("title")) for r in records}),
            "same check on normalised titles",
        ),
        ("documents_with_usable_abstract", n_abstract, "non-empty abstract field"),
        ("pct_with_usable_abstract", _pct(n_abstract, n), "of documents_retrieved"),
        (
            "documents_without_usable_abstract",
            n - n_abstract,
            "no source returned an abstract, or the validity gate rejected it",
        ),
        ("documents_with_extracted_metadata", n_metadata, "non-empty extracted_metadata"),
        ("abstract_but_no_metadata", n_abstract_only, "extraction failures after the self-correction retry"),
        ("metadata_but_no_abstract", n_metadata_only, "should be 0"),
        ("documents_without_publication_date", n - len(years), ""),
        ("earliest_publication_year", min(years, default=""), ""),
        ("latest_publication_year", max(years, default=""), ""),
        (f"documents_published_{RECENT_FROM_YEAR}_or_later", n_recent, ""),
        ("pct_recent_of_all_documents", _pct(n_recent, n), "denominator: documents_retrieved"),
        (
            "pct_recent_of_dated_documents",
            _pct(n_recent, len(years)),
            "denominator: documents with a publication date",
        ),
        ("similarity_score_min", round(min(scores), 4) if scores else "", "Logic-Mill score, 4 decimals"),
        ("similarity_score_max", round(max(scores), 4) if scores else "", "Logic-Mill score, 4 decimals"),
    ]
    # dtype=object keeps integers as integers (a mixed int/float column would become float).
    return pd.DataFrame(
        {
            "metric": [row[0] for row in rows],
            "value": pd.Series([row[1] for row in rows], dtype=object),
            "note": [row[2] for row in rows],
        }
    )


def compute_corpus_per_process(records: list[dict]) -> pd.DataFrame:
    """Paper-table version of per_process_completeness: alphabetical, with a Total row."""
    rows = []
    for process in sorted({r["process"] for r in records}):
        subset = [r for r in records if r["process"] == process]
        rows.append(
            {
                "process": process,
                "n_retrieved": len(subset),
                "n_with_abstract": sum(_has_usable_abstract(r) for r in subset),
                "n_extracted": sum(_has_metadata(r) for r in subset),
            }
        )
    return _append_total_row(pd.DataFrame(rows), "process")


def compute_document_type_by_process(records: list[dict]) -> pd.DataFrame:
    type_order = _types_by_frequency(records)
    rows = []
    for process in sorted({r["process"] for r in records}):
        subset = [r for r in records if r["process"] == process]
        counts = Counter(_document_type(r) for r in subset)
        rows.append({"process": process, **{t: counts.get(t, 0) for t in type_order}, "n_total": len(subset)})
    return _append_total_row(pd.DataFrame(rows), "process")


def compute_document_type_by_abstract(records: list[dict]) -> pd.DataFrame:
    """Which document types are lost before extraction, and how the usable-abstract
    subset differs in composition from the retrieved corpus."""
    n_total = len(records)
    n_with_total = sum(_has_usable_abstract(r) for r in records)
    n_without_total = n_total - n_with_total

    def row(label: str, n: int, n_with: int) -> dict:
        n_without = n - n_with
        return {
            "document_type": label,
            "n": n,
            "n_with_abstract": n_with,
            "n_without_abstract": n_without,
            "pct_without_abstract": _pct(n_without, n),
            "pct_of_retrieved": _pct(n, n_total),
            "pct_of_with_abstract": _pct(n_with, n_with_total),
            "pct_of_without_abstract": _pct(n_without, n_without_total),
        }

    rows = []
    for doc_type in _types_by_frequency(records):
        subset = [r for r in records if _document_type(r) == doc_type]
        rows.append(row(doc_type, len(subset), sum(_has_usable_abstract(r) for r in subset)))
    rows.append(row("Total", n_total, n_with_total))
    return pd.DataFrame(rows)


def compute_abstract_gap_by_process_and_type(records: list[dict]) -> pd.DataFrame:
    """Long format (only combinations that occur): shows where the missing abstracts arise."""
    rows = []
    for process in sorted({r["process"] for r in records}):
        for doc_type in _types_by_frequency(records):
            subset = [r for r in records if r["process"] == process and _document_type(r) == doc_type]
            if not subset:
                continue
            n_without = sum(not _has_usable_abstract(r) for r in subset)
            rows.append(
                {
                    "process": process,
                    "document_type": doc_type,
                    "n": len(subset),
                    "n_without_abstract": n_without,
                    "pct_without_abstract": _pct(n_without, len(subset)),
                }
            )
    return pd.DataFrame(rows)


def list_other_category_documents(records: list[dict]) -> pd.DataFrame:
    """The documents the source database types as "other", to see what the category contains."""
    rows = [
        {
            "process": r["process"],
            "title": r.get("title") or "",
            "doi": r.get("doi") or "",
            "publication_date": r.get("publicationDate") or "",
            "has_abstract": _has_usable_abstract(r),
        }
        for r in records
        if _document_type(r) == OTHER_TYPE
    ]
    columns = ["process", "title", "doi", "publication_date", "has_abstract"]
    return pd.DataFrame(rows, columns=columns).sort_values(["process", "title"]).reset_index(drop=True)


def compute_preprint_crosscheck(records: list[dict]) -> pd.DataFrame:
    """For every preprint, the most similar title among all other retrieved documents
    (any process, any type), on the same normalisation as the notebook's deduplication.
    A ratio at or above TITLE_SIMILARITY_THRESHOLD would have been merged there if both
    documents had been retrieved for the same process."""
    rows = []
    for preprint in (r for r in records if _document_type(r) == PREPRINT_TYPE):
        own_title = _normalize_title(preprint.get("title"))
        best, best_ratio = None, 0.0
        for other in records:
            if other is preprint:
                continue
            ratio = SequenceMatcher(None, own_title, _normalize_title(other.get("title"))).ratio()
            if ratio > best_ratio:
                best, best_ratio = other, ratio
        rows.append(
            {
                "process": preprint["process"],
                "preprint_title": preprint.get("title") or "",
                "preprint_doi": preprint.get("doi") or "",
                "closest_title": (best.get("title") or "") if best else "",
                "closest_process": best["process"] if best else "",
                "closest_type": _document_type(best) if best else "",
                "title_similarity_score": round(best_ratio, 4),
                "reaches_dedup_threshold": best_ratio >= TITLE_SIMILARITY_THRESHOLD,
            }
        )
    columns = [
        "process", "preprint_title", "preprint_doi", "closest_title", "closest_process",
        "closest_type", "title_similarity_score", "reaches_dedup_threshold",
    ]
    return pd.DataFrame(rows, columns=columns)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--poc-response-dir", type=Path, default=DEFAULT_POC_RESPONSE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    records = load_all_documents(args.poc_response_dir)

    summary = compute_corpus_summary(records)
    per_process = compute_corpus_per_process(records)
    type_by_process = compute_document_type_by_process(records)
    type_by_abstract = compute_document_type_by_abstract(records)
    abstract_gap = compute_abstract_gap_by_process_and_type(records)
    other_documents = list_other_category_documents(records)
    preprints = compute_preprint_crosscheck(records)

    tables = {
        "corpus_summary": summary,
        "corpus_per_process": per_process,
        "document_type_by_process": type_by_process,
        "document_type_by_abstract": type_by_abstract,
        "abstract_gap_by_process_and_type": abstract_gap,
        "other_category_documents": other_documents,
        "preprint_crosscheck": preprints,
    }
    for name, df in tables.items():
        export_table(df, name, args.output_dir)

    print("=" * 60)
    print("Corpus composition")
    print("=" * 60)
    print(summary[["metric", "value"]].to_string(index=False))
    print()
    print("Document types with and without a usable abstract")
    print(type_by_abstract.to_string(index=False))
    print()
    print("Per process")
    print(per_process.to_string(index=False))
    print()
    print("Where documents lack a usable abstract (process x type)")
    print(abstract_gap[abstract_gap["n_without_abstract"] > 0].to_string(index=False))
    print()
    print(f'Documents typed "{OTHER_TYPE}"')
    if len(other_documents):
        print(other_documents[["process", "title", "doi"]].to_string(index=False))
    else:
        print("(none)")
    print()
    print("Preprints: closest title in the corpus")
    if len(preprints):
        columns = ["preprint_title", "closest_title", "title_similarity_score", "reaches_dedup_threshold"]
        print(preprints[columns].to_string(index=False))
    else:
        print("(none)")
    print()
    print("NOTE: no ground-truth annotation exists; these tables describe corpus composition")
    print("and abstract availability only, not topical relevance or extraction accuracy.")
    print()
    print(f"Tables written to: {args.output_dir / 'tables'}")


if __name__ == "__main__":
    main()

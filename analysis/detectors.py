"""Pure, dependency-free detectors for the two failure modes surfaced by the PoC.

No file I/O here -- these are unit-tested directly (see test_detectors.py) and
imported by analyze_poc_results.py, so the report and the tests can never
drift apart.
"""

from __future__ import annotations

import re
from typing import Optional

_TEMP_UNIT_RE = re.compile(r"(?<![A-Za-z])(deg\s?c|°\s?c|℃)", re.IGNORECASE)

# Requires whitespace directly before "(" -- see normalization_keys() docstring
# for why that guard matters.
_PAREN_RE = re.compile(r"^(.*\S)\s+\(([^()]+)\)$")


def quantity_is_empty(value: object) -> bool:
    """True if `value` is not a populated Quantity-shaped dict.

    A Quantity (see coremeta4cat_reaction_schema.py) is
    {value, unit, raw_text}; it counts as empty when it's not a dict, or all
    three keys are None.
    """
    if not isinstance(value, dict):
        return True
    return all(value.get(key) is None for key in ("value", "unit", "raw_text"))


def has_duration_temperature_confusion(extracted_metadata: dict) -> Optional[dict]:
    """Flag records where a Celsius-style temperature reading was filed under
    `has_duration` while `has_temperature` was left empty.

    Both conditions are required: if `has_temperature` is independently
    populated too, that's redundancy, not the "confusion" pattern this
    targets. Scope: matches degC/deg C/°C/° C/℃ only -- the only patterns
    observed leaking into has_duration in this dataset. Extend the regex if a
    future run shows a different leak pattern (e.g. Kelvin, pressure units).
    """
    duration = extracted_metadata.get("has_duration")
    if not isinstance(duration, str) or not _TEMP_UNIT_RE.search(duration):
        return None
    if not quantity_is_empty(extracted_metadata.get("has_temperature")):
        return None
    return {
        "has_duration_value": duration,
        "has_temperature_value": extracted_metadata.get("has_temperature"),
    }


def normalization_keys(label: str) -> set[str]:
    """Candidate dedup keys for a chemical/catalyst label -- mechanical only,
    no domain knowledge.

    Returns the whitespace-collapsed lowercase form and the fully
    whitespace-stripped lowercase form (catches "N 2" vs "N2"). If the label
    ends in a parenthetical preceded by whitespace, e.g. "dinitrogen (N2)" or
    "sulfur dioxide (SO2)", also returns the stripped head and stripped
    parenthetical content as two bridging keys -- this is what lets a bare
    formula ("SO2"), a bare name ("sulfur dioxide"), and a "name (FORMULA)"
    label all land in one cluster without needing a synonym table.

    The whitespace-before-"(" requirement is deliberate: without it, a
    mid-token paren in a real formula like "CO(NH2)2" (urea) would split into
    "CO" + "NH2)2" and falsely merge with "CO2"/"CO 2" (carbon dioxide).
    Requiring a preceding space means only "name (FORMULA)"-style labels get
    split, not bare formulas that happen to contain parentheses.
    """
    collapsed = re.sub(r"\s+", " ", label).strip().lower()
    stripped = re.sub(r"\s+", "", label).lower()
    keys = {collapsed, stripped}

    match = _PAREN_RE.match(label)
    if match:
        head, paren = match.group(1), match.group(2)
        keys.add(re.sub(r"\s+", "", head).lower())
        keys.add(re.sub(r"\s+", "", paren).lower())

    return keys


def cluster_labels(labels: list[str], synonyms: Optional[dict[str, str]] = None) -> list[list[str]]:
    """Union-find labels that share a normalization key, optionally also
    unioning through a `synonyms` map (label.lower() -> an extra shared key).

    Returns clusters with >=2 distinct members, each a sorted list of the
    original labels, sorted by descending cluster size then alphabetically.
    Union-find operates over label *indices*, not the label/key strings
    themselves, so there is no risk of a generated key colliding with an
    unrelated label string.
    """
    parent = list(range(len(labels)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    key_to_index: dict[str, int] = {}
    for i, label in enumerate(labels):
        keys = normalization_keys(label)
        if synonyms and label.lower() in synonyms:
            keys = keys | {synonyms[label.lower()]}
        for key in keys:
            if key in key_to_index:
                union(i, key_to_index[key])
            else:
                key_to_index[key] = i

    groups: dict[int, list[str]] = {}
    for i, label in enumerate(labels):
        groups.setdefault(find(i), []).append(label)

    clusters = [sorted(set(members)) for members in groups.values() if len(set(members)) >= 2]
    clusters.sort(key=lambda members: (-len(members), members[0]))
    return clusters


def mechanical_fragmentation_clusters(labels: list[str]) -> list[list[str]]:
    """Tier 1: fully automatic, no domain knowledge. This is the citable,
    exact fragmentation statistic."""
    return cluster_labels(labels, synonyms=None)


# Tier 2: small, hand-reviewed synonym tables. Illustrative only -- present
# clusters built with these as curated examples, never as an
# automatically-discovered statistic. Chemical and catalyst labels must be
# clustered separately with their own table below; pooling them would wrongly
# merge catalyst "Co"/"cobalt" with chemical "CO"/"carbon monoxide", which
# share a normalized key but are different substances in different roles.
CURATED_CHEMICAL_SYNONYMS: dict[str, str] = {
    "nitrogen": "n2",
    "hydrogen": "h2",
    "oxygen": "o2",
    "ammonia": "nh3",
    "water": "h2o",
    "carbon dioxide": "co2",
    "carbon monoxide": "co",
    "sulfur dioxide": "so2",
    "sulfur trioxide": "so3",
}

CURATED_CATALYST_SYNONYMS: dict[str, str] = {
    "cobalt": "co",
}


def curated_fragmentation_clusters(labels: list[str], synonyms: dict[str, str]) -> list[list[str]]:
    """Tier 2: mechanical clustering plus a small hand-reviewed synonym layer
    layered in as extra shared keys. Illustrative only -- see module notes."""
    return cluster_labels(labels, synonyms=synonyms)

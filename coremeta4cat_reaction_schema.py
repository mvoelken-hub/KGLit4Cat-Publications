"""CoreMeta4Cat CatalyticReaction -- trimmed field subset for LLM extraction.

Hand-written, lightweight Pydantic v2 model mirroring a subset of the slot
names defined on ChemicalReaction / CatalyticReaction in the CoreMeta4Cat
LinkML ontology (https://github.com/nfdi4cat/CoreMeta4Cat). We do NOT import
the ontology's generated coremeta4cat_pydantic.py -- every class there needs a
mandatory `id` URI, unrealistic for a 4B local LLM to invent per substance.

Excluded: chemical identifiers (SMILES/InChI/formula/IUPAC -- substances are
plain name strings), `used_reactor` (reactor hardware),
`product_identification_method`, `has_reaction_step`, `rdf_type`, and the
CatalyticReaction range/experiment variants (`reactor_temperature_range`,
`experiment_pressure`, `feed_composition_range`, `has_experiment_duration`,
`has_atmosphere`).

One reaction per document. Fields that are multivalued (list[...]) in the real
CoreMeta4Cat schema (`reaction_name`, `has_temperature`, `has_pressure`,
`has_yield`, `catalyst_quantity`, `catalyst_type`, `catalyst_form`) are modeled
here as single values -- a deliberate simplification. To switch to list
semantics later: change the annotations to `Optional[List[...]]` and update
the SYSTEM_PROMPT wording; no other code changes needed.

This is intentionally a partial / non-strictly-valid CoreMeta4Cat instance:
`used_reactor` and `product_identification_method` are required at the real
CatalyticReaction level but excluded here, and no `id` URI is produced.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CatalysisResearchFieldEnum(str, Enum):
    """Used for `catalyst_type`. Verified against coremeta4cat_common.yaml."""

    heterogeneous_catalysis = "heterogeneous_catalysis"
    homogeneous_catalysis = "homogeneous_catalysis"
    biocatalysis = "biocatalysis"
    electrocatalysis = "electrocatalysis"
    photocatalysis = "photocatalysis"
    hybrid_catalysis = "hybrid_catalysis"
    other = "other"


class CatalystFormEnum(str, Enum):
    """Used for `catalyst_form`. Verified against coremeta4cat_common.yaml."""

    thin_film = "thin_film"
    bulk = "bulk"
    powdered = "powdered"
    deposited_sample = "deposited_sample"
    supported = "supported"
    other = "other"


class Quantity(BaseModel):
    """Shared shape for has_temperature/has_pressure/has_yield/catalyst_quantity.

    `raw_text` is the fallback when value/unit can't be cleanly split (ranges,
    "up to X", multi-point profiles). Note: Ollama's format= grammar constraint
    does not show these `description=` texts to the model during generation --
    field meaning still has to come from the prompt text (see SYSTEM_PROMPT).
    """

    model_config = ConfigDict(extra="forbid")

    value: Optional[float] = Field(default=None, description="Numeric value, if a single clean number is stated.")
    unit: Optional[str] = Field(default=None, description="Unit as stated in the text, e.g. 'degC', 'bar', '%'.")
    raw_text: Optional[str] = Field(default=None, description="Verbatim text when value/unit can't be split, e.g. a range.")


class CatalyticReactionExtraction(BaseModel):
    """One catalytic reaction as reported in a single abstract.

    Field names match CoreMeta4Cat slot names exactly -- no separate
    custom-name-to-CoreMeta4Cat mapping layer.
    """

    model_config = ConfigDict(extra="forbid")

    reaction_name: Optional[str] = Field(default=None, description="Name of the catalytic reaction/process.")

    used_starting_material: Optional[List[str]] = Field(default=None, description="Starting material substance names (precursors).")
    used_reactant: Optional[List[str]] = Field(default=None, description="Reactant substance names (the feed).")
    generated_product: Optional[List[str]] = Field(default=None, description="Product substance names.")
    used_catalyst: Optional[List[str]] = Field(default=None, description="Catalyst substance names.")
    used_solvent: Optional[List[str]] = Field(default=None, description="Solvent substance names.")

    has_duration: Optional[str] = None
    has_temperature: Optional[Quantity] = None
    has_pressure: Optional[Quantity] = None
    has_yield: Optional[Quantity] = None

    catalyst_quantity: Optional[Quantity] = None
    catalyst_type: Optional[CatalysisResearchFieldEnum] = None
    catalyst_form: Optional[CatalystFormEnum] = None


def get_ollama_format_schema() -> dict:
    """JSON schema to pass as `format=` to `ollama.generate`.

    Plain `.model_json_schema()`, unmodified -- Ollama's grammar-constrained
    decoding consumes standard JSON Schema including the $defs/$ref pointers
    Pydantic emits for Quantity and the two enums. `extra="forbid"` on both
    models above adds `"additionalProperties": false`, tightening the grammar.

    Keep nesting at the current single level (top model -> Quantity). Reports
    on 4B-class quantized models show degraded reliability (empty
    arrays/objects) at 3+ levels of nesting -- don't add another layer without
    re-testing.
    """
    return CatalyticReactionExtraction.model_json_schema()

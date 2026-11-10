| field | field_kind | n_populated | n_total | pct_populated | note |
| --- | --- | --- | --- | --- | --- |
| used_starting_material | list | 0 | 66 | 0.0 |  |
| used_reactant | list | 58 | 66 | 87.9 |  |
| generated_product | list | 57 | 66 | 86.4 |  |
| used_catalyst | list | 38 | 66 | 57.6 |  |
| used_solvent | list | 4 | 66 | 6.1 |  |
| has_duration | str | 17 | 66 | 25.8 |  |
| has_temperature | quantity | 4 | 66 | 6.1 |  |
| has_pressure | quantity | 4 | 66 | 6.1 |  |
| has_yield | quantity | 0 | 66 | 0.0 |  |
| catalyst_quantity | quantity | 0 | 66 | 0.0 |  |
| catalyst_type | enum | 66 | 66 | 100.0 |  |
| catalyst_form | enum | 53 | 66 | 80.3 |  |
| reaction_name | str | 66 | 66 | 100.0 | Prompt-hardcoded to the queried process name -- not an extraction-fidelity signal. See the retrieval-noise-propagated mislabeling failure mode. |
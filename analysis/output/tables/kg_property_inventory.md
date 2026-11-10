| property_name | property_kind | domain | range | mapped_concept_iri |
| --- | --- | --- | --- | --- |
| reportsReaction | object | Publication | ReactionInstance |  |
| instantiates | object | ReactionInstance | CatalyticReaction |  |
| hasStartingMaterial | object | ReactionInstance | ChemicalSpecies | http://purl.obolibrary.org/obo/RO_0004009 |
| hasReactant | object | ReactionInstance | ChemicalSpecies | http://purl.obolibrary.org/obo/RO_0004009 |
| hasProduct | object | ReactionInstance | ChemicalSpecies | http://purl.obolibrary.org/obo/RO_0004008 |
| hasSolvent | object | ReactionInstance | ChemicalSpecies | http://www.w3.org/ns/prov#wasAssociatedWith |
| hasCatalyst | object | ReactionInstance | Catalyst | http://purl.obolibrary.org/obo/RXNO_0000425 |
| doi | datatype | Publication | string |  |
| openalexId | datatype | Publication | string |  |
| score | datatype | Publication | decimal |  |
| publicationDate | datatype | Publication | string |  |
| catalystType | datatype | ReactionInstance | string | https://w3id.org/nfdi4cat/voc4cat_0007014 |
| catalystForm | datatype | ReactionInstance | string | TODO:catalyst_form |
| duration | datatype | ReactionInstance | string | https://schema.org/duration |
| temperatureValue | datatype | ReactionInstance | decimal | http://semanticscience.org/resource/SIO_000008 |
| temperatureUnit | datatype | ReactionInstance | string | http://semanticscience.org/resource/SIO_000008 |
| temperatureRawText | datatype | ReactionInstance | string | http://semanticscience.org/resource/SIO_000008 |
| pressureValue | datatype | ReactionInstance | decimal | http://semanticscience.org/resource/SIO_000008 |
| pressureUnit | datatype | ReactionInstance | string | http://semanticscience.org/resource/SIO_000008 |
| pressureRawText | datatype | ReactionInstance | string | http://semanticscience.org/resource/SIO_000008 |
| yieldValue | datatype | ReactionInstance | decimal | http://semanticscience.org/resource/SIO_000008 |
| yieldUnit | datatype | ReactionInstance | string | http://semanticscience.org/resource/SIO_000008 |
| yieldRawText | datatype | ReactionInstance | string | http://semanticscience.org/resource/SIO_000008 |
| catalystQuantityValue | datatype | ReactionInstance | decimal | https://w3id.org/nfdi4cat/coremeta4cat/catalyst_quantity |
| catalystQuantityUnit | datatype | ReactionInstance | string | https://w3id.org/nfdi4cat/coremeta4cat/catalyst_quantity |
| catalystQuantityRawText | datatype | ReactionInstance | string | https://w3id.org/nfdi4cat/coremeta4cat/catalyst_quantity |
| mappedConcept | annotation |  |  |  |
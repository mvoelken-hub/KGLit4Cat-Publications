| metric | value | note |
| --- | --- | --- |
| documents_retrieved | 90 | after per-process deduplication |
| processes | 10 | with at least one retrieved document |
| documents_per_process_min | 8 |  |
| documents_per_process_max | 10 |  |
| distinct_openalex_ids | 90 | equals documents_retrieved if no document appears under two processes |
| distinct_normalized_titles | 90 | same check on normalised titles |
| documents_with_usable_abstract | 66 | non-empty abstract field |
| pct_with_usable_abstract | 73.3 | of documents_retrieved |
| documents_without_usable_abstract | 24 | no source returned an abstract, or the validity gate rejected it |
| documents_with_extracted_metadata | 66 | non-empty extracted_metadata |
| abstract_but_no_metadata | 0 | extraction failures after the self-correction retry |
| metadata_but_no_abstract | 0 | should be 0 |
| documents_without_publication_date | 1 |  |
| earliest_publication_year | 1925 |  |
| latest_publication_year | 2025 |  |
| documents_published_2010_or_later | 52 |  |
| pct_recent_of_all_documents | 57.8 | denominator: documents_retrieved |
| pct_recent_of_dated_documents | 58.4 | denominator: documents with a publication date |
| similarity_score_min | 0.9787 | Logic-Mill score, 4 decimals |
| similarity_score_max | 0.9933 | Logic-Mill score, 4 decimals |
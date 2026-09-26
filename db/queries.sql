-- name: prior_art
-- Has :target been tried, in what context, with what outcome? (label match, case-insensitive)
SELECT r.slug, r.study_id, r.kind, r.attempt_type, f.finding_id, f.target_label, f.target_identifier, f.outcome_class,
       f.informativeness, f.effect_value, f.effect_n, f.dose, f.proposed_by, r.title
FROM findings f JOIN records r ON r.id = f.record_id
WHERE lower(f.target_label) LIKE '%' || lower(:target) || '%'
UNION
SELECT r.slug, r.study_id, r.kind, r.attempt_type, NULL, s.label, s.identifier, r.outcome_class,
       NULL, NULL, NULL, NULL, s.proposed_by, r.title
FROM screened_items s JOIN records r ON r.id = s.record_id
WHERE lower(s.label) LIKE '%' || lower(:target) || '%'
ORDER BY 1;

-- name: prior_art_by_identifier
-- Same question keyed on a resolved identifier (PubChem, UniProt, HGNC, OBI...).
SELECT r.slug, r.study_id, f.finding_id, f.target_label, f.outcome_class, f.informativeness, f.effect_value, f.effect_n, f.dose
FROM findings f JOIN records r ON r.id = f.record_id
WHERE f.target_identifier = :identifier
ORDER BY r.slug;

-- name: by_entity
-- Records that mention an entity (taxon, cell line, gene, assay, agent...).
SELECT r.slug, r.study_id, r.kind, r.outcome_class, re.role
FROM record_entities re JOIN records r ON r.id = re.record_id
WHERE re.entity_id = :entity_id
ORDER BY r.slug;

-- name: uninformative_negatives
-- Negatives that do not count as evidence of absence, and why (the rule made machine-checkable).
SELECT r.slug, r.study_id, f.finding_id, f.target_label, f.outcome_class, f.informativeness_reason,
       f.positive_control_kind, f.positive_control_passed
FROM findings f JOIN records r ON r.id = f.record_id
WHERE f.informativeness = 'uninformative'
ORDER BY r.slug, f.finding_id;

-- name: search
-- Full-text search over titles, questions, summaries, applicability and findings.
SELECT r.slug, r.study_id, r.kind, r.outcome_class, bm25(records_fts) AS score
FROM records_fts JOIN records r ON r.rowid = records_fts.rowid
WHERE records_fts MATCH :text
ORDER BY score
LIMIT 20;

-- name: negatives_for_target
-- Informative negatives for a target with the tested dose and conditions.
SELECT r.slug, f.target_label, f.outcome_class, f.informativeness, f.effect_value, f.effect_n, f.dose, f.sensitivity
FROM findings f JOIN records r ON r.id = f.record_id
WHERE lower(f.target_label) = lower(:target) AND f.outcome_class LIKE 'negative-%'
ORDER BY r.slug;

-- name: by_performer
-- What did a given agent or model produce?
SELECT DISTINCT r.slug, r.study_id, r.outcome_class, p.role, p.model
FROM performers p JOIN records r ON r.id = p.record_id
WHERE p.name = :name
ORDER BY r.slug;

-- name: open_branches
-- Untried branches, open questions and next steps across the corpus: where to pick up work.
SELECT r.slug, r.study_id, b.branch_kind, b.status, b.description, b.data_pointers
FROM branches b JOIN records r ON r.id = b.record_id
ORDER BY r.study_id, r.slug, b.branch_kind, b.seq;

-- name: references_status
-- Version and integrity status of every DOI a study's records depend on, as checked at ingest.
SELECT DISTINCT s.identifier, s.role, s.status_version AS version, s.status_integrity AS integrity, s.status_asserted_by AS asserted_by, s.status_checked_at AS checked_at
FROM sources s JOIN records r ON r.id = s.record_id
WHERE r.study_id = :study_id AND s.identifier LIKE 'doi:%'
ORDER BY s.identifier;

-- name: agents_and_cost
-- Which records involved software agents, and what did they cost?
SELECT r.slug, r.study_id, r.cost, group_concat(DISTINCT p.name) AS agents
FROM records r LEFT JOIN performers p ON p.record_id = r.id AND p.performer_type IN ('software-agent', 'llm')
GROUP BY r.id ORDER BY r.study_id, r.slug;

-- name: outcome_summary
-- Corpus overview: findings by outcome class and informativeness.
SELECT r.study_id, f.outcome_class, f.informativeness, count(*) AS n
FROM findings f JOIN records r ON r.id = f.record_id
GROUP BY r.study_id, f.outcome_class, f.informativeness ORDER BY r.study_id, n DESC;

PRAGMA foreign_keys = ON;

CREATE TABLE run_meta (
    run_id TEXT PRIMARY KEY,
    protocol_version TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (
        length(manifest_sha256) = 64
        AND manifest_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    observations_sha256 TEXT NOT NULL CHECK (
        length(observations_sha256) = 64
        AND observations_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    validation_sha256 TEXT NOT NULL CHECK (
        length(validation_sha256) = 64
        AND validation_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    manifest_quality TEXT NOT NULL CHECK (manifest_quality = 'PASS')
);

CREATE TABLE stg_r2_observation (
    run_id TEXT NOT NULL REFERENCES run_meta(run_id),
    observation_id TEXT NOT NULL,
    match_id TEXT NOT NULL,
    player_key TEXT NOT NULL CHECK (
        length(player_key) = 24
        AND player_key NOT GLOB '*[^0-9a-f]*'
    ),
    rank INTEGER NOT NULL CHECK (rank BETWEEN 1 AND 100),
    rank_decile INTEGER NOT NULL CHECK (rank_decile = ((rank - 1) / 10) + 1),
    split TEXT NOT NULL CHECK (split = 'holdout'),
    recent_index INTEGER NOT NULL CHECK (recent_index BETWEEN 1 AND 5),
    season_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode = 'squad-fpp'),
    map_name TEXT NOT NULL,
    attacks INTEGER NOT NULL CHECK (attacks >= 0),
    damage_events INTEGER NOT NULL CHECK (damage_events >= 0),
    ratio REAL,
    review_candidate INTEGER NOT NULL CHECK (review_candidate IN (0, 1)),
    minimum_signal_pool INTEGER NOT NULL CHECK (minimum_signal_pool >= 1),
    status TEXT NOT NULL CHECK (status IN (
        'evaluated',
        'target_below_min_attacks',
        'match_pool_below_8',
        'match_pool_below_signal_capable'
    )),
    eligible_players INTEGER,
    match_mean REAL,
    match_sd REAL,
    local_z REAL,
    skip_reason TEXT,
    PRIMARY KEY (run_id, observation_id),
    UNIQUE (run_id, match_id, player_key),
    CHECK (
        (attacks = 0 AND ratio IS NULL)
        OR (attacks > 0 AND ratio IS NOT NULL
            AND abs(ratio - (1.0 * damage_events / attacks)) < 0.000000000001)
    ),
    CHECK ((
        (status = 'evaluated'
            AND attacks >= 30
            AND eligible_players >= minimum_signal_pool
            AND match_mean IS NOT NULL
            AND match_sd IS NOT NULL
            AND local_z IS NOT NULL
            AND skip_reason IS NULL)
        OR (status = 'target_below_min_attacks'
            AND attacks < 30
            AND eligible_players IS NULL
            AND match_mean IS NULL
            AND match_sd IS NULL
            AND local_z IS NULL
            AND skip_reason = status
            AND review_candidate = 0)
        OR (status = 'match_pool_below_8'
            AND attacks >= 30
            AND eligible_players BETWEEN 0 AND 7
            AND local_z IS NULL
            AND skip_reason = status
            AND review_candidate = 0)
        OR (status = 'match_pool_below_signal_capable'
            AND attacks >= 30
            AND eligible_players BETWEEN 8 AND minimum_signal_pool - 1
            AND local_z IS NULL
            AND skip_reason = status
            AND review_candidate = 0)
    ) IS TRUE)
);

CREATE TABLE dim_player (
    run_id TEXT NOT NULL REFERENCES run_meta(run_id),
    player_key TEXT NOT NULL CHECK (
        length(player_key) = 24
        AND player_key NOT GLOB '*[^0-9a-f]*'
    ),
    rank INTEGER NOT NULL CHECK (rank BETWEEN 1 AND 100),
    rank_decile INTEGER NOT NULL CHECK (rank_decile = ((rank - 1) / 10) + 1),
    PRIMARY KEY (run_id, player_key),
    UNIQUE (run_id, rank)
);

CREATE TABLE dim_match (
    run_id TEXT NOT NULL REFERENCES run_meta(run_id),
    match_id TEXT NOT NULL,
    season_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode = 'squad-fpp'),
    map_name TEXT NOT NULL,
    PRIMARY KEY (run_id, match_id)
);

CREATE TABLE fact_r2_observation (
    run_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    match_id TEXT NOT NULL,
    player_key TEXT NOT NULL,
    recent_index INTEGER NOT NULL,
    attacks INTEGER NOT NULL,
    damage_events INTEGER NOT NULL,
    ratio REAL,
    eligible_players INTEGER,
    match_mean REAL,
    match_sd REAL,
    local_z REAL,
    status TEXT NOT NULL,
    review_candidate INTEGER NOT NULL,
    skip_reason TEXT,
    PRIMARY KEY (run_id, observation_id),
    UNIQUE (run_id, match_id, player_key),
    FOREIGN KEY (run_id, player_key) REFERENCES dim_player(run_id, player_key),
    FOREIGN KEY (run_id, match_id) REFERENCES dim_match(run_id, match_id)
);

CREATE TABLE artifact (
    run_id TEXT NOT NULL REFERENCES run_meta(run_id),
    artifact_path TEXT NOT NULL,
    layer TEXT NOT NULL CHECK (layer IN ('bronze', 'silver', 'gold')),
    dataset TEXT NOT NULL,
    media_type TEXT NOT NULL,
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
    record_count INTEGER NOT NULL CHECK (record_count >= 0),
    sha256 TEXT NOT NULL CHECK (
        length(sha256) = 64
        AND sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    PRIMARY KEY (run_id, artifact_path)
);

CREATE TABLE lineage_edge (
    run_id TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    source_path TEXT NOT NULL,
    PRIMARY KEY (run_id, artifact_path, source_path),
    FOREIGN KEY (run_id, artifact_path) REFERENCES artifact(run_id, artifact_path)
);

-- @load-boundary

BEGIN IMMEDIATE;

INSERT INTO dim_player (run_id, player_key, rank, rank_decile)
SELECT run_id, player_key, MIN(rank), MIN(rank_decile)
FROM stg_r2_observation
GROUP BY run_id, player_key
HAVING MIN(rank) = MAX(rank) AND MIN(rank_decile) = MAX(rank_decile);

INSERT INTO dim_match (run_id, match_id, season_id, mode, map_name)
SELECT run_id, match_id, MIN(season_id), MIN(mode), MIN(map_name)
FROM stg_r2_observation
GROUP BY run_id, match_id
HAVING MIN(season_id) = MAX(season_id)
   AND MIN(mode) = MAX(mode)
   AND MIN(map_name) = MAX(map_name);

INSERT INTO fact_r2_observation (
    run_id, observation_id, match_id, player_key, recent_index,
    attacks, damage_events, ratio, eligible_players, match_mean,
    match_sd, local_z, status, review_candidate, skip_reason
)
SELECT
    run_id, observation_id, match_id, player_key, recent_index,
    attacks, damage_events, ratio, eligible_players, match_mean,
    match_sd, local_z, status, review_candidate, skip_reason
FROM stg_r2_observation;

CREATE VIEW v_observation_funnel AS
SELECT
    run_id,
    COUNT(*) AS accepted_observations,
    SUM(CASE WHEN status = 'evaluated' THEN 1 ELSE 0 END) AS evaluated,
    SUM(CASE WHEN status = 'target_below_min_attacks' THEN 1 ELSE 0 END)
        AS target_below_min_attacks,
    SUM(CASE WHEN status = 'match_pool_below_8' THEN 1 ELSE 0 END)
        AS match_pool_below_8,
    SUM(CASE WHEN status = 'match_pool_below_signal_capable' THEN 1 ELSE 0 END)
        AS match_pool_below_signal_capable,
    SUM(review_candidate) AS review_candidates
FROM fact_r2_observation
GROUP BY run_id;

CREATE VIEW v_primary_first_evaluated AS
WITH ranked AS (
    SELECT
        run_id,
        player_key,
        review_candidate,
        ROW_NUMBER() OVER (
            PARTITION BY run_id, player_key
            ORDER BY recent_index, match_id, observation_id
        ) AS sample_order
    FROM fact_r2_observation
    WHERE status = 'evaluated'
)
SELECT
    run_id,
    COUNT(*) AS evaluated_players,
    SUM(review_candidate) AS review_candidates,
    1.0 * SUM(review_candidate) / COUNT(*) AS review_candidate_rate
FROM ranked
WHERE sample_order = 1
GROUP BY run_id;

CREATE VIEW v_decile_coverage AS
WITH RECURSIVE decile(rank_decile) AS (
    VALUES (1)
    UNION ALL
    SELECT rank_decile + 1 FROM decile WHERE rank_decile < 10
)
SELECT
    r.run_id,
    d.rank_decile,
    COUNT(f.observation_id) AS accepted_observations,
    SUM(CASE WHEN f.status = 'evaluated' THEN 1 ELSE 0 END) AS evaluated,
    SUM(CASE WHEN f.status = 'evaluated' THEN f.review_candidate ELSE 0 END)
        AS review_candidates
FROM run_meta AS r
CROSS JOIN decile AS d
LEFT JOIN dim_player AS p
    ON p.run_id = r.run_id AND p.rank_decile = d.rank_decile
LEFT JOIN fact_r2_observation AS f
    ON f.run_id = p.run_id AND f.player_key = p.player_key
GROUP BY r.run_id, d.rank_decile;

CREATE VIEW v_map_coverage AS
SELECT
    f.run_id,
    m.map_name,
    COUNT(*) AS evaluated,
    SUM(f.review_candidate) AS review_candidates
FROM fact_r2_observation AS f
JOIN dim_match AS m
    ON m.run_id = f.run_id AND m.match_id = f.match_id
WHERE f.status = 'evaluated'
GROUP BY f.run_id, m.map_name;

CREATE VIEW v_lineage_reachability AS
WITH RECURSIVE walk(run_id, root_path, node_path, depth, trail, cycle) AS (
    SELECT
        run_id,
        artifact_path,
        artifact_path,
        0,
        char(31) || artifact_path || char(31),
        0
    FROM artifact
    WHERE layer = 'gold'
    UNION ALL
    SELECT
        w.run_id,
        w.root_path,
        e.source_path,
        w.depth + 1,
        w.trail || e.source_path || char(31),
        instr(w.trail, char(31) || e.source_path || char(31)) > 0
    FROM walk AS w
    JOIN lineage_edge AS e
        ON e.run_id = w.run_id AND e.artifact_path = w.node_path
    WHERE w.cycle = 0 AND w.depth < 64
)
SELECT
    r.run_id,
    (SELECT COUNT(*) FROM artifact AS a WHERE a.run_id = r.run_id)
        AS managed_artifacts,
    (SELECT COUNT(*) FROM lineage_edge AS e WHERE e.run_id = r.run_id)
        AS lineage_edges,
    COUNT(DISTINCT CASE WHEN w.depth > 0 THEN w.node_path END)
        AS reachable_sources,
    MAX(w.depth) AS maximum_depth,
    MAX(w.cycle) AS cyclic
FROM run_meta AS r
LEFT JOIN walk AS w ON w.run_id = r.run_id
GROUP BY r.run_id;

COMMIT;

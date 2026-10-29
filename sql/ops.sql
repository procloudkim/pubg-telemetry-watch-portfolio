PRAGMA foreign_keys = ON;

CREATE TABLE batch (
    batch_id TEXT PRIMARY KEY NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    code_sha256 TEXT NOT NULL,
    rule_protocol TEXT NOT NULL,
    created_at TEXT NOT NULL,
    runtime_json TEXT NOT NULL
);
CREATE TABLE job (
    job_id TEXT PRIMARY KEY NOT NULL,
    match_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_bytes INTEGER NOT NULL CHECK (source_bytes >= 0),
    source_records INTEGER NOT NULL CHECK (source_records > 0),
    rule_protocol TEXT NOT NULL,
    code_sha256 TEXT NOT NULL,
    map_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
    created_at TEXT NOT NULL,
    finished_at TEXT,
    event_count INTEGER CHECK (event_count >= 0),
    player_count INTEGER CHECK (player_count >= 0),
    result_sha256 TEXT,
    CHECK ((state != 'SUCCEEDED' OR (finished_at IS NOT NULL AND event_count IS NOT NULL
        AND player_count IS NOT NULL AND result_sha256 IS NOT NULL)) IS TRUE)
);
CREATE INDEX job_state ON job(state, created_at, job_id);
CREATE TABLE batch_job (
    batch_id TEXT NOT NULL REFERENCES batch(batch_id),
    job_id TEXT NOT NULL REFERENCES job(job_id),
    PRIMARY KEY (batch_id, job_id)
);
CREATE TABLE attempt (
    job_id TEXT NOT NULL REFERENCES job(job_id),
    attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    recovered_at TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN ('RUNNING','SUCCEEDED','FAILED','INTERRUPTED')),
    stage TEXT NOT NULL,
    error_code TEXT,
    elapsed_s REAL CHECK (elapsed_s >= 0),
    stage_seconds_json TEXT NOT NULL DEFAULT '{}',
    process_peak_rss_kib INTEGER CHECK (process_peak_rss_kib >= 0),
    PRIMARY KEY (job_id, attempt_no)
);
CREATE TABLE combat_event (
    job_id TEXT NOT NULL REFERENCES job(job_id),
    event_index INTEGER NOT NULL CHECK (event_index >= 0),
    player_key TEXT NOT NULL CHECK (length(player_key) = 24 AND player_key NOT GLOB '*[^0-9a-f]*'),
    event_type TEXT NOT NULL CHECK (event_type IN ('attack','damage')),
    attack_id TEXT,
    damage REAL,
    event_time TEXT,
    PRIMARY KEY (job_id, event_index),
    CHECK (event_type != 'damage' OR damage IS NOT NULL)
);
CREATE INDEX combat_attack ON combat_event(job_id, player_key, attack_id) WHERE event_type = 'attack';
CREATE TABLE player_match (
    job_id TEXT NOT NULL REFERENCES job(job_id),
    player_key TEXT NOT NULL CHECK (length(player_key) = 24 AND player_key NOT GLOB '*[^0-9a-f]*'),
    attacks INTEGER NOT NULL CHECK (attacks >= 0),
    damage_events INTEGER NOT NULL CHECK (damage_events >= 0),
    ratio REAL,
    review_candidate INTEGER NOT NULL CHECK (review_candidate IN (0,1)),
    minimum_signal_pool INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('evaluated','target_below_min_attacks',
                                          'match_pool_below_8','match_pool_below_signal_capable')),
    eligible_players INTEGER,
    match_mean REAL,
    match_sd REAL,
    local_z REAL,
    skip_reason TEXT,
    PRIMARY KEY (job_id, player_key),
    CHECK (((attacks = 0 AND ratio IS NULL) OR (attacks > 0 AND ratio IS NOT NULL)) IS TRUE),
    CHECK (((status = 'evaluated' AND eligible_players >= minimum_signal_pool
        AND match_mean IS NOT NULL AND match_sd IS NOT NULL AND local_z IS NOT NULL AND skip_reason IS NULL)
        OR (status != 'evaluated' AND local_z IS NULL AND skip_reason = status AND review_candidate = 0)) IS TRUE)
);
CREATE TABLE review_signal (
    job_id TEXT NOT NULL,
    player_key TEXT NOT NULL,
    rule TEXT NOT NULL CHECK (rule IN ('R1_speed','R2_hit_ratio','R3_kill_burst')),
    signal_json TEXT NOT NULL,
    PRIMARY KEY (job_id, player_key, rule),
    FOREIGN KEY (job_id, player_key) REFERENCES player_match(job_id, player_key)
);
CREATE TABLE review_case (
    case_id TEXT PRIMARY KEY NOT NULL,
    job_id TEXT NOT NULL,
    player_key TEXT NOT NULL,
    rule TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('OPEN','IN_REVIEW','COMPLETED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (job_id, player_key, rule),
    FOREIGN KEY (job_id, player_key, rule) REFERENCES review_signal(job_id, player_key, rule)
);
CREATE TABLE review_history (
    case_id TEXT NOT NULL REFERENCES review_case(case_id),
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    action TEXT NOT NULL CHECK (action IN ('created','start','note','complete','reopen')),
    operator TEXT NOT NULL CHECK (length(trim(operator)) > 0),
    recorded_at TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL CHECK (to_state IN ('OPEN','IN_REVIEW','COMPLETED')),
    note TEXT,
    PRIMARY KEY (case_id, sequence),
    CHECK (((action='created' AND from_state IS NULL AND to_state='OPEN')
        OR (action='start' AND from_state='OPEN' AND to_state='IN_REVIEW')
        OR (action='complete' AND from_state='IN_REVIEW' AND to_state='COMPLETED')
        OR (action='reopen' AND from_state='COMPLETED' AND to_state='OPEN')
        OR (action='note' AND from_state=to_state)) IS TRUE),
    CHECK (((action='note' AND note IS NOT NULL AND length(trim(note))>0)
        OR (action!='note' AND note IS NULL)) IS TRUE)
);
CREATE TRIGGER review_history_no_update BEFORE UPDATE ON review_history
BEGIN SELECT RAISE(ABORT, 'REVIEW_HISTORY_APPEND_ONLY'); END;
CREATE TRIGGER review_history_no_delete BEFORE DELETE ON review_history
BEGIN SELECT RAISE(ABORT, 'REVIEW_HISTORY_APPEND_ONLY'); END;
PRAGMA user_version = 2;

-- @compute
WITH counted AS (
    SELECT e.player_key, e.event_type,
        CASE WHEN e.event_type = 'damage' AND
            (:legacy OR (e.damage > 0 AND e.attack_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM combat_event a
                WHERE a.job_id = e.job_id AND a.player_key = e.player_key
                  AND a.event_type = 'attack' AND a.attack_id = e.attack_id
            ))) THEN 1 ELSE 0 END AS valid_damage
    FROM combat_event e WHERE e.job_id = :job_id
), counts AS (
    SELECT p.player_key,
        SUM(CASE WHEN c.event_type = 'attack' THEN 1 ELSE 0 END) AS attacks,
        COALESCE(SUM(c.valid_damage), 0) AS damage_events
    FROM input_player p LEFT JOIN counted c ON c.player_key = p.player_key
    GROUP BY p.player_key
), ratios AS (
    SELECT *, CASE WHEN attacks > 0 THEN 1.0 * damage_events / attacks END AS ratio FROM counts
), centered AS (
    SELECT ratio, COUNT(*) OVER () AS eligible_players,
        CASE WHEN MIN(ratio) OVER () = MAX(ratio) OVER () THEN MIN(ratio) OVER ()
             ELSE AVG(ratio) OVER () END AS mean,
        MIN(ratio) OVER () = MAX(ratio) OVER () AS constant_pool
    FROM ratios WHERE attacks >= :min_attacks
), pool AS (
    SELECT COUNT(*) AS eligible_players, MIN(mean) AS mean,
        CASE WHEN MAX(constant_pool) THEN 1e-9
             ELSE SQRT(AVG((ratio - mean) * (ratio - mean))) END AS sd
    FROM centered
), states AS (
    SELECT r.*, :min_signal_pool AS minimum_signal_pool,
        CASE WHEN r.attacks < :min_attacks THEN 'target_below_min_attacks'
             WHEN p.eligible_players < :min_pool THEN 'match_pool_below_8'
             WHEN p.eligible_players < :min_signal_pool THEN 'match_pool_below_signal_capable'
             ELSE 'evaluated' END AS status,
        CASE WHEN r.attacks >= :min_attacks THEN p.eligible_players END AS eligible_players,
        CASE WHEN r.attacks >= :min_attacks THEN p.mean END AS match_mean,
        CASE WHEN r.attacks >= :min_attacks THEN p.sd END AS match_sd,
        CASE WHEN r.attacks >= :min_attacks AND p.eligible_players >= :min_signal_pool
             THEN (r.ratio - p.mean) / p.sd END AS local_z
    FROM ratios r CROSS JOIN pool p
)
SELECT *, CASE WHEN status = 'evaluated' THEN local_z > :z_hit ELSE 0 END AS review_candidate,
       CASE WHEN status != 'evaluated' THEN status END AS skip_reason
FROM states ORDER BY player_key;

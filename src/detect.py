"""Compatibility entry point; implementation is separated by responsibility."""

from .domain.pubg.detection import (
    SPEED_MS,
    SPEED_WINDOW_S,
    Z_HIT,
    MIN_ATTACKS,
    MIN_R2_POOL,
    MIN_R2_SIGNAL_POOL,
    KILL_N,
    KILL_WINDOW_S,
    in_vehicle,
    r1_speed,
    r2_hit_ratio,
    r2_context,
    r2_observation,
    r3_kill_burst,
    mask_signals,
    detect_match,
)
from .cli.detect import main
from .cli.research_composition import pipeline


if __name__ == "__main__":
    main()

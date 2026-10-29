"""Compatibility entry point; implementation is separated by responsibility."""

from .adapters.presentation import RULE_KO
from .cli.report import main
from .cli.research_composition import pipeline


def render_review(signals, manifest, generated_at=None):
    return pipeline().render_review(signals, manifest, generated_at)


if __name__ == "__main__":
    main()

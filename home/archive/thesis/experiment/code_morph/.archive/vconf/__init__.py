"""Reproduction of *How do LLMs Compute Verbal Confidence?* (Kumaran et al., 2026).

The package mirrors the reproduction guidebook: :mod:`vconf.config`,
:mod:`vconf.prompts`, :mod:`vconf.data`, :mod:`vconf.models`,
:mod:`vconf.positions`, :mod:`vconf.hooks`, :mod:`vconf.attention`,
:mod:`vconf.metrics`, :mod:`vconf.grading` and :mod:`vconf.pipeline` implement
the shared setup (§2), and ``vconf.exp0``–``vconf.exp9`` implement one
experiment section each.
"""

from . import config, metrics, positions, prompts  # noqa: F401

__all__ = [
    "config",
    "prompts",
    "positions",
    "metrics",
    "data",
    "models",
    "hooks",
    "attention",
    "grading",
    "pipeline",
    "plotting",
    "exp0_behavioral",
    "exp1_steering",
    "exp2_patching",
    "exp3_noising",
    "exp4_swap",
    "exp5_ood",
    "exp6_probing",
    "exp7_answer_colon",
    "exp8_attention_blocking",
    "exp9_generalization",
]

__version__ = "1.0.0"

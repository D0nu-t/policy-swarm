"""
Coverage functions for the methods note; they live in ``policyswarm.coverage``
so the dashboard's ε explorer uses exactly the same code.
"""

from policyswarm.coverage import *  # noqa: F401,F403
from policyswarm.coverage import (  # noqa: F401  (explicit for readers and linters)
    METRICS, SPACES, distances, matched_epsilon, pass_curve, pass_fraction,
    pass_fraction_quadrature, sample_opinions, sample_pairs,
)

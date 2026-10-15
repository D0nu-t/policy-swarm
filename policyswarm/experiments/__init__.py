"""
policyswarm.experiments
=======================
Experiment modules for the PolicySwarm framework.

Available experiments
---------------------
Exp 1  OversightPhaseExperiment      — Regime phase transitions (CB, variance)
Exp 2  EnforcementLagExperiment      — Lag sensitivity (strongest finding)
Exp 3  MediaInteractionExperiment    — Media × lag interaction
Exp 4  CounterfactualShockExperiment — Paired shock counterfactuals (geometry × lag)
Exp 4b TopologyValidationExperiment  — Exp 4 on stochastic block model networks
Exp 4c EpsilonCalibrationExperiment  — Raw vs coverage-matched thresholds
Exp 5  CentralitySweepExperiment     — Hub vs random targeting × strength
Exp 6  GeometryExperiment            — Euclidean vs cosine vs manifold
"""

from .exp1_oversight         import OversightPhaseExperiment
from .exp2_enforcement_lag   import EnforcementLagExperiment
from .exp3_media_interaction import MediaInteractionExperiment
from .exp4_counterfactual    import CounterfactualShockExperiment
from .exp5_centrality        import CentralitySweepExperiment
from .exp6_geometry          import GeometryExperiment
from .exp4b_topology_validation import TopologyValidationExperiment
from .exp4c_epsilon_calibration import EpsilonCalibrationExperiment

__all__ = [
    "OversightPhaseExperiment",
    "EnforcementLagExperiment",
    "MediaInteractionExperiment",
    "CounterfactualShockExperiment",
    "CentralitySweepExperiment",
    "GeometryExperiment",
    "TopologyValidationExperiment",
    "EpsilonCalibrationExperiment",
]

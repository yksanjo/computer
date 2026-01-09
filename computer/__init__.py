"""
Computer - GPU Cost Intelligence Platform

See, analyze, and optimize your GPU spend across cloud providers.
"""

__version__ = "0.1.0"
__author__ = "Yoshi Kondo"

from computer.connect import AWSConnector, GCPConnector, VastAIConnector, RunPodConnector
from computer.see import SpendAggregator
from computer.waste import WasteDetector
from computer.forecast import CostPredictor
from computer.optimize import Recommender

__all__ = [
    "AWSConnector",
    "GCPConnector",
    "VastAIConnector",
    "RunPodConnector",
    "SpendAggregator",
    "WasteDetector",
    "CostPredictor",
    "Recommender",
]

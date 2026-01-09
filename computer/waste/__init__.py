"""
Waste Module - Detect GPU Waste and Inefficiencies

Identify idle GPUs, wrong instance types, missed spot opportunities.
"""

from computer.waste.detector import WasteDetector
from computer.waste.rules import WasteRule, WasteType, WasteAlert

__all__ = [
    "WasteDetector",
    "WasteRule",
    "WasteType",
    "WasteAlert",
]

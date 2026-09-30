"""Minimal batch-local registry for the five archived estimators."""
from .mdm import MDM
from .wmle import WMLE
from .lse import LSE
from .lre import LRE
from .mle import MLE

IMPLEMENTED = {"mdm": MDM, "wmle": WMLE, "lse": LSE, "lre": LRE, "mle": MLE}

def resolve_method(method_id):
    return method_id, IMPLEMENTED[method_id]

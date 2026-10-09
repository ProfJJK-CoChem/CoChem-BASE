"""Legacy module namespace shared through normal Python package discovery.

BASE owns its PES store; TORQ owns its optional legacy scientific modules.
This initializer imports neither provider and guesses no sibling checkout.
"""
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

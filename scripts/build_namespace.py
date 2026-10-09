"""Keep BASE's dotted PES module without taking TORQ's legacy initializer."""
from setuptools.command.build_py import build_py


class BaseNamespaceBuildPy(build_py):
    """Exclude only setuptools' implicit Libraries parent initializer."""

    def find_modules(self):
        return [
            item for item in super().find_modules()
            if (item[0], item[1]) != ("Libraries", "__init__")
        ]

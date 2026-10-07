"""Explicit artifact boundaries replacing obsolete import-time error shells."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict

from .artifact_handoff import ModuleHandoff, prepare_module_handoff
from .module_registry import ModuleCapability, get_module_capability


class IntegrationBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    interface: str
    module_id: str
    operation: str
    description: str

    def capability(self) -> ModuleCapability:
        return get_module_capability(self.module_id)

    def prepare_handoff(self, artifact_path: str | Path, destination: str | Path,
                        *, options: dict | None = None) -> ModuleHandoff:
        return prepare_module_handoff(self.module_id, artifact_path, destination,
                                      operation=self.operation, options=options)

    def main(self, argv: Sequence[str] | None = None) -> int:
        parser = argparse.ArgumentParser(description=self.description)
        parser.add_argument("--artifact", type=Path)
        parser.add_argument("--output", type=Path)
        args = parser.parse_args(argv)
        if args.artifact is None and args.output is None:
            print(self.capability().model_dump_json(indent=2))
            return 0
        if args.artifact is None or args.output is None:
            parser.error("Artifact handoff requires both --artifact and --output")
        result = self.prepare_handoff(args.artifact, args.output)
        print(result.model_dump_json(indent=2))
        return 0

"""
Pydantic v2 validation schemas for Antigravity ML/RL Telemetry (Task 1.01 & 1.15).

Enforces strict type contracts, ISO 8601 UTC timestamp formatting,
and extra="forbid" to eliminate unintended data leakage while ensuring
bidirectional lossless conversion with native TelemetryRecord dataclasses.

Governed by Method Matrix v4.2 and Anti-Spoofing Protocol v4.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import uuid

from pydantic import BaseModel, ConfigDict, Field

from cochem_ml.diff_ast_parser import (
    DiffASTParseResult,
    EntityModificationRecord,
    FunctionComplexityRecord,
    ImportShiftRecord,
    ImportStatementRecord,
    ImportSummaryRecord,
    ModuleComplexityRecord,
    TreeModificationRecord,
)
from cochem_ml.physical_residual import (
    ConvergenceStatus,
    EnergyGradientResidual,
    PhysicalResidualRecord,
    PhysicalResidualVector,
    RotationalDriftResidual,
    SCFConvergenceResidual,
    STRAIN_WARNING_THRESHOLD_AU,
)
from cochem_ml.telemetry_record import (
    GENESIS_HASH,
    TelemetryRecord,
    TimestampWindow,
)
from cochem_ml.token_entropy import (
    EpistemicUncertaintyVector,
    PromptResponseDistribution,
    TokenEntropyEvaluationResult,
    TokenEntropyRecord,
    TokenLogprobRecord,
    TokenVelocityRecord,
)
from cochem_ml.state_vectorizer import (
    ASTDiffVector,
    ExecutionTelemetryVector,
    MultimodalStateVector,
    StateVectorRecord,
    TaskVector,
)
from cochem_ml.feature_standardizer import (
    RollingWindowStats,
    StandardizedVectorRecord,
    StandardizerConfig,
    StandardizerMode,
)
from cochem_ml.tensor_cache import (
    PaginatedSlice,
    TensorCacheConfig,
    TensorCacheMetrics,
    TensorRecordMetadata,
)
from cochem_ml.hdf5_preallocation import (
    ChunkGeometrySpec,
    ChunkSizingPolicy,
    DatasetPreallocationSpec,
    FragmentationMetrics,
    PreallocatedStreamerConfig,
    SlabGrowthPolicy,
    StreamedBatchReceipt,
)
from cochem_ml.dag_registry import (
    DAGEdgeRecord,
    DAGNodeRecord,
    DAGNodeType,
    DAGRelationType,
    DAGVisualizerState,
    NodeExecutionStatus,
    RollbackResult,
    VisualizerEdgeLayout,
    VisualizerNodeLayout,
)
from cochem_ml.ram_guardrail import (
    ProcessMemorySnapshot,
    RAMGuardrailConfig,
    RAMGuardrailMetrics,
    RAMGuardrailStage,
    RAMTelemetryRecord,
)






class TelemetryRecordSchema(BaseModel):
    """Pydantic v2 schema validating TelemetryRecord payloads with extra='forbid'.

    Preserves all cryptographic chain identifiers, sequence indices, execution
    metrics, and AST metrics without data loss.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str = Field(..., min_length=1, description="Tool or subsystem identifier")
    command_string: str = Field(..., description="Executed command line or payload string")
    pid: int = Field(..., ge=0, description="Genuine operating system process identifier")
    execution_latency: float = Field(..., ge=0.0, description="Physical execution latency in seconds")
    execution_latency_ms: Optional[float] = Field(default=None, ge=0.0, description="Execution latency in milliseconds")
    memory_footprint: int = Field(..., ge=0, description="Memory consumption in RSS bytes")
    memory_footprint_mb: Optional[float] = Field(default=None, ge=0.0, description="Memory consumption in megabytes")
    exit_code: int = Field(..., description="Subprocess termination code (0 for success)")
    start_timestamp: str = Field(..., description="ISO 8601 UTC start timestamp")
    end_timestamp: str = Field(..., description="ISO 8601 UTC completion timestamp")
    timestamps: Optional[Union[Dict[str, Any], TimestampWindow]] = Field(default=None, description="Timestamp window mapping")
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Cryptographic unique record identifier")
    prev_hash: str = Field(default=GENESIS_HASH, description="SHA-256 hash of preceding telemetry record")
    record_hash: str = Field(default="", description="Cryptographic SHA-256 digest of record contents")
    ast_diff_length: int = Field(default=0, ge=0, description="AST diff or code delta length")
    stdout_tail: str = Field(default="", description="Tail-truncated stdout output")
    stderr_tail: str = Field(default="", description="Tail-truncated stderr output")
    seq: int = Field(default=0, ge=0, description="Sequential event index")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom execution metadata")

    def to_dataclass(self) -> TelemetryRecord:
        """Convert schema instance to native immutable TelemetryRecord dataclass without data loss."""
        ts = self.timestamps
        if ts is None:
            ts = (self.start_timestamp, self.end_timestamp)

        return TelemetryRecord(
            tool_name=self.tool_name,
            command_string=self.command_string,
            pid=self.pid,
            execution_latency=self.execution_latency,
            memory_footprint=self.memory_footprint,
            exit_code=self.exit_code,
            timestamps=ts,
            start_timestamp=self.start_timestamp,
            end_timestamp=self.end_timestamp,
            record_id=self.record_id,
            prev_hash=self.prev_hash,
            record_hash=self.record_hash,
            ast_diff_length=self.ast_diff_length,
            stdout_tail=self.stdout_tail,
            stderr_tail=self.stderr_tail,
            seq=self.seq,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_dataclass(cls, record: TelemetryRecord) -> TelemetryRecordSchema:
        """Construct schema instance from native TelemetryRecord dataclass."""
        ts_dict = record.timestamps.to_dict() if hasattr(record.timestamps, "to_dict") else None
        return cls(
            tool_name=record.tool_name,
            command_string=record.command_string,
            pid=record.pid,
            execution_latency=record.execution_latency,
            execution_latency_ms=record.execution_latency_ms,
            memory_footprint=record.memory_footprint,
            memory_footprint_mb=record.memory_footprint_mb,
            exit_code=record.exit_code,
            start_timestamp=record.start_timestamp,
            end_timestamp=record.end_timestamp,
            timestamps=ts_dict,
            record_id=record.record_id,
            prev_hash=record.prev_hash,
            record_hash=record.record_hash,
            ast_diff_length=record.ast_diff_length,
            stdout_tail=record.stdout_tail,
            stderr_tail=record.stderr_tail,
            seq=record.seq,
            metadata=dict(record.metadata),
        )


class FileSystemEventSchema(BaseModel):
    """Pydantic v2 validation schema for FileSystemEventRecord (Task 1.02 & 1.15).

    Enforces strict typing, extra='forbid', and bidirectional lossless conversion
    with native FileSystemEventRecord dataclass instances.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event UUID")
    event_type: str = Field(..., description="Filesystem event type: created, modified, deleted, moved")
    src_path: str = Field(..., min_length=1, description="Normalized absolute source file path")
    dest_path: Optional[str] = Field(default=None, description="Normalized absolute destination file path for moves")
    is_directory: bool = Field(default=False, description="Whether event target is a directory")
    timestamp: str = Field(..., description="ISO 8601 UTC event timestamp")
    timestamp_epoch_ms: int = Field(default=0, ge=0, description="Timestamp in epoch milliseconds")
    file_size: int = Field(default=0, ge=0, description="File size in bytes")
    sha256_hash: Optional[str] = Field(default=None, description="SHA-256 digest of file contents")
    watch_category: str = Field(default="general", description="Dropzone or scratch watch category")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom event metadata")

    def to_record(self) -> Any:
        """Convert schema instance to native FileSystemEventRecord dataclass."""
        from cochem_ml.filesystem_listener import FileSystemEventRecord

        return FileSystemEventRecord(
            event_id=self.event_id,
            event_type=self.event_type,
            src_path=self.src_path,
            dest_path=self.dest_path,
            is_directory=self.is_directory,
            timestamp=self.timestamp,
            timestamp_epoch_ms=self.timestamp_epoch_ms,
            file_size=self.file_size,
            sha256_hash=self.sha256_hash,
            watch_category=self.watch_category,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_record(cls, record: Any) -> FileSystemEventSchema:
        """Construct schema instance from native FileSystemEventRecord dataclass."""
        return cls(
            event_id=record.event_id,
            event_type=record.event_type,
            src_path=record.src_path,
            dest_path=record.dest_path,
            is_directory=record.is_directory,
            timestamp=record.timestamp,
            timestamp_epoch_ms=record.timestamp_epoch_ms,
            file_size=record.file_size,
            sha256_hash=record.sha256_hash,
            watch_category=record.watch_category,
            metadata=dict(record.metadata),
        )


class ImportStatementSchema(BaseModel):
    """Pydantic v2 validation schema for ImportStatementRecord."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    module: str = Field(..., description="Module path or name")
    name: str = Field(..., description="Imported symbol name")
    alias: Optional[str] = Field(default=None, description="Local alias binding")
    is_from_import: bool = Field(default=False, description="Whether statement is from-import")
    level: int = Field(default=0, ge=0, description="Relative dot level")
    line_number: int = Field(default=1, ge=1, description="Line number of statement")
    is_top_level: bool = Field(default=True, description="Whether statement is at module scope")
    category: str = Field(default="unknown", description="Classification: stdlib, third_party, internal, unknown")

    def to_dataclass(self) -> ImportStatementRecord:
        """Convert schema instance to native ImportStatementRecord dataclass."""
        return ImportStatementRecord(
            module=self.module,
            name=self.name,
            alias=self.alias,
            is_from_import=self.is_from_import,
            level=self.level,
            line_number=self.line_number,
            is_top_level=self.is_top_level,
            category=self.category,
        )

    @classmethod
    def from_dataclass(cls, record: ImportStatementRecord) -> ImportStatementSchema:
        """Construct schema instance from native ImportStatementRecord dataclass."""
        return cls(
            module=record.module,
            name=record.name,
            alias=record.alias,
            is_from_import=record.is_from_import,
            level=record.level,
            line_number=record.line_number,
            is_top_level=record.is_top_level,
            category=record.category,
        )


class ImportShiftSchema(BaseModel):
    """Pydantic v2 validation schema for ImportShiftRecord."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    import_key: str = Field(..., description="Deterministic unique identifier")
    shift_type: str = Field(..., description="Shift type: added, removed, modified, retained")
    old_import: Optional[ImportStatementSchema] = Field(default=None, description="Pre-diff import record")
    new_import: Optional[ImportStatementSchema] = Field(default=None, description="Post-diff import record")
    details: str = Field(default="", description="Descriptive rationale or shift details")

    def to_dataclass(self) -> ImportShiftRecord:
        """Convert schema instance to native ImportShiftRecord dataclass."""
        return ImportShiftRecord(
            import_key=self.import_key,
            shift_type=self.shift_type,
            old_import=self.old_import.to_dataclass() if self.old_import else None,
            new_import=self.new_import.to_dataclass() if self.new_import else None,
            details=self.details,
        )

    @classmethod
    def from_dataclass(cls, record: ImportShiftRecord) -> ImportShiftSchema:
        """Construct schema instance from native ImportShiftRecord dataclass."""
        return cls(
            import_key=record.import_key,
            shift_type=record.shift_type,
            old_import=ImportStatementSchema.from_dataclass(record.old_import) if record.old_import else None,
            new_import=ImportStatementSchema.from_dataclass(record.new_import) if record.new_import else None,
            details=record.details,
        )


class ImportSummarySchema(BaseModel):
    """Pydantic v2 validation schema for ImportSummaryRecord."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_old_imports: int = Field(..., ge=0, description="Total imports prior to diff")
    total_new_imports: int = Field(..., ge=0, description="Total imports after diff")
    added_count: int = Field(..., ge=0, description="Number of newly introduced imports")
    removed_count: int = Field(..., ge=0, description="Number of deleted imports")
    modified_count: int = Field(..., ge=0, description="Number of modified imports")
    retained_count: int = Field(..., ge=0, description="Number of retained imports")
    shifts: List[ImportShiftSchema] = Field(default_factory=list, description="Collection of import shift records")
    added_modules: List[str] = Field(default_factory=list, description="Unique module paths added")
    removed_modules: List[str] = Field(default_factory=list, description="Unique module paths removed")

    def to_dataclass(self) -> ImportSummaryRecord:
        """Convert schema instance to native ImportSummaryRecord dataclass."""
        return ImportSummaryRecord(
            total_old_imports=self.total_old_imports,
            total_new_imports=self.total_new_imports,
            added_count=self.added_count,
            removed_count=self.removed_count,
            modified_count=self.modified_count,
            retained_count=self.retained_count,
            shifts=[s.to_dataclass() for s in self.shifts],
            added_modules=list(self.added_modules),
            removed_modules=list(self.removed_modules),
        )

    @classmethod
    def from_dataclass(cls, record: ImportSummaryRecord) -> ImportSummarySchema:
        """Construct schema instance from native ImportSummaryRecord dataclass."""
        return cls(
            total_old_imports=record.total_old_imports,
            total_new_imports=record.total_new_imports,
            added_count=record.added_count,
            removed_count=record.removed_count,
            modified_count=record.modified_count,
            retained_count=record.retained_count,
            shifts=[ImportShiftSchema.from_dataclass(s) for s in record.shifts],
            added_modules=list(record.added_modules),
            removed_modules=list(record.removed_modules),
        )


class FunctionComplexitySchema(BaseModel):
    """Pydantic v2 validation schema for FunctionComplexityRecord."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Function or method identifier")
    qualified_name: str = Field(..., description="Full hierarchical qualified name")
    old_complexity: Optional[int] = Field(default=None, ge=1, description="Pre-diff McCabe complexity")
    new_complexity: Optional[int] = Field(default=None, ge=1, description="Post-diff McCabe complexity")
    delta: Optional[int] = Field(default=None, description="Change in cyclomatic complexity")
    line_number: int = Field(default=1, ge=1, description="Declaration line number")
    is_high_risk: bool = Field(default=False, description="True if post-diff complexity exceeds risk threshold")

    def to_dataclass(self) -> FunctionComplexityRecord:
        """Convert schema instance to native FunctionComplexityRecord dataclass."""
        return FunctionComplexityRecord(
            name=self.name,
            qualified_name=self.qualified_name,
            old_complexity=self.old_complexity,
            new_complexity=self.new_complexity,
            delta=self.delta,
            line_number=self.line_number,
            is_high_risk=self.is_high_risk,
        )

    @classmethod
    def from_dataclass(cls, record: FunctionComplexityRecord) -> FunctionComplexitySchema:
        """Construct schema instance from native FunctionComplexityRecord dataclass."""
        return cls(
            name=record.name,
            qualified_name=record.qualified_name,
            old_complexity=record.old_complexity,
            new_complexity=record.new_complexity,
            delta=record.delta,
            line_number=record.line_number,
            is_high_risk=record.is_high_risk,
        )


class ModuleComplexitySchema(BaseModel):
    """Pydantic v2 validation schema for ModuleComplexityRecord."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    old_module_complexity: int = Field(..., ge=0, description="Overall pre-diff module complexity")
    new_module_complexity: int = Field(..., ge=0, description="Overall post-diff module complexity")
    module_complexity_delta: int = Field(..., description="Module cyclomatic complexity delta")
    functions: Dict[str, FunctionComplexitySchema] = Field(default_factory=dict, description="Per-function complexity records")
    peak_complexity_entity: Optional[str] = Field(default=None, description="Entity with highest cyclomatic complexity")
    peak_complexity_value: int = Field(default=0, ge=0, description="Highest cyclomatic complexity observed")
    high_risk_entities: List[str] = Field(default_factory=list, description="Entities exceeding complexity ceiling")

    def to_dataclass(self) -> ModuleComplexityRecord:
        """Convert schema instance to native ModuleComplexityRecord dataclass."""
        funcs = {k: v.to_dataclass() for k, v in self.functions.items()}
        return ModuleComplexityRecord(
            old_module_complexity=self.old_module_complexity,
            new_module_complexity=self.new_module_complexity,
            module_complexity_delta=self.module_complexity_delta,
            functions=funcs,
            peak_complexity_entity=self.peak_complexity_entity,
            peak_complexity_value=self.peak_complexity_value,
            high_risk_entities=list(self.high_risk_entities),
        )

    @classmethod
    def from_dataclass(cls, record: ModuleComplexityRecord) -> ModuleComplexitySchema:
        """Construct schema instance from native ModuleComplexityRecord dataclass."""
        funcs = {k: FunctionComplexitySchema.from_dataclass(v) for k, v in record.functions.items()}
        return cls(
            old_module_complexity=record.old_module_complexity,
            new_module_complexity=record.new_module_complexity,
            module_complexity_delta=record.module_complexity_delta,
            functions=funcs,
            peak_complexity_entity=record.peak_complexity_entity,
            peak_complexity_value=record.peak_complexity_value,
            high_risk_entities=list(record.high_risk_entities),
        )


class EntityModificationSchema(BaseModel):
    """Pydantic v2 validation schema for EntityModificationRecord."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_type: str = Field(..., description="Entity type: class, function, async_function")
    name: str = Field(..., description="Simple identifier name")
    qualified_name: str = Field(..., description="Full qualified identifier name")
    change_type: str = Field(..., description="Modification status: added, removed, modified, retained")
    old_line: Optional[int] = Field(default=None, ge=1, description="Line number in pre-diff source")
    new_line: Optional[int] = Field(default=None, ge=1, description="Line number in post-diff source")
    old_complexity: Optional[int] = Field(default=None, ge=1, description="Pre-diff complexity")
    new_complexity: Optional[int] = Field(default=None, ge=1, description="Post-diff complexity")
    complexity_delta: Optional[int] = Field(default=None, description="Complexity change")
    signature_changed: bool = Field(default=False, description="Whether parameter signature altered")
    docstring_changed: bool = Field(default=False, description="Whether docstring altered")
    body_changed: bool = Field(default=False, description="Whether AST body altered")
    body_node_count_delta: int = Field(default=0, description="Delta in total AST nodes in body")

    def to_dataclass(self) -> EntityModificationRecord:
        """Convert schema instance to native EntityModificationRecord dataclass."""
        return EntityModificationRecord(
            entity_type=self.entity_type,
            name=self.name,
            qualified_name=self.qualified_name,
            change_type=self.change_type,
            old_line=self.old_line,
            new_line=self.new_line,
            old_complexity=self.old_complexity,
            new_complexity=self.new_complexity,
            complexity_delta=self.complexity_delta,
            signature_changed=self.signature_changed,
            docstring_changed=self.docstring_changed,
            body_changed=self.body_changed,
            body_node_count_delta=self.body_node_count_delta,
        )

    @classmethod
    def from_dataclass(cls, record: EntityModificationRecord) -> EntityModificationSchema:
        """Construct schema instance from native EntityModificationRecord dataclass."""
        return cls(
            entity_type=record.entity_type,
            name=record.name,
            qualified_name=record.qualified_name,
            change_type=record.change_type,
            old_line=record.old_line,
            new_line=record.new_line,
            old_complexity=record.old_complexity,
            new_complexity=record.new_complexity,
            complexity_delta=record.complexity_delta,
            signature_changed=record.signature_changed,
            docstring_changed=record.docstring_changed,
            body_changed=record.body_changed,
            body_node_count_delta=record.body_node_count_delta,
        )


class TreeModificationSchema(BaseModel):
    """Pydantic v2 validation schema for TreeModificationRecord."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_nodes_old: int = Field(..., ge=0, description="Total AST node count in pre-diff source")
    total_nodes_new: int = Field(..., ge=0, description="Total AST node count in post-diff source")
    node_delta: int = Field(..., description="Net AST node count delta")
    nodes_added_by_type: Dict[str, int] = Field(default_factory=dict, description="Nodes added grouped by AST type")
    nodes_removed_by_type: Dict[str, int] = Field(default_factory=dict, description="Nodes removed grouped by AST type")
    classes_added: List[str] = Field(default_factory=list, description="Newly introduced class names")
    classes_removed: List[str] = Field(default_factory=list, description="Deleted class names")
    classes_modified: List[str] = Field(default_factory=list, description="Modified class names")
    functions_added: List[str] = Field(default_factory=list, description="Newly introduced function names")
    functions_removed: List[str] = Field(default_factory=list, description="Deleted function names")
    functions_modified: List[str] = Field(default_factory=list, description="Modified function names")
    entity_modifications: List[EntityModificationSchema] = Field(default_factory=list, description="Entity-level modification records")
    structural_hash_old: str = Field(default="", description="Pre-diff structural AST hash")
    structural_hash_new: str = Field(default="", description="Post-diff structural AST hash")

    def to_dataclass(self) -> TreeModificationRecord:
        """Convert schema instance to native TreeModificationRecord dataclass."""
        entities = [e.to_dataclass() for e in self.entity_modifications]
        return TreeModificationRecord(
            total_nodes_old=self.total_nodes_old,
            total_nodes_new=self.total_nodes_new,
            node_delta=self.node_delta,
            nodes_added_by_type=dict(self.nodes_added_by_type),
            nodes_removed_by_type=dict(self.nodes_removed_by_type),
            classes_added=list(self.classes_added),
            classes_removed=list(self.classes_removed),
            classes_modified=list(self.classes_modified),
            functions_added=list(self.functions_added),
            functions_removed=list(self.functions_removed),
            functions_modified=list(self.functions_modified),
            entity_modifications=entities,
            structural_hash_old=self.structural_hash_old,
            structural_hash_new=self.structural_hash_new,
        )

    @classmethod
    def from_dataclass(cls, record: TreeModificationRecord) -> TreeModificationSchema:
        """Construct schema instance from native TreeModificationRecord dataclass."""
        entities = [EntityModificationSchema.from_dataclass(e) for e in record.entity_modifications]
        return cls(
            total_nodes_old=record.total_nodes_old,
            total_nodes_new=record.total_nodes_new,
            node_delta=record.node_delta,
            nodes_added_by_type=dict(record.nodes_added_by_type),
            nodes_removed_by_type=dict(record.nodes_removed_by_type),
            classes_added=list(record.classes_added),
            classes_removed=list(record.classes_removed),
            classes_modified=list(record.classes_modified),
            functions_added=list(record.functions_added),
            functions_removed=list(record.functions_removed),
            functions_modified=list(record.functions_modified),
            entity_modifications=entities,
            structural_hash_old=record.structural_hash_old,
            structural_hash_new=record.structural_hash_new,
        )


class DiffASTParseSchema(BaseModel):
    """Pydantic v2 validation schema for DiffASTParseResult with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    filename: str = Field(..., description="Target file name or path")
    is_valid_python_old: bool = Field(..., description="Whether pre-diff source compiled without syntax errors")
    is_valid_python_new: bool = Field(..., description="Whether post-diff source compiled without syntax errors")
    old_sha256: str = Field(..., description="SHA-256 digest of pre-diff source")
    new_sha256: str = Field(..., description="SHA-256 digest of post-diff source")
    tree_modifications: TreeModificationSchema = Field(..., description="AST tree structural modification metrics")
    complexity_summary: ModuleComplexitySchema = Field(..., description="Cyclomatic complexity metrics and deltas")
    import_shifts: ImportSummarySchema = Field(..., description="Import statement shift metrics")
    ast_diff_length: int = Field(default=0, ge=0, description="Aggregated AST diff length metric")
    syntax_error_old: Optional[str] = Field(default=None, description="Syntax error message in pre-diff source if any")
    syntax_error_new: Optional[str] = Field(default=None, description="Syntax error message in post-diff source if any")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of parse operation")
    record_hash: str = Field(..., description="Cryptographic SHA-256 digest of record contents")

    def to_dataclass(self) -> DiffASTParseResult:
        """Convert schema instance to native DiffASTParseResult dataclass."""
        return DiffASTParseResult(
            filename=self.filename,
            is_valid_python_old=self.is_valid_python_old,
            is_valid_python_new=self.is_valid_python_new,
            old_sha256=self.old_sha256,
            new_sha256=self.new_sha256,
            tree_modifications=self.tree_modifications.to_dataclass(),
            complexity_summary=self.complexity_summary.to_dataclass(),
            import_shifts=self.import_shifts.to_dataclass(),
            ast_diff_length=self.ast_diff_length,
            syntax_error_old=self.syntax_error_old,
            syntax_error_new=self.syntax_error_new,
            timestamp=self.timestamp,
            record_hash=self.record_hash,
        )

    @classmethod
    def from_dataclass(cls, record: DiffASTParseResult) -> DiffASTParseSchema:
        """Construct schema instance from native DiffASTParseResult dataclass."""
        return cls(
            filename=record.filename,
            is_valid_python_old=record.is_valid_python_old,
            is_valid_python_new=record.is_valid_python_new,
            old_sha256=record.old_sha256,
            new_sha256=record.new_sha256,
            tree_modifications=TreeModificationSchema.from_dataclass(record.tree_modifications),
            complexity_summary=ModuleComplexitySchema.from_dataclass(record.complexity_summary),
            import_shifts=ImportSummarySchema.from_dataclass(record.import_shifts),
            ast_diff_length=record.ast_diff_length,
            syntax_error_old=record.syntax_error_old,
            syntax_error_new=record.syntax_error_new,
            timestamp=record.timestamp,
            record_hash=record.record_hash,
        )


class TokenLogprobSchema(BaseModel):
    """Pydantic v2 schema validating TokenLogprobRecord with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    token_text: str = Field(..., description="Token text representation")
    logprob: float = Field(..., description="Log probability of generated token")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp of token generation")
    inter_token_latency_ms: float = Field(default=0.0, ge=0.0, description="Inter-token generation latency in milliseconds")
    top_logprobs: Dict[str, float] = Field(default_factory=dict, description="Top-K alternative token log probabilities")
    step_index: int = Field(default=0, ge=0, description="Step sequence index in generation sequence")

    def to_dataclass(self) -> TokenLogprobRecord:
        """Convert schema to native TokenLogprobRecord dataclass."""
        return TokenLogprobRecord(
            token_text=self.token_text,
            logprob=self.logprob,
            timestamp_iso=self.timestamp_iso,
            inter_token_latency_ms=self.inter_token_latency_ms,
            top_logprobs=dict(self.top_logprobs),
            step_index=self.step_index,
        )

    @classmethod
    def from_dataclass(cls, record: TokenLogprobRecord) -> TokenLogprobSchema:
        """Construct schema from native TokenLogprobRecord dataclass."""
        return cls(
            token_text=record.token_text,
            logprob=record.logprob,
            timestamp_iso=record.timestamp_iso,
            inter_token_latency_ms=record.inter_token_latency_ms,
            top_logprobs=dict(record.top_logprobs),
            step_index=record.step_index,
        )


class TokenEntropySchema(BaseModel):
    """Pydantic v2 schema validating TokenEntropyRecord with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    shannon_entropy_nats: float = Field(..., ge=0.0, description="Shannon entropy in nats")
    shannon_entropy_bits: float = Field(..., ge=0.0, description="Shannon entropy in bits")
    normalized_entropy: float = Field(..., ge=0.0, le=1.0, description="Entropy normalized by maximum possible entropy")
    perplexity: float = Field(..., ge=1.0, description="Perplexity exponentiation of unigram entropy")
    unigram_entropy: float = Field(..., ge=0.0, description="Unigram frequency entropy in bits")
    bigram_entropy: float = Field(..., ge=0.0, description="Bigram transition entropy in bits")
    repetition_index: float = Field(..., ge=0.0, le=1.0, description="Proportion of immediate token repetitions")
    vocabulary_richness: float = Field(..., ge=0.0, le=1.0, description="Type-token ratio (unique / total tokens)")
    unique_tokens: int = Field(..., ge=0, description="Count of distinct vocabulary tokens observed")
    total_tokens: int = Field(..., ge=0, description="Total count of tokens evaluated")

    def to_dataclass(self) -> TokenEntropyRecord:
        """Convert schema to native TokenEntropyRecord dataclass."""
        return TokenEntropyRecord(
            shannon_entropy_nats=self.shannon_entropy_nats,
            shannon_entropy_bits=self.shannon_entropy_bits,
            normalized_entropy=self.normalized_entropy,
            perplexity=self.perplexity,
            unigram_entropy=self.unigram_entropy,
            bigram_entropy=self.bigram_entropy,
            repetition_index=self.repetition_index,
            vocabulary_richness=self.vocabulary_richness,
            unique_tokens=self.unique_tokens,
            total_tokens=self.total_tokens,
        )

    @classmethod
    def from_dataclass(cls, record: TokenEntropyRecord) -> TokenEntropySchema:
        """Construct schema from native TokenEntropyRecord dataclass."""
        return cls(
            shannon_entropy_nats=record.shannon_entropy_nats,
            shannon_entropy_bits=record.shannon_entropy_bits,
            normalized_entropy=record.normalized_entropy,
            perplexity=record.perplexity,
            unigram_entropy=record.unigram_entropy,
            bigram_entropy=record.bigram_entropy,
            repetition_index=record.repetition_index,
            vocabulary_richness=record.vocabulary_richness,
            unique_tokens=record.unique_tokens,
            total_tokens=record.total_tokens,
        )


class TokenVelocitySchema(BaseModel):
    """Pydantic v2 schema validating TokenVelocityRecord with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tokens_per_second: float = Field(..., ge=0.0, description="Tokens generated per second (TPS)")
    mean_inter_token_latency_ms: float = Field(..., ge=0.0, description="Mean inter-token latency in milliseconds")
    std_inter_token_latency_ms: float = Field(..., ge=0.0, description="Standard deviation of inter-token latency")
    min_inter_token_latency_ms: float = Field(..., ge=0.0, description="Minimum inter-token latency in milliseconds")
    max_inter_token_latency_ms: float = Field(..., ge=0.0, description="Maximum inter-token latency in milliseconds")
    jitter_ms: float = Field(..., ge=0.0, description="Mean absolute inter-token latency jitter in milliseconds")
    total_duration_ms: float = Field(..., ge=0.0, description="Total generation duration in milliseconds")
    total_tokens_evaluated: int = Field(..., ge=0, description="Total number of tokens included in velocity calculation")
    stall_count: int = Field(..., ge=0, description="Count of generation pauses exceeding stall threshold")
    instantaneous_velocities: List[float] = Field(default_factory=list, description="Rolling window velocity series")

    def to_dataclass(self) -> TokenVelocityRecord:
        """Convert schema to native TokenVelocityRecord dataclass."""
        return TokenVelocityRecord(
            tokens_per_second=self.tokens_per_second,
            mean_inter_token_latency_ms=self.mean_inter_token_latency_ms,
            std_inter_token_latency_ms=self.std_inter_token_latency_ms,
            min_inter_token_latency_ms=self.min_inter_token_latency_ms,
            max_inter_token_latency_ms=self.max_inter_token_latency_ms,
            jitter_ms=self.jitter_ms,
            total_duration_ms=self.total_duration_ms,
            total_tokens_evaluated=self.total_tokens_evaluated,
            stall_count=self.stall_count,
            instantaneous_velocities=list(self.instantaneous_velocities),
        )

    @classmethod
    def from_dataclass(cls, record: TokenVelocityRecord) -> TokenVelocitySchema:
        """Construct schema from native TokenVelocityRecord dataclass."""
        return cls(
            tokens_per_second=record.tokens_per_second,
            mean_inter_token_latency_ms=record.mean_inter_token_latency_ms,
            std_inter_token_latency_ms=record.std_inter_token_latency_ms,
            min_inter_token_latency_ms=record.min_inter_token_latency_ms,
            max_inter_token_latency_ms=record.max_inter_token_latency_ms,
            jitter_ms=record.jitter_ms,
            total_duration_ms=record.total_duration_ms,
            total_tokens_evaluated=record.total_tokens_evaluated,
            stall_count=record.stall_count,
            instantaneous_velocities=list(record.instantaneous_velocities),
        )


class PromptResponseDistributionSchema(BaseModel):
    """Pydantic v2 schema validating PromptResponseDistribution with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_token_count: int = Field(..., ge=0, description="Number of tokens in prompt")
    response_token_count: int = Field(..., ge=0, description="Number of tokens in response")
    kl_divergence: float = Field(..., description="Kullback-Leibler divergence from response to prompt")
    js_divergence: float = Field(..., ge=0.0, le=1.0, description="Jensen-Shannon divergence between prompt and response")
    cross_entropy: float = Field(..., description="Cross-entropy between prompt and response distributions")
    vocabulary_overlap_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of shared unique vocabulary")
    prompt_entropy_bits: float = Field(..., ge=0.0, description="Prompt unigram entropy in bits")
    response_entropy_bits: float = Field(..., ge=0.0, description="Response unigram entropy in bits")
    topical_drift_score: float = Field(..., ge=0.0, le=1.0, description="Composite topical drift indicator")

    def to_dataclass(self) -> PromptResponseDistribution:
        """Convert schema to native PromptResponseDistribution dataclass."""
        return PromptResponseDistribution(
            prompt_token_count=self.prompt_token_count,
            response_token_count=self.response_token_count,
            kl_divergence=self.kl_divergence,
            js_divergence=self.js_divergence,
            cross_entropy=self.cross_entropy,
            vocabulary_overlap_ratio=self.vocabulary_overlap_ratio,
            prompt_entropy_bits=self.prompt_entropy_bits,
            response_entropy_bits=self.response_entropy_bits,
            topical_drift_score=self.topical_drift_score,
        )

    @classmethod
    def from_dataclass(cls, record: PromptResponseDistribution) -> PromptResponseDistributionSchema:
        """Construct schema from native PromptResponseDistribution dataclass."""
        return cls(
            prompt_token_count=record.prompt_token_count,
            response_token_count=record.response_token_count,
            kl_divergence=record.kl_divergence,
            js_divergence=record.js_divergence,
            cross_entropy=record.cross_entropy,
            vocabulary_overlap_ratio=record.vocabulary_overlap_ratio,
            prompt_entropy_bits=record.prompt_entropy_bits,
            response_entropy_bits=record.response_entropy_bits,
            topical_drift_score=record.topical_drift_score,
        )


class EpistemicUncertaintyVectorSchema(BaseModel):
    """Pydantic v2 schema validating 16-dimensional EpistemicUncertaintyVector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    values: List[float] = Field(..., min_length=16, max_length=16, description="16-dimensional uncertainty tensor")

    def to_dataclass(self) -> EpistemicUncertaintyVector:
        """Convert schema to native EpistemicUncertaintyVector dataclass."""
        return EpistemicUncertaintyVector(values=tuple(self.values))

    @classmethod
    def from_dataclass(cls, record: EpistemicUncertaintyVector) -> EpistemicUncertaintyVectorSchema:
        """Construct schema from native EpistemicUncertaintyVector dataclass."""
        return cls(values=list(record.values))


class TokenEntropyEvaluationSchema(BaseModel):
    """Pydantic v2 schema validating complete TokenEntropyEvaluationResult with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entropy: TokenEntropySchema = Field(..., description="Entropy metrics")
    velocity: TokenVelocitySchema = Field(..., description="Velocity and latency metrics")
    distribution: PromptResponseDistributionSchema = Field(..., description="Prompt-response comparative distribution")
    epistemic_vector: EpistemicUncertaintyVectorSchema = Field(..., description="16-dimensional epistemic tensor")
    evaluation_id: str = Field(..., description="Unique evaluation identifier")
    prev_hash: str = Field(..., description="Cryptographic SHA-256 hash of previous record")
    record_hash: str = Field(..., description="Cryptographic SHA-256 digest of record contents")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp of evaluation")
    tokens_evaluated: int = Field(..., ge=0, description="Total tokens evaluated")
    anomaly_detected: bool = Field(..., description="Whether generation anomaly was flagged")
    anomaly_reason: Optional[str] = Field(default=None, description="Diagnostic rationale if anomaly flagged")

    def to_dataclass(self) -> TokenEntropyEvaluationResult:
        """Convert schema to native TokenEntropyEvaluationResult dataclass."""
        return TokenEntropyEvaluationResult(
            entropy=self.entropy.to_dataclass(),
            velocity=self.velocity.to_dataclass(),
            distribution=self.distribution.to_dataclass(),
            epistemic_vector=self.epistemic_vector.to_dataclass(),
            evaluation_id=self.evaluation_id,
            prev_hash=self.prev_hash,
            record_hash=self.record_hash,
            timestamp_iso=self.timestamp_iso,
            tokens_evaluated=self.tokens_evaluated,
            anomaly_detected=self.anomaly_detected,
            anomaly_reason=self.anomaly_reason,
        )

    @classmethod
    def from_dataclass(cls, record: TokenEntropyEvaluationResult) -> TokenEntropyEvaluationSchema:
        """Construct schema from native TokenEntropyEvaluationResult dataclass."""
        return cls(
            entropy=TokenEntropySchema.from_dataclass(record.entropy),
            velocity=TokenVelocitySchema.from_dataclass(record.velocity),
            distribution=PromptResponseDistributionSchema.from_dataclass(record.distribution),
            epistemic_vector=EpistemicUncertaintyVectorSchema.from_dataclass(record.epistemic_vector),
            evaluation_id=record.evaluation_id,
            prev_hash=record.prev_hash,
            record_hash=record.record_hash,
            timestamp_iso=record.timestamp_iso,
            tokens_evaluated=record.tokens_evaluated,
            anomaly_detected=record.anomaly_detected,
            anomaly_reason=record.anomaly_reason,
        )


class EnergyGradientResidualSchema(BaseModel):
    """Pydantic v2 schema validating EnergyGradientResidual payloads with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_gradient_au: float = Field(..., ge=0.0, description="Maximum force/gradient component in atomic units")
    rms_gradient_au: float = Field(..., ge=0.0, description="Root-mean-square gradient in atomic units")
    energy_delta_hartree: float = Field(..., ge=0.0, description="Absolute energy difference |E_k - E_{k-1}| in Hartree")
    max_displacement_bohr: float = Field(..., ge=0.0, description="Maximum atomic displacement in bohr")
    rms_displacement_bohr: float = Field(..., ge=0.0, description="Root-mean-square atomic displacement in bohr")
    has_geometric_strain: bool = Field(..., description="Method Matrix §10.2 geometric strain caveat active")
    quintuple_converged: bool = Field(..., description="Method Matrix §4.4 stationary quintuple convergence status")
    optimization_cycle: int = Field(default=1, ge=1, description="Optimization iteration step")
    total_energy_hartree: Optional[float] = Field(default=None, description="Total electronic energy in Hartree")
    strain_threshold_au: float = Field(default=STRAIN_WARNING_THRESHOLD_AU, ge=0.0, description="Strain threshold")

    def to_dataclass(self) -> EnergyGradientResidual:
        """Convert schema to native EnergyGradientResidual dataclass."""
        return EnergyGradientResidual(
            max_gradient_au=self.max_gradient_au,
            rms_gradient_au=self.rms_gradient_au,
            energy_delta_hartree=self.energy_delta_hartree,
            max_displacement_bohr=self.max_displacement_bohr,
            rms_displacement_bohr=self.rms_displacement_bohr,
            has_geometric_strain=self.has_geometric_strain,
            quintuple_converged=self.quintuple_converged,
            optimization_cycle=self.optimization_cycle,
            total_energy_hartree=self.total_energy_hartree,
            strain_threshold_au=self.strain_threshold_au,
        )

    @classmethod
    def from_dataclass(cls, record: EnergyGradientResidual) -> EnergyGradientResidualSchema:
        """Construct schema from native EnergyGradientResidual dataclass."""
        return cls(
            max_gradient_au=record.max_gradient_au,
            rms_gradient_au=record.rms_gradient_au,
            energy_delta_hartree=record.energy_delta_hartree,
            max_displacement_bohr=record.max_displacement_bohr,
            rms_displacement_bohr=record.rms_displacement_bohr,
            has_geometric_strain=record.has_geometric_strain,
            quintuple_converged=record.quintuple_converged,
            optimization_cycle=record.optimization_cycle,
            total_energy_hartree=record.total_energy_hartree,
            strain_threshold_au=record.strain_threshold_au,
        )


class RotationalDriftResidualSchema(BaseModel):
    """Pydantic v2 schema validating RotationalDriftResidual payloads with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rotational_constants_mhz: List[float] = Field(..., min_length=3, max_length=3, description="Principal rotational constants (A, B, C) in MHz")
    principal_moments_u_angstrom_sq: List[float] = Field(..., min_length=3, max_length=3, description="Principal moments of inertia in u * Angstrom^2")
    ray_asymmetry_kappa: float = Field(..., ge=-1.0, le=1.0, description="Ray's asymmetry parameter kappa in [-1, +1]")
    inertial_defect_u_angstrom_sq: float = Field(..., description="Inertial defect Delta = I_C - I_A - I_B")
    center_of_mass_drift_au: float = Field(..., ge=0.0, description="Center of mass translation drift in atomic units")
    eckart_torque_residual_au: float = Field(..., ge=0.0, description="Rotational Eckart Coriolis torque residual norm in atomic units")
    relative_drift_a: float = Field(default=0.0, ge=0.0, description="Relative drift for rotational constant A")
    relative_drift_b: float = Field(default=0.0, ge=0.0, description="Relative drift for rotational constant B")
    relative_drift_c: float = Field(default=0.0, ge=0.0, description="Relative drift for rotational constant C")
    max_relative_drift: float = Field(default=0.0, ge=0.0, description="Maximum relative drift across all three rotational constants")
    conformer_drift_exceeded: bool = Field(default=False, description="Whether conformer rotational constant drift exceeded tolerance")
    rotor_classification: str = Field(default="asymmetric_top", description="Authoritative rotor top classification")

    def to_dataclass(self) -> RotationalDriftResidual:
        """Convert schema to native RotationalDriftResidual dataclass."""
        return RotationalDriftResidual(
            rotational_constants_mhz=(
                self.rotational_constants_mhz[0],
                self.rotational_constants_mhz[1],
                self.rotational_constants_mhz[2],
            ),
            principal_moments_u_angstrom_sq=(
                self.principal_moments_u_angstrom_sq[0],
                self.principal_moments_u_angstrom_sq[1],
                self.principal_moments_u_angstrom_sq[2],
            ),
            ray_asymmetry_kappa=self.ray_asymmetry_kappa,
            inertial_defect_u_angstrom_sq=self.inertial_defect_u_angstrom_sq,
            center_of_mass_drift_au=self.center_of_mass_drift_au,
            eckart_torque_residual_au=self.eckart_torque_residual_au,
            relative_drift_a=self.relative_drift_a,
            relative_drift_b=self.relative_drift_b,
            relative_drift_c=self.relative_drift_c,
            max_relative_drift=self.max_relative_drift,
            conformer_drift_exceeded=self.conformer_drift_exceeded,
            rotor_classification=self.rotor_classification,
        )

    @classmethod
    def from_dataclass(cls, record: RotationalDriftResidual) -> RotationalDriftResidualSchema:
        """Construct schema from native RotationalDriftResidual dataclass."""
        return cls(
            rotational_constants_mhz=list(record.rotational_constants_mhz),
            principal_moments_u_angstrom_sq=list(record.principal_moments_u_angstrom_sq),
            ray_asymmetry_kappa=record.ray_asymmetry_kappa,
            inertial_defect_u_angstrom_sq=record.inertial_defect_u_angstrom_sq,
            center_of_mass_drift_au=record.center_of_mass_drift_au,
            eckart_torque_residual_au=record.eckart_torque_residual_au,
            relative_drift_a=record.relative_drift_a,
            relative_drift_b=record.relative_drift_b,
            relative_drift_c=record.relative_drift_c,
            max_relative_drift=record.max_relative_drift,
            conformer_drift_exceeded=record.conformer_drift_exceeded,
            rotor_classification=record.rotor_classification,
        )


class SCFConvergenceResidualSchema(BaseModel):
    """Pydantic v2 schema validating SCFConvergenceResidual payloads with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scf_energy_delta_hartree: float = Field(..., ge=0.0, description="Absolute SCF energy step difference |Delta E| in Hartree")
    density_matrix_delta_max: float = Field(..., ge=0.0, description="Maximum change in density matrix elements")
    density_matrix_delta_rms: float = Field(..., ge=0.0, description="Root-mean-square change in density matrix")
    orbital_gradient_max: float = Field(..., ge=0.0, description="Maximum orbital gradient / Fock commutator norm")
    scf_iterations: int = Field(..., ge=1, description="Total SCF iterations executed")
    max_scf_iterations: int = Field(..., ge=1, description="Maximum allowed SCF iterations")
    spin_s2_expectation: float = Field(..., ge=0.0, description="Expectation value <S^2>")
    spin_s2_ideal: float = Field(..., ge=0.0, description="Ideal spin eigenvalue S*(S+1)")
    spin_contamination_delta: float = Field(..., ge=0.0, description="Spin contamination difference |<S^2> - S*(S+1)|")
    spin_contamination_ratio: float = Field(..., ge=0.0, description="Relative spin contamination ratio")
    scf_converged: bool = Field(..., description="Whether SCF converged cleanly")
    status: str = Field(..., description="Categorical convergence status string")
    total_energy_hartree: Optional[float] = Field(default=None, description="Final electronic energy in Hartree")
    has_spin_contamination: bool = Field(default=False, description="Whether spin contamination exceeds threshold")

    def to_dataclass(self) -> SCFConvergenceResidual:
        """Convert schema to native SCFConvergenceResidual dataclass."""
        return SCFConvergenceResidual(
            scf_energy_delta_hartree=self.scf_energy_delta_hartree,
            density_matrix_delta_max=self.density_matrix_delta_max,
            density_matrix_delta_rms=self.density_matrix_delta_rms,
            orbital_gradient_max=self.orbital_gradient_max,
            scf_iterations=self.scf_iterations,
            max_scf_iterations=self.max_scf_iterations,
            spin_s2_expectation=self.spin_s2_expectation,
            spin_s2_ideal=self.spin_s2_ideal,
            spin_contamination_delta=self.spin_contamination_delta,
            spin_contamination_ratio=self.spin_contamination_ratio,
            scf_converged=self.scf_converged,
            status=ConvergenceStatus(self.status),
            total_energy_hartree=self.total_energy_hartree,
            has_spin_contamination=self.has_spin_contamination,
        )

    @classmethod
    def from_dataclass(cls, record: SCFConvergenceResidual) -> SCFConvergenceResidualSchema:
        """Construct schema from native SCFConvergenceResidual dataclass."""
        return cls(
            scf_energy_delta_hartree=record.scf_energy_delta_hartree,
            density_matrix_delta_max=record.density_matrix_delta_max,
            density_matrix_delta_rms=record.density_matrix_delta_rms,
            orbital_gradient_max=record.orbital_gradient_max,
            scf_iterations=record.scf_iterations,
            max_scf_iterations=record.max_scf_iterations,
            spin_s2_expectation=record.spin_s2_expectation,
            spin_s2_ideal=record.spin_s2_ideal,
            spin_contamination_delta=record.spin_contamination_delta,
            spin_contamination_ratio=record.spin_contamination_ratio,
            scf_converged=record.scf_converged,
            status=record.status.value,
            total_energy_hartree=record.total_energy_hartree,
            has_spin_contamination=record.has_spin_contamination,
        )


class PhysicalResidualVectorSchema(BaseModel):
    """Pydantic v2 schema validating 16-dimensional PhysicalResidualVector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    values: List[float] = Field(..., min_length=16, max_length=16, description="16-dimensional physical residual state vector v_res")

    def to_dataclass(self) -> PhysicalResidualVector:
        """Convert schema to native PhysicalResidualVector dataclass."""
        return PhysicalResidualVector(values=tuple(self.values))

    @classmethod
    def from_dataclass(cls, record: PhysicalResidualVector) -> PhysicalResidualVectorSchema:
        """Construct schema from native PhysicalResidualVector dataclass."""
        return cls(values=list(record.values))


class PhysicalResidualRecordSchema(BaseModel):
    """Pydantic v2 schema validating complete PhysicalResidualRecord with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gradient: EnergyGradientResidualSchema = Field(..., description="Energy gradient residuals")
    rotational: RotationalDriftResidualSchema = Field(..., description="Rotational constant and inertial drift residuals")
    scf: SCFConvergenceResidualSchema = Field(..., description="SCF convergence residuals")
    residual_vector: PhysicalResidualVectorSchema = Field(..., description="16-dimensional physical residual state tensor")
    record_id: str = Field(..., description="Unique record identifier")
    prev_hash: str = Field(..., description="Cryptographic SHA-256 hash of preceding record")
    record_hash: str = Field(..., description="Cryptographic SHA-256 digest of record contents")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp of record creation")
    molecule_formula: str = Field(..., description="Molecular formula or identifier")
    atom_count: int = Field(..., ge=0, description="Total number of atoms in molecular system")
    all_invariants_satisfied: bool = Field(..., description="Whether all physical invariants passed")
    diagnostic_messages: List[str] = Field(default_factory=list, description="Diagnostic and strain warning messages")

    def to_dataclass(self) -> PhysicalResidualRecord:
        """Convert schema to native PhysicalResidualRecord dataclass."""
        return PhysicalResidualRecord(
            gradient=self.gradient.to_dataclass(),
            rotational=self.rotational.to_dataclass(),
            scf=self.scf.to_dataclass(),
            residual_vector=self.residual_vector.to_dataclass(),
            record_id=self.record_id,
            prev_hash=self.prev_hash,
            record_hash=self.record_hash,
            timestamp_iso=self.timestamp_iso,
            molecule_formula=self.molecule_formula,
            atom_count=self.atom_count,
            all_invariants_satisfied=self.all_invariants_satisfied,
            diagnostic_messages=list(self.diagnostic_messages),
        )

    @classmethod
    def from_dataclass(cls, record: PhysicalResidualRecord) -> PhysicalResidualRecordSchema:
        """Construct schema from native PhysicalResidualRecord dataclass."""
        return cls(
            gradient=EnergyGradientResidualSchema.from_dataclass(record.gradient),
            rotational=RotationalDriftResidualSchema.from_dataclass(record.rotational),
            scf=SCFConvergenceResidualSchema.from_dataclass(record.scf),
            residual_vector=PhysicalResidualVectorSchema.from_dataclass(record.residual_vector),
            record_id=record.record_id,
            prev_hash=record.prev_hash,
            record_hash=record.record_hash,
            timestamp_iso=record.timestamp_iso,
            molecule_formula=record.molecule_formula,
            atom_count=record.atom_count,
            all_invariants_satisfied=record.all_invariants_satisfied,
            diagnostic_messages=list(record.diagnostic_messages),
        )


class TaskVectorSchema(BaseModel):
    """Pydantic v2 schema validating 64-dimensional TaskVector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    values: List[float] = Field(..., min_length=64, max_length=64, description="64-dimensional semantic task embedding vector v_task")

    def to_dataclass(self) -> TaskVector:
        """Convert schema to native TaskVector dataclass."""
        return TaskVector(values=tuple(self.values))

    @classmethod
    def from_dataclass(cls, record: TaskVector) -> TaskVectorSchema:
        """Construct schema from native TaskVector dataclass."""
        return cls(values=list(record.values))


class ASTDiffVectorSchema(BaseModel):
    """Pydantic v2 schema validating 128-dimensional ASTDiffVector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    values: List[float] = Field(..., min_length=128, max_length=128, description="128-dimensional AST diff structural delta vector v_ast")

    def to_dataclass(self) -> ASTDiffVector:
        """Convert schema to native ASTDiffVector dataclass."""
        return ASTDiffVector(values=tuple(self.values))

    @classmethod
    def from_dataclass(cls, record: ASTDiffVector) -> ASTDiffVectorSchema:
        """Construct schema from native ASTDiffVector dataclass."""
        return cls(values=list(record.values))


class ExecutionTelemetryVectorSchema(BaseModel):
    """Pydantic v2 schema validating 32-dimensional ExecutionTelemetryVector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    values: List[float] = Field(..., min_length=32, max_length=32, description="32-dimensional normalized execution telemetry vector v_exec")

    def to_dataclass(self) -> ExecutionTelemetryVector:
        """Convert schema to native ExecutionTelemetryVector dataclass."""
        return ExecutionTelemetryVector(values=tuple(self.values))

    @classmethod
    def from_dataclass(cls, record: ExecutionTelemetryVector) -> ExecutionTelemetryVectorSchema:
        """Construct schema from native ExecutionTelemetryVector dataclass."""
        return cls(values=list(record.values))


class MultimodalStateVectorSchema(BaseModel):
    """Pydantic v2 schema validating composite 256-dimensional MultimodalStateVector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    values: List[float] = Field(..., min_length=256, max_length=256, description="256-dimensional composite multimodal state vector s_t")

    def to_dataclass(self) -> MultimodalStateVector:
        """Convert schema to native MultimodalStateVector dataclass."""
        return MultimodalStateVector(values=tuple(self.values))

    @classmethod
    def from_dataclass(cls, record: MultimodalStateVector) -> MultimodalStateVectorSchema:
        """Construct schema from native MultimodalStateVector dataclass."""
        return cls(values=list(record.values))


class StateVectorRecordSchema(BaseModel):
    """Pydantic v2 schema validating complete StateVectorRecord with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(..., description="Unique state record identifier")
    step_index: int = Field(..., ge=0, description="Discrete interaction step index t")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp of state recording")
    task_id: str = Field(..., description="WBS task identifier")
    agent_name: str = Field(..., description="Responsible agent role name")
    state_vector: MultimodalStateVectorSchema = Field(..., description="256-dimensional composite state vector s_t")
    task_vector: TaskVectorSchema = Field(..., description="64-dimensional semantic task embedding v_task")
    ast_vector: ASTDiffVectorSchema = Field(..., description="128-dimensional structural codebase delta v_ast")
    exec_vector: ExecutionTelemetryVectorSchema = Field(..., description="32-dimensional execution telemetry v_exec")
    epistemic_vector: EpistemicUncertaintyVectorSchema = Field(..., description="16-dimensional epistemic uncertainty v_epistemic")
    residual_vector: PhysicalResidualVectorSchema = Field(..., description="16-dimensional physical residual vector v_res")
    prev_hash: str = Field(..., description="Cryptographic SHA-256 hash of preceding record in chain")
    record_hash: str = Field(..., description="Cryptographic SHA-256 digest of record contents")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary task metadata")

    def to_dataclass(self) -> StateVectorRecord:
        """Convert schema to native StateVectorRecord dataclass."""
        return StateVectorRecord(
            record_id=self.record_id,
            step_index=self.step_index,
            timestamp_iso=self.timestamp_iso,
            task_id=self.task_id,
            agent_name=self.agent_name,
            state_vector=self.state_vector.to_dataclass(),
            task_vector=self.task_vector.to_dataclass(),
            ast_vector=self.ast_vector.to_dataclass(),
            exec_vector=self.exec_vector.to_dataclass(),
            epistemic_vector=self.epistemic_vector.to_dataclass(),
            residual_vector=self.residual_vector.to_dataclass(),
            prev_hash=self.prev_hash,
            record_hash=self.record_hash,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_dataclass(cls, record: StateVectorRecord) -> StateVectorRecordSchema:
        """Construct schema from native StateVectorRecord dataclass."""
        return cls(
            record_id=record.record_id,
            step_index=record.step_index,
            timestamp_iso=record.timestamp_iso,
            task_id=record.task_id,
            agent_name=record.agent_name,
            state_vector=MultimodalStateVectorSchema.from_dataclass(record.state_vector),
            task_vector=TaskVectorSchema.from_dataclass(record.task_vector),
            ast_vector=ASTDiffVectorSchema.from_dataclass(record.ast_vector),
            exec_vector=ExecutionTelemetryVectorSchema.from_dataclass(record.exec_vector),
            epistemic_vector=EpistemicUncertaintyVectorSchema.from_dataclass(record.epistemic_vector),
            residual_vector=PhysicalResidualVectorSchema.from_dataclass(record.residual_vector),
            prev_hash=record.prev_hash,
            record_hash=record.record_hash,
            metadata=dict(record.metadata),
        )


class StandardizerConfigSchema(BaseModel):
    """Pydantic v2 schema validating StandardizerConfig with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: str = Field(..., description="Operational mode ('zscore', 'minmax', 'zscore_bounded_tanh', 'robust_iqr')")
    window_size: int = Field(..., ge=2, description="Rolling window size in discrete steps")
    feature_dim: Optional[int] = Field(default=None, ge=1, description="Expected feature vector dimensionality")
    epsilon: float = Field(..., gt=0.0, description="Numerical stability offset")
    clip_bounds: Optional[List[float]] = Field(default=None, min_length=2, max_length=2, description="Lower and upper clipping bounds")
    feature_range: List[float] = Field(..., min_length=2, max_length=2, description="Target Min-Max feature range [a, b]")
    ddof: int = Field(default=1, ge=0, description="Delta degrees of freedom for variance")
    tanh_scale: float = Field(default=1.0, gt=0.0, description="Hyperbolic tangent scaling factor")
    enforce_finite: bool = Field(default=True, description="Strictly forbid NaNs and Infs")

    def to_dataclass(self) -> StandardizerConfig:
        """Convert schema instance to StandardizerConfig dataclass."""
        cb = tuple(self.clip_bounds) if self.clip_bounds is not None else None
        return StandardizerConfig(
            mode=StandardizerMode(self.mode),
            window_size=self.window_size,
            feature_dim=self.feature_dim,
            epsilon=self.epsilon,
            clip_bounds=cb,
            feature_range=tuple(self.feature_range),
            ddof=self.ddof,
            tanh_scale=self.tanh_scale,
            enforce_finite=self.enforce_finite,
        )

    @classmethod
    def from_dataclass(cls, config: StandardizerConfig) -> StandardizerConfigSchema:
        """Construct schema from StandardizerConfig dataclass."""
        cb = list(config.clip_bounds) if config.clip_bounds is not None else None
        return cls(
            mode=config.mode.value,
            window_size=config.window_size,
            feature_dim=config.feature_dim,
            epsilon=config.epsilon,
            clip_bounds=cb,
            feature_range=list(config.feature_range),
            ddof=config.ddof,
            tanh_scale=config.tanh_scale,
            enforce_finite=config.enforce_finite,
        )


class RollingWindowStatsSchema(BaseModel):
    """Pydantic v2 schema validating RollingWindowStats with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int = Field(..., ge=0, description="Number of observations currently ingested in window")
    window_size: int = Field(..., ge=2, description="Maximum rolling window capacity")
    feature_dim: int = Field(..., ge=1, description="Feature vector dimensionality")
    mean: List[float] = Field(..., description="Running feature-wise mean")
    std: List[float] = Field(..., description="Running feature-wise standard deviation")
    min_val: List[float] = Field(..., description="Running feature-wise minimum")
    max_val: List[float] = Field(..., description="Running feature-wise maximum")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp of calculation")

    def to_dataclass(self) -> RollingWindowStats:
        """Convert schema instance to RollingWindowStats dataclass."""
        return RollingWindowStats(
            count=self.count,
            window_size=self.window_size,
            feature_dim=self.feature_dim,
            mean=tuple(self.mean),
            std=tuple(self.std),
            min_val=tuple(self.min_val),
            max_val=tuple(self.max_val),
            timestamp_iso=self.timestamp_iso,
        )

    @classmethod
    def from_dataclass(cls, stats: RollingWindowStats) -> RollingWindowStatsSchema:
        """Construct schema from RollingWindowStats dataclass."""
        return cls(
            count=stats.count,
            window_size=stats.window_size,
            feature_dim=stats.feature_dim,
            mean=list(stats.mean),
            std=list(stats.std),
            min_val=list(stats.min_val),
            max_val=list(stats.max_val),
            timestamp_iso=stats.timestamp_iso,
        )


class StandardizedVectorRecordSchema(BaseModel):
    """Pydantic v2 schema validating StandardizedVectorRecord with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(..., description="Unique deliverable record identifier")
    step_index: int = Field(..., ge=0, description="Discrete interaction step index")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp of standardization")
    standardizer_mode: str = Field(..., description="Standardizer mode applied")
    feature_dim: int = Field(..., ge=1, description="Feature vector dimensionality")
    window_size: int = Field(..., ge=2, description="Rolling window size in steps")
    raw_values: List[float] = Field(..., description="Original unstandardized feature vector")
    standardized_values: List[float] = Field(..., description="Standardized feature vector values")
    prev_hash: str = Field(..., description="Cryptographic SHA-256 predecessor hash")
    record_hash: str = Field(..., description="Cryptographic SHA-256 digest of record payload")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary execution metadata")

    def to_dataclass(self) -> StandardizedVectorRecord:
        """Convert schema instance to StandardizedVectorRecord dataclass."""
        return StandardizedVectorRecord(
            record_id=self.record_id,
            step_index=self.step_index,
            timestamp_iso=self.timestamp_iso,
            standardizer_mode=self.standardizer_mode,
            feature_dim=self.feature_dim,
            window_size=self.window_size,
            raw_values=tuple(self.raw_values),
            standardized_values=tuple(self.standardized_values),
            prev_hash=self.prev_hash,
            record_hash=self.record_hash,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_dataclass(cls, record: StandardizedVectorRecord) -> StandardizedVectorRecordSchema:
        """Construct schema from StandardizedVectorRecord dataclass."""
        return cls(
            record_id=record.record_id,
            step_index=record.step_index,
            timestamp_iso=record.timestamp_iso,
            standardizer_mode=record.standardizer_mode,
            feature_dim=record.feature_dim,
            window_size=record.window_size,
            raw_values=list(record.raw_values),
            standardized_values=list(record.standardized_values),
            prev_hash=record.prev_hash,
            record_hash=record.record_hash,
            metadata=dict(record.metadata),
        )


class TensorCacheConfigSchema(BaseModel):
    """Pydantic v2 schema validating TensorCacheConfig with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(..., description="Absolute or relative path to HDF5 cache container")
    swmr_mode: bool = Field(default=True, description="Single-Writer Multiple-Reader enablement")
    libver: str = Field(default="latest", description="HDF5 library version setting")
    chunk_size_covariance: List[int] = Field(
        default=[64, 64], description="HDF5 2D chunk dimensions for covariance matrices"
    )
    chunk_size_ast: List[int] = Field(
        default=[64, 64], description="HDF5 2D chunk dimensions for AST matrices"
    )
    chunk_size_multimodal: List[int] = Field(
        default=[64, 256], description="HDF5 2D chunk dimensions for multimodal trajectories"
    )
    compression: Optional[str] = Field(default="gzip", description="Compression filter identifier")
    compression_opts: Optional[int] = Field(default=4, ge=0, le=9, description="Compression level")
    ram_ceiling_bytes: int = Field(default=2147483648, ge=1, description="Strict RAM ceiling in bytes")
    default_batch_size: int = Field(default=32, ge=1, description="Default pagination slice size")
    max_slice_latency_ms: float = Field(
        default=50.0, gt=0.0, description="Maximum slice latency target in milliseconds"
    )

    def to_dataclass(self) -> TensorCacheConfig:
        """Convert schema instance to TensorCacheConfig dataclass."""
        return TensorCacheConfig(
            file_path=self.file_path,
            swmr_mode=self.swmr_mode,
            libver=self.libver,
            chunk_size_covariance=(
                self.chunk_size_covariance[0],
                self.chunk_size_covariance[1],
            ),
            chunk_size_ast=(self.chunk_size_ast[0], self.chunk_size_ast[1]),
            chunk_size_multimodal=(
                self.chunk_size_multimodal[0],
                self.chunk_size_multimodal[1],
            ),
            compression=self.compression,
            compression_opts=self.compression_opts,
            ram_ceiling_bytes=self.ram_ceiling_bytes,
            default_batch_size=self.default_batch_size,
            max_slice_latency_ms=self.max_slice_latency_ms,
        )

    @classmethod
    def from_dataclass(cls, config: TensorCacheConfig) -> TensorCacheConfigSchema:
        """Construct schema from TensorCacheConfig dataclass."""
        return cls(
            file_path=str(config.file_path),
            swmr_mode=config.swmr_mode,
            libver=config.libver,
            chunk_size_covariance=list(config.chunk_size_covariance),
            chunk_size_ast=list(config.chunk_size_ast),
            chunk_size_multimodal=list(config.chunk_size_multimodal),
            compression=config.compression,
            compression_opts=config.compression_opts,
            ram_ceiling_bytes=config.ram_ceiling_bytes,
            default_batch_size=config.default_batch_size,
            max_slice_latency_ms=config.max_slice_latency_ms,
        )


class TensorRecordMetadataSchema(BaseModel):
    """Pydantic v2 schema validating TensorRecordMetadata with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_path: str = Field(..., description="Canonical path of dataset within HDF5 hierarchy")
    matrix_type: str = Field(..., description="Matrix class identifier (covariance, ast, multimodal)")
    session_id: str = Field(..., description="Swarm execution session identifier")
    tensor_name: str = Field(..., description="Feature or tensor name")
    shape: List[int] = Field(..., description="Tensor dimensionality tuple")
    dtype: str = Field(..., description="NumPy datatype string")
    chunk_shape: Optional[List[int]] = Field(default=None, description="HDF5 chunk dimensions")
    provenance_tag: str = Field(..., description="Provenance classification tag ([M], [D], [E])")
    sha256_digest: str = Field(..., description="Cryptographic SHA-256 payload digest")
    prev_hash: str = Field(..., description="Cryptographic SHA-256 predecessor hash")
    block_hash: str = Field(..., description="Cryptographic SHA-256 block hash")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC creation timestamp")
    is_positive_semidefinite: Optional[bool] = Field(
        default=None, description="Positive semi-definiteness indicator"
    )
    condition_number: Optional[float] = Field(default=None, description="Matrix condition number")
    trace: Optional[float] = Field(default=None, description="Matrix trace")
    frobenius_norm: Optional[float] = Field(default=None, description="Frobenius matrix norm")
    cyclomatic_complexity: Optional[float] = Field(
        default=None, description="AST cyclomatic complexity"
    )
    node_count: Optional[int] = Field(default=None, ge=0, description="Total node count")
    edge_count: Optional[int] = Field(default=None, ge=0, description="Total edge count")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary execution metadata")

    def to_dataclass(self) -> TensorRecordMetadata:
        """Convert schema instance to TensorRecordMetadata dataclass."""
        return TensorRecordMetadata(
            dataset_path=self.dataset_path,
            matrix_type=self.matrix_type,
            session_id=self.session_id,
            tensor_name=self.tensor_name,
            shape=tuple(self.shape),
            dtype=self.dtype,
            chunk_shape=tuple(self.chunk_shape) if self.chunk_shape else None,
            provenance_tag=self.provenance_tag,
            sha256_digest=self.sha256_digest,
            prev_hash=self.prev_hash,
            block_hash=self.block_hash,
            timestamp_iso=self.timestamp_iso,
            is_positive_semidefinite=self.is_positive_semidefinite,
            condition_number=self.condition_number,
            trace=self.trace,
            frobenius_norm=self.frobenius_norm,
            cyclomatic_complexity=self.cyclomatic_complexity,
            node_count=self.node_count,
            edge_count=self.edge_count,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_dataclass(cls, rec: TensorRecordMetadata) -> TensorRecordMetadataSchema:
        """Construct schema from TensorRecordMetadata dataclass."""
        return cls(
            dataset_path=rec.dataset_path,
            matrix_type=rec.matrix_type,
            session_id=rec.session_id,
            tensor_name=rec.tensor_name,
            shape=list(rec.shape),
            dtype=rec.dtype,
            chunk_shape=list(rec.chunk_shape) if rec.chunk_shape else None,
            provenance_tag=rec.provenance_tag,
            sha256_digest=rec.sha256_digest,
            prev_hash=rec.prev_hash,
            block_hash=rec.block_hash,
            timestamp_iso=rec.timestamp_iso,
            is_positive_semidefinite=rec.is_positive_semidefinite,
            condition_number=rec.condition_number,
            trace=rec.trace,
            frobenius_norm=rec.frobenius_norm,
            cyclomatic_complexity=rec.cyclomatic_complexity,
            node_count=rec.node_count,
            edge_count=rec.edge_count,
            metadata=dict(rec.metadata),
        )


class PaginatedSliceSchema(BaseModel):
    """Pydantic v2 schema validating PaginatedSlice with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_path: str = Field(..., description="Canonical path of sliced dataset")
    slice_index: int = Field(..., ge=0, description="Sequential slice index")
    start_row: int = Field(..., ge=0, description="Start row index along axis 0")
    end_row: int = Field(..., ge=0, description="End row index along axis 0")
    total_rows: int = Field(..., ge=0, description="Total rows in dataset along axis 0")
    shape: List[int] = Field(..., description="Dimensions of sliced numpy array")
    latency_ms: float = Field(..., ge=0.0, description="Query retrieval latency in milliseconds")
    sha256_digest: str = Field(..., description="Cryptographic SHA-256 digest of slice payload")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp of pagination")

    def to_dataclass(self) -> PaginatedSlice:
        """Convert schema instance to PaginatedSlice dataclass."""
        return PaginatedSlice(
            dataset_path=self.dataset_path,
            slice_index=self.slice_index,
            start_row=self.start_row,
            end_row=self.end_row,
            total_rows=self.total_rows,
            shape=tuple(self.shape),
            latency_ms=self.latency_ms,
            sha256_digest=self.sha256_digest,
            timestamp_iso=self.timestamp_iso,
        )

    @classmethod
    def from_dataclass(cls, slice_obj: PaginatedSlice) -> PaginatedSliceSchema:
        """Construct schema from PaginatedSlice dataclass."""
        return cls(
            dataset_path=slice_obj.dataset_path,
            slice_index=slice_obj.slice_index,
            start_row=slice_obj.start_row,
            end_row=slice_obj.end_row,
            total_rows=slice_obj.total_rows,
            shape=list(slice_obj.shape),
            latency_ms=slice_obj.latency_ms,
            sha256_digest=slice_obj.sha256_digest,
            timestamp_iso=slice_obj.timestamp_iso,
        )


class TensorCacheMetricsSchema(BaseModel):
    """Pydantic v2 schema validating TensorCacheMetrics with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_datasets: int = Field(..., ge=0, description="Total datasets stored in container")
    covariance_datasets: int = Field(..., ge=0, description="Total covariance datasets")
    ast_datasets: int = Field(..., ge=0, description="Total AST datasets")
    multimodal_datasets: int = Field(..., ge=0, description="Total multimodal state datasets")
    total_bytes: int = Field(..., ge=0, description="Total uncompressed data bytes")
    active_ram_bytes: int = Field(..., ge=0, description="Process resident memory footprint in bytes")
    ram_ceiling_bytes: int = Field(..., ge=1, description="Strict RAM ceiling in bytes")
    is_swmr_active: bool = Field(..., description="Whether SWMR mode is active")
    cache_file_exists: bool = Field(..., description="Whether cache file exists on disk")
    cache_file_size_bytes: int = Field(..., ge=0, description="File size on disk in bytes")
    last_predecessor_hash: str = Field(..., description="Cryptographic predecessor hash")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp")

    def to_dataclass(self) -> TensorCacheMetrics:
        """Convert schema instance to TensorCacheMetrics dataclass."""
        return TensorCacheMetrics(
            total_datasets=self.total_datasets,
            covariance_datasets=self.covariance_datasets,
            ast_datasets=self.ast_datasets,
            multimodal_datasets=self.multimodal_datasets,
            total_bytes=self.total_bytes,
            active_ram_bytes=self.active_ram_bytes,
            ram_ceiling_bytes=self.ram_ceiling_bytes,
            is_swmr_active=self.is_swmr_active,
            cache_file_exists=self.cache_file_exists,
            cache_file_size_bytes=self.cache_file_size_bytes,
            last_predecessor_hash=self.last_predecessor_hash,
            timestamp_iso=self.timestamp_iso,
        )

    @classmethod
    def from_dataclass(cls, metrics: TensorCacheMetrics) -> TensorCacheMetricsSchema:
        """Construct schema from TensorCacheMetrics dataclass."""
        return cls(
            total_datasets=metrics.total_datasets,
            covariance_datasets=metrics.covariance_datasets,
            ast_datasets=metrics.ast_datasets,
            multimodal_datasets=metrics.multimodal_datasets,
            total_bytes=metrics.total_bytes,
            active_ram_bytes=metrics.active_ram_bytes,
            ram_ceiling_bytes=metrics.ram_ceiling_bytes,
            is_swmr_active=metrics.is_swmr_active,
            cache_file_exists=metrics.cache_file_exists,
            cache_file_size_bytes=metrics.cache_file_size_bytes,
            last_predecessor_hash=metrics.last_predecessor_hash,
            timestamp_iso=metrics.timestamp_iso,
        )


class ChunkGeometrySpecSchema(BaseModel):
    """Pydantic v2 schema validating ChunkGeometrySpec with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_shape: List[int] = Field(..., description="Chunk dimensions")
    chunk_bytes: int = Field(..., ge=1, description="Calculated chunk size in bytes")
    alignment_bytes: int = Field(..., ge=1, description="Target alignment boundary in bytes")
    is_page_aligned: bool = Field(..., description="Whether chunk size is multiple of alignment")
    policy: str = Field(..., description="Chunk sizing policy")
    target_bytes: int = Field(..., ge=1, description="Target chunk size in bytes")
    feature_dimension: int = Field(..., ge=1, description="Total elements per frame")
    itemsize: int = Field(..., ge=1, description="Bytes per element")

    def to_dataclass(self) -> ChunkGeometrySpec:
        """Convert schema to ChunkGeometrySpec dataclass."""
        return ChunkGeometrySpec(
            chunk_shape=tuple(self.chunk_shape),
            chunk_bytes=self.chunk_bytes,
            alignment_bytes=self.alignment_bytes,
            is_page_aligned=self.is_page_aligned,
            policy=self.policy,
            target_bytes=self.target_bytes,
            feature_dimension=self.feature_dimension,
            itemsize=self.itemsize,
        )

    @classmethod
    def from_dataclass(cls, spec: ChunkGeometrySpec) -> ChunkGeometrySpecSchema:
        """Construct schema from ChunkGeometrySpec dataclass."""
        return cls(
            chunk_shape=list(spec.chunk_shape),
            chunk_bytes=spec.chunk_bytes,
            alignment_bytes=spec.alignment_bytes,
            is_page_aligned=spec.is_page_aligned,
            policy=spec.policy,
            target_bytes=spec.target_bytes,
            feature_dimension=spec.feature_dimension,
            itemsize=spec.itemsize,
        )


class DatasetPreallocationSpecSchema(BaseModel):
    """Pydantic v2 schema validating DatasetPreallocationSpec with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_name: str = Field(..., min_length=1, description="Dataset path within container")
    trailing_shape: List[int] = Field(..., description="Shape of trailing dimensions per frame")
    dtype: str = Field(default="float64", description="NumPy dtype string")
    initial_capacity: int = Field(default=1024, ge=1, description="Initial slab capacity")
    slab_stride: int = Field(default=1024, ge=1, description="Incremental slab capacity")
    chunk_shape: Optional[List[int]] = Field(default=None, description="Explicit chunk shape")
    target_chunk_bytes: int = Field(default=262144, ge=1, description="Target chunk size")
    alignment_bytes: int = Field(default=4096, ge=1, description="Filesystem alignment")
    chunk_policy: str = Field(default="PAGE_ALIGNED", description="Chunk sizing policy")
    growth_policy: str = Field(default="LINEAR_STRIDE", description="Slab growth policy")
    compression: Optional[str] = Field(default="gzip", description="Compression filter")
    compression_opts: Optional[int] = Field(default=4, ge=0, description="Compression level")
    enable_shuffle: bool = Field(default=True, description="Whether shuffle filter is enabled")
    enable_fletcher32: bool = Field(default=True, description="Whether Fletcher32 checksum is enabled")
    fill_value: float = Field(default=0.0, description="Default fill value")

    def to_dataclass(self) -> DatasetPreallocationSpec:
        """Convert schema to DatasetPreallocationSpec dataclass."""
        return DatasetPreallocationSpec(
            dataset_name=self.dataset_name,
            trailing_shape=tuple(self.trailing_shape),
            dtype=self.dtype,
            initial_capacity=self.initial_capacity,
            slab_stride=self.slab_stride,
            chunk_shape=tuple(self.chunk_shape) if self.chunk_shape is not None else None,
            target_chunk_bytes=self.target_chunk_bytes,
            alignment_bytes=self.alignment_bytes,
            chunk_policy=ChunkSizingPolicy(self.chunk_policy),
            growth_policy=SlabGrowthPolicy(self.growth_policy),
            compression=self.compression,
            compression_opts=self.compression_opts,
            enable_shuffle=self.enable_shuffle,
            enable_fletcher32=self.enable_fletcher32,
            fill_value=self.fill_value,
        )

    @classmethod
    def from_dataclass(cls, spec: DatasetPreallocationSpec) -> DatasetPreallocationSpecSchema:
        """Construct schema from DatasetPreallocationSpec dataclass."""
        return cls(
            dataset_name=spec.dataset_name,
            trailing_shape=list(spec.trailing_shape),
            dtype=spec.dtype,
            initial_capacity=spec.initial_capacity,
            slab_stride=spec.slab_stride,
            chunk_shape=list(spec.chunk_shape) if spec.chunk_shape is not None else None,
            target_chunk_bytes=spec.target_chunk_bytes,
            alignment_bytes=spec.alignment_bytes,
            chunk_policy=spec.chunk_policy.value,
            growth_policy=spec.growth_policy.value,
            compression=spec.compression,
            compression_opts=spec.compression_opts,
            enable_shuffle=spec.enable_shuffle,
            enable_fletcher32=spec.enable_fletcher32,
            fill_value=spec.fill_value,
        )


class PreallocatedStreamerConfigSchema(BaseModel):
    """Pydantic v2 schema validating PreallocatedStreamerConfig with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(..., description="Target HDF5 file path")
    swmr_mode: bool = Field(default=True, description="Whether SWMR mode is enabled")
    libver: str = Field(default="latest", description="HDF5 library version setting")
    fapl_alignment_threshold: int = Field(default=4096, ge=1, description="FAPL alignment threshold")
    fapl_alignment_interval: int = Field(default=4096, ge=1, description="FAPL alignment interval")
    rdcc_nbytes: int = Field(default=16777216, ge=1, description="RDCC cache size in bytes")
    rdcc_nslots: int = Field(default=10007, ge=1, description="RDCC hash slot count")
    rdcc_w0: float = Field(default=0.75, ge=0.0, le=1.0, description="RDCC preemption policy")
    ram_ceiling_bytes: int = Field(default=2147483648, ge=1, description="RAM ceiling in bytes")
    truncate_on_close: bool = Field(default=False, description="Whether to truncate unused tail on close")

    def to_dataclass(self) -> PreallocatedStreamerConfig:
        """Convert schema to PreallocatedStreamerConfig dataclass."""
        return PreallocatedStreamerConfig(
            file_path=self.file_path,
            swmr_mode=self.swmr_mode,
            libver=self.libver,
            fapl_alignment_threshold=self.fapl_alignment_threshold,
            fapl_alignment_interval=self.fapl_alignment_interval,
            rdcc_nbytes=self.rdcc_nbytes,
            rdcc_nslots=self.rdcc_nslots,
            rdcc_w0=self.rdcc_w0,
            ram_ceiling_bytes=self.ram_ceiling_bytes,
            truncate_on_close=self.truncate_on_close,
        )

    @classmethod
    def from_dataclass(cls, cfg: PreallocatedStreamerConfig) -> PreallocatedStreamerConfigSchema:
        """Construct schema from PreallocatedStreamerConfig dataclass."""
        return cls(
            file_path=str(cfg.file_path),
            swmr_mode=cfg.swmr_mode,
            libver=cfg.libver,
            fapl_alignment_threshold=cfg.fapl_alignment_threshold,
            fapl_alignment_interval=cfg.fapl_alignment_interval,
            rdcc_nbytes=cfg.rdcc_nbytes,
            rdcc_nslots=cfg.rdcc_nslots,
            rdcc_w0=cfg.rdcc_w0,
            ram_ceiling_bytes=cfg.ram_ceiling_bytes,
            truncate_on_close=cfg.truncate_on_close,
        )


class FragmentationMetricsSchema(BaseModel):
    """Pydantic v2 schema validating FragmentationMetrics with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_path: str = Field(..., description="Dataset path within container")
    logical_frames: int = Field(..., ge=0, description="Active valid data frames")
    allocated_frames: int = Field(..., ge=0, description="Physical allocated frame capacity")
    logical_bytes: int = Field(..., ge=0, description="Valid data bytes")
    allocated_bytes: int = Field(..., ge=0, description="Physical allocated bytes")
    chunk_shape: List[int] = Field(..., description="Chunk shape")
    chunk_count: int = Field(..., ge=0, description="Total physical chunks")
    chunk_size_bytes: int = Field(..., ge=1, description="Size of one chunk in bytes")
    fragmentation_ratio: float = Field(..., ge=0.0, le=1.0, description="Unpopulated capacity ratio")
    allocation_events: int = Field(..., ge=0, description="Count of slab resize events")
    fapl_alignment_bytes: int = Field(..., ge=1, description="Enforced FAPL alignment")
    fletcher32_enabled: bool = Field(..., description="Whether Fletcher32 is active")
    shuffle_enabled: bool = Field(..., description="Whether byte shuffle is active")
    is_swmr_active: bool = Field(..., description="Whether SWMR mode is active")
    write_latency_ms: float = Field(..., ge=0.0, description="Write latency in ms")
    predecessor_hash: str = Field(..., description="Cryptographic predecessor hash")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp")

    def to_dataclass(self) -> FragmentationMetrics:
        """Convert schema to FragmentationMetrics dataclass."""
        return FragmentationMetrics(
            dataset_path=self.dataset_path,
            logical_frames=self.logical_frames,
            allocated_frames=self.allocated_frames,
            logical_bytes=self.logical_bytes,
            allocated_bytes=self.allocated_bytes,
            chunk_shape=tuple(self.chunk_shape),
            chunk_count=self.chunk_count,
            chunk_size_bytes=self.chunk_size_bytes,
            fragmentation_ratio=self.fragmentation_ratio,
            allocation_events=self.allocation_events,
            fapl_alignment_bytes=self.fapl_alignment_bytes,
            fletcher32_enabled=self.fletcher32_enabled,
            shuffle_enabled=self.shuffle_enabled,
            is_swmr_active=self.is_swmr_active,
            write_latency_ms=self.write_latency_ms,
            predecessor_hash=self.predecessor_hash,
            timestamp_iso=self.timestamp_iso,
        )

    @classmethod
    def from_dataclass(cls, metrics: FragmentationMetrics) -> FragmentationMetricsSchema:
        """Construct schema from FragmentationMetrics dataclass."""
        return cls(
            dataset_path=metrics.dataset_path,
            logical_frames=metrics.logical_frames,
            allocated_frames=metrics.allocated_frames,
            logical_bytes=metrics.logical_bytes,
            allocated_bytes=metrics.allocated_bytes,
            chunk_shape=list(metrics.chunk_shape),
            chunk_count=metrics.chunk_count,
            chunk_size_bytes=metrics.chunk_size_bytes,
            fragmentation_ratio=metrics.fragmentation_ratio,
            allocation_events=metrics.allocation_events,
            fapl_alignment_bytes=metrics.fapl_alignment_bytes,
            fletcher32_enabled=metrics.fletcher32_enabled,
            shuffle_enabled=metrics.shuffle_enabled,
            is_swmr_active=metrics.is_swmr_active,
            write_latency_ms=metrics.write_latency_ms,
            predecessor_hash=metrics.predecessor_hash,
            timestamp_iso=metrics.timestamp_iso,
        )


class StreamedBatchReceiptSchema(BaseModel):
    """Pydantic v2 schema validating StreamedBatchReceipt with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_path: str = Field(..., description="Dataset path within container")
    batch_frames: int = Field(..., ge=1, description="Number of frames appended")
    start_logical_frame: int = Field(..., ge=0, description="Start index in logical sequence")
    end_logical_frame: int = Field(..., ge=1, description="End index in logical sequence")
    allocated_capacity: int = Field(..., ge=1, description="Total allocated capacity after write")
    latency_ms: float = Field(..., ge=0.0, description="Batch write latency in ms")
    sha256_digest: str = Field(..., description="SHA-256 digest of written batch")
    prev_hash: str = Field(..., description="Predecessor block hash")
    block_hash: str = Field(..., description="Committed block hash")
    allocation_triggered: bool = Field(..., description="Whether physical slab expansion occurred")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp")

    def to_dataclass(self) -> StreamedBatchReceipt:
        """Convert schema to StreamedBatchReceipt dataclass."""
        return StreamedBatchReceipt(
            dataset_path=self.dataset_path,
            batch_frames=self.batch_frames,
            start_logical_frame=self.start_logical_frame,
            end_logical_frame=self.end_logical_frame,
            allocated_capacity=self.allocated_capacity,
            latency_ms=self.latency_ms,
            sha256_digest=self.sha256_digest,
            prev_hash=self.prev_hash,
            block_hash=self.block_hash,
            allocation_triggered=self.allocation_triggered,
            timestamp_iso=self.timestamp_iso,
        )

    @classmethod
    def from_dataclass(cls, receipt: StreamedBatchReceipt) -> StreamedBatchReceiptSchema:
        """Construct schema from StreamedBatchReceipt dataclass."""
        return cls(
            dataset_path=receipt.dataset_path,
            batch_frames=receipt.batch_frames,
            start_logical_frame=receipt.start_logical_frame,
            end_logical_frame=receipt.end_logical_frame,
            allocated_capacity=receipt.allocated_capacity,
            latency_ms=receipt.latency_ms,
            sha256_digest=receipt.sha256_digest,
            prev_hash=receipt.prev_hash,
            block_hash=receipt.block_hash,
            allocation_triggered=receipt.allocation_triggered,
            timestamp_iso=receipt.timestamp_iso,
        )


class DAGNodeSchema(BaseModel):
    """Pydantic v2 schema validating DAGNodeRecord with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str = Field(..., description="Unique node URI or identifier")
    node_type: DAGNodeType = Field(..., description="W3C PROV-O aligned node type")
    wbs_task_id: str = Field(..., description="WBS task identifier")
    agent_role: str = Field(..., description="Agent role responsible for execution")
    status: NodeExecutionStatus = Field(..., description="Node execution status")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp")
    latency_ms: float = Field(..., ge=0.0, description="Execution latency in ms")
    parent_ids: List[str] = Field(default_factory=list, description="Causal parent node IDs")
    child_ids: List[str] = Field(default_factory=list, description="Causal child node IDs")
    state_vector_digest: Optional[str] = Field(None, description="256-D state vector digest")
    tensor_cache_ref: Optional[str] = Field(None, description="Coordinates in ml_tensor_cache.h5")
    ast_complexity_delta: Optional[float] = Field(None, description="AST cyclomatic complexity delta")
    physical_residual_norm: Optional[float] = Field(None, description="Physical residual force/torque norm")
    sha256_digest: str = Field(..., description="SHA-256 payload digest")
    predecessor_hash: str = Field(..., description="PCA-74 predecessor block hash")
    block_hash: str = Field(..., description="Committed block hash")
    depth: int = Field(0, ge=0, description="Topological depth in DAG")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Domain metadata annotations")

    def to_dataclass(self) -> DAGNodeRecord:
        """Convert schema to DAGNodeRecord dataclass."""
        return DAGNodeRecord(
            node_id=self.node_id,
            node_type=self.node_type,
            wbs_task_id=self.wbs_task_id,
            agent_role=self.agent_role,
            status=self.status,
            timestamp_iso=self.timestamp_iso,
            latency_ms=self.latency_ms,
            parent_ids=list(self.parent_ids),
            child_ids=list(self.child_ids),
            state_vector_digest=self.state_vector_digest,
            tensor_cache_ref=self.tensor_cache_ref,
            ast_complexity_delta=self.ast_complexity_delta,
            physical_residual_norm=self.physical_residual_norm,
            sha256_digest=self.sha256_digest,
            predecessor_hash=self.predecessor_hash,
            block_hash=self.block_hash,
            depth=self.depth,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_dataclass(cls, record: DAGNodeRecord) -> DAGNodeSchema:
        """Construct schema from DAGNodeRecord dataclass."""
        return cls(
            node_id=record.node_id,
            node_type=record.node_type,
            wbs_task_id=record.wbs_task_id,
            agent_role=record.agent_role,
            status=record.status,
            timestamp_iso=record.timestamp_iso,
            latency_ms=record.latency_ms,
            parent_ids=list(record.parent_ids),
            child_ids=list(record.child_ids),
            state_vector_digest=record.state_vector_digest,
            tensor_cache_ref=record.tensor_cache_ref,
            ast_complexity_delta=record.ast_complexity_delta,
            physical_residual_norm=record.physical_residual_norm,
            sha256_digest=record.sha256_digest,
            predecessor_hash=record.predecessor_hash,
            block_hash=record.block_hash,
            depth=record.depth,
            metadata=dict(record.metadata),
        )


class DAGEdgeSchema(BaseModel):
    """Pydantic v2 schema validating DAGEdgeRecord with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str = Field(..., description="Unique edge identifier")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relation: DAGRelationType = Field(..., description="W3C PROV-O relationship type")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp")
    edge_weight: float = Field(1.0, gt=0.0, description="Edge weight or latency metric")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Domain metadata annotations")

    def to_dataclass(self) -> DAGEdgeRecord:
        """Convert schema to DAGEdgeRecord dataclass."""
        return DAGEdgeRecord(
            edge_id=self.edge_id,
            source_id=self.source_id,
            target_id=self.target_id,
            relation=self.relation,
            timestamp_iso=self.timestamp_iso,
            edge_weight=self.edge_weight,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_dataclass(cls, record: DAGEdgeRecord) -> DAGEdgeSchema:
        """Construct schema from DAGEdgeRecord dataclass."""
        return cls(
            edge_id=record.edge_id,
            source_id=record.source_id,
            target_id=record.target_id,
            relation=record.relation,
            timestamp_iso=record.timestamp_iso,
            edge_weight=record.edge_weight,
            metadata=dict(record.metadata),
        )


class RollbackResultSchema(BaseModel):
    """Pydantic v2 schema validating RollbackResult telemetry receipts with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_node_id: str = Field(..., description="Target rollback node ID")
    rolled_back_node_ids: List[str] = Field(..., description="List of pruned/rolled-back descendant IDs")
    rollback_checkpoint_id: str = Field(..., description="Created rollback audit node ID")
    reconstituted_head_hash: str = Field(..., description="New committed head block hash")
    latency_ms: float = Field(..., ge=0.0, description="Rollback execution latency in ms")
    timestamp_iso: str = Field(..., description="ISO 8601 UTC timestamp")

    def to_dataclass(self) -> RollbackResult:
        """Convert schema to RollbackResult dataclass."""
        return RollbackResult(
            target_node_id=self.target_node_id,
            rolled_back_node_ids=list(self.rolled_back_node_ids),
            rollback_checkpoint_id=self.rollback_checkpoint_id,
            reconstituted_head_hash=self.reconstituted_head_hash,
            latency_ms=self.latency_ms,
            timestamp_iso=self.timestamp_iso,
        )

    @classmethod
    def from_dataclass(cls, result: RollbackResult) -> RollbackResultSchema:
        """Construct schema from RollbackResult dataclass."""
        return cls(
            target_node_id=result.target_node_id,
            rolled_back_node_ids=list(result.rolled_back_node_ids),
            rollback_checkpoint_id=result.rollback_checkpoint_id,
            reconstituted_head_hash=result.reconstituted_head_hash,
            latency_ms=result.latency_ms,
            timestamp_iso=result.timestamp_iso,
        )


class VisualizerNodeLayoutSchema(BaseModel):
    """Pydantic v2 schema validating VisualizerNodeLayout with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str = Field(..., description="Node identifier")
    label: str = Field(..., description="Display label for UI")
    level: int = Field(..., ge=0, description="Topological vertical tier")
    column: int = Field(..., ge=0, description="Horizontal layout column")
    status: str = Field(..., description="Status string")
    agent_role: str = Field(..., description="Agent role string")
    color_hex: str = Field(..., description="Hex color code for rendering")
    latency_ms: float = Field(..., ge=0.0, description="Execution latency in ms")
    wbs_task_id: str = Field(..., description="WBS task ID")

    def to_dataclass(self) -> VisualizerNodeLayout:
        """Convert schema to VisualizerNodeLayout dataclass."""
        return VisualizerNodeLayout(
            node_id=self.node_id,
            label=self.label,
            level=self.level,
            column=self.column,
            status=self.status,
            agent_role=self.agent_role,
            color_hex=self.color_hex,
            latency_ms=self.latency_ms,
            wbs_task_id=self.wbs_task_id,
        )

    @classmethod
    def from_dataclass(cls, layout: VisualizerNodeLayout) -> VisualizerNodeLayoutSchema:
        """Construct schema from VisualizerNodeLayout dataclass."""
        return cls(
            node_id=layout.node_id,
            label=layout.label,
            level=layout.level,
            column=layout.column,
            status=layout.status,
            agent_role=layout.agent_role,
            color_hex=layout.color_hex,
            latency_ms=layout.latency_ms,
            wbs_task_id=layout.wbs_task_id,
        )


class VisualizerEdgeLayoutSchema(BaseModel):
    """Pydantic v2 schema validating VisualizerEdgeLayout with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str = Field(..., description="Edge identifier")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relation: str = Field(..., description="Relation label")

    def to_dataclass(self) -> VisualizerEdgeLayout:
        """Convert schema to VisualizerEdgeLayout dataclass."""
        return VisualizerEdgeLayout(
            edge_id=self.edge_id,
            source_id=self.source_id,
            target_id=self.target_id,
            relation=self.relation,
        )

    @classmethod
    def from_dataclass(cls, layout: VisualizerEdgeLayout) -> VisualizerEdgeLayoutSchema:
        """Construct schema from VisualizerEdgeLayout dataclass."""
        return cls(
            edge_id=layout.edge_id,
            source_id=layout.source_id,
            target_id=layout.target_id,
            relation=layout.relation,
        )


class DAGVisualizerStateSchema(BaseModel):
    """Pydantic v2 schema validating DAGVisualizerState with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nodes: List[VisualizerNodeLayoutSchema] = Field(..., description="Node layout geometry list")
    edges: List[VisualizerEdgeLayoutSchema] = Field(..., description="Edge layout geometry list")
    max_depth: int = Field(..., ge=0, description="Maximum tree depth")
    max_breadth: int = Field(..., ge=0, description="Maximum width across levels")
    mermaid_markup: str = Field(..., description="Renderable Mermaid flowchart markup")
    cytoscape_elements: List[Dict[str, Any]] = Field(..., description="Cytoscape graph JSON elements")
    total_nodes: int = Field(..., ge=0, description="Total node count")
    total_edges: int = Field(..., ge=0, description="Total edge count")

    def to_dataclass(self) -> DAGVisualizerState:
        """Convert schema to DAGVisualizerState dataclass."""
        return DAGVisualizerState(
            nodes=[n.to_dataclass() for n in self.nodes],
            edges=[e.to_dataclass() for e in self.edges],
            max_depth=self.max_depth,
            max_breadth=self.max_breadth,
            mermaid_markup=self.mermaid_markup,
            cytoscape_elements=list(self.cytoscape_elements),
            total_nodes=self.total_nodes,
            total_edges=self.total_edges,
        )

    @classmethod
    def from_dataclass(cls, state: DAGVisualizerState) -> DAGVisualizerStateSchema:
        """Construct schema from DAGVisualizerState dataclass."""
        return cls(
            nodes=[VisualizerNodeLayoutSchema.from_dataclass(n) for n in state.nodes],
            edges=[VisualizerEdgeLayoutSchema.from_dataclass(e) for e in state.edges],
            max_depth=state.max_depth,
            max_breadth=state.max_breadth,
            mermaid_markup=state.mermaid_markup,
            cytoscape_elements=list(state.cytoscape_elements),
            total_nodes=state.total_nodes,
            total_edges=state.total_edges,
        )


class JSONLDRegistryPayloadSchema(BaseModel):
    """Pydantic v2 schema validating complete cochem_ml_dag_registry.json documents."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    context: Dict[str, str] = Field(..., alias="@context", description="Semantic JSON-LD context")
    id_uri: str = Field(..., alias="@id", description="Registry resource URI")
    type_list: List[str] = Field(..., alias="@type", description="W3C PROV-O bundle types")
    registry_version: str = Field(..., alias="registryVersion", description="Schema version")
    genesis_hash: str = Field(..., alias="genesisHash", description="Root genesis block hash")
    latest_block_hash: str = Field(..., alias="latestBlockHash", description="Latest committed block hash")
    total_nodes: int = Field(..., alias="totalNodes", ge=0, description="Total node count")
    total_edges: int = Field(..., alias="totalEdges", ge=0, description="Total edge count")
    created_at: str = Field(..., alias="createdAt", description="Creation ISO timestamp")
    updated_at: str = Field(..., alias="updatedAt", description="Last update ISO timestamp")
    graph: List[Dict[str, Any]] = Field(..., alias="@graph", description="Node and edge entity list")


class ProcessMemorySnapshotSchema(BaseModel):
    """Pydantic v2 schema validating ProcessMemorySnapshot with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pid: int = Field(..., ge=0, description="Operating system process identifier")
    name: str = Field(..., description="Process binary name")
    rss_bytes: int = Field(..., ge=0, description="Resident set size in bytes")
    vms_bytes: int = Field(..., ge=0, description="Virtual memory size in bytes")
    num_threads: int = Field(..., ge=1, description="Active thread count")
    cpu_percent: float = Field(..., ge=0.0, description="Observed CPU utilization percentage")
    timestamp_sec: float = Field(..., ge=0.0, description="Epoch timestamp of snapshot")

    def to_dataclass(self) -> ProcessMemorySnapshot:
        """Convert schema to ProcessMemorySnapshot dataclass."""
        return ProcessMemorySnapshot(
            pid=self.pid,
            name=self.name,
            rss_bytes=self.rss_bytes,
            vms_bytes=self.vms_bytes,
            num_threads=self.num_threads,
            cpu_percent=self.cpu_percent,
            timestamp_sec=self.timestamp_sec,
        )

    @classmethod
    def from_dataclass(cls, snapshot: ProcessMemorySnapshot) -> ProcessMemorySnapshotSchema:
        """Construct schema from ProcessMemorySnapshot dataclass."""
        return cls(
            pid=snapshot.pid,
            name=snapshot.name,
            rss_bytes=snapshot.rss_bytes,
            vms_bytes=snapshot.vms_bytes,
            num_threads=snapshot.num_threads,
            cpu_percent=snapshot.cpu_percent,
            timestamp_sec=snapshot.timestamp_sec,
        )


class RAMTelemetryRecordSchema(BaseModel):
    """Pydantic v2 schema validating RAMTelemetryRecord with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence_idx: int = Field(..., ge=1, description="Monotonically increasing sequence index")
    timestamp_sec: float = Field(..., ge=0.0, description="Epoch timestamp of observation")
    target_pid: int = Field(..., ge=0, description="Target process identifier")
    parent_rss_bytes: int = Field(..., ge=0, description="Parent process RSS in bytes")
    child_rss_bytes: int = Field(..., ge=0, description="Sum of child processes RSS in bytes")
    total_rss_bytes: int = Field(..., ge=0, description="Aggregate resident memory in bytes")
    vms_bytes: int = Field(..., ge=0, description="Aggregate virtual memory in bytes")
    vram_bytes: int = Field(default=0, ge=0, description="GPU VRAM allocation in bytes")
    ceiling_bytes: int = Field(..., ge=1, description="Statutory RAM ceiling in bytes")
    utilization_ratio: float = Field(..., ge=0.0, description="Memory utilization relative to ceiling")
    stage: str = Field(..., description="Categorical guardrail stage")
    child_process_count: int = Field(..., ge=0, description="Count of enumerated child processes")
    predecessor_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 predecessor hash")
    record_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 record hash")

    def to_dataclass(self) -> RAMTelemetryRecord:
        """Convert schema to RAMTelemetryRecord dataclass."""
        return RAMTelemetryRecord(
            sequence_idx=self.sequence_idx,
            timestamp_sec=self.timestamp_sec,
            target_pid=self.target_pid,
            parent_rss_bytes=self.parent_rss_bytes,
            child_rss_bytes=self.child_rss_bytes,
            total_rss_bytes=self.total_rss_bytes,
            vms_bytes=self.vms_bytes,
            vram_bytes=self.vram_bytes,
            ceiling_bytes=self.ceiling_bytes,
            utilization_ratio=self.utilization_ratio,
            stage=RAMGuardrailStage(self.stage),
            child_process_count=self.child_process_count,
            predecessor_hash=self.predecessor_hash,
            record_hash=self.record_hash,
        )

    @classmethod
    def from_dataclass(cls, record: RAMTelemetryRecord) -> RAMTelemetryRecordSchema:
        """Construct schema from RAMTelemetryRecord dataclass."""
        return cls(
            sequence_idx=record.sequence_idx,
            timestamp_sec=record.timestamp_sec,
            target_pid=record.target_pid,
            parent_rss_bytes=record.parent_rss_bytes,
            child_rss_bytes=record.child_rss_bytes,
            total_rss_bytes=record.total_rss_bytes,
            vms_bytes=record.vms_bytes,
            vram_bytes=record.vram_bytes,
            ceiling_bytes=record.ceiling_bytes,
            utilization_ratio=record.utilization_ratio,
            stage=record.stage.value,
            child_process_count=record.child_process_count,
            predecessor_hash=record.predecessor_hash,
            record_hash=record.record_hash,
        )


class RAMGuardrailConfigSchema(BaseModel):
    """Pydantic v2 schema validating RAMGuardrailConfig with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ceiling_bytes: int = Field(default=2147483648, ge=1, description="Strict RAM ceiling in bytes")
    warning_ratio: float = Field(default=0.75, gt=0.0, lt=1.0, description="Warning threshold ratio")
    critical_ratio: float = Field(default=0.90, gt=0.0, le=1.0, description="Critical threshold ratio")
    include_children: bool = Field(default=True, description="Whether to aggregate child process trees")
    auto_gc_remediation: bool = Field(default=False, description="Whether to trigger gc.collect() automatically")
    history_capacity: int = Field(default=1000, ge=1, description="Capacity of telemetry history buffer")
    target_pid: Optional[int] = Field(default=None, description="Optional target process PID")

    def to_dataclass(self) -> RAMGuardrailConfig:
        """Convert schema to RAMGuardrailConfig dataclass."""
        return RAMGuardrailConfig(
            ceiling_bytes=self.ceiling_bytes,
            warning_ratio=self.warning_ratio,
            critical_ratio=self.critical_ratio,
            include_children=self.include_children,
            auto_gc_remediation=self.auto_gc_remediation,
            history_capacity=self.history_capacity,
            target_pid=self.target_pid,
        )

    @classmethod
    def from_dataclass(cls, config: RAMGuardrailConfig) -> RAMGuardrailConfigSchema:
        """Construct schema from RAMGuardrailConfig dataclass."""
        return cls(
            ceiling_bytes=config.ceiling_bytes,
            warning_ratio=config.warning_ratio,
            critical_ratio=config.critical_ratio,
            include_children=config.include_children,
            auto_gc_remediation=config.auto_gc_remediation,
            history_capacity=config.history_capacity,
            target_pid=config.target_pid,
        )


class RAMGuardrailMetricsSchema(BaseModel):
    """Pydantic v2 schema validating RAMGuardrailMetrics with extra='forbid'."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_polls: int = Field(..., ge=0, description="Total physical polls performed")
    peak_rss_bytes: int = Field(..., ge=0, description="Peak resident memory observed in bytes")
    min_rss_bytes: int = Field(..., ge=0, description="Minimum resident memory observed in bytes")
    current_rss_bytes: int = Field(..., ge=0, description="Current resident memory in bytes")
    ceiling_bytes: int = Field(..., ge=1, description="Configured RAM ceiling in bytes")
    peak_utilization_ratio: float = Field(..., ge=0.0, description="Peak utilization ratio")
    warning_events: int = Field(..., ge=0, description="Count of WARNING stage transitions")
    critical_events: int = Field(..., ge=0, description="Count of CRITICAL stage transitions")
    breach_events: int = Field(..., ge=0, description="Count of EXCEEDED stage transitions")
    remediation_events: int = Field(..., ge=0, description="Count of proactive remediation triggers")
    average_poll_latency_ms: float = Field(..., ge=0.0, description="Average polling duration in ms")
    growth_rate_bytes_per_sec: float = Field(..., description="OLS memory growth trajectory slope")

    def to_dataclass(self) -> RAMGuardrailMetrics:
        """Convert schema to RAMGuardrailMetrics dataclass."""
        return RAMGuardrailMetrics(
            total_polls=self.total_polls,
            peak_rss_bytes=self.peak_rss_bytes,
            min_rss_bytes=self.min_rss_bytes,
            current_rss_bytes=self.current_rss_bytes,
            ceiling_bytes=self.ceiling_bytes,
            peak_utilization_ratio=self.peak_utilization_ratio,
            warning_events=self.warning_events,
            critical_events=self.critical_events,
            breach_events=self.breach_events,
            remediation_events=self.remediation_events,
            average_poll_latency_ms=self.average_poll_latency_ms,
            growth_rate_bytes_per_sec=self.growth_rate_bytes_per_sec,
        )

    @classmethod
    def from_dataclass(cls, metrics: RAMGuardrailMetrics) -> RAMGuardrailMetricsSchema:
        """Construct schema from RAMGuardrailMetrics dataclass."""
        return cls(
            total_polls=metrics.total_polls,
            peak_rss_bytes=metrics.peak_rss_bytes,
            min_rss_bytes=metrics.min_rss_bytes,
            current_rss_bytes=metrics.current_rss_bytes,
            ceiling_bytes=metrics.ceiling_bytes,
            peak_utilization_ratio=metrics.peak_utilization_ratio,
            warning_events=metrics.warning_events,
            critical_events=metrics.critical_events,
            breach_events=metrics.breach_events,
            remediation_events=metrics.remediation_events,
            average_poll_latency_ms=metrics.average_poll_latency_ms,
            growth_rate_bytes_per_sec=metrics.growth_rate_bytes_per_sec,
        )





"""AI utilities, loaded on demand to keep optional model dependencies isolated."""

from importlib import import_module

_EXPORT_MODULES = {
    'AIAPIRouter': 'api_router',
    'APS_UNIT_MAPPINGS': 'template_engine',
    'ApiRouterConfig': 'api_router',
    'ContextCompressor': 'context_compression',
    'DEFAULT_CHUNK_MAX_CHARS': 'context_compression',
    'DEFAULT_LTTB_THRESHOLD': 'lttb_downsampling',
    'DEFAULT_ROLE_PROMPT': 'template_engine',
    'DEFAULT_TENSOR_THRESHOLD': 'context_compression',
    'DEFAULT_TRACEBACK_MAX_LINES': 'context_compression',
    'GeminiApiRouter': 'api_router',
    'H5DataInjector': 'template_engine',
    'HDF5PointerModel': 'context_compression',
    'InjectedDataSummary': 'template_engine',
    'LTTBDownsampler': 'lttb_downsampling',
    'LTTBResult': 'lttb_downsampling',
    'LaTeXFormatter': 'template_engine',
    'LaTeXFormattingOptions': 'template_engine',
    'MarkdownChunkModel': 'context_compression',
    'PayloadBuilder': 'template_engine',
    'PriorityLevel': 'api_router',
    'PromptPayload': 'template_engine',
    'PromptSection': 'api_router',
    'SYSTEMIC_COMMAND': 'template_engine',
    'SYSTEMIC_COMMAND_AIRGAP': 'template_engine',
    'TemplateEngine': 'template_engine',
    'TensorSummaryModel': 'context_compression',
    'TracebackSummaryModel': 'context_compression',
    'TruncationAuditRecord': 'api_router',
    'TruncationResult': 'api_router',
    'assemble_prompt_from_sections': 'api_router',
    'build_system_prompt': 'template_engine',
    'build_tenacity_retryer': 'api_router',
    'chunk_literature_by_headers': 'context_compression',
    'chunk_markdown_by_headers': 'context_compression',
    'compress_tensors_for_llm': 'context_compression',
    'compute_effective_token_limit': 'api_router',
    'count_tokens': 'api_router',
    'count_tokens_google': 'api_router',
    'create_hdf5_pointer': 'context_compression',
    'create_payload': 'template_engine',
    'dumps_rfc8259': 'context_compression',
    'enforce_latex_siunitx': 'template_engine',
    'estimate_tokens_heuristic': 'api_router',
    'extract_h5_float64_dataset': 'template_engine',
    'extract_hdf5_pointers': 'context_compression',
    'format_siunitx_angle': 'template_engine',
    'format_siunitx_num': 'template_engine',
    'format_siunitx_qty': 'template_engine',
    'inject_landscape_data': 'template_engine',
    'is_hdf5_pointer': 'context_compression',
    'is_transient_api_error': 'api_router',
    'loads_rfc8259': 'context_compression',
    'lttb_downsample': 'lttb_downsampling',
    'lttb_downsample_1d': 'lttb_downsampling',
    'lttb_downsample_indices': 'lttb_downsampling',
    'lttb_downsample_xy': 'lttb_downsampling',
    'parse_hdf5_pointer': 'context_compression',
    'resolve_hdf5_pointer': 'context_compression',
    'resolve_landscape_h5_file': 'template_engine',
    'sanitize_numerical_values': 'context_compression',
    'strip_ansi_escape_codes': 'context_compression',
    'to_rfc8259_json': 'context_compression',
    'truncate_prompt_by_priority': 'api_router',
    'truncate_traceback': 'context_compression',
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str):
    if name in _EXPORT_MODULES:
        value = getattr(import_module(f"{__name__}.{_EXPORT_MODULES[name]}"), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

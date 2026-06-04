"""Test helper for deep_analyst tests - handles dependency mocking"""

import sys
import importlib
import types


def _patch_pydantic_v1():
    """Patch pydantic v1 to accept v2-style features"""
    import pydantic

    if not hasattr(pydantic, 'field_validator'):
        def field_validator(*args, **kwargs):
            def decorator(fn):
                return pydantic.validator(*args, pre=True, always=True)(fn)
            return decorator
        pydantic.field_validator = field_validator

    if not hasattr(pydantic.BaseModel, 'model_dump'):
        pydantic.BaseModel.model_dump = pydantic.BaseModel.dict

    original_field = pydantic.Field
    def patched_field(*args, **kwargs):
        kwargs.pop('max_length', None)
        return original_field(*args, **kwargs)
    pydantic.Field = patched_field


def _load_module(name, path):
    """Load a module directly from file path"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_package(name, path=None):
    """Ensure a package exists in sys.modules"""
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        if path:
            pkg.__path__ = [path]
        sys.modules[name] = pkg


def _mock_module(name, attrs=None):
    """Create a mock module with optional attributes"""
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def ensure_deep_analyst_imports():
    """Ensure deep_analyst modules are importable"""
    if 'deep_analyst.utils' in sys.modules:
        return  # Already loaded

    _patch_pydantic_v1()

    # Mock models.base to avoid sqlalchemy async import
    mock_base = types.ModuleType('models.base')
    mock_base.Base = type('Base', (), {
        '__tablename__': '',
        '__table_args__': (),
    })
    mock_base.get_session = lambda: None
    mock_base.engine = None
    mock_base.async_session = None
    sys.modules['models.base'] = mock_base

    _ensure_package('models')
    _ensure_package('deep_analyst')
    _ensure_package('deep_analyst.models', 'deep_analyst/models')

    # Load utils first (no deep deps)
    _load_module('deep_analyst.utils', 'deep_analyst/utils.py')

    # Load schemas (needs utils + pydantic)
    _load_module('deep_analyst.schemas', 'deep_analyst/schemas.py')

    # Load analogy (needs utils + schemas)
    _load_module('deep_analyst.analogy', 'deep_analyst/analogy.py')

    # Load causal_chain models (needs models.base which is mocked)
    _load_module('deep_analyst.models.causal_chain', 'deep_analyst/models/causal_chain.py')


def ensure_pipeline_imports():
    """Ensure pipeline module is importable (needs more mocks)"""
    ensure_deep_analyst_imports()

    if 'deep_analyst.pipeline' in sys.modules:
        return

    # Mock heavy dependencies
    mock_ai = types.ModuleType('deep_analyst.ai_analysis')
    mock_ai.DeepSeekClient = type('DeepSeekClient', (), {'enabled': False})
    sys.modules['deep_analyst.ai_analysis'] = mock_ai

    mock_knowledge = types.ModuleType('deep_analyst.knowledge')
    mock_knowledge.analyze_event_knowledge = None
    mock_knowledge.analyze_causal_chain = None
    sys.modules['deep_analyst.knowledge'] = mock_knowledge

    mock_scenario = types.ModuleType('deep_analyst.scenario')
    mock_scenario.analyze_scenarios = None
    sys.modules['deep_analyst.scenario'] = mock_scenario

    # Mock DB models
    for mod_name, attrs in [
        ('deep_analyst.models.knowledge', {
            'EventKnowledge': type('EventKnowledge', (), {}),
            'EventKnowledgeAtom': type('EventKnowledgeAtom', (), {}),
            'KnowledgeAtom': type('KnowledgeAtom', (), {}),
        }),
        ('deep_analyst.models.event_representation', {
            'EventRepresentation': type('EventRepresentation', (), {}),
            'HistoricalAnalogy': type('HistoricalAnalogy', (), {}),
        }),
        ('deep_analyst.models.scenario', {
            'EventScenario': type('EventScenario', (), {}),
        }),
        ('models.event', {
            'Event': type('Event', (), {}),
        }),
    ]:
        if mod_name not in sys.modules:
            _mock_module(mod_name, attrs)

    _load_module('deep_analyst.pipeline', 'deep_analyst/pipeline.py')

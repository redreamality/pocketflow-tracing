# PocketFlow Tracing Cookbook: In-Depth Analysis

## Overview and Purpose

The PocketFlow Tracing cookbook (`cookbook/pocketflow-tracing`) provides comprehensive observability for PocketFlow workflows using [Langfuse](https://langfuse.com/) as the tracing backend. This implementation enables automatic tracing of workflow execution with minimal code changes - requiring only a single decorator to be added to flow classes.

### Key Goals
- **Minimal Code Changes**: Add observability with just `@trace_flow()` decorator
- **Comprehensive Tracing**: Automatically trace all node phases (prep, exec, post)
- **Input/Output Tracking**: Capture all data flowing through workflows
- **Error Tracking**: Automatically capture and trace exceptions
- **Async Support**: Full support for AsyncFlow and AsyncNode
- **Production Ready**: Packaged as a distributable Python package

## Architecture and Design Patterns

### Decorator-Based Architecture

The implementation follows a decorator pattern that wraps PocketFlow classes and methods to add tracing capabilities without modifying the core workflow logic:

```python
@trace_flow()  # Single decorator adds full tracing
class MyFlow(Flow):
    def __init__(self):
        super().__init__(start=MyNode())
```

### Core Components

#### 1. **TracingConfig** (`config.py`)
- **Purpose**: Centralized configuration management using dataclasses
- **Features**: 
  - Environment variable loading with `python-dotenv`
  - Validation of required Langfuse credentials
  - Granular control over what gets traced (inputs, outputs, errors, etc.)
  - Support for session and user tracking

#### 2. **LangfuseTracer** (`core.py`)
- **Purpose**: Core tracing engine that interfaces with Langfuse
- **Features**:
  - Langfuse v2 low-level SDK integration (compatible with server at 192.168.1.216:3000)
  - Safe data serialization for complex PocketFlow objects
  - Hierarchical trace/span management
  - Automatic error handling and recovery

#### 3. **trace_flow Decorator** (`decorator.py`)
- **Purpose**: Main decorator that adds tracing to Flow classes
- **Features**:
  - Dynamic method patching for both sync and async flows
  - Node discovery and automatic patching
  - Wrapper creation for all node phases (prep, exec, post)
  - Exception handling and trace cleanup

### Design Patterns Used

1. **Decorator Pattern**: Non-intrusive enhancement of existing classes
2. **Wrapper Pattern**: Method wrapping to add tracing behavior
3. **Factory Pattern**: Configuration creation from environment variables
4. **Observer Pattern**: Automatic tracking of workflow execution events

## Langfuse Integration Implementation

### Configuration Strategy
The implementation uses Langfuse v2 low-level SDK with environment-based configuration:

```python
# Required environment variables
LANGFUSE_SECRET_KEY=your-secret-key
LANGFUSE_PUBLIC_KEY=your-public-key  
LANGFUSE_HOST=http://192.168.1.216:3000  # User's preferred host
POCKETFLOW_TRACING_DEBUG=true
```

### Trace Hierarchy
```
Trace (Flow Execution)
├── Span (Node1.prep)
├── Span (Node1.exec) 
├── Span (Node1.post)
├── Span (Node2.prep)
├── Span (Node2.exec)
└── Span (Node2.post)
```

### Data Serialization
The tracer includes sophisticated data serialization to handle PocketFlow's complex data types:

```python
def _serialize_data(self, data: Any) -> Any:
    if hasattr(data, "__dict__"):
        return {"_type": type(data).__name__, "_data": str(data)}
    elif isinstance(data, (dict, list, str, int, float, bool, type(None))):
        return data
    else:
        return {"_type": type(data).__name__, "_data": str(data)}
```

## Key Components and Their Roles

### Node Execution Tracing
Each node's execution is automatically traced across three phases:

1. **prep() Phase**: 
   - Input: `shared` data
   - Output: `prep_res` returned by prep method
   - Automatic span creation and timing

2. **exec() Phase**:
   - Input: `prep_res` from prep phase  
   - Output: `exec_res` returned by exec method
   - Retry attempts tracking (if configured)

3. **post() Phase**:
   - Input: `shared`, `prep_res`, `exec_res`
   - Output: Action string returned
   - Final state updates

### Flow-Level Tracing
- **Flow Start/End**: Overall execution time and status
- **Input Data**: Initial shared state when flow starts
- **Output Data**: Final shared state when flow completes  
- **Errors**: Any exceptions during flow execution

### Async Support
Full support for AsyncFlow and AsyncNode with separate async method wrapping:

```python
async def traced_async_method(*args, **kwargs):
    span_id = self._tracer.start_node_span(node_name, node_id, phase)
    try:
        result = await original_method(*args, **kwargs)
        self._tracer.end_node_span(span_id, input_data=args, output_data=result)
        return result
    except Exception as e:
        self._tracer.end_node_span(span_id, input_data=args, error=e)
        raise
```

## Configuration Requirements

### Environment Variables

#### Required (Langfuse Configuration)
```env
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_HOST=your-langfuse-host-url
```

#### Optional (Tracing Behavior)
```env
POCKETFLOW_TRACING_DEBUG=true
POCKETFLOW_TRACE_INPUTS=true
POCKETFLOW_TRACE_OUTPUTS=true
POCKETFLOW_TRACE_PREP=true
POCKETFLOW_TRACE_EXEC=true
POCKETFLOW_TRACE_POST=true
POCKETFLOW_TRACE_ERRORS=true
```

#### Optional (Session Tracking)
```env
POCKETFLOW_SESSION_ID=your-session-id
POCKETFLOW_USER_ID=your-user-id
```

### Dependencies
```toml
dependencies = [
    "langfuse>=2.0.0,<3.0.0",  # v2 SDK as preferred
    "python-dotenv>=1.0.0",   # Environment variable loading
    "pydantic>=2.0.0"         # Data validation
]
```

## Usage Examples and Execution

### Basic Synchronous Flow
```python
from pocketflow import Node, Flow
from pocketflow_tracing import trace_flow

@trace_flow(flow_name="BasicGreetingFlow")
class BasicGreetingFlow(Flow):
    def __init__(self):
        greeting_node = GreetingNode()
        uppercase_node = UppercaseNode()
        greeting_node >> uppercase_node
        super().__init__(start=greeting_node)

# Usage
flow = BasicGreetingFlow()
shared = {"name": "PocketFlow User"}
result = flow.run(shared)
```

### Asynchronous Flow
```python
from pocketflow import AsyncNode, AsyncFlow
from pocketflow_tracing import trace_flow

@trace_flow(flow_name="AsyncDataProcessingFlow")
class AsyncDataProcessingFlow(AsyncFlow):
    def __init__(self):
        fetch_node = AsyncDataFetchNode()
        process_node = AsyncDataProcessNode()
        fetch_node - "process" >> process_node
        super().__init__(start=fetch_node)

# Usage
flow = AsyncDataProcessingFlow()
shared = {"query": "machine learning tutorials"}
result = await flow.run_async(shared)
```

### Running Examples
```bash
# Basic synchronous example
cd cookbook/pocketflow-tracing/examples
python basic_example.py

# Asynchronous example  
python async_example.py

# Run tests
python ../test_tracing.py
```

## Package Distribution and Installation

The cookbook is packaged as a proper Python package using modern packaging standards:

### Installation Options
```bash
# From PyPI (when published)
pip install pocketflow-tracing

# From source
git clone https://github.com/The-Pocket/PocketFlow.git
cd PocketFlow/cookbook/pocketflow-tracing
pip install .

# Development installation
pip install -e ".[dev]"
```

### Package Structure
```
pocketflow-tracing/
├── pocketflow_tracing/          # Main package
│   ├── __init__.py             # Public API exports
│   ├── config.py               # Configuration management
│   ├── core.py                 # Core tracing engine
│   ├── decorator.py            # Main decorator implementation
│   └── utils/                  # Utility functions
│       ├── __init__.py
│       └── setup.py            # Setup and testing utilities
├── examples/                   # Usage examples
│   ├── basic_example.py        # Synchronous flow example
│   └── async_example.py        # Asynchronous flow example
├── tests/                      # Test files
├── pyproject.toml             # Modern Python packaging
├── README.md                  # Comprehensive documentation
└── .env.example               # Environment template
```

## Relationship to PocketFlow Framework

### Integration Strategy
The tracing implementation is designed as a **non-intrusive enhancement** to PocketFlow:

1. **Zero Core Changes**: No modifications to PocketFlow core required
2. **Decorator-Based**: Uses Python decorators for clean separation
3. **Optional Dependency**: Can be installed and used independently
4. **Backward Compatible**: Existing flows work unchanged

### Observability Strategy
This cookbook represents PocketFlow's approach to observability:

1. **Minimal Friction**: Single decorator adds full observability
2. **Production Ready**: Proper error handling and recovery
3. **Configurable**: Granular control over what gets traced
4. **Extensible**: Can be extended for other observability backends

### Future Integration
The patterns established in this cookbook could be:
- Integrated into PocketFlow core as optional features
- Extended to support other observability platforms (OpenTelemetry, etc.)
- Used as a template for other PocketFlow enhancements

## Testing and Validation

The cookbook includes comprehensive testing:

### Test Coverage
- Configuration loading and validation
- Synchronous flow tracing
- Asynchronous flow tracing  
- Error handling and recovery
- Package installation verification

### Setup Utilities
- `pocketflow-tracing-setup` console script for configuration testing
- Connection validation utilities
- Debug mode for troubleshooting

This implementation demonstrates PocketFlow's commitment to production-ready, observable workflows with minimal developer overhead.

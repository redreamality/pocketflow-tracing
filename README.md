# PocketFlow Tracing with Langfuse

This [repository](https://github.com/redreamality/pocketflow-tracing) provides comprehensive observability for PocketFlow workflows using [Langfuse](https://langfuse.com/) as the tracing backend. With minimal code changes (just adding a decorator), you can automatically trace all node executions, inputs, outputs, and errors in your PocketFlow workflows. Checkout the [blog](https://redreamality.com/blog/pocketflow-tracing) post for more details.

## 🎯 Features

### Core Tracing
- **Automatic Tracing**: Trace entire flows with a single decorator
- **Node-Level Observability**: Automatically trace `prep`, `exec`, and `post` phases of each node
- **Input/Output Tracking**: Capture all data flowing through your workflow
- **Error Tracking**: Automatically capture and trace exceptions
- **Minimal Code Changes**: Just add `@trace_flow()` to your flow classes
- **Langfuse Integration**: Leverage Langfuse's powerful observability platform

### 🚀 Advanced Async Support
- **Comprehensive Async Context Management**: Proper context propagation across async boundaries
- **Advanced Lifecycle Tracking**: Detailed tracking of async node states including suspend/resume events
- **Async Flow Composition**: Support for nested, concurrent, and batch async flows
- **Robust Error Handling**: Comprehensive error management for async operations including cancellation, timeouts, and recovery
- **Performance Monitoring**: Built-in performance tracking for async operations
- **Concurrent Flow Execution**: Execute multiple flows concurrently with proper isolation
- **Backward Compatibility**: Existing synchronous code continues to work unchanged

## 🚀 Quick Start

### 1. Installation

Install the package using pip:

```bash
pip install pocketflow-tracing
```

Or install from source:

```bash
git clone https://github.com/The-Pocket/PocketFlow.git
cd PocketFlow/cookbook/pocketflow-tracing
pip install .
```

For development installation:

```bash
pip install -e ".[dev]"
```

### 2. Environment Setup

Copy the example environment file and configure your Langfuse credentials:

```bash
cp .env.example .env
```

Then edit the `.env` file with your actual Langfuse configuration:

```env
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_HOST=your-langfuse-host-url
POCKETFLOW_TRACING_DEBUG=true
```

**Note**: Replace the placeholder values with your actual Langfuse credentials and host URL.

### 3. Basic Usage

For a flow you want to trace, say:

```python
# flow.py

node1 = MyNode1()
node2 = MyNode2()

node1 >> node2

flow = Flow(node1)
```


The only thing you need to do is add the `@trace_flow()` decorator to your flow classes:

```python
# flow.py

node1 = MyNode1()
node2 = MyNode2()

node1 >> node2

@trace_flow()  # 🎉 That's it! Your flow is now traced
class MyFlow(Flow):
    pass

# Run your flow - tracing happens automatically
flow = MyFlow(node1)
```

We recommend to use an semantic name for your flow, e.g. `MyFlow` here.

---

Full code for the tracing example:

```python
from pocketflow import Node, Flow
from pocketflow_tracing import trace_flow

# nodes.py
class MyNode1(Node):
    def prep(self, shared):
        return shared["input"]
    
    def exec(self, data):
        return f"Processed: {data}"
    
    def post(self, shared, prep_res, exec_res):
        shared["output"] = exec_res
        return "default"

class MyNode2(Node):
    def prep(self, shared):
        return shared["input"]
    
    def exec(self, data):
        return f"Processed: {data}"
    
    def post(self, shared, prep_res, exec_res):
        shared["output"] = exec_res
        return "default"


# flow.py

node1 = MyNode1()
node2 = MyNode2()

node1 >> node2

@trace_flow()  # 🎉 That's it! Your flow is now traced
class MyFlow(Flow):
    pass

# Run your flow - tracing happens automatically
flow = MyFlow(node1)
shared = {"input": "Hello World"}
flow.run(shared)
```


## 📊 What Gets Traced

When you apply the `@trace_flow()` decorator, the system automatically traces:

### Flow Level
- **Flow Start/End**: Overall execution time and status
- **Input Data**: Initial shared state when flow starts
- **Output Data**: Final shared state when flow completes
- **Errors**: Any exceptions that occur during flow execution

### Node Level
For each node in your flow, the system traces:

- **prep() Phase**: 
  - Input: `shared` data
  - Output: `prep_res` returned by prep method
  - Execution time and any errors

- **exec() Phase**:
  - Input: `prep_res` from prep phase
  - Output: `exec_res` returned by exec method
  - Execution time and any errors
  - Retry attempts (if configured)

- **post() Phase**:
  - Input: `shared`, `prep_res`, `exec_res`
  - Output: Action string returned
  - Execution time and any errors

## 🔧 Configuration Options

### Basic Configuration

```python
from tracing import trace_flow, TracingConfig

# Use environment variables (default)
@trace_flow()
class MyFlow(Flow):
    pass

# Custom flow name
@trace_flow(flow_name="CustomFlowName")
class MyFlow(Flow):
    pass

# Custom session and user IDs
@trace_flow(session_id="session-123", user_id="user-456")
class MyFlow(Flow):
    pass
```

### Advanced Configuration

```python
from tracing import TracingConfig

# Create custom configuration
config = TracingConfig(
    langfuse_secret_key="your-secret-key",
    langfuse_public_key="your-public-key", 
    langfuse_host="https://your-langfuse-instance.com",
    debug=True,
    trace_inputs=True,
    trace_outputs=True,
    trace_errors=True
)

@trace_flow(config=config)
class MyFlow(Flow):
    pass
```

## 📁 Examples

### Basic Synchronous Flow
See `examples/basic_example.py` for a complete example of tracing a simple synchronous flow.

```bash
cd examples
python basic_example.py
```

### Asynchronous Flow
See `examples/async_example.py` for basic async tracing and `examples/comprehensive_async_example.py` for advanced async features.

```bash
cd examples
python async_example.py

# For comprehensive async features demonstration
python comprehensive_async_example.py
```

### 🚀 Advanced Async Usage

The enhanced async support provides comprehensive tracing for complex async patterns:

#### Concurrent Flow Execution
```python
import asyncio
from pocketflow_tracing import trace_flow

@trace_flow(flow_name="ConcurrentFlow")
class ConcurrentFlow(AsyncFlow):
    # ... your async flow definition ...

async def run_concurrent_flows():
    flows = [ConcurrentFlow() for _ in range(5)]
    shared_data = [{"input": f"data_{i}"} for i in range(5)]

    # Execute flows concurrently with proper tracing
    results = await asyncio.gather(*[
        flow.run_async(shared)
        for flow, shared in zip(flows, shared_data)
    ])

    return results
```

#### Error Handling and Recovery
```python
class RobustAsyncNode(AsyncNode):
    def __init__(self, max_retries=3):
        super().__init__(max_retries=max_retries, wait=1.0)

    async def exec_async(self, prep_res):
        # This will automatically retry on failure
        return await risky_async_operation(prep_res)

    async def exec_fallback_async(self, prep_res, exc):
        # Fallback when all retries are exhausted
        return await safe_fallback_operation(prep_res)
```

#### Nested Flow Composition
```python
@trace_flow(flow_name="MainFlow")
class MainFlow(AsyncFlow):
    async def run_async(self, shared):
        # Run main processing
        result = await super().run_async(shared)

        # Run nested analysis flow with proper context
        if result == "success":
            analysis_flow = AnalysisFlow()
            analysis_result = await analysis_flow.run_async(shared)
            shared["analysis"] = analysis_result

        return result
```

For complete migration guidance, see [docs/async_migration_guide.md](docs/async_migration_guide.md).

## 🔍 Viewing Traces

After running your traced flows, visit your Langfuse dashboard to view the traces:

**Dashboard URL**: Use the URL you configured in `LANGFUSE_HOST` environment variable

In the dashboard you'll see:
- **Traces**: One trace per flow execution
- **Spans**: Individual node phases (prep, exec, post)
- **Input/Output Data**: All data flowing through your workflow
- **Performance Metrics**: Execution times for each phase
- **Error Details**: Stack traces and error messages

The tracings in examples.
![alt text](screenshots/chrome_2025-06-27_12-05-28.png)

Detailed tracing for a node.
![langfuse](screenshots/chrome_2025-06-27_12-07-56.png)

## 🛠️ Advanced Usage

### Custom Tracer Configuration

```python
from tracing import TracingConfig, LangfuseTracer

# Create custom configuration
config = TracingConfig.from_env()
config.debug = True

# Use tracer directly (for advanced use cases)
tracer = LangfuseTracer(config)
```

### Environment Variables

You can customize tracing behavior with these environment variables:

```env
# Required Langfuse configuration
LANGFUSE_SECRET_KEY=your-secret-key
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_HOST=your-langfuse-host

# Optional tracing configuration
POCKETFLOW_TRACING_DEBUG=true
POCKETFLOW_TRACE_INPUTS=true
POCKETFLOW_TRACE_OUTPUTS=true
POCKETFLOW_TRACE_PREP=true
POCKETFLOW_TRACE_EXEC=true
POCKETFLOW_TRACE_POST=true
POCKETFLOW_TRACE_ERRORS=true

# Optional session/user tracking
POCKETFLOW_SESSION_ID=your-session-id
POCKETFLOW_USER_ID=your-user-id
```

## 🐛 Troubleshooting

### Common Issues

1. **"langfuse package not installed"**
   ```bash
   pip install langfuse
   ```

2. **"Langfuse client initialization failed"**
   - Check your `.env` file configuration
   - Verify Langfuse server is running at the specified host
   - Check network connectivity

3. **"No traces appearing in dashboard"**
   - Ensure `POCKETFLOW_TRACING_DEBUG=true` to see debug output
   - Check that your flow is actually being executed
   - Verify Langfuse credentials are correct

### Debug Mode

Enable debug mode to see detailed tracing information:

```env
POCKETFLOW_TRACING_DEBUG=true
```

This will print detailed information about:
- Langfuse client initialization
- Trace and span creation
- Data serialization
- Error messages

## 📚 API Reference

### `@trace_flow()`

Decorator to add Langfuse tracing to PocketFlow flows.

**Parameters:**
- `config` (TracingConfig, optional): Custom configuration. If None, loads from environment.
- `flow_name` (str, optional): Custom name for the flow. If None, uses class name.
- `session_id` (str, optional): Session ID for grouping related traces.
- `user_id` (str, optional): User ID for the trace.

### `TracingConfig`

Configuration class for tracing settings.

**Methods:**
- `TracingConfig.from_env()`: Create config from environment variables
- `validate()`: Check if configuration is valid
- `to_langfuse_kwargs()`: Convert to Langfuse client kwargs

### `LangfuseTracer`

Core tracer class for Langfuse integration.

**Methods:**
- `start_trace()`: Start a new trace
- `end_trace()`: End the current trace
- `start_node_span()`: Start a span for node execution
- `end_node_span()`: End a node execution span
- `flush()`: Flush pending traces to Langfuse

## 🤝 Contributing

This cookbook is designed to be a starting point for PocketFlow observability. Feel free to extend and customize it for your specific needs!

## 📄 License

This cookbook follows the same license as PocketFlow.

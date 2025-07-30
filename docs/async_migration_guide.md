# Async Migration Guide for PocketFlow Tracing

This guide helps you migrate your existing PocketFlow applications to use the comprehensive async tracing features introduced in the latest version.

## Overview

The enhanced PocketFlow tracing system now provides:

- **Advanced Async Context Management**: Proper context propagation across async boundaries
- **Comprehensive Lifecycle Tracking**: Detailed tracking of async node states including suspend/resume events
- **Async Flow Composition**: Support for nested, concurrent, and batch async flows
- **Robust Error Handling**: Comprehensive error management for async operations
- **Backward Compatibility**: Existing synchronous code continues to work unchanged

## Migration Steps

### 1. Update Your Dependencies

First, ensure you have the latest version of pocketflow-tracing:

```bash
pip install --upgrade pocketflow-tracing
```

### 2. Basic Async Node Migration

#### Before (Synchronous Node)
```python
from pocketflow import Node

class DataProcessingNode(Node):
    def prep(self, shared):
        return shared.get("input_data")
    
    def exec(self, prep_res):
        # Synchronous processing
        return process_data(prep_res)
    
    def post(self, shared, prep_res, exec_res):
        shared["output"] = exec_res
        return "default"
```

#### After (Async Node)
```python
from pocketflow import AsyncNode

class DataProcessingNode(AsyncNode):
    async def prep_async(self, shared):
        return shared.get("input_data")
    
    async def exec_async(self, prep_res):
        # Asynchronous processing with proper tracing
        return await async_process_data(prep_res)
    
    async def post_async(self, shared, prep_res, exec_res):
        shared["output"] = exec_res
        return "default"
```

### 3. Flow Migration

#### Before (Synchronous Flow)
```python
from pocketflow import Flow
from pocketflow_tracing import trace_flow

@trace_flow(flow_name="DataProcessingFlow")
class DataProcessingFlow(Flow):
    def __init__(self):
        node1 = DataProcessingNode()
        node2 = OutputNode()
        node1.next(node2)
        super().__init__(start=node1)
```

#### After (Async Flow)
```python
from pocketflow import AsyncFlow
from pocketflow_tracing import trace_flow

@trace_flow(flow_name="DataProcessingFlow")
class DataProcessingFlow(AsyncFlow):
    def __init__(self):
        node1 = DataProcessingNode()  # Now async
        node2 = OutputNode()          # Now async
        node1.next(node2)
        super().__init__(start=node1)
    
    async def prep_async(self, shared):
        """Optional: Flow-level async preparation"""
        return await super().prep_async(shared)
    
    async def post_async(self, shared, prep_res, exec_res):
        """Optional: Flow-level async post-processing"""
        return await super().post_async(shared, prep_res, exec_res)
```

### 4. Execution Migration

#### Before (Synchronous Execution)
```python
flow = DataProcessingFlow()
shared = {"input_data": "test"}
result = flow.run(shared)
```

#### After (Async Execution)
```python
import asyncio

async def main():
    flow = DataProcessingFlow()
    shared = {"input_data": "test"}
    result = await flow.run_async(shared)
    return result

# Run the async flow
result = asyncio.run(main())
```

## Advanced Features

### 1. Concurrent Flow Execution

```python
import asyncio
from pocketflow_tracing import trace_flow

@trace_flow(flow_name="ConcurrentFlow")
class ConcurrentFlow(AsyncFlow):
    # ... flow definition ...

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

### 2. Error Handling and Recovery

```python
class RobustAsyncNode(AsyncNode):
    def __init__(self, max_retries=3):
        super().__init__(max_retries=max_retries, wait=1.0)
    
    async def exec_async(self, prep_res):
        try:
            return await risky_async_operation(prep_res)
        except ConnectionError as e:
            # This will trigger automatic retry
            raise
    
    async def exec_fallback_async(self, prep_res, exc):
        """Fallback when all retries are exhausted"""
        return await safe_fallback_operation(prep_res)
```

### 3. Nested Flow Composition

```python
@trace_flow(flow_name="MainFlow")
class MainFlow(AsyncFlow):
    async def run_async(self, shared):
        # Run main processing
        result = await super().run_async(shared)
        
        # Run nested analysis flow
        if result == "success":
            analysis_flow = AnalysisFlow()
            analysis_result = await analysis_flow.run_async(shared)
            shared["analysis"] = analysis_result
        
        return result
```

### 4. Performance Monitoring

```python
import time

@trace_flow(flow_name="MonitoredFlow")
class MonitoredFlow(AsyncFlow):
    async def prep_async(self, shared):
        shared["start_time"] = time.time()
        return await super().prep_async(shared)
    
    async def post_async(self, shared, prep_res, exec_res):
        duration = time.time() - shared["start_time"]
        shared["execution_time"] = duration
        
        # Log performance metrics
        if duration > 5.0:
            print(f"⚠️ Slow execution detected: {duration:.2f}s")
        
        return await super().post_async(shared, prep_res, exec_res)
```

## Configuration Updates

### Enhanced Tracing Configuration

```python
from pocketflow_tracing import TracingConfig

config = TracingConfig(
    # Existing options
    trace_inputs=True,
    trace_outputs=True,
    trace_errors=True,
    
    # New async-specific options
    trace_async_lifecycle=True,      # Track async node lifecycle events
    trace_async_context=True,        # Track async context propagation
    trace_concurrent_flows=True,     # Track concurrent flow execution
    async_error_recovery=True,       # Enable async error recovery
    performance_monitoring=True,     # Enable performance monitoring
)
```

## Common Migration Patterns

### 1. Mixed Sync/Async Flows

You can gradually migrate by mixing sync and async nodes:

```python
@trace_flow(flow_name="MixedFlow")
class MixedFlow(AsyncFlow):
    def __init__(self):
        sync_node = SyncProcessingNode()      # Still synchronous
        async_node = AsyncProcessingNode()    # Now asynchronous
        
        sync_node.next(async_node)
        super().__init__(start=sync_node)
```

### 2. Batch Processing Migration

#### Before
```python
def process_batch(items):
    results = []
    for item in items:
        result = process_item(item)
        results.append(result)
    return results
```

#### After
```python
async def process_batch_async(items):
    # Process items concurrently
    results = await asyncio.gather(*[
        process_item_async(item) for item in items
    ])
    return results
```

### 3. Database Operations

#### Before
```python
class DatabaseNode(Node):
    def exec(self, prep_res):
        conn = get_db_connection()
        result = conn.execute(query, prep_res)
        return result.fetchall()
```

#### After
```python
class DatabaseNode(AsyncNode):
    async def exec_async(self, prep_res):
        async with get_async_db_connection() as conn:
            result = await conn.execute(query, prep_res)
            return await result.fetchall()
```

## Testing Your Migration

### 1. Unit Tests

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_flow():
    flow = YourAsyncFlow()
    shared = {"test_input": "data"}
    
    result = await flow.run_async(shared)
    
    assert result == "expected_result"
    assert "expected_output" in shared
```

### 2. Performance Tests

```python
import time

@pytest.mark.asyncio
async def test_concurrent_performance():
    flows = [YourAsyncFlow() for _ in range(10)]
    shared_data = [{"input": f"data_{i}"} for i in range(10)]
    
    start_time = time.time()
    results = await asyncio.gather(*[
        flow.run_async(shared) 
        for flow, shared in zip(flows, shared_data)
    ])
    execution_time = time.time() - start_time
    
    # Should be faster than sequential execution
    assert execution_time < 5.0  # Adjust based on your requirements
    assert len(results) == 10
```

## Troubleshooting

### Common Issues and Solutions

1. **Context Lost Across Async Boundaries**
   ```python
   # Problem: Context not propagated
   async def problematic_function():
       # Context might be lost here
       pass
   
   # Solution: Use proper async context management
   async def fixed_function():
       # Context is automatically managed by the tracing system
       pass
   ```

2. **Mixed Sync/Async Deadlocks**
   ```python
   # Problem: Calling sync code from async context
   async def problematic_async():
       return sync_blocking_function()  # Can cause deadlocks
   
   # Solution: Use proper async alternatives
   async def fixed_async():
       return await async_non_blocking_function()
   ```

3. **Memory Leaks in Long-Running Flows**
   ```python
   # Problem: Not cleaning up resources
   async def problematic_flow():
       # Resources not cleaned up
       pass
   
   # Solution: Use proper resource management
   async def fixed_flow():
       async with resource_manager():
           # Resources automatically cleaned up
           pass
   ```

## Best Practices

1. **Always use `await` for async operations**
2. **Use `asyncio.gather()` for concurrent operations**
3. **Implement proper error handling with try/except**
4. **Use async context managers for resource management**
5. **Test both success and failure scenarios**
6. **Monitor performance and optimize bottlenecks**
7. **Gradually migrate complex flows**

## Getting Help

If you encounter issues during migration:

1. Check the [comprehensive async example](../examples/comprehensive_async_example.py)
2. Review the [test files](../tests/) for usage patterns
3. Enable debug logging to see detailed trace information
4. Open an issue on GitHub with your specific use case

## Next Steps

After successful migration:

1. Explore advanced async patterns in your flows
2. Implement performance monitoring and optimization
3. Set up comprehensive error handling and recovery
4. Consider using concurrent execution for improved performance
5. Monitor your Langfuse dashboard for detailed async traces

## API Reference

### Core Async Classes

#### `AsyncTraceContext`
Manages async tracing context across async boundaries.

```python
from pocketflow_tracing.core import AsyncTraceContext

# Create async context
context = AsyncTraceContext(tracer, trace_id, flow_name)

# Use as async context manager
async with context:
    # Your async operations here
    pass

# Get current context
current = AsyncTraceContext.get_current_context()
```

#### `AsyncLifecycleManager`
Manages async node lifecycles and events.

```python
from pocketflow_tracing.async_lifecycle import AsyncLifecycleManager

manager = AsyncLifecycleManager(tracer)

# Start lifecycle tracking
lifecycle = manager.start_lifecycle(node_id, node_name, phase)

# Transition states
manager.transition_state(node_id, AsyncNodeState.RUNNING)
manager.suspend_node(node_id, "await_operation")
manager.resume_node(node_id, "operation_complete")
```

#### `AsyncFlowCompositionManager`
Manages async flow composition and execution.

```python
from pocketflow_tracing.async_composition import AsyncFlowCompositionManager

manager = AsyncFlowCompositionManager(tracer)

# Execute parallel flows
results = await manager.execute_parallel_flows(flows, flow_names)

# Execute nested flow
result = await manager.execute_nested_flow(flow, flow_name)

# Execute batch flows
results = await manager.execute_batch_flows(
    flow_factory, batch_data, flow_name, parallel=True
)
```

#### `AsyncErrorHandler`
Comprehensive async error handler.

```python
from pocketflow_tracing.async_error_handling import AsyncErrorHandler

handler = AsyncErrorHandler(tracer)

# Handle async error
error_event = await handler.handle_async_error(
    error, node_id="node_1", flow_name="TestFlow"
)

# Register custom error handler
handler.register_error_handler(AsyncErrorType.TIMEOUT, custom_handler)
```

### Enhanced LangfuseTracer Methods

#### Async Context Management
```python
# Start async trace
async_context = await tracer.start_trace_async(flow_name, input_data)

# Create async context
context = tracer.create_async_context(flow_name, trace_id)
```

#### Async Node Lifecycle
```python
# Start async node lifecycle
span_id = await tracer.start_async_node_lifecycle(node_id, node_name, phase)

# Transition node state
await tracer.transition_async_node_state(node_id, "running", phase)

# Suspend/resume node
await tracer.suspend_async_node(node_id, "await_operation")
await tracer.resume_async_node(node_id, "operation_complete")
```

#### Async Flow Composition
```python
# Start flow composition
execution_id = await tracer.start_async_flow_composition(
    flow_name, "parallel", parent_execution_id
)

# Execute parallel flows
results = await tracer.execute_parallel_async_flows(
    flows, flow_names, parent_execution_id
)
```

#### Async Error Handling
```python
# Handle async error
error_event = await tracer.handle_async_error(
    error, node_id, flow_name, context_data
)

# Safe async execution
result = await tracer.safe_async_execute(
    coro, node_id, flow_name, timeout_seconds=10, retry_count=3
)

# Execute with timeout
result = await tracer.with_timeout(coro, timeout_seconds, node_id, flow_name)
```

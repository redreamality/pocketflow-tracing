"""
Async performance and compatibility tests for PocketFlow tracing.

This module contains performance tests to ensure async tracing doesn't introduce
significant overhead and tests backward compatibility with existing synchronous code.
"""

import asyncio
import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

# Import the modules we're testing
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pocketflow_tracing import trace_flow, TracingConfig, LangfuseTracer
from pocketflow_tracing.core import AsyncTraceContext


# Mock classes for testing
class MockSyncNode:
    """Mock synchronous node for compatibility testing."""
    
    def __init__(self, name="MockSyncNode"):
        self.name = name
        self.params = {}
        self.successors = {}
    
    def set_params(self, params):
        self.params = params
    
    def next(self, node, action="default"):
        self.successors[action] = node
        return node
    
    def prep(self, shared):
        time.sleep(0.01)  # Simulate work
        return shared.get("input", f"prep_{self.name}")
    
    def exec(self, prep_res):
        time.sleep(0.02)  # Simulate work
        return f"processed_{prep_res}"
    
    def post(self, shared, prep_res, exec_res):
        time.sleep(0.005)  # Simulate work
        shared[f"output_{self.name}"] = exec_res
        return "default"
    
    def _run(self, shared):
        prep_res = self.prep(shared)
        exec_res = self.exec(prep_res)
        return self.post(shared, prep_res, exec_res)


class MockSyncFlow:
    """Mock synchronous flow for compatibility testing."""
    
    def __init__(self, start_node=None):
        self.start_node = start_node
        self.params = {}
    
    def prep(self, shared):
        time.sleep(0.001)
        return {}
    
    def post(self, shared, prep_res, exec_res):
        time.sleep(0.001)
        return exec_res
    
    def _orch(self, shared, params=None):
        """Orchestrate synchronous flow execution."""
        if not self.start_node:
            return None
        
        current = self.start_node
        last_action = None
        
        while current:
            current.set_params(params or self.params)
            last_action = current._run(shared)
            
            # Get next node
            next_node = current.successors.get(last_action or "default")
            current = next_node
        
        return last_action
    
    def _run(self, shared):
        prep_res = self.prep(shared)
        exec_res = self._orch(shared)
        return self.post(shared, prep_res, exec_res)
    
    def run(self, shared):
        return self._run(shared)


class MockAsyncNode:
    """Mock async node for performance testing."""
    
    def __init__(self, name="MockAsyncNode", delay=0.01):
        self.name = name
        self.delay = delay
        self.params = {}
        self.successors = {}
    
    def set_params(self, params):
        self.params = params
    
    def next(self, node, action="default"):
        self.successors[action] = node
        return node
    
    async def prep_async(self, shared):
        await asyncio.sleep(self.delay)
        return shared.get("input", f"prep_{self.name}")
    
    async def exec_async(self, prep_res):
        await asyncio.sleep(self.delay * 2)
        return f"processed_{prep_res}"
    
    async def post_async(self, shared, prep_res, exec_res):
        await asyncio.sleep(self.delay * 0.5)
        shared[f"output_{self.name}"] = exec_res
        return "default"
    
    async def _run_async(self, shared):
        prep_res = await self.prep_async(shared)
        exec_res = await self.exec_async(prep_res)
        return await self.post_async(shared, prep_res, exec_res)


@pytest.fixture
def mock_config():
    """Create a mock tracing configuration."""
    config = TracingConfig()
    config.debug = False  # Disable debug for performance tests
    config.trace_inputs = True
    config.trace_outputs = True
    config.trace_errors = True
    return config


class TestAsyncTracingPerformance:
    """Test async tracing performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_async_context_creation_overhead(self, mock_config):
        """Test overhead of async context creation."""
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            tracer = LangfuseTracer(mock_config)
            
            # Measure context creation time
            num_contexts = 1000
            start_time = time.time()
            
            contexts = []
            for i in range(num_contexts):
                context = AsyncTraceContext(tracer, f"trace_{i}", f"Flow_{i}")
                contexts.append(context)
            
            creation_time = time.time() - start_time
            
            # Should be very fast
            assert creation_time < 0.5  # Less than 0.5 seconds for 1000 contexts
            assert len(contexts) == num_contexts
            
            # Test context manager overhead
            start_time = time.time()
            
            for context in contexts[:100]:  # Test subset for async operations
                async with context:
                    pass
            
            context_mgr_time = time.time() - start_time
            assert context_mgr_time < 1.0  # Less than 1 second for 100 context operations
    
    @pytest.mark.asyncio
    async def test_async_span_creation_overhead(self, mock_config):
        """Test overhead of async span creation."""
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            tracer = LangfuseTracer(mock_config)
            tracer.current_trace = Mock()
            tracer.current_trace.span = Mock(return_value=Mock())
            
            # Measure span creation time
            num_spans = 1000
            start_time = time.time()
            
            span_ids = []
            for i in range(num_spans):
                span_id = await tracer.start_node_span_async(f"Node_{i}", f"node_{i}", "exec")
                span_ids.append(span_id)
            
            span_creation_time = time.time() - start_time
            
            # Should be reasonably fast
            assert span_creation_time < 2.0  # Less than 2 seconds for 1000 spans
            assert len(span_ids) == num_spans
            
            # Measure span ending time
            start_time = time.time()
            
            for span_id in span_ids:
                await tracer.end_node_span_async(span_id, output_data="test_result")
            
            span_ending_time = time.time() - start_time
            assert span_ending_time < 2.0  # Less than 2 seconds for 1000 span endings
    
    @pytest.mark.asyncio
    async def test_async_lifecycle_tracking_overhead(self, mock_config):
        """Test overhead of async lifecycle tracking."""
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            tracer = LangfuseTracer(mock_config)
            lifecycle_manager = tracer.get_lifecycle_manager()
            
            # Measure lifecycle tracking overhead
            num_lifecycles = 500
            start_time = time.time()
            
            for i in range(num_lifecycles):
                node_id = f"node_{i}"
                lifecycle_manager.start_lifecycle(node_id, f"Node_{i}")
                lifecycle_manager.transition_state(node_id, "running")
                lifecycle_manager.suspend_node(node_id)
                lifecycle_manager.resume_node(node_id)
                lifecycle_manager.transition_state(node_id, "completed")
            
            tracking_time = time.time() - start_time
            
            # Should be reasonably fast
            assert tracking_time < 3.0  # Less than 3 seconds for 500 full lifecycles
            assert len(lifecycle_manager.completed_lifecycles) == num_lifecycles
    
    @pytest.mark.asyncio
    async def test_async_error_handling_overhead(self, mock_config):
        """Test overhead of async error handling."""
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            tracer = LangfuseTracer(mock_config)
            tracer.current_trace = Mock()
            tracer.current_trace.span = Mock(return_value=Mock())
            
            # Measure error handling overhead
            num_errors = 200
            start_time = time.time()
            
            for i in range(num_errors):
                error = ValueError(f"Test error {i}")
                await tracer.handle_async_error(
                    error,
                    node_id=f"node_{i}",
                    flow_name=f"Flow_{i}"
                )
            
            error_handling_time = time.time() - start_time
            
            # Should be reasonably fast
            assert error_handling_time < 5.0  # Less than 5 seconds for 200 errors
            assert len(tracer.get_error_handler().error_events) == num_errors
    
    @pytest.mark.asyncio
    async def test_concurrent_async_operations_performance(self, mock_config):
        """Test performance with many concurrent async operations."""
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            tracer = LangfuseTracer(mock_config)
            tracer.current_trace = Mock()
            tracer.current_trace.span = Mock(return_value=Mock())
            
            async def async_operation(operation_id):
                """Simulate an async operation with tracing."""
                # Start lifecycle
                await tracer.start_async_node_lifecycle(f"op_{operation_id}", "AsyncOp")
                
                # Simulate work
                await asyncio.sleep(0.01)
                
                # Transition states
                await tracer.transition_async_node_state(f"op_{operation_id}", "running")
                await asyncio.sleep(0.01)
                await tracer.transition_async_node_state(f"op_{operation_id}", "completed")
                
                return f"result_{operation_id}"
            
            # Run many concurrent operations
            num_operations = 100
            start_time = time.time()
            
            results = await asyncio.gather(*[
                async_operation(i) for i in range(num_operations)
            ])
            
            concurrent_time = time.time() - start_time
            
            # Should complete in reasonable time
            assert concurrent_time < 5.0  # Less than 5 seconds for 100 concurrent operations
            assert len(results) == num_operations
            assert all(f"result_{i}" in results for i in range(num_operations))


class TestBackwardCompatibility:
    """Test backward compatibility with existing synchronous code."""
    
    def test_sync_tracing_still_works(self, mock_config):
        """Test that synchronous tracing still works after async enhancements."""
        
        @trace_flow(config=mock_config, flow_name="SyncCompatibilityFlow")
        class SyncCompatibilityFlow(MockSyncFlow):
            def __init__(self):
                node = MockSyncNode("CompatNode")
                super().__init__(start_node=node)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            flow = SyncCompatibilityFlow()
            shared = {"input": "sync_test"}
            
            # Should work exactly as before
            result = flow.run(shared)
            
            assert result == "default"
            assert "output_CompatNode" in shared
            assert shared["output_CompatNode"] == "processed_prep_CompatNode"
    
    def test_mixed_sync_async_flows(self, mock_config):
        """Test mixed synchronous and asynchronous flows."""
        
        @trace_flow(config=mock_config, flow_name="MixedSyncFlow")
        class MixedSyncFlow(MockSyncFlow):
            def __init__(self):
                node1 = MockSyncNode("SyncNode1")
                node2 = MockSyncNode("SyncNode2")
                node1.next(node2)
                super().__init__(start_node=node1)
        
        @trace_flow(config=mock_config, flow_name="MixedAsyncFlow")
        class MixedAsyncFlow:
            def __init__(self):
                self.node = MockAsyncNode("AsyncNode", delay=0.01)
            
            async def run_async(self, shared):
                return await self.node._run_async(shared)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            # Run sync flow
            sync_flow = MixedSyncFlow()
            sync_shared = {"input": "sync_mixed"}
            sync_result = sync_flow.run(sync_shared)
            
            # Run async flow
            async def run_async_flow():
                async_flow = MixedAsyncFlow()
                async_shared = {"input": "async_mixed"}
                return await async_flow.run_async(async_shared)
            
            async_result = asyncio.run(run_async_flow())
            
            # Both should work
            assert sync_result == "default"
            assert async_result == "default"
            assert "output_SyncNode2" in sync_shared
            assert "output_AsyncNode" in asyncio.run(run_async_flow.__code__.co_consts[1])  # Access async_shared
    
    def test_sync_async_tracer_coexistence(self, mock_config):
        """Test that sync and async tracer features can coexist."""
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            tracer = LangfuseTracer(mock_config)
            tracer.current_trace = Mock()
            tracer.current_trace.span = Mock(return_value=Mock())
            
            # Use sync features
            sync_span_id = tracer.start_node_span("SyncNode", "sync_1", "exec")
            tracer.end_node_span(sync_span_id, output_data="sync_result")
            
            # Use async features
            async def use_async_features():
                async_span_id = await tracer.start_node_span_async("AsyncNode", "async_1", "exec")
                await tracer.end_node_span_async(async_span_id, output_data="async_result")
                
                # Start lifecycle
                await tracer.start_async_node_lifecycle("lifecycle_node", "LifecycleNode")
                
                # Handle error
                await tracer.handle_async_error(ValueError("Test error"), "error_node", "ErrorFlow")
            
            asyncio.run(use_async_features())
            
            # Both sync and async features should work without interference
            assert tracer.lifecycle_manager is not None
            assert tracer.error_handler is not None
    
    def test_thread_safety_with_async(self, mock_config):
        """Test thread safety when using async features."""
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            tracer = LangfuseTracer(mock_config)
            tracer.current_trace = Mock()
            tracer.current_trace.span = Mock(return_value=Mock())
            
            results = []
            
            def sync_worker(worker_id):
                """Synchronous worker function."""
                for i in range(10):
                    span_id = tracer.start_node_span(f"SyncNode_{worker_id}", f"sync_{worker_id}_{i}", "exec")
                    tracer.end_node_span(span_id, output_data=f"sync_result_{worker_id}_{i}")
                    time.sleep(0.001)
                results.append(f"sync_worker_{worker_id}_done")
            
            async def async_worker(worker_id):
                """Asynchronous worker function."""
                for i in range(10):
                    span_id = await tracer.start_node_span_async(f"AsyncNode_{worker_id}", f"async_{worker_id}_{i}", "exec")
                    await tracer.end_node_span_async(span_id, output_data=f"async_result_{worker_id}_{i}")
                    await asyncio.sleep(0.001)
                results.append(f"async_worker_{worker_id}_done")
            
            # Run sync workers in threads
            with ThreadPoolExecutor(max_workers=3) as executor:
                sync_futures = [executor.submit(sync_worker, i) for i in range(3)]
                
                # Run async workers
                async def run_async_workers():
                    await asyncio.gather(*[async_worker(i) for i in range(3)])
                
                asyncio.run(run_async_workers())
                
                # Wait for sync workers
                for future in sync_futures:
                    future.result()
            
            # All workers should complete
            assert len(results) == 6
            assert sum(1 for r in results if "sync_worker" in r) == 3
            assert sum(1 for r in results if "async_worker" in r) == 3


class TestPerformanceRegression:
    """Test for performance regressions in async tracing."""
    
    @pytest.mark.asyncio
    async def test_no_significant_overhead_vs_untraced(self, mock_config):
        """Test that tracing doesn't add significant overhead."""
        
        # Untraced async operation
        async def untraced_operation():
            node = MockAsyncNode("UnTracedNode", delay=0.001)
            shared = {"input": "untraced_test"}
            return await node._run_async(shared)
        
        # Traced async operation
        @trace_flow(config=mock_config, flow_name="TracedOperation")
        class TracedOperation:
            def __init__(self):
                self.node = MockAsyncNode("TracedNode", delay=0.001)
            
            async def run_async(self, shared):
                return await self.node._run_async(shared)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            # Measure untraced performance
            num_operations = 50
            
            start_time = time.time()
            untraced_results = await asyncio.gather(*[
                untraced_operation() for _ in range(num_operations)
            ])
            untraced_time = time.time() - start_time
            
            # Measure traced performance
            start_time = time.time()
            traced_operations = [TracedOperation() for _ in range(num_operations)]
            traced_results = await asyncio.gather(*[
                op.run_async({"input": "traced_test"}) for op in traced_operations
            ])
            traced_time = time.time() - start_time
            
            # Tracing overhead should be reasonable (less than 3x slower)
            overhead_ratio = traced_time / untraced_time if untraced_time > 0 else 1
            assert overhead_ratio < 3.0, f"Tracing overhead too high: {overhead_ratio}x"
            
            # Both should produce correct results
            assert len(untraced_results) == num_operations
            assert len(traced_results) == num_operations
    
    def test_memory_usage_stability(self, mock_config):
        """Test that memory usage remains stable with async tracing."""
        import gc
        import psutil
        import os
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss
            
            # Create and use many tracers
            tracers = []
            for i in range(100):
                tracer = LangfuseTracer(mock_config)
                tracer.current_trace = Mock()
                tracer.current_trace.span = Mock(return_value=Mock())
                
                # Use async features
                async def use_tracer():
                    await tracer.start_async_node_lifecycle(f"node_{i}", f"Node_{i}")
                    await tracer.handle_async_error(ValueError(f"Error {i}"), f"node_{i}", f"Flow_{i}")
                
                asyncio.run(use_tracer())
                tracers.append(tracer)
            
            # Force garbage collection
            gc.collect()
            
            # Check memory usage
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (less than 100MB)
            assert memory_increase < 100 * 1024 * 1024, f"Memory usage increased by {memory_increase / 1024 / 1024:.2f}MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

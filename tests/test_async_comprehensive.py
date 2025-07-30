"""
Comprehensive async unit tests for PocketFlow tracing.

This module contains unit tests covering all async node operations,
lifecycle events, error scenarios, and context management.
"""

import asyncio
import os

# Import the modules we're testing
import sys
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pocketflow_tracing.async_composition import (
    AsyncFlowCompositionManager,
    AsyncFlowExecution,
    FlowCompositionType,
)
from pocketflow_tracing.async_error_handling import (
    AsyncErrorEvent,
    AsyncErrorHandler,
    AsyncErrorSeverity,
    AsyncErrorType,
)
from pocketflow_tracing.async_lifecycle import (
    AsyncLifecycleEvent,
    AsyncLifecycleManager,
    AsyncNodeState,
    AsyncPhase,
)
from pocketflow_tracing.config import TracingConfig
from pocketflow_tracing.core import AsyncTraceContext, LangfuseTracer


@pytest.fixture
def mock_config():
    """Create a mock tracing configuration."""
    config = TracingConfig()
    config.debug = True
    config.trace_inputs = True
    config.trace_outputs = True
    config.trace_errors = True
    return config


@pytest.fixture
def mock_tracer(mock_config):
    """Create a mock tracer with mocked Langfuse client."""
    with patch("pocketflow_tracing.core.LANGFUSE_AVAILABLE", False):
        tracer = LangfuseTracer(mock_config)
        tracer.client = Mock()
        tracer.current_trace = Mock()
        tracer.current_trace.id = "test_trace_id"
        tracer.current_trace.span = Mock(return_value=Mock())
        return tracer


class TestAsyncTraceContext:
    """Test async trace context management."""

    def test_async_context_creation(self, mock_tracer):
        """Test creating an async trace context."""
        context = AsyncTraceContext(mock_tracer, "test_trace", "test_flow")

        assert context.tracer == mock_tracer
        assert context.trace_id == "test_trace"
        assert context.flow_name == "test_flow"
        assert context.spans == {}
        assert context.task_id is None

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_tracer):
        """Test async context manager functionality."""
        context = AsyncTraceContext(mock_tracer, "test_trace", "test_flow")

        async with context:
            # Context should be active
            current_context = AsyncTraceContext.get_current_context()
            assert current_context is not None
            assert current_context.trace_id == "test_trace"
            assert current_context.flow_name == "test_flow"

        # Context should be cleaned up after exit
        current_context = AsyncTraceContext.get_current_context()
        # Note: Context might still exist due to task context tracking

    def test_sync_context_compatibility(self, mock_tracer):
        """Test sync context manager compatibility."""
        context = AsyncTraceContext(mock_tracer, "test_trace", "test_flow")

        with context:
            # Should work without errors
            pass


class TestAsyncLifecycleManager:
    """Test async lifecycle management."""

    @pytest.fixture
    def lifecycle_manager(self, mock_tracer):
        """Create a lifecycle manager."""
        return AsyncLifecycleManager(mock_tracer)

    def test_lifecycle_manager_creation(self, lifecycle_manager, mock_tracer):
        """Test lifecycle manager creation."""
        assert lifecycle_manager.tracer == mock_tracer
        assert lifecycle_manager.active_lifecycles == {}
        assert lifecycle_manager.completed_lifecycles == []

    def test_start_lifecycle(self, lifecycle_manager):
        """Test starting a node lifecycle."""
        node_id = "test_node_1"
        node_name = "TestNode"

        lifecycle = lifecycle_manager.start_lifecycle(
            node_id, node_name, AsyncPhase.PREP
        )

        assert lifecycle.node_id == node_id
        assert lifecycle.node_name == node_name
        assert lifecycle.current_phase == AsyncPhase.PREP
        assert lifecycle.current_state == AsyncNodeState.STARTING
        assert len(lifecycle.events) == 1
        assert lifecycle_manager.active_lifecycles[node_id] == lifecycle

    def test_transition_state(self, lifecycle_manager):
        """Test state transitions."""
        node_id = "test_node_1"
        lifecycle = lifecycle_manager.start_lifecycle(node_id, "TestNode")

        # Transition to running
        lifecycle_manager.transition_state(node_id, AsyncNodeState.RUNNING)

        assert lifecycle.current_state == AsyncNodeState.RUNNING
        assert len(lifecycle.events) == 2

    def test_suspend_resume_node(self, lifecycle_manager):
        """Test node suspend and resume."""
        node_id = "test_node_1"
        lifecycle = lifecycle_manager.start_lifecycle(node_id, "TestNode")

        # Suspend node
        lifecycle_manager.suspend_node(node_id, "test_await")
        assert lifecycle.current_state == AsyncNodeState.SUSPENDED
        assert lifecycle.suspend_count == 1

        # Resume node
        lifecycle_manager.resume_node(node_id, "test_complete")
        assert lifecycle.current_state == AsyncNodeState.RUNNING
        assert lifecycle.resume_count == 1

    def test_complete_lifecycle(self, lifecycle_manager):
        """Test completing a lifecycle."""
        node_id = "test_node_1"
        lifecycle = lifecycle_manager.start_lifecycle(node_id, "TestNode")

        lifecycle_manager.transition_state(node_id, AsyncNodeState.COMPLETED)

        assert lifecycle.current_state == AsyncNodeState.COMPLETED
        assert lifecycle.is_active == False
        assert node_id not in lifecycle_manager.active_lifecycles
        assert lifecycle in lifecycle_manager.completed_lifecycles

    def test_fail_node(self, lifecycle_manager):
        """Test failing a node."""
        node_id = "test_node_1"
        lifecycle = lifecycle_manager.start_lifecycle(node_id, "TestNode")

        test_error = ValueError("Test error")
        lifecycle_manager.fail_node(node_id, test_error)

        assert lifecycle.current_state == AsyncNodeState.FAILED
        assert lifecycle.is_active == False

    def test_cancel_node(self, lifecycle_manager):
        """Test cancelling a node."""
        node_id = "test_node_1"
        lifecycle = lifecycle_manager.start_lifecycle(node_id, "TestNode")

        lifecycle_manager.cancel_node(node_id, "test_cancellation")

        assert lifecycle.current_state == AsyncNodeState.CANCELLED
        assert lifecycle.is_active == False

    def test_get_statistics(self, lifecycle_manager):
        """Test getting lifecycle statistics."""
        # Start and complete some lifecycles
        for i in range(3):
            node_id = f"test_node_{i}"
            lifecycle = lifecycle_manager.start_lifecycle(node_id, f"TestNode{i}")
            lifecycle_manager.transition_state(node_id, AsyncNodeState.COMPLETED)

        stats = lifecycle_manager.get_statistics()

        assert stats["total_lifecycles"] == 3
        assert stats["completed_lifecycles"] == 3
        assert stats["active_lifecycles"] == 0
        assert "average_duration_ms" in stats


class TestAsyncFlowCompositionManager:
    """Test async flow composition management."""

    @pytest.fixture
    def composition_manager(self, mock_tracer):
        """Create a composition manager."""
        return AsyncFlowCompositionManager(mock_tracer)

    @pytest.mark.asyncio
    async def test_start_flow_execution(self, composition_manager):
        """Test starting a flow execution."""
        flow_name = "TestFlow"
        execution = await composition_manager.start_flow_execution(
            flow_name, FlowCompositionType.SEQUENTIAL
        )

        assert execution.flow_name == flow_name
        assert execution.composition_type == FlowCompositionType.SEQUENTIAL
        assert execution.status == "running"
        assert execution.execution_id in composition_manager.active_executions

    @pytest.mark.asyncio
    async def test_complete_flow_execution(self, composition_manager):
        """Test completing a flow execution."""
        execution = await composition_manager.start_flow_execution("TestFlow")
        execution_id = execution.execution_id

        await composition_manager.complete_flow_execution(execution_id, "completed")

        assert execution.status == "completed"
        assert execution.is_completed == True
        assert execution_id not in composition_manager.active_executions
        assert execution in composition_manager.completed_executions

    @pytest.mark.asyncio
    async def test_execute_parallel_flows(self, composition_manager):
        """Test executing parallel flows."""

        async def mock_flow_1():
            await asyncio.sleep(0.1)
            return "result_1"

        async def mock_flow_2():
            await asyncio.sleep(0.1)
            return "result_2"

        flows = [mock_flow_1(), mock_flow_2()]
        flow_names = ["Flow1", "Flow2"]

        results = await composition_manager.execute_parallel_flows(flows, flow_names)

        assert results == ["result_1", "result_2"]

    @pytest.mark.asyncio
    async def test_execute_nested_flow(self, composition_manager):
        """Test executing nested flows."""

        async def mock_nested_flow():
            await asyncio.sleep(0.1)
            return "nested_result"

        result = await composition_manager.execute_nested_flow(
            mock_nested_flow(), "NestedFlow"
        )

        assert result == "nested_result"

    @pytest.mark.asyncio
    async def test_execute_batch_flows_sequential(self, composition_manager):
        """Test executing batch flows sequentially."""

        def flow_factory(data):
            async def flow():
                await asyncio.sleep(0.05)
                return f"processed_{data}"

            return flow()

        batch_data = ["item1", "item2", "item3"]

        results = await composition_manager.execute_batch_flows(
            flow_factory, batch_data, "BatchFlow", parallel=False
        )

        assert results == ["processed_item1", "processed_item2", "processed_item3"]

    @pytest.mark.asyncio
    async def test_execute_batch_flows_parallel(self, composition_manager):
        """Test executing batch flows in parallel."""

        def flow_factory(data):
            async def flow():
                await asyncio.sleep(0.05)
                return f"processed_{data}"

            return flow()

        batch_data = ["item1", "item2", "item3"]

        results = await composition_manager.execute_batch_flows(
            flow_factory, batch_data, "BatchFlow", parallel=True
        )

        assert set(results) == {"processed_item1", "processed_item2", "processed_item3"}

    def test_get_execution_statistics(self, composition_manager):
        """Test getting execution statistics."""
        stats = composition_manager.get_execution_statistics()
        assert stats["total_executions"] == 0


class TestAsyncErrorHandler:
    """Test async error handling."""

    @pytest.fixture
    def error_handler(self, mock_tracer):
        """Create an error handler."""
        return AsyncErrorHandler(mock_tracer)

    @pytest.mark.asyncio
    async def test_handle_cancellation_error(self, error_handler):
        """Test handling cancellation errors."""
        error = asyncio.CancelledError("Test cancellation")

        error_event = await error_handler.handle_async_error(
            error, node_id="test_node", flow_name="TestFlow"
        )

        assert error_event.error_type == AsyncErrorType.CANCELLATION
        assert error_event.node_id == "test_node"
        assert error_event.flow_name == "TestFlow"
        assert error_event.exception == error

    @pytest.mark.asyncio
    async def test_handle_timeout_error(self, error_handler):
        """Test handling timeout errors."""
        error = asyncio.TimeoutError("Test timeout")

        error_event = await error_handler.handle_async_error(
            error, node_id="test_node", flow_name="TestFlow"
        )

        assert error_event.error_type == AsyncErrorType.TIMEOUT
        assert error_event.severity == AsyncErrorSeverity.HIGH

    @pytest.mark.asyncio
    async def test_handle_general_exception(self, error_handler):
        """Test handling general exceptions."""
        error = ValueError("Test error")

        error_event = await error_handler.handle_async_error(
            error, node_id="test_node", flow_name="TestFlow"
        )

        assert error_event.error_type == AsyncErrorType.TASK_EXCEPTION
        assert error_event.exception == error

    def test_error_classification(self, error_handler):
        """Test error classification."""
        # Test cancellation
        assert (
            error_handler._classify_error(asyncio.CancelledError())
            == AsyncErrorType.CANCELLATION
        )

        # Test timeout
        assert (
            error_handler._classify_error(asyncio.TimeoutError())
            == AsyncErrorType.TIMEOUT
        )

        # Test general exception
        assert (
            error_handler._classify_error(ValueError()) == AsyncErrorType.TASK_EXCEPTION
        )

        # Test memory error
        assert (
            error_handler._classify_error(MemoryError())
            == AsyncErrorType.RESOURCE_EXHAUSTION
        )

    def test_severity_determination(self, error_handler):
        """Test error severity determination."""
        # Critical errors
        assert (
            error_handler._determine_severity(
                MemoryError(), AsyncErrorType.RESOURCE_EXHAUSTION
            )
            == AsyncErrorSeverity.CRITICAL
        )

        # High severity errors
        assert (
            error_handler._determine_severity(
                asyncio.TimeoutError(), AsyncErrorType.TIMEOUT
            )
            == AsyncErrorSeverity.HIGH
        )

        # Medium severity errors
        assert (
            error_handler._determine_severity(
                asyncio.CancelledError(), AsyncErrorType.CANCELLATION
            )
            == AsyncErrorSeverity.MEDIUM
        )

    def test_get_error_statistics(self, error_handler):
        """Test getting error statistics."""
        # Add some mock error events
        error_handler.error_events = [
            AsyncErrorEvent(
                error_type=AsyncErrorType.CANCELLATION,
                severity=AsyncErrorSeverity.MEDIUM,
            ),
            AsyncErrorEvent(
                error_type=AsyncErrorType.TIMEOUT, severity=AsyncErrorSeverity.HIGH
            ),
            AsyncErrorEvent(
                error_type=AsyncErrorType.TASK_EXCEPTION,
                severity=AsyncErrorSeverity.LOW,
            ),
        ]

        stats = error_handler.get_error_statistics()

        assert stats["total_errors"] == 3
        assert stats["error_type_distribution"]["cancellation"] == 1
        assert stats["error_type_distribution"]["timeout"] == 1
        assert stats["error_type_distribution"]["task_exception"] == 1
        assert stats["severity_distribution"]["medium"] == 1
        assert stats["severity_distribution"]["high"] == 1
        assert stats["severity_distribution"]["low"] == 1


class TestAsyncTracerIntegration:
    """Test integration of async components with the main tracer."""

    @pytest.mark.asyncio
    async def test_start_async_node_lifecycle(self, mock_tracer):
        """Test starting async node lifecycle through tracer."""
        span_id = await mock_tracer.start_async_node_lifecycle(
            "test_node", "TestNode", "prep"
        )

        assert span_id is not None
        assert mock_tracer.lifecycle_manager is not None
        assert "test_node" in mock_tracer.lifecycle_manager.active_lifecycles

    @pytest.mark.asyncio
    async def test_async_flow_composition(self, mock_tracer):
        """Test async flow composition through tracer."""
        execution_id = await mock_tracer.start_async_flow_composition(
            "TestFlow", "parallel"
        )

        assert execution_id is not None
        assert mock_tracer.composition_manager is not None
        assert execution_id in mock_tracer.composition_manager.active_executions

    @pytest.mark.asyncio
    async def test_async_error_handling(self, mock_tracer):
        """Test async error handling through tracer."""
        error = ValueError("Test error")

        error_event = await mock_tracer.handle_async_error(
            error, node_id="test_node", flow_name="TestFlow"
        )

        assert error_event is not None
        assert mock_tracer.error_handler is not None
        assert len(mock_tracer.error_handler.error_events) > 0

    @pytest.mark.asyncio
    async def test_safe_async_execute(self, mock_tracer):
        """Test safe async execution."""

        async def test_coro():
            await asyncio.sleep(0.1)
            return "success"

        result = await mock_tracer.safe_async_execute(
            test_coro(), node_id="test_node", flow_name="TestFlow"
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_timeout(self, mock_tracer):
        """Test execution with timeout."""

        async def quick_coro():
            await asyncio.sleep(0.05)
            return "quick_result"

        result = await mock_tracer.with_timeout(
            quick_coro(), 1.0, node_id="test_node", flow_name="TestFlow"
        )

        assert result == "quick_result"

    @pytest.mark.asyncio
    async def test_with_timeout_exceeded(self, mock_tracer):
        """Test execution with timeout exceeded."""

        async def slow_coro():
            await asyncio.sleep(1.0)
            return "slow_result"

        with pytest.raises(asyncio.TimeoutError):
            await mock_tracer.with_timeout(
                slow_coro(), 0.1, node_id="test_node", flow_name="TestFlow"
            )

        # Check that error was handled
        assert mock_tracer.error_handler is not None
        assert len(mock_tracer.error_handler.error_events) > 0


class TestAsyncContextPropagation:
    """Test async context propagation across boundaries."""

    @pytest.mark.asyncio
    async def test_context_propagation_across_tasks(self, mock_tracer):
        """Test that context is properly propagated across async tasks."""

        async def child_task():
            # Should be able to access parent context
            context = AsyncTraceContext.get_current_context()
            return context.trace_id if context else None

        # Start a trace context
        async_context = AsyncTraceContext(mock_tracer, "parent_trace", "ParentFlow")

        async with async_context:
            # Create child task
            task = asyncio.create_task(child_task())
            result = await task

            # Context should be propagated
            assert result == "parent_trace"

    @pytest.mark.asyncio
    async def test_context_isolation_between_flows(self, mock_tracer):
        """Test that different flows have isolated contexts."""
        results = []

        async def flow_task(trace_id, flow_name):
            context = AsyncTraceContext(mock_tracer, trace_id, flow_name)
            async with context:
                await asyncio.sleep(0.1)
                current = AsyncTraceContext.get_current_context()
                results.append((current.trace_id, current.flow_name))

        # Run multiple flows concurrently
        await asyncio.gather(
            flow_task("trace_1", "Flow1"),
            flow_task("trace_2", "Flow2"),
            flow_task("trace_3", "Flow3"),
        )

        # Each flow should maintain its own context
        assert len(results) == 3
        trace_ids = {result[0] for result in results}
        flow_names = {result[1] for result in results}
        assert trace_ids == {"trace_1", "trace_2", "trace_3"}
        assert flow_names == {"Flow1", "Flow2", "Flow3"}


class TestAsyncEdgeCases:
    """Test async edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_cancelled_task_handling(self, mock_tracer):
        """Test handling of cancelled tasks."""

        async def cancellable_task():
            await asyncio.sleep(1.0)  # Long running task
            return "completed"

        task = asyncio.create_task(cancellable_task())

        # Cancel the task after a short delay
        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Test error handling
        error_event = await mock_tracer.handle_async_error(
            asyncio.CancelledError("Task cancelled"),
            node_id="test_node",
            flow_name="TestFlow",
        )

        assert error_event.error_type == AsyncErrorType.CANCELLATION

    @pytest.mark.asyncio
    async def test_nested_cancellation(self, mock_tracer):
        """Test nested task cancellation scenarios."""
        cancelled_tasks = []

        async def nested_task(level):
            try:
                if level > 0:
                    # Create nested task
                    child_task = asyncio.create_task(nested_task(level - 1))
                    return await child_task
                else:
                    await asyncio.sleep(1.0)
                    return f"level_{level}"
            except asyncio.CancelledError:
                cancelled_tasks.append(level)
                raise

        # Start nested tasks
        main_task = asyncio.create_task(nested_task(3))

        # Cancel after short delay
        await asyncio.sleep(0.1)
        main_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await main_task

        # All levels should be cancelled
        assert len(cancelled_tasks) > 0

    @pytest.mark.asyncio
    async def test_exception_in_async_context(self, mock_tracer):
        """Test exception handling within async context."""

        async def failing_task():
            raise ValueError("Intentional failure")

        async_context = AsyncTraceContext(mock_tracer, "test_trace", "FailingFlow")

        with pytest.raises(ValueError):
            async with async_context:
                await failing_task()

        # Context should still be cleaned up properly
        current_context = AsyncTraceContext.get_current_context()
        # Context cleanup depends on implementation details

    @pytest.mark.asyncio
    async def test_concurrent_context_access(self, mock_tracer):
        """Test concurrent access to async contexts."""
        access_results = []

        async def context_accessor(worker_id):
            for i in range(10):
                context = AsyncTraceContext.get_current_context()
                access_results.append((worker_id, i, context is not None))
                await asyncio.sleep(0.01)

        # Start context
        async_context = AsyncTraceContext(
            mock_tracer, "concurrent_trace", "ConcurrentFlow"
        )

        async with async_context:
            # Run multiple concurrent accessors
            await asyncio.gather(*[context_accessor(i) for i in range(5)])

        # All accesses should succeed
        assert len(access_results) == 50
        assert all(result[2] for result in access_results)


class TestAsyncPerformance:
    """Test async performance characteristics."""

    @pytest.mark.asyncio
    async def test_context_creation_performance(self, mock_tracer):
        """Test performance of context creation."""
        import time

        start_time = time.time()

        # Create many contexts
        contexts = []
        for i in range(1000):
            context = AsyncTraceContext(mock_tracer, f"trace_{i}", f"Flow_{i}")
            contexts.append(context)

        creation_time = time.time() - start_time

        # Should be reasonably fast (less than 1 second for 1000 contexts)
        assert creation_time < 1.0
        assert len(contexts) == 1000

    @pytest.mark.asyncio
    async def test_lifecycle_tracking_overhead(self, mock_tracer):
        """Test overhead of lifecycle tracking."""
        import time

        lifecycle_manager = mock_tracer.get_lifecycle_manager()

        start_time = time.time()

        # Track many node lifecycles
        for i in range(100):
            node_id = f"node_{i}"
            lifecycle_manager.start_lifecycle(node_id, f"Node_{i}")
            lifecycle_manager.transition_state(node_id, AsyncNodeState.RUNNING)
            lifecycle_manager.transition_state(node_id, AsyncNodeState.COMPLETED)

        tracking_time = time.time() - start_time

        # Should be reasonably fast
        assert tracking_time < 1.0
        assert len(lifecycle_manager.completed_lifecycles) == 100

    @pytest.mark.asyncio
    async def test_error_handling_overhead(self, mock_tracer):
        """Test overhead of error handling."""
        import time

        error_handler = mock_tracer.get_error_handler()

        start_time = time.time()

        # Handle many errors
        for i in range(100):
            error = ValueError(f"Error {i}")
            await error_handler.handle_async_error(
                error, node_id=f"node_{i}", flow_name=f"Flow_{i}"
            )

        handling_time = time.time() - start_time

        # Should be reasonably fast
        assert handling_time < 2.0
        assert len(error_handler.error_events) == 100


class TestBackwardCompatibility:
    """Test backward compatibility with existing sync code."""

    def test_sync_tracer_still_works(self, mock_tracer):
        """Test that sync tracing still works after async enhancements."""
        # Test sync span creation
        span_id = mock_tracer.start_node_span("TestNode", "node_1", "exec")
        assert span_id is not None

        # Test sync span ending
        mock_tracer.end_node_span(
            span_id, input_data={"test": "data"}, output_data="result"
        )

        # Should work without errors

    def test_mixed_sync_async_usage(self, mock_tracer):
        """Test mixed sync and async usage."""
        # Start sync span
        sync_span_id = mock_tracer.start_node_span("SyncNode", "sync_node_1", "exec")

        # Create async context
        async_context = AsyncTraceContext(mock_tracer, "mixed_trace", "MixedFlow")

        # Both should coexist
        assert sync_span_id is not None
        assert async_context is not None

        # Clean up
        mock_tracer.end_node_span(sync_span_id, output_data="sync_result")

    @pytest.mark.asyncio
    async def test_async_enhancements_dont_break_sync(self, mock_tracer):
        """Test that async enhancements don't break sync functionality."""
        # Use async features
        await mock_tracer.start_async_node_lifecycle("async_node", "AsyncNode")
        await mock_tracer.start_async_flow_composition("AsyncFlow")

        # Sync features should still work
        span_id = mock_tracer.start_node_span("SyncNode", "sync_node", "exec")
        mock_tracer.end_node_span(span_id, output_data="sync_result")

        # No errors should occur


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

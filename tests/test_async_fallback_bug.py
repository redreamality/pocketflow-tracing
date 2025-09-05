"""
Test for the missing _traced_run_async_fallback method bug.

This test demonstrates the AttributeError that occurs when the @trace_flow
decorator fails to assign the _traced_run_async_fallback method to the
decorated class, causing failures when async context creation fails.
"""

import asyncio
import pytest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pocketflow_tracing import trace_flow, TracingConfig


# Mock PocketFlow AsyncFlow for testing
class MockAsyncFlow:
    """Mock async flow that mimics PocketFlow's AsyncFlow interface."""
    
    def __init__(self):
        self.params = {}
        self.flow_name = "MockFlow"
    
    async def prep_async(self, shared):
        """Mock prep phase."""
        await asyncio.sleep(0.01)  # Simulate async work
        return {"prep": "completed"}
    
    async def post_async(self, shared, prep_res, exec_res):
        """Mock post phase."""
        await asyncio.sleep(0.01)  # Simulate async work
        shared["post_result"] = "completed"
        return exec_res
    
    async def _orch_async(self, shared, params=None):
        """Mock orchestration phase."""
        await asyncio.sleep(0.05)  # Simulate async work
        shared["orchestration"] = "completed"
        return "orchestration_result"
    
    async def _run_async(self, shared):
        """Mock internal run method."""
        prep_res = await self.prep_async(shared)
        exec_res = await self._orch_async(shared)
        return await self.post_async(shared, prep_res, exec_res)
    
    async def run_async(self, shared):
        """Public run method."""
        return await self._run_async(shared)


class TestAsyncFallbackFunctionality:
    """Test cases that verify the async fallback functionality works correctly."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock tracing configuration."""
        config = TracingConfig()
        config.debug = True
        config.trace_inputs = True
        config.trace_outputs = True
        config.trace_errors = True
        return config

    def test_fallback_method_is_assigned(self, mock_config):
        """Test that the _traced_run_async_fallback method is properly assigned to the class."""
        
        @trace_flow(config=mock_config, flow_name="TestFlow")
        class TracedFlow(MockAsyncFlow):
            def __init__(self):
                super().__init__()

        flow = TracedFlow()
        
        # The method should exist and be callable
        assert hasattr(flow, '_traced_run_async_fallback'), \
            "_traced_run_async_fallback method should be assigned to the class"
        assert callable(getattr(flow, '_traced_run_async_fallback')), \
            "_traced_run_async_fallback should be callable"

    def test_decorator_assigns_all_required_methods(self, mock_config):
        """Test that the decorator assigns all required methods including the fallback."""
        
        @trace_flow(config=mock_config, flow_name="TestFlow")
        class TracedFlow(MockAsyncFlow):
            def __init__(self):
                super().__init__()

        flow = TracedFlow()
        
        # All these methods should be assigned by the decorator
        expected_methods = [
            '_patch_nodes',
            '_patch_node', 
            '_create_traced_method',
            '_create_traced_async_method',
            '_execute_with_lifecycle_tracking',
            '_traced_run_async_fallback'  # This should now be included
        ]
        
        for method in expected_methods:
            assert hasattr(flow, method), f"Expected method {method} not found"

    @pytest.mark.asyncio
    async def test_fallback_mechanism_works(self, mock_config):
        """Test that the fallback mechanism works correctly when async context creation fails."""
        
        @trace_flow(config=mock_config, flow_name="TestFlow")
        class TracedFlow(MockAsyncFlow):
            def __init__(self):
                super().__init__()

        flow = TracedFlow()
        shared = {"input": "test_data"}

        # Mock start_trace_async to return None (triggering fallback)
        with patch.object(flow._tracer, 'start_trace_async', return_value=None):
            with patch.object(flow._tracer, 'start_trace', return_value="mock_trace_id"):
                with patch.object(flow._tracer, 'end_trace'):
                    with patch.object(flow._tracer, 'flush_async', new_callable=AsyncMock):
                        # This should work via fallback mechanism
                        result = await flow.run_async(shared)
                        
                        # Verify the flow executed correctly via fallback
                        assert "orchestration" in shared
                        assert shared["orchestration"] == "completed"
                        assert "post_result" in shared
                        assert shared["post_result"] == "completed"

    @pytest.mark.asyncio
    async def test_successful_async_context_bypasses_fallback(self, mock_config):
        """Test that when async context creation succeeds, the normal path is taken."""
        
        @trace_flow(config=mock_config, flow_name="TestFlow")
        class TracedFlow(MockAsyncFlow):
            def __init__(self):
                super().__init__()

        flow = TracedFlow()
        shared = {"input": "test_data"}

        # Mock successful async context creation
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_context)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        with patch.object(flow._tracer, 'start_trace_async', return_value=mock_context):
            with patch.object(flow._tracer, 'end_trace'):
                with patch.object(flow._tracer, 'flush_async', new_callable=AsyncMock):
                    # This should work through the normal async context path
                    result = await flow.run_async(shared)
                    
                    # Verify the flow executed correctly
                    assert "orchestration" in shared
                    assert shared["orchestration"] == "completed"

    def test_sync_flows_not_affected(self, mock_config):
        """Test that sync flows continue to work normally."""
        
        class MockSyncFlow:
            """Mock sync flow."""
            
            def __init__(self):
                self.params = {}
            
            def run(self, shared):
                shared["sync_result"] = "completed"
                return "sync_completed"

        @trace_flow(config=mock_config, flow_name="SyncTestFlow")
        class TracedSyncFlow(MockSyncFlow):
            def __init__(self):
                super().__init__()

        flow = TracedSyncFlow()
        shared = {"input": "test_data"}

        # Mock the tracer methods
        with patch.object(flow._tracer, 'start_trace', return_value="mock_trace_id"):
            with patch.object(flow._tracer, 'end_trace'):
                # Sync flows should work normally
                result = flow.run(shared)
                
                assert result == "sync_completed"
                assert shared["sync_result"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

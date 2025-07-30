"""
Async integration tests for PocketFlow tracing.

This module contains integration tests demonstrating real-world async usage
patterns including concurrent flows, nested execution, and performance scenarios.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch

# Import the modules we're testing
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pocketflow_tracing import trace_flow, TracingConfig, LangfuseTracer
from pocketflow_tracing.decorator import _trace_flow_class


# Mock PocketFlow classes for testing
class MockAsyncNode:
    """Mock async node for testing."""
    
    def __init__(self, name="MockAsyncNode"):
        self.name = name
        self.params = {}
        self.successors = {}
    
    def set_params(self, params):
        self.params = params
    
    def next(self, node, action="default"):
        self.successors[action] = node
        return node
    
    async def prep_async(self, shared):
        await asyncio.sleep(0.05)  # Simulate async work
        return shared.get("input", f"prep_{self.name}")
    
    async def exec_async(self, prep_res):
        await asyncio.sleep(0.1)  # Simulate async work
        return f"processed_{prep_res}"
    
    async def post_async(self, shared, prep_res, exec_res):
        await asyncio.sleep(0.02)  # Simulate async work
        shared[f"output_{self.name}"] = exec_res
        return "default"
    
    async def _run_async(self, shared):
        prep_res = await self.prep_async(shared)
        exec_res = await self.exec_async(prep_res)
        return await self.post_async(shared, prep_res, exec_res)


class MockAsyncFlow:
    """Mock async flow for testing."""
    
    def __init__(self, start_node=None):
        self.start_node = start_node
        self.params = {}
    
    def start(self, node):
        self.start_node = node
        return node
    
    async def prep_async(self, shared):
        await asyncio.sleep(0.01)
        return {}
    
    async def post_async(self, shared, prep_res, exec_res):
        await asyncio.sleep(0.01)
        return exec_res
    
    async def _orch_async(self, shared, params=None):
        """Orchestrate async flow execution."""
        if not self.start_node:
            return None
        
        current = self.start_node
        last_action = None
        
        while current:
            current.set_params(params or self.params)
            last_action = await current._run_async(shared)
            
            # Get next node
            next_node = current.successors.get(last_action or "default")
            current = next_node
        
        return last_action
    
    async def _run_async(self, shared):
        prep_res = await self.prep_async(shared)
        exec_res = await self._orch_async(shared)
        return await self.post_async(shared, prep_res, exec_res)
    
    async def run_async(self, shared):
        return await self._run_async(shared)


@pytest.fixture
def mock_config():
    """Create a mock tracing configuration."""
    config = TracingConfig()
    config.debug = True
    config.trace_inputs = True
    config.trace_outputs = True
    config.trace_errors = True
    return config


class TestRealWorldAsyncPatterns:
    """Test real-world async usage patterns."""
    
    @pytest.mark.asyncio
    async def test_simple_async_flow_tracing(self, mock_config):
        """Test tracing a simple async flow."""
        
        # Create traced async flow
        @trace_flow(config=mock_config, flow_name="SimpleAsyncFlow")
        class SimpleAsyncFlow(MockAsyncFlow):
            def __init__(self):
                node = MockAsyncNode("SimpleNode")
                super().__init__(start_node=node)
        
        # Mock Langfuse to avoid external dependencies
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            flow = SimpleAsyncFlow()
            shared = {"input": "test_data"}
            
            # Execute the flow
            result = await flow.run_async(shared)
            
            # Verify execution
            assert "output_SimpleNode" in shared
            assert shared["output_SimpleNode"] == "processed_prep_SimpleNode"
            assert result == "default"
    
    @pytest.mark.asyncio
    async def test_multi_node_async_flow(self, mock_config):
        """Test tracing a multi-node async flow."""
        
        @trace_flow(config=mock_config, flow_name="MultiNodeAsyncFlow")
        class MultiNodeAsyncFlow(MockAsyncFlow):
            def __init__(self):
                node1 = MockAsyncNode("Node1")
                node2 = MockAsyncNode("Node2")
                node3 = MockAsyncNode("Node3")
                
                # Chain nodes
                node1.next(node2)
                node2.next(node3)
                
                super().__init__(start_node=node1)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            flow = MultiNodeAsyncFlow()
            shared = {"input": "multi_node_test"}
            
            result = await flow.run_async(shared)
            
            # All nodes should have executed
            assert "output_Node1" in shared
            assert "output_Node2" in shared
            assert "output_Node3" in shared
    
    @pytest.mark.asyncio
    async def test_concurrent_async_flows(self, mock_config):
        """Test concurrent execution of multiple async flows."""
        
        @trace_flow(config=mock_config, flow_name="ConcurrentFlow")
        class ConcurrentFlow(MockAsyncFlow):
            def __init__(self, node_name):
                node = MockAsyncNode(node_name)
                super().__init__(start_node=node)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            # Create multiple flows
            flows = [ConcurrentFlow(f"Flow{i}") for i in range(5)]
            shared_data = [{"input": f"data_{i}"} for i in range(5)]
            
            # Execute concurrently
            start_time = time.time()
            results = await asyncio.gather(*[
                flow.run_async(shared) 
                for flow, shared in zip(flows, shared_data)
            ])
            execution_time = time.time() - start_time
            
            # Verify all flows completed
            assert len(results) == 5
            assert all(result == "default" for result in results)
            
            # Should be faster than sequential execution
            assert execution_time < 1.0  # Should complete in less than 1 second
    
    @pytest.mark.asyncio
    async def test_nested_async_flows(self, mock_config):
        """Test nested async flow execution."""
        
        @trace_flow(config=mock_config, flow_name="InnerFlow")
        class InnerFlow(MockAsyncFlow):
            def __init__(self):
                node = MockAsyncNode("InnerNode")
                super().__init__(start_node=node)
        
        @trace_flow(config=mock_config, flow_name="OuterFlow")
        class OuterFlow(MockAsyncFlow):
            def __init__(self):
                node = MockAsyncNode("OuterNode")
                super().__init__(start_node=node)
            
            async def _orch_async(self, shared, params=None):
                # Execute outer node
                await super()._orch_async(shared, params)
                
                # Execute nested flow
                inner_flow = InnerFlow()
                await inner_flow.run_async(shared)
                
                return "nested_complete"
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            flow = OuterFlow()
            shared = {"input": "nested_test"}
            
            result = await flow.run_async(shared)
            
            # Both outer and inner nodes should have executed
            assert "output_OuterNode" in shared
            assert "output_InnerNode" in shared
            assert result == "nested_complete"
    
    @pytest.mark.asyncio
    async def test_async_flow_with_errors(self, mock_config):
        """Test async flow error handling."""
        
        class FailingAsyncNode(MockAsyncNode):
            async def exec_async(self, prep_res):
                await asyncio.sleep(0.05)
                raise ValueError("Intentional test failure")
        
        @trace_flow(config=mock_config, flow_name="FailingAsyncFlow")
        class FailingAsyncFlow(MockAsyncFlow):
            def __init__(self):
                node = FailingAsyncNode("FailingNode")
                super().__init__(start_node=node)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            flow = FailingAsyncFlow()
            shared = {"input": "error_test"}
            
            # Should raise the error
            with pytest.raises(ValueError, match="Intentional test failure"):
                await flow.run_async(shared)
    
    @pytest.mark.asyncio
    async def test_async_flow_cancellation(self, mock_config):
        """Test async flow cancellation handling."""
        
        class SlowAsyncNode(MockAsyncNode):
            async def exec_async(self, prep_res):
                await asyncio.sleep(2.0)  # Long running operation
                return f"slow_processed_{prep_res}"
        
        @trace_flow(config=mock_config, flow_name="SlowAsyncFlow")
        class SlowAsyncFlow(MockAsyncFlow):
            def __init__(self):
                node = SlowAsyncNode("SlowNode")
                super().__init__(start_node=node)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            flow = SlowAsyncFlow()
            shared = {"input": "cancellation_test"}
            
            # Start the flow
            task = asyncio.create_task(flow.run_async(shared))
            
            # Cancel after short delay
            await asyncio.sleep(0.1)
            task.cancel()
            
            # Should raise CancelledError
            with pytest.raises(asyncio.CancelledError):
                await task


class TestAsyncPerformanceScenarios:
    """Test async performance scenarios."""
    
    @pytest.mark.asyncio
    async def test_high_throughput_async_flows(self, mock_config):
        """Test high throughput async flow execution."""
        
        @trace_flow(config=mock_config, flow_name="HighThroughputFlow")
        class HighThroughputFlow(MockAsyncFlow):
            def __init__(self):
                node = MockAsyncNode("ThroughputNode")
                super().__init__(start_node=node)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            # Execute many flows concurrently
            num_flows = 50
            flows = [HighThroughputFlow() for _ in range(num_flows)]
            shared_data = [{"input": f"throughput_{i}"} for i in range(num_flows)]
            
            start_time = time.time()
            results = await asyncio.gather(*[
                flow.run_async(shared)
                for flow, shared in zip(flows, shared_data)
            ])
            execution_time = time.time() - start_time
            
            # All flows should complete successfully
            assert len(results) == num_flows
            assert all(result == "default" for result in results)
            
            # Should maintain reasonable performance
            assert execution_time < 5.0  # Should complete in less than 5 seconds
            
            # Calculate throughput
            throughput = num_flows / execution_time
            assert throughput > 10  # At least 10 flows per second
    
    @pytest.mark.asyncio
    async def test_memory_usage_with_many_contexts(self, mock_config):
        """Test memory usage with many async contexts."""
        
        @trace_flow(config=mock_config, flow_name="MemoryTestFlow")
        class MemoryTestFlow(MockAsyncFlow):
            def __init__(self):
                node = MockAsyncNode("MemoryNode")
                super().__init__(start_node=node)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            # Create many flows with contexts
            flows = []
            for i in range(100):
                flow = MemoryTestFlow()
                flows.append(flow)
            
            # Execute in batches to avoid overwhelming the system
            batch_size = 10
            all_results = []
            
            for i in range(0, len(flows), batch_size):
                batch = flows[i:i + batch_size]
                shared_batch = [{"input": f"memory_{j}"} for j in range(len(batch))]
                
                batch_results = await asyncio.gather(*[
                    flow.run_async(shared)
                    for flow, shared in zip(batch, shared_batch)
                ])
                all_results.extend(batch_results)
                
                # Small delay between batches
                await asyncio.sleep(0.01)
            
            # All flows should complete
            assert len(all_results) == 100
            assert all(result == "default" for result in all_results)
    
    @pytest.mark.asyncio
    async def test_long_running_async_flow(self, mock_config):
        """Test long-running async flow with many nodes."""
        
        @trace_flow(config=mock_config, flow_name="LongRunningFlow")
        class LongRunningFlow(MockAsyncFlow):
            def __init__(self, num_nodes=20):
                # Create a chain of many nodes
                nodes = [MockAsyncNode(f"Node{i}") for i in range(num_nodes)]
                
                # Chain them together
                for i in range(len(nodes) - 1):
                    nodes[i].next(nodes[i + 1])
                
                super().__init__(start_node=nodes[0])
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            flow = LongRunningFlow(num_nodes=20)
            shared = {"input": "long_running_test"}
            
            start_time = time.time()
            result = await flow.run_async(shared)
            execution_time = time.time() - start_time
            
            # Should complete successfully
            assert result == "default"
            
            # All nodes should have executed
            for i in range(20):
                assert f"output_Node{i}" in shared
            
            # Should complete in reasonable time
            assert execution_time < 10.0  # Should complete in less than 10 seconds


class TestAsyncErrorRecoveryScenarios:
    """Test async error recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self, mock_config):
        """Test recovery from partial failures in async flows."""
        
        class SometimesFailingNode(MockAsyncNode):
            def __init__(self, name, fail_probability=0.3):
                super().__init__(name)
                self.fail_probability = fail_probability
                self.attempt_count = 0
            
            async def exec_async(self, prep_res):
                self.attempt_count += 1
                
                # Fail on first attempt, succeed on retry
                if self.attempt_count == 1:
                    raise ValueError(f"Temporary failure in {self.name}")
                
                await asyncio.sleep(0.05)
                return f"recovered_{prep_res}"
        
        @trace_flow(config=mock_config, flow_name="RecoveryFlow")
        class RecoveryFlow(MockAsyncFlow):
            def __init__(self):
                node = SometimesFailingNode("RecoveryNode")
                super().__init__(start_node=node)
            
            async def run_async(self, shared, max_retries=2):
                """Run with retry logic."""
                for attempt in range(max_retries):
                    try:
                        return await super().run_async(shared)
                    except ValueError as e:
                        if attempt == max_retries - 1:
                            raise
                        await asyncio.sleep(0.1)  # Brief delay before retry
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            flow = RecoveryFlow()
            shared = {"input": "recovery_test"}
            
            # Should succeed after retry
            result = await flow.run_async(shared)
            
            assert result == "default"
            assert "output_RecoveryNode" in shared
            assert "recovered_" in shared["output_RecoveryNode"]
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_config):
        """Test timeout handling in async flows."""
        
        class TimeoutNode(MockAsyncNode):
            async def exec_async(self, prep_res):
                await asyncio.sleep(2.0)  # Long operation
                return f"timeout_processed_{prep_res}"
        
        @trace_flow(config=mock_config, flow_name="TimeoutFlow")
        class TimeoutFlow(MockAsyncFlow):
            def __init__(self):
                node = TimeoutNode("TimeoutNode")
                super().__init__(start_node=node)
            
            async def run_async(self, shared, timeout=0.5):
                """Run with timeout."""
                return await asyncio.wait_for(super().run_async(shared), timeout=timeout)
        
        with patch('pocketflow_tracing.core.LANGFUSE_AVAILABLE', False):
            flow = TimeoutFlow()
            shared = {"input": "timeout_test"}
            
            # Should timeout
            with pytest.raises(asyncio.TimeoutError):
                await flow.run_async(shared, timeout=0.5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

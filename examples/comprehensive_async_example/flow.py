#!/usr/bin/env python3
"""
Flow creation functions for the comprehensive async example.

This module implements functions that create flows by importing node definitions 
and connecting them according to the PocketFlow guide patterns.

Available flows:
- create_comprehensive_async_flow(): Main flow with conditional routing
- create_concurrent_data_flow(): Flow for concurrent processing demonstrations
- create_performance_monitoring_flow(): Flow with performance tracking
- create_simple_async_flow(): Basic async flow for testing
"""

import asyncio
import sys
import os

# Add parent directories to path to import pocketflow
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pocketflow import AsyncFlow
from pocketflow_tracing import trace_flow
from nodes import (
    AsyncDataFetchNode,
    AsyncDataProcessNode,
    AsyncFallbackProcessNode,
    AsyncConcurrentProcessNode,
    AsyncPerformanceMonitorNode,
    AsyncConcurrentExecutionNode
)


@trace_flow(flow_name="ComprehensiveAsyncFlow")
class ComprehensiveAsyncFlow(AsyncFlow):
    """Comprehensive async flow demonstrating advanced tracing features."""

    async def prep_async(self, shared):
        """Flow-level preparation."""
        print("🚀 Starting comprehensive async flow...")
        shared["flow_start_time"] = asyncio.get_event_loop().time()
        return {
            "flow_start_time": shared["flow_start_time"],
            "flow_id": shared.get("flow_id", "default")
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Flow-level post-processing."""
        flow_duration = asyncio.get_event_loop().time() - prep_res["flow_start_time"]
        
        shared["flow_metadata"] = {
            "flow_id": prep_res["flow_id"],
            "duration": flow_duration,
            "status": "completed",
            "nodes_executed": len([k for k in shared.keys() if k.endswith("_data") or k.endswith("_result")])
        }
        
        print(f"✅ Flow completed in {flow_duration:.2f} seconds")
        return exec_res


@trace_flow(flow_name="ConcurrentDataFlow")
class ConcurrentDataFlow(AsyncFlow):
    """Flow that demonstrates concurrent execution patterns."""

    async def run_async(self, shared):
        """Override to demonstrate concurrent execution."""
        # Run the base flow
        result = await super().run_async(shared)
        
        # Add concurrent processing demonstration
        if "fetched_data" in shared:
            from utils.concurrent_utils import demonstrate_concurrent_processing
            await demonstrate_concurrent_processing(shared)
        
        return result


@trace_flow(flow_name="PerformanceMonitoringFlow")
class PerformanceMonitoringFlow(AsyncFlow):
    """Flow with integrated performance monitoring."""

    async def prep_async(self, shared):
        """Initialize performance monitoring."""
        shared["flow_start_time"] = asyncio.get_event_loop().time()
        print("📊 Starting performance monitoring flow...")
        return {
            "flow_start_time": shared["flow_start_time"],
            "flow_id": shared.get("flow_id", "perf_monitor")
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Finalize performance monitoring."""
        flow_duration = asyncio.get_event_loop().time() - prep_res["flow_start_time"]
        
        # Generate performance report
        performance_data = shared.get("performance_metrics", {})
        
        print(f"\n📈 Performance Monitoring Report:")
        print(f"   Flow ID: {prep_res['flow_id']}")
        print(f"   Total Duration: {flow_duration:.3f}s")
        if performance_data:
            print(f"   Performance Score: {performance_data.get('performance_score', 'N/A')}")
            print(f"   Monitoring Overhead: {performance_data.get('monitoring_overhead', 'N/A'):.3f}s")
        
        shared["final_performance_report"] = {
            "flow_id": prep_res["flow_id"],
            "total_duration": flow_duration,
            "detailed_metrics": performance_data
        }
        
        return exec_res


def create_comprehensive_async_flow():
    """
    Create and return a comprehensive async flow with conditional routing.

    This flow demonstrates:
    - Data fetching with error handling
    - Conditional routing based on results
    - Fallback processing
    - Concurrent execution within the main flow
    - Advanced async patterns

    Returns:
        ComprehensiveAsyncFlow: Configured flow instance
    """
    # Create nodes
    fetch_node = AsyncDataFetchNode(max_retries=2, timeout=3.0)
    process_node = AsyncDataProcessNode()
    fallback_node = AsyncFallbackProcessNode()
    concurrent_node = AsyncConcurrentExecutionNode()

    # Connect nodes with conditional routing
    fetch_node - "full_process" >> process_node
    fetch_node - "simple_process" >> process_node
    fetch_node - "fallback_process" >> fallback_node

    # Add concurrent execution after processing
    process_node - "concurrent_complete" >> concurrent_node
    fallback_node - "concurrent_complete" >> concurrent_node

    # Create and return flow
    flow = ComprehensiveAsyncFlow()
    flow.start_node = fetch_node
    return flow


def create_concurrent_data_flow():
    """
    Create and return a flow for concurrent processing demonstrations.
    
    This flow shows:
    - Basic data fetching
    - Concurrent processing patterns
    - Performance optimization
    
    Returns:
        ConcurrentDataFlow: Configured flow instance
    """
    # Single fetch node for concurrent demo
    fetch_node = AsyncDataFetchNode(max_retries=1, timeout=2.0)
    
    # Create and return flow
    flow = ConcurrentDataFlow()
    flow.start_node = fetch_node
    return flow


def create_performance_monitoring_flow():
    """
    Create and return a flow with integrated performance monitoring.
    
    This flow demonstrates:
    - Performance tracking throughout execution
    - Resource usage monitoring
    - Detailed performance reporting
    
    Returns:
        PerformanceMonitoringFlow: Configured flow instance
    """
    # Create nodes
    fetch_node = AsyncDataFetchNode(max_retries=1, timeout=2.0)
    process_node = AsyncDataProcessNode()
    concurrent_node = AsyncConcurrentProcessNode()
    monitor_node = AsyncPerformanceMonitorNode()

    # Connect nodes in sequence
    fetch_node >> process_node
    process_node >> concurrent_node
    concurrent_node >> monitor_node

    # Create and return flow
    flow = PerformanceMonitoringFlow()
    flow.start_node = fetch_node
    return flow


def create_simple_async_flow():
    """
    Create and return a simple async flow for basic testing.
    
    This flow provides:
    - Basic fetch and process pattern
    - Minimal configuration
    - Easy testing and debugging
    
    Returns:
        AsyncFlow: Simple configured flow instance
    """
    # Create basic nodes
    fetch_node = AsyncDataFetchNode(max_retries=1, timeout=1.0)
    process_node = AsyncDataProcessNode()

    # Connect nodes
    fetch_node >> process_node

    # Create and return basic flow
    flow = AsyncFlow(start=fetch_node)
    return flow


def create_fallback_demonstration_flow():
    """
    Create and return a flow specifically for demonstrating fallback mechanisms.
    
    This flow is designed to:
    - Trigger fallback scenarios
    - Show error recovery patterns
    - Demonstrate graceful degradation
    
    Returns:
        ComprehensiveAsyncFlow: Flow configured for fallback testing
    """
    # Create nodes with aggressive timeouts to trigger fallbacks
    fetch_node = AsyncDataFetchNode(max_retries=1, timeout=0.5)  # Short timeout
    process_node = AsyncDataProcessNode()
    fallback_node = AsyncFallbackProcessNode()

    # Connect with fallback routing
    fetch_node - "full_process" >> process_node
    fetch_node - "simple_process" >> process_node
    fetch_node - "fallback_process" >> fallback_node

    # Create flow optimized for fallback demonstration
    flow = ComprehensiveAsyncFlow()
    flow.start_node = fetch_node
    return flow


if __name__ == "__main__":
    """Test flow creation functions."""
    
    async def test_flows():
        """Test flow creation and basic functionality."""
        print("Testing flow creation functions...")
        
        # Test comprehensive flow
        try:
            flow = create_comprehensive_async_flow()
            print(f"✅ Comprehensive flow created: {type(flow).__name__}")
            
            # Test with sample data
            shared = {
                "query": "test query",
                "source": "test_api",
                "flow_id": "test_comprehensive"
            }
            
            result = await flow.run_async(shared)
            print(f"✅ Comprehensive flow test completed: {result}")
            
        except Exception as e:
            print(f"❌ Comprehensive flow test failed: {e}")
        
        # Test simple flow
        try:
            simple_flow = create_simple_async_flow()
            print(f"✅ Simple flow created: {type(simple_flow).__name__}")
            
            shared = {
                "query": "simple test",
                "source": "simple_api"
            }
            
            result = await simple_flow.run_async(shared)
            print(f"✅ Simple flow test completed: {result}")
            
        except Exception as e:
            print(f"❌ Simple flow test failed: {e}")
    
    asyncio.run(test_flows())

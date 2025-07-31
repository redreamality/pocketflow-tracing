#!/usr/bin/env python3
"""
Node definitions for the comprehensive async example.

This module contains all node class definitions following the PocketFlow guide patterns:
- AsyncDataFetchNode: Handles async data fetching with error handling
- AsyncDataProcessNode: Processes fetched data with different strategies  
- AsyncFallbackProcessNode: Handles fallback processing scenarios

Each node follows the standard PocketFlow async node pattern:
- prep_async(): Prepare data for execution
- exec_async(): Execute the main node logic
- post_async(): Post-process results and determine next action
"""

import asyncio
import sys
import os

# Add parent directories to path to import pocketflow and utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pocketflow import AsyncNode
from utils.async_data_fetch import fetch_data_from_api, get_fallback_data, validate_query_params
from utils.async_data_process import validate_processing_data, process_data_with_strategy
from utils.async_data_process import handle_fallback_processing
from typing import Dict, Any, List, Tuple


class AsyncDataFetchNode(AsyncNode):
    """
    Advanced async node that simulates data fetching with error handling.
    
    This node demonstrates:
    - Async data fetching with timeout and retries
    - Error handling and fallback mechanisms
    - Conditional routing based on results
    """

    def __init__(self, max_retries=3, timeout=5.0):
        """
        Initialize the data fetch node.
        
        Args:
            max_retries: Maximum number of retry attempts
            timeout: Timeout in seconds for fetch operations
        """
        super().__init__(max_retries=max_retries, wait=0.5)
        self.timeout = timeout

    async def prep_async(self, shared):
        """Extract and validate query parameters."""
        return validate_query_params(shared)

    async def exec_async(self, prep_res):
        """Simulate async data fetching with timeout and retries."""
        return await fetch_data_from_api(
            query=prep_res['query'],
            source=prep_res['source'],
            timeout=self.timeout
        )

    async def exec_fallback_async(self, prep_res, exc):
        """Fallback when all retries are exhausted."""
        return await get_fallback_data(prep_res['query'], exc)

    async def post_async(self, shared, prep_res, exec_res):
        """Store the fetched data and determine next action."""
        shared["fetched_data"] = exec_res
        
        # Determine next action based on results
        if exec_res.get("fallback"):
            return "fallback_process"
        elif len(exec_res.get("results", [])) > 3:
            return "full_process"
        else:
            return "simple_process"


class AsyncDataProcessNode(AsyncNode):
    """
    Advanced async node that processes data with different strategies.
    
    This node demonstrates:
    - Strategy-based data processing
    - Performance monitoring
    - Async data transformation
    """

    async def prep_async(self, shared):
        """Get and validate the fetched data."""
        return validate_processing_data(shared)

    async def exec_async(self, prep_res):
        """Process the data using the determined strategy."""
        return await process_data_with_strategy(
            data=prep_res["data"],
            strategy=prep_res["strategy"],
            start_time=prep_res["start_time"]
        )

    async def post_async(self, shared, prep_res, exec_res):
        """Store the processed data."""
        shared["processed_data"] = exec_res
        return "concurrent_complete"


class AsyncFallbackProcessNode(AsyncNode):
    """
    Special node for handling fallback processing.
    
    This node demonstrates:
    - Minimal resource fallback processing
    - Error recovery patterns
    - Graceful degradation
    """

    async def prep_async(self, shared):
        """Prepare for fallback processing."""
        # No special preparation needed for fallback
        return {}

    async def exec_async(self, prep_res):
        """Handle fallback processing with minimal resources."""
        return await handle_fallback_processing()

    async def post_async(self, shared, prep_res, exec_res):
        """Store fallback results."""
        shared["fallback_result"] = exec_res
        return "concurrent_complete"


# Additional specialized nodes for advanced demonstrations

class AsyncConcurrentProcessNode(AsyncNode):
    """
    Node that demonstrates concurrent processing within a single node.
    
    This node shows how to handle concurrent operations while maintaining
    proper async lifecycle tracking.
    """

    async def prep_async(self, shared):
        """Prepare data for concurrent processing."""
        data = shared.get("fetched_data", {})
        results = data.get("results", [])
        
        return {
            "items": results,
            "concurrent_limit": min(len(results), 5),  # Limit concurrency
            "start_time": asyncio.get_event_loop().time()
        }

    async def exec_async(self, prep_res):
        """Execute concurrent processing of items."""
        from utils.concurrent_utils import process_items_concurrently
        
        items = prep_res["items"]
        concurrent_limit = prep_res["concurrent_limit"]
        
        if len(items) > 1:
            processed_items = await process_items_concurrently(
                items, max_concurrent=concurrent_limit
            )
            
            return {
                "processed_items": processed_items,
                "item_count": len(processed_items),
                "processing_time": asyncio.get_event_loop().time() - prep_res["start_time"],
                "concurrent_limit": concurrent_limit
            }
        else:
            return {
                "processed_items": items,
                "item_count": len(items),
                "processing_time": 0.0,
                "concurrent_limit": 1,
                "note": "Not enough items for concurrent processing"
            }

    async def post_async(self, shared, prep_res, exec_res):
        """Store concurrent processing results."""
        shared["concurrent_processing_result"] = exec_res
        return "default"


class AsyncPerformanceMonitorNode(AsyncNode):
    """
    Node that monitors and reports performance metrics.
    
    This node demonstrates:
    - Performance measurement and reporting
    - Flow metadata collection
    - System resource monitoring
    """

    async def prep_async(self, shared):
        """Prepare performance monitoring data."""
        return {
            "flow_start_time": shared.get("flow_start_time", asyncio.get_event_loop().time()),
            "flow_id": shared.get("flow_id", "unknown"),
            "monitoring_start": asyncio.get_event_loop().time()
        }

    async def exec_async(self, prep_res):
        """Collect and analyze performance metrics."""
        current_time = asyncio.get_event_loop().time()
        flow_duration = current_time - prep_res["flow_start_time"]
        
        # Simulate performance analysis
        await asyncio.sleep(0.05)  # Brief analysis time
        
        return {
            "flow_id": prep_res["flow_id"],
            "total_flow_duration": flow_duration,
            "monitoring_overhead": current_time - prep_res["monitoring_start"],
            "performance_score": min(100, max(0, 100 - (flow_duration * 10))),  # Simple scoring
            "timestamp": current_time
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Store performance metrics."""
        shared["performance_metrics"] = exec_res
        
        # Log performance summary
        metrics = exec_res
        print(f"📊 Performance Summary:")
        print(f"   Flow Duration: {metrics['total_flow_duration']:.3f}s")
        print(f"   Performance Score: {metrics['performance_score']:.1f}/100")
        print(f"   Monitoring Overhead: {metrics['monitoring_overhead']:.3f}s")
        
        return "default"


if __name__ == "__main__":
    """Test node functionality."""
    
    async def test_nodes():
        """Test individual node functionality."""
        print("Testing async nodes...")
        
        # Test data fetch node
        fetch_node = AsyncDataFetchNode(max_retries=1, timeout=2.0)
        shared = {
            "query": "test query",
            "source": "test_api"
        }
        
        try:
            result = await fetch_node.run_async(shared)
            print(f"✅ Fetch node test: {result}")
            print(f"   Fetched data keys: {list(shared.get('fetched_data', {}).keys())}")
        except Exception as e:
            print(f"❌ Fetch node test failed: {e}")
        
        # Test process node (if fetch succeeded)
        if "fetched_data" in shared:
            process_node = AsyncDataProcessNode()
            try:
                result = await process_node.run_async(shared)
                print(f"✅ Process node test: {result}")
                processed = shared.get("processed_data", {})
                print(f"   Processed {processed.get('result_count', 0)} results")
            except Exception as e:
                print(f"❌ Process node test failed: {e}")
    
    asyncio.run(test_nodes())


class AsyncConcurrentExecutionNode(AsyncNode):
    """
    Node that executes multiple flows concurrently within the main trace.

    This node demonstrates concurrent execution while maintaining proper
    trace hierarchy and error handling.
    """

    async def prep_async(self, shared):
        """Prepare concurrent execution parameters."""
        # Import here to avoid circular imports
        from flow import create_concurrent_data_flow

        # Define queries for concurrent execution
        queries = [
            "python async programming",
            "machine learning basics",
            "data science tools",
            "fail_test",  # This will trigger fallback
            "web development"
        ]

        # Create flows and data for concurrent execution
        flows_and_data = []
        for i, query in enumerate(queries):
            flow = create_concurrent_data_flow()
            shared_data = {
                "query": query,
                "source": "concurrent_api",
                "flow_id": f"concurrent_{i}"
            }
            flows_and_data.append((flow, shared_data))

        # Store flows_and_data in instance variable to avoid serialization issues
        self._flows_and_data = flows_and_data

        # Return only serializable data for tracing
        return {
            "queries": queries,
            "total_flows": len(flows_and_data),
            "execution_start_time": asyncio.get_event_loop().time()
        }

    async def exec_async(self, prep_res):
        """Execute multiple flows concurrently."""
        flows_and_data = self._flows_and_data

        print(f"🚀 Starting {len(flows_and_data)} concurrent flows...")
        start_time = asyncio.get_event_loop().time()

        # Execute all flows concurrently
        results = await asyncio.gather(*[
            flow.run_async(shared_data)
            for flow, shared_data in flows_and_data
        ], return_exceptions=True)

        execution_time = asyncio.get_event_loop().time() - start_time

        # Analyze results
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful

        print(f"⏱️ All flows completed in {execution_time:.2f} seconds")
        print(f"✅ Successful flows: {successful}")
        print(f"❌ Failed flows: {failed}")

        # Store results in instance variable to avoid serialization issues
        self._execution_results = results

        # Return only serializable data for tracing
        return {
            "execution_time": execution_time,
            "statistics": {
                "total": len(results),
                "successful": successful,
                "failed": failed
            },
            "result_summary": [
                "success" if not isinstance(r, Exception) else f"error: {type(r).__name__}"
                for r in results
            ]
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Process concurrent execution results."""
        statistics = exec_res["statistics"]
        execution_time = exec_res["execution_time"]

        # Store results in shared context using instance variable
        shared["concurrent_results"] = self._execution_results
        shared["concurrent_statistics"] = statistics
        shared["concurrent_execution_time"] = execution_time

        # Determine success status
        success_rate = statistics["successful"] / statistics["total"]

        if success_rate >= 0.8:  # 80% success rate threshold
            shared["concurrent_status"] = "success"
            print(f"🎉 Concurrent execution successful: {success_rate:.1%} success rate")
        elif success_rate >= 0.5:  # 50% success rate threshold
            shared["concurrent_status"] = "partial_success"
            print(f"⚠️ Concurrent execution partially successful: {success_rate:.1%} success rate")
        else:
            shared["concurrent_status"] = "failed"
            print(f"❌ Concurrent execution failed: {success_rate:.1%} success rate")

        return "concurrent_complete"

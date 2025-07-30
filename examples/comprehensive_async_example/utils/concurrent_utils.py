#!/usr/bin/env python3
"""
Concurrent processing utilities for the comprehensive async example.

This module provides utilities for:
- Concurrent processing of multiple items
- Flow execution coordination
- Performance monitoring for concurrent operations
"""

import asyncio
from typing import Dict, Any, List, Tuple
from datetime import datetime


async def process_item_concurrently(item: str, index: int, delay: float = 0.1) -> str:
    """
    Process a single item concurrently.
    
    Args:
        item: The item to process
        index: The item index
        delay: Processing delay in seconds
        
    Returns:
        Processed item string
    """
    await asyncio.sleep(delay)  # Simulate processing
    return f"Concurrent[{index}]: {item.upper()}"


async def process_items_concurrently(items: List[str], max_concurrent: int = 10) -> List[str]:
    """
    Process multiple items concurrently with concurrency limit.
    
    Args:
        items: List of items to process
        max_concurrent: Maximum number of concurrent operations
        
    Returns:
        List of processed items
    """
    print(f"🔄 Processing {len(items)} items concurrently (max {max_concurrent})...")
    
    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(item: str, index: int) -> str:
        async with semaphore:
            return await process_item_concurrently(item, index)
    
    # Process items concurrently
    concurrent_results = await asyncio.gather(*[
        process_with_semaphore(item, i) for i, item in enumerate(items)
    ])
    
    print(f"✅ Processed {len(concurrent_results)} items concurrently")
    return concurrent_results


async def demonstrate_concurrent_processing(shared: Dict[str, Any]) -> None:
    """
    Demonstrate concurrent processing of fetched data.
    
    Args:
        shared: Shared data dictionary containing fetched_data
    """
    data = shared.get("fetched_data", {})
    results = data.get("results", [])
    
    if len(results) > 1:
        concurrent_results = await process_items_concurrently(results)
        shared["concurrent_results"] = concurrent_results
    else:
        print("⚠️ Not enough items for concurrent processing demonstration")


async def execute_flows_concurrently(
    flows_and_data: List[Tuple[Any, Dict[str, Any]]]
) -> Tuple[List[Any], float, Dict[str, int]]:
    """
    Execute multiple flows concurrently and collect results.
    
    Args:
        flows_and_data: List of (flow, shared_data) tuples
        
    Returns:
        Tuple of (results, execution_time, statistics)
    """
    print(f"🚀 Starting {len(flows_and_data)} concurrent flows...")
    start_time = asyncio.get_event_loop().time()
    
    # Execute all flows concurrently
    results = await asyncio.gather(*[
        flow.run_async(shared) 
        for flow, shared in flows_and_data
    ], return_exceptions=True)
    
    execution_time = asyncio.get_event_loop().time() - start_time
    
    # Analyze results
    successful = sum(1 for r in results if not isinstance(r, Exception))
    failed = len(results) - successful
    
    statistics = {
        "total": len(results),
        "successful": successful,
        "failed": failed
    }
    
    print(f"⏱️ All flows completed in {execution_time:.2f} seconds")
    print(f"✅ Successful flows: {successful}")
    print(f"❌ Failed flows: {failed}")
    
    return results, execution_time, statistics


def analyze_concurrent_results(
    results: List[Any], 
    shared_data_list: List[Dict[str, Any]]
) -> None:
    """
    Analyze and display results from concurrent flow execution.
    
    Args:
        results: List of flow execution results
        shared_data_list: List of shared data dictionaries
    """
    print("\n📊 Concurrent Execution Analysis:")
    print("-" * 40)
    
    for i, (result, shared) in enumerate(zip(results, shared_data_list)):
        if not isinstance(result, Exception):
            metadata = shared.get("flow_metadata", {})
            duration = metadata.get("duration", 0)
            nodes_executed = metadata.get("nodes_executed", 0)
            print(f"  Flow {i}: {duration:.2f}s, {nodes_executed} nodes")
        else:
            print(f"  Flow {i}: Failed with {type(result).__name__}")


async def measure_performance(operation_name: str, operation_func, *args, **kwargs) -> Tuple[Any, float]:
    """
    Measure the performance of an async operation.
    
    Args:
        operation_name: Name of the operation for logging
        operation_func: The async function to measure
        *args: Arguments for the operation function
        **kwargs: Keyword arguments for the operation function
        
    Returns:
        Tuple of (result, execution_time_seconds)
    """
    print(f"⏱️ Starting performance measurement for: {operation_name}")
    start_time = asyncio.get_event_loop().time()
    
    try:
        result = await operation_func(*args, **kwargs)
        execution_time = asyncio.get_event_loop().time() - start_time
        print(f"✅ {operation_name} completed in {execution_time:.3f} seconds")
        return result, execution_time
    except Exception as e:
        execution_time = asyncio.get_event_loop().time() - start_time
        print(f"❌ {operation_name} failed after {execution_time:.3f} seconds: {e}")
        raise


if __name__ == "__main__":
    """Test the concurrent processing utilities."""
    
    async def test_concurrent_utils():
        """Test concurrent processing functionality."""
        print("Testing concurrent processing utilities...")
        
        # Test concurrent item processing
        test_items = ["item1", "item2", "item3", "item4", "item5"]
        
        try:
            processed_items = await process_items_concurrently(test_items, max_concurrent=3)
            print(f"✅ Concurrent processing: {len(processed_items)} items processed")
        except Exception as e:
            print(f"❌ Concurrent processing failed: {e}")
        
        # Test performance measurement
        async def dummy_operation(delay: float = 0.1):
            await asyncio.sleep(delay)
            return "operation_result"
        
        try:
            result, duration = await measure_performance("dummy_operation", dummy_operation, 0.05)
            print(f"✅ Performance measurement: {result} in {duration:.3f}s")
        except Exception as e:
            print(f"❌ Performance measurement failed: {e}")
    
    asyncio.run(test_concurrent_utils())

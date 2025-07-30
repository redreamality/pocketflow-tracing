#!/usr/bin/env python3
"""
Async data processing utilities for the comprehensive async example.

This module provides utilities for:
- Processing fetched data with different strategies
- Async data transformation and analysis
- Performance monitoring during processing
"""

import asyncio
from typing import Dict, Any, List


async def process_data_advanced(results: List[str]) -> List[Dict[str, Any]]:
    """
    Process data using advanced strategy with detailed analysis.
    
    Args:
        results: List of raw result strings
        
    Returns:
        List of processed result dictionaries
    """
    print("⚙️ Processing data using advanced strategy...")
    
    processed_results = []
    for i, result in enumerate(results):
        await asyncio.sleep(0.1)  # Simulate processing time
        processed_results.append({
            "id": i,
            "original": result,
            "processed": f"ADVANCED: {result.upper()}",
            "score": len(result) * 2
        })
    
    return processed_results


async def process_data_simple(results: List[str]) -> List[Dict[str, Any]]:
    """
    Process data using simple strategy for quick results.
    
    Args:
        results: List of raw result strings
        
    Returns:
        List of processed result dictionaries
    """
    print("⚙️ Processing data using simple strategy...")
    
    # Simple processing
    await asyncio.sleep(0.2)
    processed_results = [
        {"processed": f"SIMPLE: {result}", "score": len(result)}
        for result in results
    ]
    
    return processed_results


def determine_processing_strategy(data: Dict[str, Any]) -> str:
    """
    Determine the appropriate processing strategy based on data characteristics.
    
    Args:
        data: The fetched data dictionary
        
    Returns:
        Strategy name ("advanced" or "simple")
    """
    results = data.get("results", [])
    return "advanced" if len(results) > 3 else "simple"


async def process_data_with_strategy(data: Dict[str, Any], strategy: str, start_time: float) -> Dict[str, Any]:
    """
    Process data using the specified strategy.
    
    Args:
        data: The fetched data dictionary
        strategy: Processing strategy ("advanced" or "simple")
        start_time: Processing start time for duration calculation
        
    Returns:
        Dictionary containing processed results and metadata
    """
    results = data.get("results", [])
    
    if strategy == "advanced":
        processed_results = await process_data_advanced(results)
    else:
        processed_results = await process_data_simple(results)
    
    return {
        "original_query": data.get("query"),
        "source": data.get("source"),
        "strategy": strategy,
        "processed_results": processed_results,
        "result_count": len(processed_results),
        "processing_time": asyncio.get_event_loop().time() - start_time,
        "fallback_used": data.get("fallback", False)
    }


def validate_processing_data(shared: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and prepare data for processing.
    
    Args:
        shared: Shared data dictionary
        
    Returns:
        Validated processing parameters
        
    Raises:
        ValueError: When no data is available for processing
    """
    data = shared.get("fetched_data", {})
    if not data:
        raise ValueError("No data to process")
    
    processing_strategy = determine_processing_strategy(data)
    
    return {
        "data": data,
        "strategy": processing_strategy,
        "start_time": asyncio.get_event_loop().time()
    }


async def handle_fallback_processing() -> Dict[str, Any]:
    """
    Handle fallback processing with minimal resources.
    
    Returns:
        Dictionary containing fallback processing results
    """
    print("🔄 Executing fallback processing...")
    await asyncio.sleep(0.1)
    
    return {
        "status": "fallback_processed",
        "message": "Data processed using fallback strategy"
    }


if __name__ == "__main__":
    """Test the data processing utilities."""
    
    async def test_data_processing():
        """Test data processing functionality."""
        print("Testing async data processing utilities...")
        
        # Mock data for testing
        test_data = {
            "query": "test query",
            "source": "test_api",
            "results": ["Result 1", "Result 2", "Result 3", "Result 4", "Result 5"],
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Test strategy determination
        strategy = determine_processing_strategy(test_data)
        print(f"✅ Strategy determined: {strategy}")
        
        # Test processing
        try:
            start_time = asyncio.get_event_loop().time()
            processed = await process_data_with_strategy(test_data, strategy, start_time)
            print(f"✅ Processing completed: {processed['result_count']} results in {processed['processing_time']:.3f}s")
        except Exception as e:
            print(f"❌ Processing failed: {e}")
        
        # Test fallback processing
        try:
            fallback_result = await handle_fallback_processing()
            print(f"✅ Fallback processing: {fallback_result['status']}")
        except Exception as e:
            print(f"❌ Fallback processing failed: {e}")
    
    asyncio.run(test_data_processing())

#!/usr/bin/env python3
"""
Async data fetching utilities for the comprehensive async example.

This module provides utilities for:
- Simulating async data fetching with timeout and retries
- Handling connection errors and fallback scenarios
- Mock data generation for testing
"""

import asyncio
from typing import Dict, Any, List


async def fetch_data_from_api(query: str, source: str = "api", timeout: float = 5.0) -> Dict[str, Any]:
    """
    Simulate async data fetching from an external API.
    
    Args:
        query: The search query
        source: The data source identifier
        timeout: Timeout in seconds
        
    Returns:
        Dictionary containing fetched data
        
    Raises:
        ConnectionError: When simulated connection fails
        asyncio.TimeoutError: When operation times out
    """
    print(f"🔍 Fetching data for query: {query} from {source}")
    
    try:
        # Simulate async operation with timeout
        async with asyncio.timeout(timeout):
            await asyncio.sleep(1.0)  # Simulate network delay
            
            # Simulate potential failure for demonstration
            if query == "fail_test":
                raise ConnectionError("Simulated connection failure")
            
            # Return mock data
            data = {
                "query": query,
                "source": source,
                "results": [f"Result {i} for {query}" for i in range(5)],
                "timestamp": asyncio.get_event_loop().time(),
                "fetch_duration": 1.0
            }
            return data
            
    except asyncio.TimeoutError:
        print(f"⏰ Timeout fetching data for {query}")
        raise
    except ConnectionError as e:
        print(f"🔌 Connection error: {e}")
        raise


async def get_fallback_data(query: str, error: Exception) -> Dict[str, Any]:
    """
    Generate fallback data when primary fetch fails.
    
    Args:
        query: The original query
        error: The exception that caused the fallback
        
    Returns:
        Dictionary containing fallback data
    """
    print(f"💥 Generating fallback data for {query}: {error}")
    
    # Return cached or default data
    return {
        "query": query,
        "source": "cache",
        "results": [f"Cached result for {query}"],
        "timestamp": asyncio.get_event_loop().time(),
        "fetch_duration": 0.0,
        "fallback": True,
        "error": str(error)
    }


def validate_query_params(shared: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and validate query parameters from shared data.
    
    Args:
        shared: Shared data dictionary
        
    Returns:
        Validated parameters dictionary
        
    Raises:
        ValueError: When required parameters are missing
    """
    query = shared.get("query", "default")
    source = shared.get("source", "api")
    
    if not query:
        raise ValueError("Query parameter is required")
    
    return {
        "query": query,
        "source": source,
        "timestamp": asyncio.get_event_loop().time()
    }


if __name__ == "__main__":
    """Test the data fetching utilities."""
    
    async def test_fetch_data():
        """Test data fetching functionality."""
        print("Testing async data fetch utilities...")
        
        # Test successful fetch
        try:
            data = await fetch_data_from_api("test query", "test_api", 2.0)
            print(f"✅ Successful fetch: {len(data['results'])} results")
        except Exception as e:
            print(f"❌ Fetch failed: {e}")
        
        # Test fallback
        try:
            await fetch_data_from_api("fail_test", "test_api", 2.0)
        except Exception as e:
            fallback_data = await get_fallback_data("fail_test", e)
            print(f"✅ Fallback generated: {fallback_data['fallback']}")
        
        # Test validation
        try:
            params = validate_query_params({"query": "test", "source": "api"})
            print(f"✅ Validation passed: {params['query']}")
        except Exception as e:
            print(f"❌ Validation failed: {e}")
    
    asyncio.run(test_fetch_data())

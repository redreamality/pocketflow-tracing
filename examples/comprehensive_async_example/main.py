#!/usr/bin/env python3
"""
Main entry point for the comprehensive async example.

This serves as the project's entry point, orchestrating all demonstrations
and showcasing the comprehensive async PocketFlow tracing features.

Demonstrations included:
- Basic async flow execution
- Concurrent flow processing
- Error handling and recovery
- Nested flow execution
- Performance monitoring
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directories to path to import pocketflow
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from flow import (
    create_comprehensive_async_flow,
    create_concurrent_data_flow,
    create_performance_monitoring_flow,
    create_fallback_demonstration_flow
)
from utils.concurrent_utils import execute_flows_concurrently, analyze_concurrent_results


async def demonstrate_basic_async_flow():
    """Demonstrate basic async flow with tracing."""
    print("\n" + "="*60)
    print("🎯 BASIC ASYNC FLOW DEMONSTRATION")
    print("="*60)

    flow = create_comprehensive_async_flow()
    shared = {
        "query": "machine learning tutorials",
        "source": "api",
        "flow_id": "basic_demo"
    }

    print(f"📥 Input: {shared}")

    try:
        result = await flow.run_async(shared)
        print(f"📤 Final result: {result}")
        print(f"🎉 Flow metadata: {shared.get('flow_metadata', {})}")
        
        if "processed_data" in shared:
            processed = shared["processed_data"]
            print(f"📊 Processed {processed['result_count']} results using {processed['strategy']} strategy")
            
    except Exception as e:
        print(f"❌ Flow failed: {e}")


async def demonstrate_concurrent_flows():
    """Demonstrate concurrent execution of multiple flows."""
    print("\n" + "="*60)
    print("🔄 CONCURRENT FLOWS DEMONSTRATION")
    print("="*60)

    # Create multiple flows with different queries
    queries = [
        "python async programming",
        "machine learning basics", 
        "data science tools",
        "fail_test",  # This will trigger fallback
        "web development"
    ]

    flows_and_data = []
    for i, query in enumerate(queries):
        flow = create_concurrent_data_flow()
        shared_data = {
            "query": query,
            "source": "concurrent_api",
            "flow_id": f"concurrent_{i}"
        }
        flows_and_data.append((flow, shared_data))

    try:
        # Execute flows concurrently and analyze results
        results, execution_time, statistics = await execute_flows_concurrently(flows_and_data)
        
        # Extract shared data for analysis
        shared_data_list = [shared for _, shared in flows_and_data]
        analyze_concurrent_results(results, shared_data_list)
        
        print(f"\n📈 Execution Statistics:")
        print(f"   Total Flows: {statistics['total']}")
        print(f"   Successful: {statistics['successful']}")
        print(f"   Failed: {statistics['failed']}")
        print(f"   Total Time: {execution_time:.2f}s")
                
    except Exception as e:
        print(f"❌ Concurrent execution failed: {e}")


async def demonstrate_error_handling():
    """Demonstrate error handling and recovery."""
    print("\n" + "="*60)
    print("🛡️ ERROR HANDLING DEMONSTRATION")
    print("="*60)

    flow = create_fallback_demonstration_flow()
    
    # Test with failing query
    shared = {
        "query": "fail_test",
        "source": "unreliable_api",
        "flow_id": "error_demo"
    }

    print(f"📥 Testing with failing input: {shared}")

    try:
        result = await flow.run_async(shared)
        print(f"📤 Result (with fallback): {result}")
        
        # Check if fallback was used
        if "fetched_data" in shared and shared["fetched_data"].get("fallback"):
            print("🔄 Fallback mechanism was successfully triggered")
            print(f"💾 Fallback data: {shared['fetched_data']}")
            
        if "fallback_result" in shared:
            print(f"🛡️ Fallback processing result: {shared['fallback_result']}")
            
    except Exception as e:
        print(f"❌ Flow failed even with fallback: {e}")


async def demonstrate_performance_monitoring():
    """Demonstrate performance monitoring capabilities."""
    print("\n" + "="*60)
    print("📊 PERFORMANCE MONITORING DEMONSTRATION")
    print("="*60)

    flow = create_performance_monitoring_flow()
    shared = {
        "query": "performance monitoring test",
        "source": "performance_api",
        "flow_id": "performance_demo"
    }

    print(f"📥 Input: {shared}")

    try:
        result = await flow.run_async(shared)
        print(f"📤 Final result: {result}")
        
        # Display performance report
        if "final_performance_report" in shared:
            report = shared["final_performance_report"]
            print(f"\n🎯 Final Performance Report:")
            print(f"   Flow ID: {report['flow_id']}")
            print(f"   Total Duration: {report['total_duration']:.3f}s")
            
            detailed = report.get("detailed_metrics", {})
            if detailed:
                print(f"   Performance Score: {detailed.get('performance_score', 'N/A')}")
                print(f"   Monitoring Overhead: {detailed.get('monitoring_overhead', 0):.3f}s")
            
    except Exception as e:
        print(f"❌ Performance monitoring failed: {e}")


async def demonstrate_nested_flows():
    """Demonstrate nested flow execution."""
    print("\n" + "="*60)
    print("🔗 NESTED FLOWS DEMONSTRATION")
    print("="*60)

    async def run_nested_analysis(shared_data):
        """Run nested analysis flows."""
        print("📊 Running nested analysis...")
        
        # Create analysis flow
        analysis_flow = create_comprehensive_async_flow()
        
        # Modify query for analysis
        analysis_shared = shared_data.copy()
        analysis_shared["query"] = f"analysis of {shared_data['query']}"
        analysis_shared["flow_id"] = "nested_analysis"
        
        return await analysis_flow.run_async(analysis_shared)

    # Main flow
    main_flow = create_comprehensive_async_flow()
    shared = {
        "query": "data processing patterns",
        "source": "main_api",
        "flow_id": "main_flow"
    }

    print(f"📥 Main flow input: {shared}")

    try:
        # Run main flow
        main_result = await main_flow.run_async(shared)
        print(f"✅ Main flow completed: {main_result}")
        
        # Run nested analysis if main flow succeeded
        if "processed_data" in shared:
            nested_result = await run_nested_analysis(shared)
            print(f"✅ Nested analysis completed: {nested_result}")
            
    except Exception as e:
        print(f"❌ Nested flow execution failed: {e}")


def display_final_summary():
    """Display final summary and next steps."""
    print("\n" + "="*80)
    print("🎉 ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY!")
    print("="*80)
    
    print("\n📊 Check your Langfuse dashboard to see the comprehensive async traces!")
    langfuse_host = os.getenv("LANGFUSE_HOST", "your-langfuse-host")
    print(f"   Dashboard URL: {langfuse_host}")
    
    print("\n💡 Key features demonstrated:")
    print("   ✅ Advanced async node lifecycle tracking")
    print("   ✅ Concurrent flow execution with isolation")
    print("   ✅ Nested async flows with context preservation")
    print("   ✅ Comprehensive error handling and recovery")
    print("   ✅ Performance monitoring and optimization")
    print("   ✅ Modular code organization following PocketFlow guide")
    
    print("\n📁 Project Structure:")
    print("   ├── main.py           # Entry point and demonstrations")
    print("   ├── nodes.py          # Node class definitions")
    print("   ├── flow.py           # Flow creation functions")
    print("   └── utils/            # Utility functions")
    print("       ├── async_data_fetch.py")
    print("       ├── async_data_process.py")
    print("       └── concurrent_utils.py")


async def main():
    """Run all async demonstrations."""
    print("🚀 COMPREHENSIVE ASYNC TRACING DEMONSTRATION")
    print("=" * 80)
    
    try:
        # Run all demonstrations
        await demonstrate_basic_async_flow()
        await demonstrate_concurrent_flows()
        await demonstrate_error_handling()
        await demonstrate_performance_monitoring()
        await demonstrate_nested_flows()
        
        # Display final summary
        display_final_summary()
        
    except Exception as e:
        print(f"❌ Demonstration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

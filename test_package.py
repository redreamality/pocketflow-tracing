#!/usr/bin/env python3
"""
Simple test to verify the packaged pocketflow-tracing works correctly.
"""

import sys
import os

def test_imports():
    """Test that all main components can be imported."""
    print("🧪 Testing imports...")
    
    try:
        from pocketflow_tracing import trace_flow, TracingConfig, LangfuseTracer
        print("✅ Main components imported successfully")
        
        from pocketflow_tracing.utils import setup_tracing, test_langfuse_connection
        print("✅ Utility functions imported successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_config():
    """Test configuration creation."""
    print("🧪 Testing configuration...")
    
    try:
        from pocketflow_tracing import TracingConfig
        
        # Test default config
        config = TracingConfig()
        print("✅ Default configuration created")
        
        # Test config validation (should fail without credentials)
        is_valid = config.validate()
        if not is_valid:
            print("✅ Configuration validation correctly failed (no credentials)")
        else:
            print("⚠️ Configuration validation unexpectedly passed")
        
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_decorator():
    """Test that the decorator can be applied (without actually tracing)."""
    print("🧪 Testing decorator...")
    
    try:
        from pocketflow_tracing import trace_flow
        
        # Test decorator creation
        decorator = trace_flow()
        print("✅ Decorator created successfully")
        
        # Test that decorator is callable
        if callable(decorator):
            print("✅ Decorator is callable")
        else:
            print("❌ Decorator is not callable")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Decorator test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Testing pocketflow-tracing package")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config,
        test_decorator,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()  # Add spacing between tests
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Package is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the package installation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

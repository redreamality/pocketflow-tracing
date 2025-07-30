# Comprehensive Async Example

A comprehensive demonstration of PocketFlow's async capabilities, organized according to the [PocketFlow Guide](../../docs/guide_for_pocketflow.md) best practices.

## Overview

This example showcases advanced async features including:
- Advanced async node lifecycle tracking
- Concurrent flow execution with proper isolation
- Nested async flows with context preservation
- Error handling and recovery in async contexts
- Performance monitoring and optimization
- Mixed sync/async flow patterns

## Project Structure

```
comprehensive_async_example/
├── main.py                    # Entry point and demonstrations
├── nodes.py                   # All node class definitions
├── flow.py                    # Flow creation functions
├── utils/                     # Utility functions
│   ├── __init__.py
│   ├── async_data_fetch.py    # Data fetching utilities
│   ├── async_data_process.py  # Data processing utilities
│   └── concurrent_utils.py    # Concurrent processing utilities
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

This structure follows the recommended PocketFlow project organization from the guide.

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Environment** (optional):
   ```bash
   # Create .env file with your Langfuse configuration
   echo "LANGFUSE_HOST=your-langfuse-host" > .env
   echo "LANGFUSE_PUBLIC_KEY=your-public-key" >> .env
   echo "LANGFUSE_SECRET_KEY=your-secret-key" >> .env
   ```

3. **Run the Example**:
   ```bash
   python main.py
   ```

## Components

### Nodes (`nodes.py`)

- **AsyncDataFetchNode**: Handles async data fetching with error handling and retries
- **AsyncDataProcessNode**: Processes data using different strategies (simple/advanced)
- **AsyncFallbackProcessNode**: Handles fallback processing scenarios
- **AsyncConcurrentProcessNode**: Demonstrates concurrent processing within nodes
- **AsyncPerformanceMonitorNode**: Monitors and reports performance metrics

### Flows (`flow.py`)

- **create_comprehensive_async_flow()**: Main flow with conditional routing
- **create_concurrent_data_flow()**: Flow for concurrent processing demonstrations
- **create_performance_monitoring_flow()**: Flow with integrated performance tracking
- **create_simple_async_flow()**: Basic async flow for testing
- **create_fallback_demonstration_flow()**: Flow optimized for error handling demos

### Utilities (`utils/`)

#### `async_data_fetch.py`
- `fetch_data_from_api()`: Simulates async API calls with timeout handling
- `get_fallback_data()`: Generates fallback data when primary fetch fails
- `validate_query_params()`: Validates and prepares query parameters

#### `async_data_process.py`
- `process_data_advanced()`: Advanced processing with detailed analysis
- `process_data_simple()`: Simple processing for quick results
- `determine_processing_strategy()`: Selects appropriate processing strategy

#### `concurrent_utils.py`
- `process_items_concurrently()`: Processes multiple items with concurrency limits
- `execute_flows_concurrently()`: Executes multiple flows concurrently
- `measure_performance()`: Measures and reports operation performance

## Demonstrations

### 1. Basic Async Flow
Demonstrates fundamental async flow execution with tracing.

### 2. Concurrent Flows
Shows multiple flows executing concurrently with proper isolation.

### 3. Error Handling
Demonstrates error recovery and fallback mechanisms.

### 4. Performance Monitoring
Shows integrated performance tracking and reporting.

### 5. Nested Flows
Demonstrates nested flow execution with context preservation.

## Testing Individual Components

Each component can be tested independently:

```bash
# Test nodes
python nodes.py

# Test flows
python flow.py

# Test utilities
python utils/async_data_fetch.py
python utils/async_data_process.py
python utils/concurrent_utils.py
```

## Customization

### Adding New Nodes

1. Add your node class to `nodes.py`:
   ```python
   class MyCustomNode(AsyncNode):
       async def prep_async(self, shared):
           # Preparation logic
           return prep_data
       
       async def exec_async(self, prep_res):
           # Main execution logic
           return result
       
       async def post_async(self, shared, prep_res, exec_res):
           # Post-processing logic
           shared["my_result"] = exec_res
           return "default"
   ```

### Adding New Flows

1. Add your flow creation function to `flow.py`:
   ```python
   def create_my_custom_flow():
       # Create and connect nodes
       node1 = MyCustomNode()
       node2 = AnotherNode()
       node1 >> node2
       
       # Return configured flow
       return AsyncFlow(start=node1)
   ```

### Adding New Utilities

1. Create a new file in `utils/` directory
2. Implement your utility functions
3. Add a `if __name__ == "__main__":` section for testing
4. Import and use in your nodes

### Adding New Demonstrations

1. Add your demonstration function to `main.py`:
   ```python
   async def demonstrate_my_feature():
       print("🎯 MY FEATURE DEMONSTRATION")
       # Your demonstration logic
   ```

2. Call it from the `main()` function

## Performance Considerations

- **Concurrency Limits**: The example uses semaphores to limit concurrent operations
- **Timeout Handling**: All async operations include appropriate timeouts
- **Resource Management**: Proper cleanup and resource management patterns
- **Error Recovery**: Comprehensive error handling with fallback mechanisms

## Tracing and Monitoring

The example integrates with PocketFlow tracing to provide:
- Detailed async lifecycle tracking
- Performance metrics collection
- Error tracking and analysis
- Flow execution visualization

Check your Langfuse dashboard after running the example to see the comprehensive traces.

## Best Practices Demonstrated

1. **Modular Organization**: Clear separation of concerns
2. **Async Patterns**: Proper async/await usage throughout
3. **Error Handling**: Comprehensive error recovery mechanisms
4. **Performance Monitoring**: Built-in performance tracking
5. **Testing**: Individual component testing capabilities
6. **Documentation**: Comprehensive code documentation

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're running from the correct directory
2. **Timeout Errors**: Adjust timeout values in node configurations
3. **Concurrency Issues**: Check semaphore limits in concurrent utilities

### Debug Mode

Set environment variable for verbose logging:
```bash
export POCKETFLOW_DEBUG=1
python main.py
```

## Contributing

When extending this example:
1. Follow the existing code organization patterns
2. Add appropriate documentation and docstrings
3. Include testing capabilities for new components
4. Update this README with new features

## Related Documentation

- [PocketFlow Guide](../../docs/guide_for_pocketflow.md)
- [Async Migration Guide](../../docs/async_migration_guide.md)
- [Tracing Documentation](../../tracing-in-depth.md)

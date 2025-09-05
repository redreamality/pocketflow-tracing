"""
Decorator for tracing PocketFlow workflows with Langfuse.
Enhanced with comprehensive async support and context management.
"""

import asyncio
import functools
import inspect
import uuid
from typing import Any, Callable, Dict, Optional, Union

from .config import TracingConfig
from .core import AsyncTraceContext, LangfuseTracer


def trace_flow(
    config: Optional[TracingConfig] = None,
    flow_name: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """
    Decorator to add Langfuse tracing to PocketFlow flows.

    This decorator automatically traces:
    - Flow execution start/end
    - Each node's prep, exec, and post phases
    - Input and output data for each phase
    - Errors and exceptions

    Args:
        config: TracingConfig instance. If None, loads from environment.
        flow_name: Custom name for the flow. If None, uses the flow class name.
        session_id: Session ID for grouping related traces.
        user_id: User ID for the trace.

    Returns:
        Decorated flow class or function.

    Example:
        ```python
        from tracing import trace_flow

        @trace_flow()
        class MyFlow(Flow):
            def __init__(self):
                super().__init__(start=MyNode())

        # Or with custom configuration
        config = TracingConfig.from_env()

        @trace_flow(config=config, flow_name="CustomFlow")
        class MyFlow(Flow):
            pass
        ```
    """

    def decorator(flow_class_or_func):
        # Handle both class and function decoration
        if inspect.isclass(flow_class_or_func):
            return _trace_flow_class(
                flow_class_or_func, config, flow_name, session_id, user_id
            )
        else:
            return _trace_flow_function(
                flow_class_or_func, config, flow_name, session_id, user_id
            )

    return decorator


def _trace_flow_class(flow_class, config, flow_name, session_id, user_id):
    """Trace a Flow class by wrapping its methods."""

    # Get or create config
    if config is None:
        config = TracingConfig.from_env()

    # Override session/user if provided
    if session_id:
        config.session_id = session_id
    if user_id:
        config.user_id = user_id

    # Get flow name
    if flow_name is None:
        flow_name = flow_class.__name__

    # Store original methods
    original_init = flow_class.__init__
    original_run = getattr(flow_class, "run", None)
    original_run_async = getattr(flow_class, "run_async", None)

    def traced_init(self, *args, **kwargs):
        """Initialize the flow with tracing capabilities."""
        # Call original init
        original_init(self, *args, **kwargs)

        # Add tracing attributes
        self._tracer = LangfuseTracer(config)
        self._flow_name = flow_name
        self._trace_id = None

        # Don't patch nodes immediately - wait until flow is actually run
        # This allows the flow to be properly initialized with nodes first
        self._nodes_patched = False

    def traced_run(self, shared):
        """Traced version of the run method."""
        if not hasattr(self, "_tracer"):
            # Fallback if not properly initialized
            return original_run(self, shared) if original_run else None

        # Start trace
        self._trace_id = self._tracer.start_trace(self._flow_name, shared)

        try:
            # Run the original flow
            result = original_run(self, shared) if original_run else None

            # End trace successfully
            self._tracer.end_trace(shared, "success")

            return result

        except Exception as e:
            # End trace with error
            self._tracer.end_trace(shared, "error")
            raise
        finally:
            # Ensure cleanup
            self._tracer.flush()

    async def traced_run_async(self, shared):
        """Enhanced traced version of the async run method with context management."""
        if not hasattr(self, "_tracer"):
            # Fallback if not properly initialized
            return (
                await original_run_async(self, shared) if original_run_async else None
            )

        # Patch nodes if not already done (lazy patching)
        if not self._nodes_patched:
            self._patch_nodes()
            self._nodes_patched = True

        # Start async trace with context management
        async_context = await self._tracer.start_trace_async(self._flow_name, shared)

        if not async_context:
            # Fallback to non-context version if async context creation failed
            return await self._traced_run_async_fallback(shared)

        try:
            # Use async context manager for proper context propagation
            async with async_context:
                # Run the original flow within the async context
                result = (
                    await original_run_async(self, shared)
                    if original_run_async
                    else None
                )

                # End trace successfully
                self._tracer.end_trace(shared, "success")

                return result

        except asyncio.CancelledError:
            # Handle async cancellation specifically
            self._tracer.end_trace(shared, "cancelled")
            if self._tracer.config.debug:
                print(f"✗ Async flow {self._flow_name} was cancelled")
            raise
        except Exception as e:
            # End trace with error
            self._tracer.end_trace(shared, "error")
            if self._tracer.config.debug:
                print(f"✗ Async flow {self._flow_name} failed: {e}")
            raise
        finally:
            # Ensure cleanup with async-aware flush
            await self._tracer.flush_async()

    async def _traced_run_async_fallback(self, shared):
        """Fallback async tracing without context management."""
        # Start trace normally
        self._trace_id = self._tracer.start_trace(self._flow_name, shared)

        try:
            # Run the original flow
            result = (
                await original_run_async(self, shared) if original_run_async else None
            )

            # End trace successfully
            self._tracer.end_trace(shared, "success")

            return result

        except Exception as e:
            # End trace with error
            self._tracer.end_trace(shared, "error")
            raise
        finally:
            # Ensure cleanup
            self._tracer.flush()

    def patch_nodes(self):
        """Patch all nodes in the flow to add tracing, including nested flows."""
        if not hasattr(self, "start_node") or not self.start_node:
            return

        visited = set()
        nodes_to_patch = [self.start_node]

        while nodes_to_patch:
            node = nodes_to_patch.pop(0)
            if id(node) in visited:
                continue

            visited.add(id(node))

            # Patch this node
            self._patch_node(node)

            # Add successors to patch list
            if hasattr(node, "successors"):
                for successor in node.successors.values():
                    if successor and id(successor) not in visited:
                        nodes_to_patch.append(successor)

            # Handle nested flows: if this node is also a flow, patch its internal nodes
            if (
                hasattr(node, "start_node")
                and node.start_node
                and id(node.start_node) not in visited
            ):
                nodes_to_patch.append(node.start_node)

    def patch_node(self, node):
        """Patch a single node to add tracing."""
        if hasattr(node, "_pocketflow_traced"):
            return  # Already patched

        node_id = str(uuid.uuid4())
        node_name = type(node).__name__

        # Store original methods
        original_prep = getattr(node, "prep", None)
        original_exec = getattr(node, "exec", None)
        original_post = getattr(node, "post", None)
        original_prep_async = getattr(node, "prep_async", None)
        original_exec_async = getattr(node, "exec_async", None)
        original_post_async = getattr(node, "post_async", None)

        # Create traced versions
        if original_prep:
            node.prep = self._create_traced_method(
                original_prep, node_id, node_name, "prep"
            )
        if original_exec:
            node.exec = self._create_traced_method(
                original_exec, node_id, node_name, "exec"
            )
        if original_post:
            node.post = self._create_traced_method(
                original_post, node_id, node_name, "post"
            )
        if original_prep_async:
            node.prep_async = self._create_traced_async_method(
                original_prep_async, node_id, node_name, "prep"
            )
        if original_exec_async:
            node.exec_async = self._create_traced_async_method(
                original_exec_async, node_id, node_name, "exec"
            )
        if original_post_async:
            node.post_async = self._create_traced_async_method(
                original_post_async, node_id, node_name, "post"
            )

        # Mark as traced
        node._pocketflow_traced = True

    def create_traced_method(self, original_method, node_id, node_name, phase):
        """Create a traced version of a synchronous method."""

        @functools.wraps(original_method)
        def traced_method(*args, **kwargs):
            span_id = self._tracer.start_node_span(node_name, node_id, phase)

            try:
                result = original_method(*args, **kwargs)
                self._tracer.end_node_span(span_id, input_data=args, output_data=result)
                return result
            except Exception as e:
                self._tracer.end_node_span(span_id, input_data=args, error=e)
                raise

        return traced_method

    def create_traced_async_method(self, original_method, node_id, node_name, phase):
        """Create an enhanced traced version of an asynchronous method with comprehensive lifecycle tracking."""

        @functools.wraps(original_method)
        async def traced_async_method(*args, **kwargs):
            # Start comprehensive async lifecycle tracking
            span_id = await self._tracer.start_async_node_lifecycle(
                node_id, node_name, phase
            )

            # Transition to running state
            await self._tracer.transition_async_node_state(node_id, "running", phase)

            try:
                # Execute the original async method with suspend/resume tracking
                result = await self._execute_with_lifecycle_tracking(
                    original_method, node_id, args, kwargs
                )

                # Transition to completing state
                await self._tracer.transition_async_node_state(
                    node_id, "completing", phase
                )

                # End span with async-aware method
                await self._tracer.end_node_span_async(
                    span_id, input_data=args, output_data=result
                )

                # Transition to completed state
                await self._tracer.transition_async_node_state(
                    node_id, "completed", phase
                )

                return result

            except asyncio.CancelledError as e:
                # Handle async cancellation with comprehensive error handling
                await self._tracer.handle_async_error(
                    e,
                    node_id=node_id,
                    flow_name=node_name,
                    context_data={"phase": phase, "reason": "task_cancelled"},
                )
                await self._tracer.transition_async_node_state(
                    node_id, "cancelled", phase, {"reason": "task_cancelled"}
                )
                await self._tracer.end_node_span_async(
                    span_id,
                    input_data=args,
                    error=e,
                )
                raise

            except Exception as e:
                # Handle other exceptions with comprehensive error handling
                await self._tracer.handle_async_error(
                    e,
                    node_id=node_id,
                    flow_name=node_name,
                    context_data={
                        "phase": phase,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )
                await self._tracer.transition_async_node_state(
                    node_id,
                    "failed",
                    phase,
                    {"error_type": type(e).__name__, "error_message": str(e)},
                )
                await self._tracer.end_node_span_async(
                    span_id, input_data=args, error=e
                )
                raise

        return traced_async_method

    async def execute_with_lifecycle_tracking(self, method, node_id, args, kwargs):
        """Execute a method with automatic suspend/resume tracking."""

        # Create a custom awaitable that tracks suspend/resume
        class LifecycleAwaitable:
            def __init__(self, coro, tracer, node_id):
                self.coro = coro
                self.tracer = tracer
                self.node_id = node_id

            def __await__(self):
                return self._await_with_tracking().__await__()

            async def _await_with_tracking(self):
                # Mark as suspended before await
                await self.tracer.suspend_async_node(self.node_id, "method_await")

                try:
                    # Execute the actual coroutine
                    result = await self.coro

                    # Mark as resumed after await
                    await self.tracer.resume_async_node(self.node_id, "method_complete")

                    return result
                except Exception as e:
                    # Mark as resumed even on error
                    await self.tracer.resume_async_node(self.node_id, "method_error")
                    raise

        # Execute the method
        coro = method(*args, **kwargs)

        # If it's a coroutine, wrap it with lifecycle tracking
        if asyncio.iscoroutine(coro):
            return await LifecycleAwaitable(coro, self._tracer, node_id)
        else:
            # Not a coroutine, return directly
            return coro

    # Replace methods on the class
    flow_class.__init__ = traced_init
    flow_class._patch_nodes = patch_nodes
    flow_class._patch_node = patch_node
    flow_class._create_traced_method = create_traced_method
    flow_class._create_traced_async_method = create_traced_async_method
    flow_class._execute_with_lifecycle_tracking = execute_with_lifecycle_tracking
    flow_class._traced_run_async_fallback = _traced_run_async_fallback

    if original_run:
        flow_class.run = traced_run
    if original_run_async:
        flow_class.run_async = traced_run_async

    return flow_class


def _trace_flow_function(flow_func, config, flow_name, session_id, user_id):
    """Trace a flow function (for functional-style flows)."""

    # Get or create config
    if config is None:
        config = TracingConfig.from_env()

    # Override session/user if provided
    if session_id:
        config.session_id = session_id
    if user_id:
        config.user_id = user_id

    # Get flow name
    if flow_name is None:
        flow_name = flow_func.__name__

    tracer = LangfuseTracer(config)

    @functools.wraps(flow_func)
    def traced_flow_func(*args, **kwargs):
        # Assume first argument is shared data
        shared = args[0] if args else {}

        # Start trace
        trace_id = tracer.start_trace(flow_name, shared)

        try:
            result = flow_func(*args, **kwargs)
            tracer.end_trace(shared, "success")
            return result
        except Exception as e:
            tracer.end_trace(shared, "error")
            raise
        finally:
            tracer.flush()

    return traced_flow_func

"""
Core tracing functionality for PocketFlow with Langfuse integration.
"""

import asyncio
import json
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union

try:
    from langfuse import Langfuse

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    print("Warning: langfuse package not installed. Install with: pip install langfuse")

from .config import TracingConfig

# Async context management for tracing
_current_tracer: ContextVar[Optional["LangfuseTracer"]] = ContextVar(
    "current_tracer", default=None
)
_current_trace_id: ContextVar[Optional[str]] = ContextVar(
    "current_trace_id", default=None
)
_current_flow_name: ContextVar[Optional[str]] = ContextVar(
    "current_flow_name", default=None
)
_active_spans: ContextVar[Dict[str, Any]] = ContextVar("active_spans", default={})
_async_task_contexts: Dict[asyncio.Task, Dict[str, Any]] = {}


class AsyncTraceContext:
    """
    Manages async tracing context across async boundaries.

    This class provides context management for async operations, ensuring
    that trace information is properly propagated across await boundaries,
    task switches, and concurrent operations.
    """

    def __init__(self, tracer: "LangfuseTracer", trace_id: str, flow_name: str):
        self.tracer = tracer
        self.trace_id = trace_id
        self.flow_name = flow_name
        self.spans: Dict[str, Any] = {}
        self.task_id = None

    def __enter__(self):
        """Enter sync context (for compatibility)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit sync context (for compatibility)."""
        pass

    async def __aenter__(self):
        """Enter async context."""
        # Set context variables
        _current_tracer.set(self.tracer)
        _current_trace_id.set(self.trace_id)
        _current_flow_name.set(self.flow_name)
        _active_spans.set(self.spans)

        # Track current task
        try:
            current_task = asyncio.current_task()
            if current_task:
                self.task_id = id(current_task)
                _async_task_contexts[current_task] = {
                    "tracer": self.tracer,
                    "trace_id": self.trace_id,
                    "flow_name": self.flow_name,
                    "spans": self.spans,
                }
        except RuntimeError:
            # No event loop running
            pass

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        # Clean up task context
        try:
            current_task = asyncio.current_task()
            if current_task and current_task in _async_task_contexts:
                del _async_task_contexts[current_task]
        except RuntimeError:
            pass

        # Reset context variables
        _current_tracer.set(None)
        _current_trace_id.set(None)
        _current_flow_name.set(None)
        _active_spans.set({})

    @classmethod
    def get_current_context(cls) -> Optional["AsyncTraceContext"]:
        """Get the current async trace context."""
        tracer = _current_tracer.get()
        trace_id = _current_trace_id.get()
        flow_name = _current_flow_name.get()

        if tracer and trace_id and flow_name:
            context = cls(tracer, trace_id, flow_name)
            context.spans = _active_spans.get({})
            return context

        # Fallback: try to get from current task
        try:
            current_task = asyncio.current_task()
            if current_task and current_task in _async_task_contexts:
                task_ctx = _async_task_contexts[current_task]
                context = cls(
                    task_ctx["tracer"], task_ctx["trace_id"], task_ctx["flow_name"]
                )
                context.spans = task_ctx["spans"]
                return context
        except RuntimeError:
            pass

        return None


class LangfuseTracer:
    """
    Core tracer class that handles Langfuse integration for PocketFlow.

    Enhanced with async context management for proper trace continuity
    across async boundaries and concurrent operations.
    """

    def __init__(self, config: TracingConfig):
        """
        Initialize the LangfuseTracer.

        Args:
            config: TracingConfig instance with Langfuse settings.
        """
        self.config = config
        self.client = None
        self.current_trace = None
        self.spans = {}  # Store spans by node ID
        self.async_contexts: Set[AsyncTraceContext] = (
            set()
        )  # Track active async contexts
        self.lifecycle_manager = None  # Will be initialized when needed
        self.composition_manager = None  # Will be initialized when needed
        self.error_handler = None  # Will be initialized when needed

        if LANGFUSE_AVAILABLE and config.validate():
            try:
                # Initialize Langfuse client with proper parameters
                kwargs = {}
                if config.langfuse_secret_key:
                    kwargs["secret_key"] = config.langfuse_secret_key
                if config.langfuse_public_key:
                    kwargs["public_key"] = config.langfuse_public_key
                if config.langfuse_host:
                    kwargs["host"] = config.langfuse_host
                if config.debug:
                    kwargs["debug"] = True

                self.client = Langfuse(**kwargs)
                if config.debug:
                    print(
                        f"✓ Langfuse client initialized with host: {config.langfuse_host}"
                    )
            except Exception as e:
                if config.debug:
                    print(f"✗ Failed to initialize Langfuse client: {e}")
                self.client = None
        else:
            if config.debug:
                print("✗ Langfuse not available or configuration invalid")

    def start_trace(self, flow_name: str, input_data: Dict[str, Any]) -> Optional[str]:
        """
        Start a new trace for a flow execution.

        Args:
            flow_name: Name of the flow being traced.
            input_data: Input data for the flow.

        Returns:
            Trace ID if successful, None otherwise.
        """
        if not self.client:
            return None

        try:
            # Serialize input data safely
            serialized_input = self._serialize_data(input_data)

            # Use Langfuse v2 API to create a trace
            self.current_trace = self.client.trace(
                name=flow_name,
                input=serialized_input,
                metadata={
                    "framework": "PocketFlow",
                    "trace_type": "flow_execution",
                    "timestamp": datetime.now().isoformat(),
                },
                session_id=self.config.session_id,
                user_id=self.config.user_id,
            )

            # Get the trace ID
            trace_id = self.current_trace.id

            if self.config.debug:
                print(f"✓ Started trace: {trace_id} for flow: {flow_name}")

            return trace_id

        except Exception as e:
            if self.config.debug:
                print(f"✗ Failed to start trace: {e}")
            return None

    async def start_trace_async(
        self, flow_name: str, input_data: Dict[str, Any]
    ) -> Optional[AsyncTraceContext]:
        """
        Start a new async trace with proper context management.

        Args:
            flow_name: Name of the flow being traced.
            input_data: Input data for the flow.

        Returns:
            AsyncTraceContext if successful, None otherwise.
        """
        trace_id = self.start_trace(flow_name, input_data)
        if trace_id:
            context = AsyncTraceContext(self, trace_id, flow_name)
            self.async_contexts.add(context)
            return context
        return None

    def create_async_context(
        self, flow_name: str, trace_id: Optional[str] = None
    ) -> AsyncTraceContext:
        """
        Create an async trace context for existing trace or new one.

        Args:
            flow_name: Name of the flow.
            trace_id: Existing trace ID, or None to use current trace.

        Returns:
            AsyncTraceContext instance.
        """
        if trace_id is None and self.current_trace:
            trace_id = self.current_trace.id

        if trace_id:
            context = AsyncTraceContext(self, trace_id, flow_name)
            self.async_contexts.add(context)
            return context

        raise ValueError("No active trace found and no trace_id provided")

    def end_trace(self, output_data: Dict[str, Any], status: str = "success") -> None:
        """
        End the current trace.

        Args:
            output_data: Output data from the flow.
            status: Status of the trace execution.
        """
        if not self.current_trace:
            return

        try:
            # Serialize output data safely
            serialized_output = self._serialize_data(output_data)

            # Update the trace with output data using v2 API
            self.current_trace.update(
                output=serialized_output,
                metadata={
                    "status": status,
                    "end_timestamp": datetime.now().isoformat(),
                },
            )

            if self.config.debug:
                print(f"✓ Ended trace with status: {status}")

        except Exception as e:
            if self.config.debug:
                print(f"✗ Failed to end trace: {e}")
        finally:
            self.current_trace = None
            self.spans.clear()
            # Clean up async contexts
            self._cleanup_async_contexts()

    def start_node_span(
        self, node_name: str, node_id: str, phase: str
    ) -> Optional[str]:
        """
        Start a span for a node execution phase.

        Args:
            node_name: Name/type of the node.
            node_id: Unique identifier for the node instance.
            phase: Execution phase (prep, exec, post).

        Returns:
            Span ID if successful, None otherwise.
        """
        if not self.current_trace:
            return None

        try:
            span_id = f"{node_id}_{phase}"

            # Create a child span using v2 API
            span = self.current_trace.span(
                name=f"{node_name}.{phase}",
                metadata={
                    "node_type": node_name,
                    "node_id": node_id,
                    "phase": phase,
                    "start_timestamp": datetime.now().isoformat(),
                },
            )

            self.spans[span_id] = span

            if self.config.debug:
                print(f"✓ Started span: {span_id}")

            return span_id

        except Exception as e:
            if self.config.debug:
                print(f"✗ Failed to start span: {e}")
            return None

    async def start_node_span_async(
        self, node_name: str, node_id: str, phase: str
    ) -> Optional[str]:
        """
        Start a span for async node execution with context awareness.

        Args:
            node_name: Name/type of the node.
            node_id: Unique identifier for the node instance.
            phase: Execution phase (prep, exec, post).

        Returns:
            Span ID if successful, None otherwise.
        """
        # Try to get current async context first
        current_context = AsyncTraceContext.get_current_context()
        if current_context:
            # Use the context's tracer and trace
            return current_context.tracer.start_node_span(node_name, node_id, phase)

        # Fallback to regular span creation
        return self.start_node_span(node_name, node_id, phase)

    async def end_node_span_async(
        self,
        span_id: str,
        input_data: Any = None,
        output_data: Any = None,
        error: Exception = None,
    ) -> None:
        """
        End an async node execution span with context awareness.

        Args:
            span_id: ID of the span to end.
            input_data: Input data for the phase.
            output_data: Output data from the phase.
            error: Exception if the phase failed.
        """
        # Try to get current async context first
        current_context = AsyncTraceContext.get_current_context()
        if current_context:
            # Use the context's tracer
            current_context.tracer.end_node_span(
                span_id, input_data, output_data, error
            )
        else:
            # Fallback to regular span ending
            self.end_node_span(span_id, input_data, output_data, error)

    def end_node_span(
        self,
        span_id: str,
        input_data: Any = None,
        output_data: Any = None,
        error: Exception = None,
    ) -> None:
        """
        End a node execution span.

        Args:
            span_id: ID of the span to end.
            input_data: Input data for the phase.
            output_data: Output data from the phase.
            error: Exception if the phase failed.
        """
        if span_id not in self.spans:
            return

        try:
            span = self.spans[span_id]

            # Prepare update data
            update_data = {}

            if input_data is not None and self.config.trace_inputs:
                update_data["input"] = self._serialize_data(input_data)
            if output_data is not None and self.config.trace_outputs:
                update_data["output"] = self._serialize_data(output_data)

            if error and self.config.trace_errors:
                update_data.update(
                    {
                        "level": "ERROR",
                        "status_message": str(error),
                        "metadata": {
                            "error_type": type(error).__name__,
                            "error_message": str(error),
                            "end_timestamp": datetime.now().isoformat(),
                        },
                    }
                )
            else:
                update_data.update(
                    {
                        "level": "DEFAULT",
                        "metadata": {"end_timestamp": datetime.now().isoformat()},
                    }
                )

            # Update the span with all data at once
            span.update(**update_data)

            # End the span
            span.end()

            if self.config.debug:
                status = "ERROR" if error else "SUCCESS"
                print(f"✓ Ended span: {span_id} with status: {status}")

        except Exception as e:
            if self.config.debug:
                print(f"✗ Failed to end span: {e}")
        finally:
            if span_id in self.spans:
                del self.spans[span_id]

    def _serialize_data(self, data: Any) -> Any:
        """
        Safely serialize data for Langfuse.

        Args:
            data: Data to serialize.

        Returns:
            Serialized data that can be sent to Langfuse.
        """
        try:
            # Handle common PocketFlow data types
            if hasattr(data, "__dict__"):
                # Convert objects to dict representation
                return {"_type": type(data).__name__, "_data": str(data)}
            elif isinstance(data, (dict, list, str, int, float, bool, type(None))):
                # JSON-serializable types
                return data
            else:
                # Fallback to string representation
                return {"_type": type(data).__name__, "_data": str(data)}
        except Exception:
            # Ultimate fallback
            return {"_type": "unknown", "_data": "<serialization_failed>"}

    def flush(self) -> None:
        """Flush any pending traces to Langfuse."""
        if self.client:
            try:
                self.client.flush()
                if self.config.debug:
                    print("✓ Flushed traces to Langfuse")
            except Exception as e:
                if self.config.debug:
                    print(f"✗ Failed to flush traces: {e}")

    def _cleanup_async_contexts(self) -> None:
        """Clean up all async contexts associated with this tracer."""
        contexts_to_remove = list(self.async_contexts)
        for context in contexts_to_remove:
            try:
                # Remove from tracking
                self.async_contexts.discard(context)

                # Clean up task context if it exists
                if context.task_id:
                    tasks_to_remove = []
                    for task, task_ctx in _async_task_contexts.items():
                        if id(task) == context.task_id:
                            tasks_to_remove.append(task)

                    for task in tasks_to_remove:
                        _async_task_contexts.pop(task, None)

            except Exception as e:
                if self.config.debug:
                    print(f"✗ Failed to cleanup async context: {e}")

        # Clean up lifecycle manager
        if self.lifecycle_manager:
            try:
                self.lifecycle_manager.cleanup()
            except Exception as e:
                if self.config.debug:
                    print(f"✗ Failed to cleanup lifecycle manager: {e}")

        # Clean up composition manager
        if self.composition_manager:
            try:
                self.composition_manager.cleanup()
            except Exception as e:
                if self.config.debug:
                    print(f"✗ Failed to cleanup composition manager: {e}")

        # Clean up error handler
        if self.error_handler:
            try:
                self.error_handler.cleanup()
            except Exception as e:
                if self.config.debug:
                    print(f"✗ Failed to cleanup error handler: {e}")

    async def flush_async(self) -> None:
        """Async version of flush with context cleanup."""
        # Clean up async contexts first
        self._cleanup_async_contexts()

        # Then flush normally
        self.flush()

    def get_active_async_contexts(self) -> Set[AsyncTraceContext]:
        """Get all active async contexts for this tracer."""
        return self.async_contexts.copy()

    def has_active_async_context(self) -> bool:
        """Check if there are any active async contexts."""
        return len(self.async_contexts) > 0

    def get_lifecycle_manager(self):
        """Get or create the async lifecycle manager."""
        if self.lifecycle_manager is None:
            # Import here to avoid circular imports
            from .async_lifecycle import AsyncLifecycleManager

            self.lifecycle_manager = AsyncLifecycleManager(self)
        return self.lifecycle_manager

    async def start_async_node_lifecycle(
        self, node_id: str, node_name: str, phase: str = "prep"
    ) -> Optional[str]:
        """Start comprehensive async node lifecycle tracking."""
        lifecycle_manager = self.get_lifecycle_manager()

        # Map phase string to enum
        from .async_lifecycle import AsyncPhase

        phase_enum = {
            "prep": AsyncPhase.PREP,
            "exec": AsyncPhase.EXEC,
            "post": AsyncPhase.POST,
            "cleanup": AsyncPhase.CLEANUP,
        }.get(phase, AsyncPhase.EXEC)

        # Start lifecycle tracking
        lifecycle = lifecycle_manager.start_lifecycle(node_id, node_name, phase_enum)

        # Also start a regular span for Langfuse
        span_id = await self.start_node_span_async(node_name, node_id, phase)

        return span_id

    async def transition_async_node_state(
        self,
        node_id: str,
        state: str,
        phase: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Transition an async node to a new state."""
        if self.lifecycle_manager:
            from .async_lifecycle import AsyncNodeState, AsyncPhase

            # Map state string to enum
            state_enum = {
                "starting": AsyncNodeState.STARTING,
                "running": AsyncNodeState.RUNNING,
                "suspended": AsyncNodeState.SUSPENDED,
                "resuming": AsyncNodeState.RESUMING,
                "completing": AsyncNodeState.COMPLETING,
                "completed": AsyncNodeState.COMPLETED,
                "cancelled": AsyncNodeState.CANCELLED,
                "failed": AsyncNodeState.FAILED,
            }.get(state, AsyncNodeState.RUNNING)

            phase_enum = None
            if phase:
                phase_enum = {
                    "prep": AsyncPhase.PREP,
                    "exec": AsyncPhase.EXEC,
                    "post": AsyncPhase.POST,
                    "cleanup": AsyncPhase.CLEANUP,
                }.get(phase, AsyncPhase.EXEC)

            self.lifecycle_manager.transition_state(
                node_id, state_enum, phase_enum, metadata
            )

    async def suspend_async_node(self, node_id: str, reason: str = "await") -> None:
        """Mark an async node as suspended."""
        if self.lifecycle_manager:
            self.lifecycle_manager.suspend_node(node_id, reason)

    async def resume_async_node(
        self, node_id: str, reason: str = "await_complete"
    ) -> None:
        """Mark an async node as resuming."""
        if self.lifecycle_manager:
            self.lifecycle_manager.resume_node(node_id, reason)

    def get_composition_manager(self):
        """Get or create the async composition manager."""
        if self.composition_manager is None:
            # Import here to avoid circular imports
            from .async_composition import AsyncFlowCompositionManager

            self.composition_manager = AsyncFlowCompositionManager(self)
        return self.composition_manager

    async def start_async_flow_composition(
        self,
        flow_name: str,
        composition_type: str = "sequential",
        parent_execution_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new async flow composition."""
        composition_manager = self.get_composition_manager()

        # Map composition type string to enum
        from .async_composition import FlowCompositionType

        type_enum = {
            "sequential": FlowCompositionType.SEQUENTIAL,
            "parallel": FlowCompositionType.PARALLEL,
            "nested": FlowCompositionType.NESTED,
            "conditional": FlowCompositionType.CONDITIONAL,
            "batch": FlowCompositionType.BATCH,
            "pipeline": FlowCompositionType.PIPELINE,
        }.get(composition_type, FlowCompositionType.SEQUENTIAL)

        execution = await composition_manager.start_flow_execution(
            flow_name, type_enum, parent_execution_id, metadata
        )

        return execution.execution_id

    async def complete_async_flow_composition(
        self,
        execution_id: str,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Complete an async flow composition."""
        if self.composition_manager:
            await self.composition_manager.complete_flow_execution(
                execution_id, status, metadata
            )

    async def execute_parallel_async_flows(
        self,
        flows: List[Any],
        flow_names: List[str],
        parent_execution_id: Optional[str] = None,
    ) -> List[Any]:
        """Execute multiple async flows in parallel."""
        composition_manager = self.get_composition_manager()
        return await composition_manager.execute_parallel_flows(
            flows, flow_names, parent_execution_id
        )

    async def execute_nested_async_flow(
        self, flow: Any, flow_name: str, parent_execution_id: Optional[str] = None
    ) -> Any:
        """Execute a nested async flow."""
        composition_manager = self.get_composition_manager()
        return await composition_manager.execute_nested_flow(
            flow, flow_name, parent_execution_id
        )

    async def execute_batch_async_flows(
        self,
        flow_factory: callable,
        batch_data: List[Any],
        flow_name: str,
        parallel: bool = False,
        parent_execution_id: Optional[str] = None,
    ) -> List[Any]:
        """Execute batch async flows."""
        composition_manager = self.get_composition_manager()
        return await composition_manager.execute_batch_flows(
            flow_factory, batch_data, flow_name, parallel, parent_execution_id
        )

    def get_error_handler(self):
        """Get or create the async error handler."""
        if self.error_handler is None:
            # Import here to avoid circular imports
            from .async_error_handling import AsyncErrorHandler

            self.error_handler = AsyncErrorHandler(self)
        return self.error_handler

    async def handle_async_error(
        self,
        error: Exception,
        node_id: Optional[str] = None,
        flow_name: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ):
        """Handle an async error with comprehensive error management."""
        error_handler = self.get_error_handler()
        return await error_handler.handle_async_error(
            error, node_id, flow_name, context_data
        )

    async def with_timeout(
        self,
        coro: Any,
        timeout_seconds: float,
        node_id: Optional[str] = None,
        flow_name: Optional[str] = None,
    ) -> Any:
        """Execute a coroutine with timeout and proper error handling."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            await self.handle_async_error(
                e,
                node_id=node_id,
                flow_name=flow_name,
                context_data={"timeout_seconds": timeout_seconds},
            )
            raise

    async def with_cancellation_protection(
        self, coro: Any, node_id: Optional[str] = None, flow_name: Optional[str] = None
    ) -> Any:
        """Execute a coroutine with cancellation protection and proper error handling."""
        try:
            return await coro
        except asyncio.CancelledError as e:
            await self.handle_async_error(
                e,
                node_id=node_id,
                flow_name=flow_name,
                context_data={"protection": "cancellation"},
            )
            raise

    async def safe_async_execute(
        self,
        coro: Any,
        node_id: Optional[str] = None,
        flow_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        retry_count: int = 0,
    ) -> Any:
        """Safely execute an async operation with comprehensive error handling."""
        for attempt in range(retry_count + 1):
            try:
                if timeout_seconds:
                    return await self.with_timeout(
                        coro, timeout_seconds, node_id, flow_name
                    )
                else:
                    return await self.with_cancellation_protection(
                        coro, node_id, flow_name
                    )

            except Exception as e:
                if attempt == retry_count:  # Last attempt
                    await self.handle_async_error(
                        e,
                        node_id=node_id,
                        flow_name=flow_name,
                        context_data={
                            "attempt": attempt + 1,
                            "max_attempts": retry_count + 1,
                            "timeout_seconds": timeout_seconds,
                        },
                    )
                    raise
                else:
                    # Log retry attempt
                    if self.config.debug:
                        print(
                            f"⚠️ Retry attempt {attempt + 1}/{retry_count + 1} for {node_id or 'unknown'}"
                        )

                    # Brief delay before retry
                    await asyncio.sleep(0.1 * (attempt + 1))

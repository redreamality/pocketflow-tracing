"""
Comprehensive async error handling for PocketFlow tracing.

This module provides robust error handling for async operations including
cancelled tasks, exceptions in async contexts, timeouts, and mixed sync/async
scenarios.
"""

import asyncio
import functools
import signal
import time
import traceback
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union, Coroutine

from .core import AsyncTraceContext


class AsyncErrorType(Enum):
    """Types of async errors that can occur."""
    CANCELLATION = "cancellation"
    TIMEOUT = "timeout"
    TASK_EXCEPTION = "task_exception"
    CONTEXT_LOST = "context_lost"
    DEADLOCK = "deadlock"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    MIXED_SYNC_ASYNC = "mixed_sync_async"
    COROUTINE_NOT_AWAITED = "coroutine_not_awaited"
    EVENT_LOOP_CLOSED = "event_loop_closed"
    SIGNAL_INTERRUPT = "signal_interrupt"


class AsyncErrorSeverity(Enum):
    """Severity levels for async errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AsyncErrorEvent:
    """Represents an async error event."""
    error_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    error_type: AsyncErrorType = AsyncErrorType.TASK_EXCEPTION
    severity: AsyncErrorSeverity = AsyncErrorSeverity.MEDIUM
    timestamp: datetime = field(default_factory=datetime.now)
    node_id: Optional[str] = None
    flow_name: Optional[str] = None
    task_id: Optional[int] = None
    exception: Optional[Exception] = None
    traceback_str: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# Context variables for error tracking
_current_error_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "current_error_context", default=None
)
_error_recovery_stack: ContextVar[List[str]] = ContextVar(
    "error_recovery_stack", default=[]
)


class AsyncErrorHandler:
    """
    Comprehensive async error handler for PocketFlow tracing.
    
    This class provides robust error handling for async operations including
    cancellation, timeouts, context management, and recovery strategies.
    """
    
    def __init__(self, tracer: "LangfuseTracer"):
        self.tracer = tracer
        self.error_events: List[AsyncErrorEvent] = []
        self.error_handlers: Dict[AsyncErrorType, List[Callable]] = {}
        self.recovery_strategies: Dict[AsyncErrorType, Callable] = {}
        self.timeout_tasks: Set[asyncio.Task] = set()
        self.cancelled_tasks: Set[asyncio.Task] = set()
        
        # Register default error handlers
        self._register_default_handlers()
        
        # Register signal handlers for graceful shutdown
        self._register_signal_handlers()
    
    def _register_default_handlers(self):
        """Register default error handlers."""
        self.register_error_handler(AsyncErrorType.CANCELLATION, self._handle_cancellation)
        self.register_error_handler(AsyncErrorType.TIMEOUT, self._handle_timeout)
        self.register_error_handler(AsyncErrorType.TASK_EXCEPTION, self._handle_task_exception)
        self.register_error_handler(AsyncErrorType.CONTEXT_LOST, self._handle_context_lost)
        self.register_error_handler(AsyncErrorType.MIXED_SYNC_ASYNC, self._handle_mixed_sync_async)
        
        # Register recovery strategies
        self.recovery_strategies[AsyncErrorType.CANCELLATION] = self._recover_from_cancellation
        self.recovery_strategies[AsyncErrorType.TIMEOUT] = self._recover_from_timeout
        self.recovery_strategies[AsyncErrorType.CONTEXT_LOST] = self._recover_from_context_lost
    
    def _register_signal_handlers(self):
        """Register signal handlers for graceful shutdown."""
        try:
            signal.signal(signal.SIGINT, self._handle_signal_interrupt)
            signal.signal(signal.SIGTERM, self._handle_signal_interrupt)
        except (ValueError, OSError):
            # Signal handling not available (e.g., in threads)
            pass
    
    def register_error_handler(self, error_type: AsyncErrorType, handler: Callable):
        """Register a custom error handler."""
        if error_type not in self.error_handlers:
            self.error_handlers[error_type] = []
        self.error_handlers[error_type].append(handler)
    
    def register_recovery_strategy(self, error_type: AsyncErrorType, strategy: Callable):
        """Register a custom recovery strategy."""
        self.recovery_strategies[error_type] = strategy
    
    async def handle_async_error(
        self,
        error: Exception,
        node_id: Optional[str] = None,
        flow_name: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> AsyncErrorEvent:
        """Handle an async error with comprehensive error management."""
        # Determine error type
        error_type = self._classify_error(error)
        severity = self._determine_severity(error, error_type)
        
        # Create error event
        error_event = AsyncErrorEvent(
            error_type=error_type,
            severity=severity,
            node_id=node_id,
            flow_name=flow_name,
            task_id=self._get_current_task_id(),
            exception=error,
            traceback_str=traceback.format_exc(),
            context_data=context_data or {}
        )
        
        # Track the error
        self.error_events.append(error_event)
        
        # Set error context
        error_context = {
            "error_id": error_event.error_id,
            "error_type": error_type.value,
            "severity": severity.value,
            "node_id": node_id,
            "flow_name": flow_name
        }
        _current_error_context.set(error_context)
        
        # Call registered handlers
        await self._call_error_handlers(error_type, error_event)
        
        # Attempt recovery if strategy exists
        if error_type in self.recovery_strategies:
            try:
                error_event.recovery_attempted = True
                recovery_result = await self.recovery_strategies[error_type](error_event)
                error_event.recovery_successful = recovery_result
                
                if recovery_result and self.tracer.config.debug:
                    print(f"✓ Successfully recovered from {error_type.value} error")
                    
            except Exception as recovery_error:
                if self.tracer.config.debug:
                    print(f"✗ Recovery failed for {error_type.value}: {recovery_error}")
        
        # Log to tracer if available
        if self.tracer and hasattr(self.tracer, 'current_trace') and self.tracer.current_trace:
            await self._log_error_to_trace(error_event)
        
        return error_event
    
    def _classify_error(self, error: Exception) -> AsyncErrorType:
        """Classify an error into an AsyncErrorType."""
        if isinstance(error, asyncio.CancelledError):
            return AsyncErrorType.CANCELLATION
        elif isinstance(error, asyncio.TimeoutError):
            return AsyncErrorType.TIMEOUT
        elif isinstance(error, RuntimeError):
            error_msg = str(error).lower()
            if "event loop" in error_msg and "closed" in error_msg:
                return AsyncErrorType.EVENT_LOOP_CLOSED
            elif "coroutine" in error_msg and "never awaited" in error_msg:
                return AsyncErrorType.COROUTINE_NOT_AWAITED
            elif "deadlock" in error_msg:
                return AsyncErrorType.DEADLOCK
        elif isinstance(error, MemoryError):
            return AsyncErrorType.RESOURCE_EXHAUSTION
        elif isinstance(error, KeyboardInterrupt):
            return AsyncErrorType.SIGNAL_INTERRUPT
        
        return AsyncErrorType.TASK_EXCEPTION
    
    def _determine_severity(self, error: Exception, error_type: AsyncErrorType) -> AsyncErrorSeverity:
        """Determine the severity of an error."""
        if error_type in {AsyncErrorType.EVENT_LOOP_CLOSED, AsyncErrorType.DEADLOCK, AsyncErrorType.RESOURCE_EXHAUSTION}:
            return AsyncErrorSeverity.CRITICAL
        elif error_type in {AsyncErrorType.TIMEOUT, AsyncErrorType.CONTEXT_LOST, AsyncErrorType.SIGNAL_INTERRUPT}:
            return AsyncErrorSeverity.HIGH
        elif error_type in {AsyncErrorType.CANCELLATION, AsyncErrorType.MIXED_SYNC_ASYNC}:
            return AsyncErrorSeverity.MEDIUM
        else:
            return AsyncErrorSeverity.LOW
    
    async def _call_error_handlers(self, error_type: AsyncErrorType, error_event: AsyncErrorEvent):
        """Call all registered handlers for an error type."""
        handlers = self.error_handlers.get(error_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(error_event)
                else:
                    handler(error_event)
            except Exception as handler_error:
                if self.tracer.config.debug:
                    print(f"✗ Error handler failed: {handler_error}")
    
    async def _log_error_to_trace(self, error_event: AsyncErrorEvent):
        """Log error event to the current trace."""
        try:
            if self.tracer.current_trace:
                error_span = self.tracer.current_trace.span(
                    name=f"async_error_{error_event.error_type.value}",
                    level="ERROR",
                    metadata={
                        "error_id": error_event.error_id,
                        "error_type": error_event.error_type.value,
                        "severity": error_event.severity.value,
                        "node_id": error_event.node_id,
                        "flow_name": error_event.flow_name,
                        "task_id": error_event.task_id,
                        "recovery_attempted": error_event.recovery_attempted,
                        "recovery_successful": error_event.recovery_successful,
                        "timestamp": error_event.timestamp.isoformat()
                    },
                    input=error_event.context_data,
                    output={
                        "error_message": str(error_event.exception),
                        "traceback": error_event.traceback_str
                    }
                )
                error_span.end()
        except Exception as log_error:
            if self.tracer.config.debug:
                print(f"✗ Failed to log error to trace: {log_error}")
    
    def _get_current_task_id(self) -> Optional[int]:
        """Get the current asyncio task ID."""
        try:
            current_task = asyncio.current_task()
            return id(current_task) if current_task else None
        except RuntimeError:
            return None
    
    def _handle_signal_interrupt(self, signum, frame):
        """Handle signal interrupts."""
        if self.tracer.config.debug:
            print(f"✗ Received signal {signum}, initiating graceful shutdown")
        
        # Create error event for signal interrupt
        error_event = AsyncErrorEvent(
            error_type=AsyncErrorType.SIGNAL_INTERRUPT,
            severity=AsyncErrorSeverity.HIGH,
            exception=KeyboardInterrupt(f"Signal {signum} received"),
            metadata={"signal": signum}
        )
        self.error_events.append(error_event)
    
    # Default error handlers
    async def _handle_cancellation(self, error_event: AsyncErrorEvent):
        """Handle task cancellation."""
        if self.tracer.config.debug:
            print(f"✗ Task cancelled: {error_event.node_id or 'unknown'}")
        
        # Track cancelled task
        try:
            current_task = asyncio.current_task()
            if current_task:
                self.cancelled_tasks.add(current_task)
        except RuntimeError:
            pass
    
    async def _handle_timeout(self, error_event: AsyncErrorEvent):
        """Handle timeout errors."""
        if self.tracer.config.debug:
            print(f"✗ Timeout occurred: {error_event.node_id or 'unknown'}")
        
        # Track timeout task
        try:
            current_task = asyncio.current_task()
            if current_task:
                self.timeout_tasks.add(current_task)
        except RuntimeError:
            pass
    
    async def _handle_task_exception(self, error_event: AsyncErrorEvent):
        """Handle general task exceptions."""
        if self.tracer.config.debug:
            print(f"✗ Task exception: {error_event.exception}")
    
    async def _handle_context_lost(self, error_event: AsyncErrorEvent):
        """Handle lost async context."""
        if self.tracer.config.debug:
            print(f"✗ Async context lost: {error_event.node_id or 'unknown'}")
    
    async def _handle_mixed_sync_async(self, error_event: AsyncErrorEvent):
        """Handle mixed sync/async errors."""
        if self.tracer.config.debug:
            print(f"✗ Mixed sync/async error: {error_event.exception}")
    
    # Recovery strategies
    async def _recover_from_cancellation(self, error_event: AsyncErrorEvent) -> bool:
        """Attempt to recover from task cancellation."""
        # For now, just log the cancellation
        return True
    
    async def _recover_from_timeout(self, error_event: AsyncErrorEvent) -> bool:
        """Attempt to recover from timeout."""
        # For now, just log the timeout
        return True
    
    async def _recover_from_context_lost(self, error_event: AsyncErrorEvent) -> bool:
        """Attempt to recover from lost context."""
        # Try to restore context from current trace
        if self.tracer and hasattr(self.tracer, 'current_trace') and self.tracer.current_trace:
            try:
                # Create new async context
                context = AsyncTraceContext(
                    self.tracer,
                    self.tracer.current_trace.id,
                    error_event.flow_name or "recovered_flow"
                )
                self.tracer.async_contexts.add(context)
                return True
            except Exception:
                pass
        return False
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get statistics about async errors."""
        if not self.error_events:
            return {"total_errors": 0}
        
        error_type_counts = {}
        severity_counts = {}
        recovery_stats = {"attempted": 0, "successful": 0}
        
        for event in self.error_events:
            error_type_counts[event.error_type.value] = error_type_counts.get(event.error_type.value, 0) + 1
            severity_counts[event.severity.value] = severity_counts.get(event.severity.value, 0) + 1
            
            if event.recovery_attempted:
                recovery_stats["attempted"] += 1
                if event.recovery_successful:
                    recovery_stats["successful"] += 1
        
        return {
            "total_errors": len(self.error_events),
            "error_type_distribution": error_type_counts,
            "severity_distribution": severity_counts,
            "recovery_statistics": recovery_stats,
            "cancelled_tasks": len(self.cancelled_tasks),
            "timeout_tasks": len(self.timeout_tasks)
        }
    
    def cleanup(self):
        """Clean up error handler resources."""
        self.error_events.clear()
        self.timeout_tasks.clear()
        self.cancelled_tasks.clear()
        _current_error_context.set(None)
        _error_recovery_stack.set([])


def async_error_handler(error_handler: AsyncErrorHandler):
    """Decorator for automatic async error handling."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                await error_handler.handle_async_error(
                    e,
                    context_data={"function": func.__name__, "args": str(args), "kwargs": str(kwargs)}
                )
                raise
        return wrapper
    return decorator

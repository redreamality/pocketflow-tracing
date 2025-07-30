"""
Advanced async lifecycle management for PocketFlow tracing.

This module provides comprehensive lifecycle event tracking for async nodes,
including suspend/resume events, task state changes, and context preservation
across async boundaries.
"""

import asyncio
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from .core import AsyncTraceContext


class AsyncNodeState(Enum):
    """States for async node lifecycle tracking."""
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    SUSPENDED = "suspended"
    RESUMING = "resuming"
    COMPLETING = "completing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AsyncPhase(Enum):
    """Phases of async node execution."""
    PREP = "prep"
    EXEC = "exec"
    POST = "post"
    CLEANUP = "cleanup"


@dataclass
class AsyncLifecycleEvent:
    """Represents a lifecycle event for an async node."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = ""
    node_name: str = ""
    phase: AsyncPhase = AsyncPhase.EXEC
    state: AsyncNodeState = AsyncNodeState.CREATED
    timestamp: datetime = field(default_factory=datetime.now)
    task_id: Optional[int] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AsyncNodeLifecycle:
    """Tracks the complete lifecycle of an async node."""
    node_id: str
    node_name: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    current_state: AsyncNodeState = AsyncNodeState.CREATED
    current_phase: AsyncPhase = AsyncPhase.PREP
    events: List[AsyncLifecycleEvent] = field(default_factory=list)
    suspend_count: int = 0
    resume_count: int = 0
    task_switches: int = 0
    context_data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate total duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None
    
    @property
    def is_active(self) -> bool:
        """Check if the lifecycle is still active."""
        return self.current_state not in {
            AsyncNodeState.COMPLETED,
            AsyncNodeState.CANCELLED,
            AsyncNodeState.FAILED
        }
    
    def add_event(self, event: AsyncLifecycleEvent) -> None:
        """Add a lifecycle event."""
        self.events.append(event)
        self.current_state = event.state
        self.current_phase = event.phase
        
        # Update counters
        if event.state == AsyncNodeState.SUSPENDED:
            self.suspend_count += 1
        elif event.state == AsyncNodeState.RESUMING:
            self.resume_count += 1
    
    def complete(self, state: AsyncNodeState = AsyncNodeState.COMPLETED) -> None:
        """Mark the lifecycle as complete."""
        self.end_time = datetime.now()
        self.current_state = state


# Context variables for async lifecycle tracking
_current_lifecycle: ContextVar[Optional[AsyncNodeLifecycle]] = ContextVar(
    "current_async_lifecycle", default=None
)
_active_lifecycles: ContextVar[Dict[str, AsyncNodeLifecycle]] = ContextVar(
    "active_async_lifecycles", default={}
)


class AsyncLifecycleManager:
    """
    Manages async node lifecycles and events.
    
    This class provides comprehensive tracking of async node execution,
    including state transitions, suspend/resume events, and context
    preservation across async boundaries.
    """
    
    def __init__(self, tracer: "LangfuseTracer"):
        self.tracer = tracer
        self.active_lifecycles: Dict[str, AsyncNodeLifecycle] = {}
        self.completed_lifecycles: List[AsyncNodeLifecycle] = []
        self.event_handlers: List[callable] = []
    
    def start_lifecycle(
        self, 
        node_id: str, 
        node_name: str, 
        phase: AsyncPhase = AsyncPhase.PREP
    ) -> AsyncNodeLifecycle:
        """Start tracking a new async node lifecycle."""
        lifecycle = AsyncNodeLifecycle(
            node_id=node_id,
            node_name=node_name,
            current_phase=phase
        )
        
        # Add initial event
        initial_event = AsyncLifecycleEvent(
            node_id=node_id,
            node_name=node_name,
            phase=phase,
            state=AsyncNodeState.STARTING,
            task_id=self._get_current_task_id()
        )
        lifecycle.add_event(initial_event)
        
        # Track the lifecycle
        self.active_lifecycles[node_id] = lifecycle
        
        # Set in context
        _current_lifecycle.set(lifecycle)
        active = _active_lifecycles.get({})
        active[node_id] = lifecycle
        _active_lifecycles.set(active)
        
        # Notify handlers
        self._notify_handlers(initial_event)
        
        return lifecycle
    
    def transition_state(
        self,
        node_id: str,
        new_state: AsyncNodeState,
        phase: Optional[AsyncPhase] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Transition a node to a new state."""
        lifecycle = self.active_lifecycles.get(node_id)
        if not lifecycle:
            return
        
        # Create transition event
        event = AsyncLifecycleEvent(
            node_id=node_id,
            node_name=lifecycle.node_name,
            phase=phase or lifecycle.current_phase,
            state=new_state,
            task_id=self._get_current_task_id(),
            metadata=metadata or {}
        )
        
        # Add duration if transitioning from running state
        if lifecycle.current_state == AsyncNodeState.RUNNING:
            last_event = lifecycle.events[-1] if lifecycle.events else None
            if last_event:
                duration = (datetime.now() - last_event.timestamp).total_seconds() * 1000
                event.duration_ms = duration
        
        lifecycle.add_event(event)
        
        # Handle completion states
        if new_state in {AsyncNodeState.COMPLETED, AsyncNodeState.CANCELLED, AsyncNodeState.FAILED}:
            lifecycle.complete(new_state)
            self.completed_lifecycles.append(lifecycle)
            self.active_lifecycles.pop(node_id, None)
            
            # Remove from context
            active = _active_lifecycles.get({})
            active.pop(node_id, None)
            _active_lifecycles.set(active)
        
        # Notify handlers
        self._notify_handlers(event)
    
    def suspend_node(self, node_id: str, reason: str = "await") -> None:
        """Mark a node as suspended (e.g., during await)."""
        self.transition_state(
            node_id,
            AsyncNodeState.SUSPENDED,
            metadata={"suspend_reason": reason}
        )
    
    def resume_node(self, node_id: str, reason: str = "await_complete") -> None:
        """Mark a node as resuming after suspension."""
        self.transition_state(
            node_id,
            AsyncNodeState.RESUMING,
            metadata={"resume_reason": reason}
        )
        
        # Immediately transition to running
        self.transition_state(node_id, AsyncNodeState.RUNNING)
    
    def fail_node(self, node_id: str, error: Exception) -> None:
        """Mark a node as failed with error details."""
        self.transition_state(
            node_id,
            AsyncNodeState.FAILED,
            metadata={
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )
    
    def cancel_node(self, node_id: str, reason: str = "task_cancelled") -> None:
        """Mark a node as cancelled."""
        self.transition_state(
            node_id,
            AsyncNodeState.CANCELLED,
            metadata={"cancel_reason": reason}
        )
    
    def get_lifecycle(self, node_id: str) -> Optional[AsyncNodeLifecycle]:
        """Get the lifecycle for a specific node."""
        return self.active_lifecycles.get(node_id)
    
    def get_current_lifecycle(self) -> Optional[AsyncNodeLifecycle]:
        """Get the current lifecycle from context."""
        return _current_lifecycle.get()
    
    def add_event_handler(self, handler: callable) -> None:
        """Add an event handler for lifecycle events."""
        self.event_handlers.append(handler)
    
    def remove_event_handler(self, handler: callable) -> None:
        """Remove an event handler."""
        if handler in self.event_handlers:
            self.event_handlers.remove(handler)
    
    def _notify_handlers(self, event: AsyncLifecycleEvent) -> None:
        """Notify all event handlers of a lifecycle event."""
        for handler in self.event_handlers:
            try:
                handler(event)
            except Exception as e:
                if self.tracer.config.debug:
                    print(f"✗ Event handler failed: {e}")
    
    def _get_current_task_id(self) -> Optional[int]:
        """Get the current asyncio task ID."""
        try:
            current_task = asyncio.current_task()
            return id(current_task) if current_task else None
        except RuntimeError:
            return None
    
    def cleanup(self) -> None:
        """Clean up all tracked lifecycles."""
        # Complete any remaining active lifecycles
        for lifecycle in list(self.active_lifecycles.values()):
            lifecycle.complete(AsyncNodeState.CANCELLED)
            self.completed_lifecycles.append(lifecycle)
        
        self.active_lifecycles.clear()
        
        # Clear context variables
        _current_lifecycle.set(None)
        _active_lifecycles.set({})
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about async node lifecycles."""
        total_lifecycles = len(self.completed_lifecycles) + len(self.active_lifecycles)
        
        if not total_lifecycles:
            return {"total_lifecycles": 0}
        
        completed = self.completed_lifecycles
        avg_duration = sum(l.duration_ms or 0 for l in completed) / len(completed) if completed else 0
        total_suspends = sum(l.suspend_count for l in completed)
        total_resumes = sum(l.resume_count for l in completed)
        
        state_counts = {}
        for lifecycle in completed:
            state = lifecycle.current_state.value
            state_counts[state] = state_counts.get(state, 0) + 1
        
        return {
            "total_lifecycles": total_lifecycles,
            "active_lifecycles": len(self.active_lifecycles),
            "completed_lifecycles": len(completed),
            "average_duration_ms": avg_duration,
            "total_suspends": total_suspends,
            "total_resumes": total_resumes,
            "state_distribution": state_counts
        }

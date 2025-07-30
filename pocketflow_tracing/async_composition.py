"""
Async flow composition support for PocketFlow tracing.

This module provides comprehensive support for tracing complex async flow
patterns including nested flows, concurrent execution, parallel batch flows,
and flow composition scenarios.
"""

import asyncio
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Coroutine

from .core import AsyncTraceContext


class FlowCompositionType(Enum):
    """Types of async flow composition."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    NESTED = "nested"
    CONDITIONAL = "conditional"
    BATCH = "batch"
    PIPELINE = "pipeline"


@dataclass
class AsyncFlowExecution:
    """Represents an async flow execution within a composition."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    flow_name: str = ""
    parent_execution_id: Optional[str] = None
    composition_type: FlowCompositionType = FlowCompositionType.SEQUENTIAL
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: str = "running"
    context_data: Dict[str, Any] = field(default_factory=dict)
    child_executions: List[str] = field(default_factory=list)
    concurrent_executions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate execution duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if execution is completed."""
        return self.status in {"completed", "failed", "cancelled"}


# Context variables for flow composition tracking
_current_flow_execution: ContextVar[Optional[AsyncFlowExecution]] = ContextVar(
    "current_flow_execution", default=None
)
_active_flow_executions: ContextVar[Dict[str, AsyncFlowExecution]] = ContextVar(
    "active_flow_executions", default={}
)
_flow_execution_stack: ContextVar[List[str]] = ContextVar(
    "flow_execution_stack", default=[]
)


class AsyncFlowCompositionManager:
    """
    Manages async flow composition and execution tracking.
    
    This class provides comprehensive support for tracing complex async
    flow patterns including nested flows, concurrent execution, and
    composition scenarios.
    """
    
    def __init__(self, tracer: "LangfuseTracer"):
        self.tracer = tracer
        self.active_executions: Dict[str, AsyncFlowExecution] = {}
        self.completed_executions: List[AsyncFlowExecution] = []
        self.composition_handlers: Dict[FlowCompositionType, callable] = {}
        
        # Register default composition handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default composition handlers."""
        self.composition_handlers[FlowCompositionType.SEQUENTIAL] = self._handle_sequential
        self.composition_handlers[FlowCompositionType.PARALLEL] = self._handle_parallel
        self.composition_handlers[FlowCompositionType.NESTED] = self._handle_nested
        self.composition_handlers[FlowCompositionType.BATCH] = self._handle_batch
    
    async def start_flow_execution(
        self,
        flow_name: str,
        composition_type: FlowCompositionType = FlowCompositionType.SEQUENTIAL,
        parent_execution_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncFlowExecution:
        """Start a new async flow execution."""
        execution = AsyncFlowExecution(
            flow_name=flow_name,
            parent_execution_id=parent_execution_id,
            composition_type=composition_type,
            metadata=metadata or {}
        )
        
        # Track the execution
        self.active_executions[execution.execution_id] = execution
        
        # Update context variables
        _current_flow_execution.set(execution)
        active = _active_flow_executions.get({})
        active[execution.execution_id] = execution
        _active_flow_executions.set(active)
        
        # Update execution stack
        stack = _flow_execution_stack.get([])
        stack.append(execution.execution_id)
        _flow_execution_stack.set(stack)
        
        # Handle parent-child relationship
        if parent_execution_id and parent_execution_id in self.active_executions:
            parent = self.active_executions[parent_execution_id]
            parent.child_executions.append(execution.execution_id)
        
        if self.tracer.config.debug:
            print(f"✓ Started async flow execution: {execution.execution_id} ({flow_name})")
        
        return execution
    
    async def complete_flow_execution(
        self,
        execution_id: str,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Complete an async flow execution."""
        execution = self.active_executions.get(execution_id)
        if not execution:
            return
        
        # Update execution
        execution.end_time = datetime.now()
        execution.status = status
        if metadata:
            execution.metadata.update(metadata)
        
        # Move to completed
        self.completed_executions.append(execution)
        self.active_executions.pop(execution_id, None)
        
        # Update context variables
        active = _active_flow_executions.get({})
        active.pop(execution_id, None)
        _active_flow_executions.set(active)
        
        # Update execution stack
        stack = _flow_execution_stack.get([])
        if execution_id in stack:
            stack.remove(execution_id)
            _flow_execution_stack.set(stack)
        
        # Set current execution to parent if exists
        if execution.parent_execution_id and execution.parent_execution_id in self.active_executions:
            parent = self.active_executions[execution.parent_execution_id]
            _current_flow_execution.set(parent)
        else:
            _current_flow_execution.set(None)
        
        if self.tracer.config.debug:
            print(f"✓ Completed async flow execution: {execution_id} ({status})")
    
    async def execute_parallel_flows(
        self,
        flows: List[Coroutine],
        flow_names: List[str],
        parent_execution_id: Optional[str] = None
    ) -> List[Any]:
        """Execute multiple flows in parallel with proper tracing."""
        if len(flows) != len(flow_names):
            raise ValueError("Number of flows must match number of flow names")
        
        # Start parallel execution tracking
        parallel_execution = await self.start_flow_execution(
            "ParallelFlowComposition",
            FlowCompositionType.PARALLEL,
            parent_execution_id,
            {"flow_count": len(flows), "flow_names": flow_names}
        )
        
        try:
            # Create child executions for each flow
            child_executions = []
            for i, flow_name in enumerate(flow_names):
                child_exec = await self.start_flow_execution(
                    flow_name,
                    FlowCompositionType.SEQUENTIAL,
                    parallel_execution.execution_id
                )
                child_executions.append(child_exec)
                parallel_execution.concurrent_executions.add(child_exec.execution_id)
            
            # Execute flows in parallel
            results = await asyncio.gather(*flows, return_exceptions=True)
            
            # Complete child executions
            for i, (result, child_exec) in enumerate(zip(results, child_executions)):
                if isinstance(result, Exception):
                    await self.complete_flow_execution(
                        child_exec.execution_id,
                        "failed",
                        {"error": str(result), "error_type": type(result).__name__}
                    )
                else:
                    await self.complete_flow_execution(child_exec.execution_id, "completed")
            
            # Complete parallel execution
            await self.complete_flow_execution(parallel_execution.execution_id, "completed")
            
            return results
            
        except Exception as e:
            await self.complete_flow_execution(
                parallel_execution.execution_id,
                "failed",
                {"error": str(e), "error_type": type(e).__name__}
            )
            raise
    
    async def execute_nested_flow(
        self,
        flow: Coroutine,
        flow_name: str,
        parent_execution_id: Optional[str] = None
    ) -> Any:
        """Execute a nested flow with proper context management."""
        # Start nested execution
        nested_execution = await self.start_flow_execution(
            flow_name,
            FlowCompositionType.NESTED,
            parent_execution_id
        )
        
        try:
            # Execute the nested flow
            result = await flow
            
            # Complete nested execution
            await self.complete_flow_execution(nested_execution.execution_id, "completed")
            
            return result
            
        except Exception as e:
            await self.complete_flow_execution(
                nested_execution.execution_id,
                "failed",
                {"error": str(e), "error_type": type(e).__name__}
            )
            raise
    
    async def execute_batch_flows(
        self,
        flow_factory: callable,
        batch_data: List[Any],
        flow_name: str,
        parallel: bool = False,
        parent_execution_id: Optional[str] = None
    ) -> List[Any]:
        """Execute batch flows with proper tracing."""
        batch_execution = await self.start_flow_execution(
            f"BatchFlow_{flow_name}",
            FlowCompositionType.BATCH,
            parent_execution_id,
            {"batch_size": len(batch_data), "parallel": parallel}
        )
        
        try:
            if parallel:
                # Execute batch in parallel
                flows = [flow_factory(data) for data in batch_data]
                flow_names = [f"{flow_name}_batch_{i}" for i in range(len(batch_data))]
                results = await self.execute_parallel_flows(
                    flows, flow_names, batch_execution.execution_id
                )
            else:
                # Execute batch sequentially
                results = []
                for i, data in enumerate(batch_data):
                    flow = flow_factory(data)
                    result = await self.execute_nested_flow(
                        flow,
                        f"{flow_name}_batch_{i}",
                        batch_execution.execution_id
                    )
                    results.append(result)
            
            await self.complete_flow_execution(batch_execution.execution_id, "completed")
            return results
            
        except Exception as e:
            await self.complete_flow_execution(
                batch_execution.execution_id,
                "failed",
                {"error": str(e), "error_type": type(e).__name__}
            )
            raise
    
    def get_current_execution(self) -> Optional[AsyncFlowExecution]:
        """Get the current flow execution."""
        return _current_flow_execution.get()
    
    def get_execution_stack(self) -> List[str]:
        """Get the current execution stack."""
        return _flow_execution_stack.get([])
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get statistics about flow executions."""
        total_executions = len(self.completed_executions) + len(self.active_executions)
        
        if not total_executions:
            return {"total_executions": 0}
        
        completed = self.completed_executions
        avg_duration = sum(e.duration_ms or 0 for e in completed) / len(completed) if completed else 0
        
        composition_counts = {}
        status_counts = {}
        
        for execution in completed:
            comp_type = execution.composition_type.value
            composition_counts[comp_type] = composition_counts.get(comp_type, 0) + 1
            status_counts[execution.status] = status_counts.get(execution.status, 0) + 1
        
        return {
            "total_executions": total_executions,
            "active_executions": len(self.active_executions),
            "completed_executions": len(completed),
            "average_duration_ms": avg_duration,
            "composition_type_distribution": composition_counts,
            "status_distribution": status_counts
        }
    
    # Default composition handlers
    async def _handle_sequential(self, flows: List[Coroutine]) -> List[Any]:
        """Handle sequential flow execution."""
        results = []
        for flow in flows:
            result = await flow
            results.append(result)
        return results
    
    async def _handle_parallel(self, flows: List[Coroutine]) -> List[Any]:
        """Handle parallel flow execution."""
        return await asyncio.gather(*flows)
    
    async def _handle_nested(self, flow: Coroutine) -> Any:
        """Handle nested flow execution."""
        return await flow
    
    async def _handle_batch(self, flows: List[Coroutine]) -> List[Any]:
        """Handle batch flow execution."""
        return await self._handle_sequential(flows)
    
    def cleanup(self) -> None:
        """Clean up all tracked executions."""
        # Complete any remaining active executions
        for execution in list(self.active_executions.values()):
            execution.end_time = datetime.now()
            execution.status = "cancelled"
            self.completed_executions.append(execution)
        
        self.active_executions.clear()
        
        # Clear context variables
        _current_flow_execution.set(None)
        _active_flow_executions.set({})
        _flow_execution_stack.set([])

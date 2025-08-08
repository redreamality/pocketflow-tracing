import asyncio

from pocketflow import AsyncFlow, AsyncNode, AsyncParallelBatchFlow, Flow, Node

from pocketflow_tracing import trace_flow


# 1. Define a starting node that prepares tasks
class StartNode(Node):
    def post(self, shared, prep_res, exec_res):
        # Define three different tasks
        shared["tasks"] = [
            {"type": "A", "data": "Task A data"},
            {"type": "B", "data": "Task B data"},
            {"type": "C", "data": "Task C data"},
        ]
        return "default"


# 2. Define a branching node that determines which path to take based on task type
class BranchNode(Node):
    def prep(self, shared):
        # Get task from params if available, otherwise from shared
        if "task" in self.params:
            return self.params["task"]
        # Fallback: get from shared (for batch processing)
        return shared.get("current_task")

    def exec(self, task):
        # Simply return the task type to determine which branch to follow
        return task["type"] if task else "default"

    def post(self, shared, prep_res, exec_res):
        # The task type becomes the action
        return exec_res  # "A", "B", or "C"


# 3. Define process nodes for each branch
class ProcessANode(AsyncNode):
    async def prep_async(self, shared):
        # Get the task from params if available, otherwise from shared
        if "task" in self.params:
            return self.params["task"]
        return shared.get("current_task")

    async def exec_async(self, task):
        # Simulate some async processing specific to type A
        await asyncio.sleep(1)  # Simulate work
        return {"type": "A", "result": f"Processed A: {task['data']}"}

    async def post_async(self, shared, prep_res, exec_res):
        # Store the result in shared store under the task's type
        task_type = exec_res["type"]
        if "results" not in shared:
            shared["results"] = {}
        shared["results"][task_type] = exec_res["result"]
        return "default"


class ProcessBNode(AsyncNode):
    async def prep_async(self, shared):
        # Get the task from params if available, otherwise from shared
        if "task" in self.params:
            return self.params["task"]
        return shared.get("current_task")

    async def exec_async(self, task):
        # Simulate some async processing specific to type B
        await asyncio.sleep(3)  # Simulate work (different duration)
        return {"type": "B", "result": f"Processed B: {task['data']}"}

    async def post_async(self, shared, prep_res, exec_res):
        task_type = exec_res["type"]
        if "results" not in shared:
            shared["results"] = {}
        shared["results"][task_type] = exec_res["result"]
        return "default"


class ProcessCNode(AsyncNode):
    async def prep_async(self, shared):
        # Get the task from params if available, otherwise from shared
        if "task" in self.params:
            return self.params["task"]
        return shared.get("current_task")

    async def exec_async(self, task):
        # Simulate some async processing specific to type C
        await asyncio.sleep(5)  # Simulate work (different duration)
        return {"type": "C", "result": f"Processed C: {task['data']}"}

    async def post_async(self, shared, prep_res, exec_res):
        task_type = exec_res["type"]
        if "results" not in shared:
            shared["results"] = {}
        shared["results"][task_type] = exec_res["result"]
        return "default"


# 4. Define a parallel batch flow that will execute the flow for each task in parallel
class ParallelTaskProcessor(AsyncParallelBatchFlow):
    async def prep_async(self, shared):
        # Return a list of param dicts (one per task)
        return [{"task": task} for task in shared["tasks"]]

    async def _orch_async(self, shared, params=None):
        # Override to properly pass task data to nested flow
        if params and "task" in params:
            # Set the current task in shared so nested nodes can access it
            shared["current_task"] = params["task"]
        return await super()._orch_async(shared, params)


# 5. Define a result collector node that waits for all results and combines them
class ResultCollectorNode(Node):
    def prep(self, shared):
        # Get all results from the shared store
        return shared.get("results", {})

    def exec(self, results):
        # Combine all results (in a real app, you might do something more complex)
        combined = "\n".join(
            [f"{task_type}: {result}" for task_type, result in results.items()]
        )
        return combined

    def post(self, shared, prep_res, exec_res):
        # Store the combined result
        shared["final_result"] = exec_res
        return "default"


# 6. Connect everything together

# Create nodes
start_node = StartNode()
branch_node = BranchNode()
process_a_node = ProcessANode()
process_b_node = ProcessBNode()
process_c_node = ProcessCNode()
result_node = ResultCollectorNode()

# Create branch connections
branch_node - "A" >> process_a_node
branch_node - "B" >> process_b_node
branch_node - "C" >> process_c_node

# Create the branching flow
branching_flow = AsyncFlow(start=branch_node)

# Create the parallel batch flow that wraps the branching flow
parallel_flow = ParallelTaskProcessor(start=branching_flow)

# Connect start to parallel flow to result
start_node >> parallel_flow >> result_node

# Create the final flow


@trace_flow()
class FinalFlow(AsyncFlow):
    def __init__(self):
        super().__init__(start=start_node)


complete_flow = FinalFlow()


# Run the flow
async def main():
    shared = {}
    await complete_flow.run_async(shared)
    print(f"Final result: {shared['final_result']}")


# Run the flow
if __name__ == "__main__":
    asyncio.run(main())

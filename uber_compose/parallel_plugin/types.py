from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class WorkerAssignment:
    worker_id: int
    groups: tuple[str, ...] = ()
    namespace_map: dict[str, str] = field(default_factory=dict)

    def env_id_for(self, group_key: str) -> str | None:
        return self.namespace_map.get(group_key)


@dataclass(frozen=True)
class ExecutionPlan:
    workers_total: int
    assignments: tuple[WorkerAssignment, ...] = ()

    def assignment_for(self, worker_id: int) -> WorkerAssignment | None:
        for assignment in self.assignments:
            if assignment.worker_id == worker_id:
                return assignment
        return None

    def namespace_map_for(self, worker_id: int) -> dict[str, str]:
        assignment = self.assignment_for(worker_id)
        return dict(assignment.namespace_map) if assignment is not None else {}


__all__ = ("ExecutionPlan", "WorkerAssignment",)

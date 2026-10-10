from ..data.agent import DataAgent
from ..data.analytics import AnalyticsPlan
from ..data.schemas import GeneratedSqlPlan
from ..data.sql_tool import ReadOnlySqlExecutor
from ..models import structured_model
from ..rag.service import create_rag_agent
from ..router.agent import RouterAgent
from ..router.schemas import RouteDecision
from ..triage.agent import TriageAgent
from ..triage.schemas import TriageResult
from .config import WorkflowSettings
from .graph import build_workflow
from .nodes import WorkflowNodes
from .schemas import WorkflowResult


class RetailWorkflow:
    def __init__(self, nodes: WorkflowNodes):
        self.graph = build_workflow(nodes)
        self.data = nodes.data

    def ask(
        self,
        question: str,
        *,
        viewer_employee_id: str | None = None,
        entity_context: dict[str, str] | None = None,
    ) -> WorkflowResult:
        # Caller identity is a trusted Python argument, never inferred by a model.
        return self.graph.invoke(
            {
                "question": question,
                "viewer_employee_id": viewer_employee_id,
                "entity_context": entity_context or {},
            }
        )["result"]


def create_workflow(settings: WorkflowSettings | None = None) -> RetailWorkflow:
    settings = settings or WorkflowSettings.from_env()
    return RetailWorkflow(
        WorkflowNodes(
            triage=TriageAgent(structured_model(settings.rag, TriageResult)),
            router=RouterAgent(structured_model(settings.rag, RouteDecision)),
            rag=create_rag_agent(settings.rag),
            data=DataAgent(
                structured_model(settings.rag, GeneratedSqlPlan),
                ReadOnlySqlExecutor(settings.database_path, settings.row_limit),
                settings.event_anchor,
                analytics_model=structured_model(settings.rag, AnalyticsPlan),
            ),
        )
    )

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """
    Abstract interface for multi-agent components.
    When agent development begins, all agents should implement this contract.
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent reasoning / processing loop with the given context.
        To be implemented in future phases.
        """
        raise NotImplementedError

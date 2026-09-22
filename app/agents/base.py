from abc import ABC, abstractmethod
from typing import Generic, TypeVar

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """Define the contract implemented by an Ops-Pilot agent."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the agent's name."""
        raise NotImplementedError

    @abstractmethod
    async def execute(self, input_data: InputT) -> OutputT:
        """Execute the agent with the supplied input."""
        raise NotImplementedError

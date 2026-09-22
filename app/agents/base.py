from abc import ABC, abstractmethod


class BaseAgent[InputT, OutputT](ABC):
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

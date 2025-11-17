from abc import ABC, abstractmethod

class BaseDataGateway(ABC):
    """Base interface for data gateways."""
    
    @abstractmethod
    def get_next_tick(self):
        """Retrieve the next market tick."""
        pass
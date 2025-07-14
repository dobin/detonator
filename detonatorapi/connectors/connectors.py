
from .connector import ConnectorBase
from .connector_newazure import ConnectorNewAzure
from .connector_running import ConnectorRunning


connectors_init = {
    "NewAzure": ConnectorNewAzure(),
    "Running": ConnectorRunning(),
}


class Connectors:
    """Class to manage all connectors"""
    
    def __init__(self):
        self.connectors = connectors_init


    def has(self, name: str) -> bool:
        """Check if a connector with the given name exists"""
        return name in self.connectors
    

    def get(self, name: str) -> ConnectorBase|None:
        """Get a connector by name"""
        return self.connectors.get(name, None)
    
    
    def get_all(self) -> dict:
        """Get all available connectors"""
        return self.connectors


connectors = Connectors()


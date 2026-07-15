from typing import Dict, List
from listing_hub.portals.base import AbstractPortal
from listing_hub.portals.bazos.bazos_portal import BazosPortal
from listing_hub.portals.aukro.aukro_portal import AukroPortal

class PortalRegistry:
    def __init__(self):
        self._portals: Dict[str, AbstractPortal] = {}
        
        # Registrace výchozích portálů
        self.register(BazosPortal())
        self.register(AukroPortal())

    def register(self, portal: AbstractPortal):
        self._portals[portal.name] = portal

    def get_portal(self, name: str) -> AbstractPortal:
        if name not in self._portals:
            raise ValueError(f"Portál '{name}' není registrován v systému.")
        return self._portals[name]

    def list_portals(self) -> List[AbstractPortal]:
        return list(self._portals.values())

portal_registry = PortalRegistry()

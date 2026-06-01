"""Central service registry.

Maintains a dictionary of all registered VPN protocol services and
provides convenient accessors by protocol name, active status, etc.

Usage::

    from app.services.registry import registry

    mtproto = registry.get("mtproto")
    for svc in registry.get_active_list():
        print(svc.display_name)
"""

from typing import Dict, Optional, List
from app.services.base import BaseVpnService
from app.services.mtproto import mtproto_service
from app.services.xray import xray_service
from app.services.hysteria2 import hysteria2_service


class ServiceRegistry:
    """Registry of all available VPN protocol services.

    Services are registered at import time. Once the registry is
    populated, callers use :meth:`get` or :meth:`get_active` to
    retrieve services.
    """

    def __init__(self):
        self._services: Dict[str, BaseVpnService] = {}

    def register(self, service: BaseVpnService) -> None:
        """Register a service by its protocol name.

        Args:
            service: A service instance.

        Raises:
            ValueError: If a service with the same protocol name
                is already registered.
        """
        if service.protocol_name in self._services:
            raise ValueError(f"Service '{service.protocol_name}' is already registered")
        self._services[service.protocol_name] = service

    def get(self, protocol: str) -> Optional[BaseVpnService]:
        """Get a service by protocol name.

        Args:
            protocol: The protocol identifier (e.g. 'mtproto').

        Returns:
            The service instance, or None if not found.
        """
        return self._services.get(protocol)

    def get_active(self) -> Dict[str, BaseVpnService]:
        """Return only enabled services.

        Returns:
            Dict mapping protocol name to service instance.
        """
        return {name: svc for name, svc in self._services.items() if svc.enabled}

    def get_all(self) -> Dict[str, BaseVpnService]:
        """Return all registered services (enabled or not).

        Returns:
            Dict mapping protocol name to service instance.
        """
        return dict(self._services)

    def get_active_list(self) -> List[BaseVpnService]:
        """Return a list of all enabled service instances."""
        return [svc for svc in self._services.values() if svc.enabled]

    def get_protocol_names(self) -> List[str]:
        """Return the protocol names of all enabled services."""
        return [name for name, svc in self._services.items() if svc.enabled]


# Populate the global registry at import time.
registry = ServiceRegistry()
registry.register(mtproto_service)
registry.register(xray_service)
registry.register(hysteria2_service)

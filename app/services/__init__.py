"""VPN protocol service implementations.

This package contains the abstract base class and concrete
implementations for each supported VPN protocol.

Each protocol is a sub-package (``app.services.mtproto``,
``app.services.xray``, ``app.services.hysteria2``) that exports
a singleton service instance.

The registry at ``app.services.registry`` provides centralised
access to all available services.
"""

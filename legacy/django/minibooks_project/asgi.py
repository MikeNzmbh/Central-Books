"""
ASGI config for minibooks_project project.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import agentic.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'minibooks_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            agentic.routing.websocket_urlpatterns
        )
    ),
})

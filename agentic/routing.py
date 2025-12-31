from django.urls import re_path
from .traces import consumers

websocket_urlpatterns = [
    re_path(r'ws/agent/traces/(?P<trace_id>\w+)/$', consumers.AgentTraceConsumer.as_asgi()),
    re_path(r'ws/agent/broadcast/$', consumers.AgentBroadcastConsumer.as_asgi()),
]

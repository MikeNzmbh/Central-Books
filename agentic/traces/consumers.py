import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AgentTraceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.trace_id = self.scope['url_route']['kwargs']['trace_id']
        self.group_name = f'trace_{self.trace_id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def agent_step(self, event):
        await self.send(text_data=json.dumps(event))

class AgentBroadcastConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'agent_broadcast'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def broadcast_message(self, event):
        await self.send(text_data=json.dumps(event))

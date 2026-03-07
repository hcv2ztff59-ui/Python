
class SocketManage:
    def __init__(self):
        # user_id -> lista websocket
        self.active_connections = {}

    async def connect(self, user_id: int, websocket):
        await websocket.accept()

        if user_id not in self.active_connections:
          self.active_connections[user_id] = []

        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: int, websocket):
        self.active_connections[user_id].remove(websocket)
        if len(self.active_connections[user_id]) == 0:
            self.active_connections[user_id]

    async def send_to_user(self, user_id: int, message: str):

        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_text(message)



#TODO GESTIRE ECCEZZIONI SOCKET

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
            del self.active_connections[user_id]

    async def send_complete_task_to_user(self, user_id: int, message):
        print("WS send:", user_id, message)
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_json({"task_id":message["task_id"], "type": "complete_task", "completato":message["completato"]})
               
    async def send_update_task_to_user(self, user_id: int, message):
        print("WS send:", user_id, message)
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_json({"task_id":message["task_id"], "type": "updated_task"})
               

    async def send_occurrency_update_to_user(self, user_id: int, message):
        print("WS send:", user_id, message)
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                    await connection.send_json({"task_id":message["task_id"],"type": "occurrency","date_time_repeat": message["date_time_repeat"], "end_recurrency_time":message["end_recurrency_time"]})


manager = SocketManage()

from datetime import timezone, datetime
#TODO GESTIRE ECCEZZIONI SOCKET
#TODO implementare ws send_occurrency_date_end_task_to_user 

class SocketManage:
    def __init__(self):
        # user_id -> lista websocket
        self.active_connections = {}

    async def connect(self, user_id: int, websocket):
        await websocket.accept()

        for conn in self.active_connections:
            print(f"connessione attiva: {conn}")
            
        if user_id not in self.active_connections:
          self.active_connections[user_id] = []

        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: int, websocket):
        if user_id not in self.active_connections:
            return

        if websocket in self.active_connections[user_id]:
            self.active_connections[user_id].remove(websocket)

        if not self.active_connections[user_id]:
            del self.active_connections[user_id]
        
        print(f"Connessioni attive per {user_id}: {len(self.active_connections.get(user_id, []))}")

    
    def has_multiple_connections(self, user_id: int) -> bool:
        return len(self.active_connections.get(user_id, [])) > 1

    async def send_complete_task_to_user(self, user_id: int, message):
        print("WS send:", user_id, message)
        if user_id in self.active_connections:
            dead_connections = []
            for connection in list(self.active_connections[user_id]):
                
                try:
                    await connection.send_json({
                        "task_id": message["task_id"],
                        "type": "complete_task",
                        "completato": message["completato"]
                    })
                except Exception as e:
                    print("🔴 socket morto:", e)
                    dead_connections.append(connection)
            for conn in dead_connections:
                self.disconnect(user_id, conn)
               
    async def send_update_task_to_user(self, user_id: int, message):
        print("WS send:", user_id, message)

        if user_id not in self.active_connections:
            return

        for connection in list(self.active_connections[user_id]):
            try:
                await connection.send_json({
                    "task_id": message["task_id"],
                    "type": "updated_task"
                })
            except Exception as e:
                print("🔴 socket morto:", e)

                try:
                    await connection.close()
                except:
                    pass

                self.disconnect(user_id, connection)
               
    async def send_new_task_to_user(self, user_id: int, message):
        print("WS send:", user_id, message)

        if user_id not in self.active_connections:
            return

        for connection in list(self.active_connections[user_id]):
            try:
                await connection.send_json({
                    "task_id": message["task_id"],
                    "type": "new_task"
                })
            except Exception as e:
                print("🔴 socket morto:", e)

                try:
                    await connection.close()
                except:
                    pass

                self.disconnect(user_id, connection)

    async def send_deleted_task_to_user(self, user_id: int, message):
        print("WS send:", user_id, message)

        if user_id not in self.active_connections:
            return

        for connection in list(self.active_connections[user_id]):
            try:
                await connection.send_json({
                    "task_id": message["task_id"],
                    "type": "deleted_task"
                })
            except Exception as e:
                print("🔴 socket morto:", e)

                try:
                    await connection.close()
                except:
                    pass

                self.disconnect(user_id, connection)

    async def send_occurrency_update_to_user(self, user_id: int, message):
        print("WS send:", user_id, message)
        if user_id in self.active_connections:
            dead_connections = []
            for connection in list(self.active_connections[user_id]):
                try:
                    await connection.send_json({"task_id":message["task_id"],"type": "occurrency","date_time_repeat": format_utc(message["date_time_repeat"]), "end_recurrency_time":message["end_recurrency_time"]})
                except Exception as e:
                    print("🔴 socket morto:", e)
                    dead_connections.append(connection)
            for conn in dead_connections:
                self.disconnect(user_id, conn)

manager = SocketManage()

def format_utc(dt):
    if dt is None:
        return None

    # 👉 se è stringa → parse
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))

    # 👉 se non ha timezone → aggiungila
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.isoformat().replace("+00:00", "Z")

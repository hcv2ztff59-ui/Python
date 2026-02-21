from firebase_admin import messaging

def send_service(token:str, title: str,body: str):
    message = messaging.Message(
        notification= messaging.Notification(
            title=title,
            body=body
        )
    )

    response = messaging.send(message)
    print("firebase response ", response)
    return response

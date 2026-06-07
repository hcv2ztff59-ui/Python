import firebase_admin
import os
import json

from firebase_admin import credentials, messaging
# todo per upload su github mettterlo a False
local = False
if local:
    cred = credentials.Certificate("serviceAccountKey.json")
else:
    firebase_json = json.loads(os.environ["FIREBASE_CREDENTIALS"])
    cred = credentials.Certificate(firebase_json)



print("Firebase caricato")

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)
    print("Firebase inizializzato correttamente")


def invia_push(token_dispositivo, titolo_task,msg:str):
    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=titolo_task,body=msg),
        android=messaging.AndroidConfig(
            priority='high',  # Forza la consegna immediata
            notification=messaging.AndroidNotification(
                channel_id='TODO_CHANNEL_ID',  # Deve corrispondere al Kotlin
                priority='high',  # Forza la comparsa del banner (Heads-up)
                default_sound=True,
                default_vibrate_timings=True
            ),
        ),
        tokens=token_dispositivo
    )

    try:
        response = messaging.send_each_for_multicast(message)
        print(f"Inviati con successo: {response.success_count}")
        print(f"Falliti: {response.failure_count}")
    except Exception as e:
        print(f"errore notifica {e}")

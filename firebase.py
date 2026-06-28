import firebase_admin
import os
import json

from firebase_admin import credentials, messaging
# todo per upload su github mettterlo a False





if os.path.exists("serviceAccountKey.json"):
    cred = credentials.Certificate("serviceAccountKey.json")
else:
    service_account = json.loads(os.environ["FIREBASE_CREDENTIALS"])
    cred = credentials.Certificate(service_account)


print("Firebase caricato")

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)
    print("Firebase inizializzato correttamente")


def invia_push_silenziosa(token: str, event: str):

    message = messaging.Message(

        token=token,

        data={

            "event": event,

        },

        android=messaging.AndroidConfig(

            priority="high",

        ),

    )

    try:

        response = messaging.send(message)

        print("PUSH INVIATA:", response)

        return response

    except Exception as e:

        print("ERRORE PUSH:", e)

        raise
    
def invia_push_notifica(token_dispositivo, nickname, id_utente, title,body,event):

    # Se è una stringa la trasformo in lista
    print("=== INVIA PUSH RICHIESTA ===")

    print("TOKEN:", token_dispositivo)

    print("NICKNAME:", nickname)

    print("USER ID:", id_utente)
    if isinstance(token_dispositivo, str):

        token_dispositivo = [token_dispositivo]

    print("LISTA TOKEN:", token_dispositivo)

    print("NUMERO TOKEN:", len(token_dispositivo))
    if len(token_dispositivo) == 1:
        print("Invio con Message")
        message = messaging.Message(

            token=token_dispositivo[0],

            notification=messaging.Notification(

                title= title,

                body=body,

            ),

            data={

                "event": event,

                "user_id": str(id_utente),

            },

            android=messaging.AndroidConfig(

                priority="high",

                notification=messaging.AndroidNotification(

                    channel_id="TODO_CHANNEL_ID",

                ),

            ),

        )

        response = messaging.send(message)

        print("RISPOSTA FIREBASE:", response)
        return response

    else:
        print("Invio con Multicast")
        message = messaging.MulticastMessage(

            tokens=token_dispositivo,

            notification=messaging.Notification(

                title="Nuova richiesta di amicizia",

                body=f"{nickname} ti ha inviato una richiesta di amicizia",

            ),

            data={

                "event": "friend_request",

                "user_id": str(id_utente),

            },

            android=messaging.AndroidConfig(

                priority="high",

                notification=messaging.AndroidNotification(

                    channel_id="TODO_CHANNEL_ID",

                ),

            ),

        )

        response = messaging.send_each_for_multicast(message)

        print("SUCCESS:", response.success_count)

        print("FAIL:", response.failure_count)

        return response
    
    
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

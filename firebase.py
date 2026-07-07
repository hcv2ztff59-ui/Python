import firebase_admin
import os
import json
import traceback
from firebase_admin import credentials, messaging
from firebase_admin.messaging import UnregisteredError

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


def invia_push_silenziosa(token: str, event: str, extra_data=None):
    # Prepariamo il dizionario flat chiave-valore
    payload_data = {"event": event}
    
    # Se ci sono i contatori, li uniamo direttamente al dizionario principale
    if extra_data and isinstance(extra_data, dict):
        payload_data.update(extra_data)

    message = messaging.Message(
        token=token,
        data=payload_data,  # Ora è un dizionario piatto di stringhe!
        android=messaging.AndroidConfig(
            priority="high",
        ),
        apns=messaging.APNSConfig(
            headers={
                "apns-push-type": "background",
                "apns-priority": "5",
            },
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    content_available=True,
                )
            ),
        ),
    )

    try:
        response = messaging.send(message)
        print("PUSH INVIATA:", response)
        return response
    except Exception as e:
        print(type(e))
        print(repr(e))
        traceback.print_exc()
        raise
    

def invia_push_notifica(token_dispositivo, nickname, id_utente, title, body, event, extra_data=None):
    print("=== INVIA PUSH RICHIESTA ===")
    print("TOKEN:", token_dispositivo)
    print("NICKNAME:", nickname)
    print("USER ID:", id_utente)
    
    if isinstance(token_dispositivo, str):
        token_dispositivo = [token_dispositivo]

    print("LISTA TOKEN:", token_dispositivo)
    print("NUMERO TOKEN:", len(token_dispositivo))
    
    # Prepariamo i dati flat per l'evento
    payload_data = {
        "event": event,
        "user_id": str(id_utente),
        "nickname": str(nickname)
    }
    
    # Uniamo i contatori extra in modo che siano chiavi di primo livello
    if extra_data and isinstance(extra_data, dict):
        payload_data.update(extra_data)

    if len(token_dispositivo) == 1:
        print("Invio con Message")
        message = messaging.Message(
            token=token_dispositivo[0],
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=payload_data,  # Dizionario piatto garantito
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="TODO_CHANNEL_ID",
                ),
            ),
            apns=messaging.APNSConfig(
                headers={
                    "apns-priority": "10",
                    "apns-push-type": "alert",
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                    )
                ),
            ),
        )

        try:
            response = messaging.send(message)
            print("RISPOSTA FIREBASE:", response)
            return response
        except Exception as e:
            print(type(e))
            print(repr(e))
            traceback.print_exc()
            raise

    else:
        print("Invio con Multicast")
        message = messaging.MulticastMessage(
            tokens=token_dispositivo,
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=payload_data,  # Dizionario piatto garantito
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="TODO_CHANNEL_ID",
                ),
            ),
            apns=messaging.APNSConfig(
                headers={
                    "apns-priority": "10",
                    "apns-push-type": "alert",
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                    )
                ),
            ),
        )

        response = messaging.send_each_for_multicast(message)
        print("SUCCESS:", response.success_count)
        print("FAIL:", response.failure_count)
        return response
    
    
def invia_push(token_dispositivo, titolo_task, msg: str):
    if isinstance(token_dispositivo, str):
        token_dispositivo = [token_dispositivo]
        
    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=titolo_task, body=msg),
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                channel_id='TODO_TODO_CHANNEL_ID',
                priority='high',
                default_sound=True,
                default_vibrate_timings=True
            ),
        ),
        apns=messaging.APNSConfig(
            headers={
                "apns-priority": "10",
                "apns-push-type": "alert",
            },
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound="default",
                )
            ),
        ),
        tokens=token_dispositivo
    )

    try:
        response = messaging.send_each_for_multicast(message)
        print(f"Inviati con successo: {response.success_count}")
        print(f"Falliti: {response.failure_count}")
    except Exception as e:
        print(type(e))
        print(repr(e))
        traceback.print_exc()
        raise
import requests
import pandas as pd

#data = {
#    "email": "baby@example.com",
#    "password": "0000", }
data = {
    "email": "davide@example.com",
    "password": "1234", }

response = requests.post(
    "http://127.0.0.1:8000/user/register",json=data )

#print(response.json())
#faccio login
#response = requests.post("http://127.0.0.1:80000/user/login",json=data )

#print(response.json())


#headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
#le richieste le mando con il token di accesso

#inserimento_task = {
#    "descrizione": "Una Prova del task per baby",
#    "task_datetime": "2026-02-10T08:35:02.471Z",
#    "titolo":"Preparare caffè",
#    "completato":False,
#    "user_id":0
#}

#crea task
#response = requests.post("http://127.0.0.1:8000/task/crea_task",json=inserimento_task,headers=headers )
#print(response.json())

#response = requests.get("http://127.0.0.1:8000/task/visualizza_task", headers=headers)


# a livello grafico bisogna immaginarlo come un elenco di task dove è possibile sceglierne uno, quindi prendo l'id
#id_task = response.json()[0]["id_task"]


#data_update = {
#    "descrizione": "Una Prova del task per baby",
#    "titolo": "Preparare caffè", }
#aggiorna task
#response = requests.patch(f"http://127.0.0.1:8000/task/modifica_task?id_task={id_task}", json=data_update,headers=headers)

#visualizza
#response = requests.get("http://127.0.0.1:8000/task/visualizza_task", headers=headers)
#print("*"*50)
#dt = pd.DataFrame(response.json())
#print(dt)

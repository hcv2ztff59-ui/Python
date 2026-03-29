# This is a sample Python script.
from datetime import datetime
from dataclasses import dataclass
from threading import Thread


# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.
@dataclass
class TodoList:
    def __init__(self,id_evento=0,nome_evento="",descrizione="",alert=False,date="",atTime="",notified=False):
        self.id_evento = id_evento
        self.nome_evento = nome_evento
        self.descrizione = descrizione
        self.alert = alert
        self.date = date
        self.atTime = atTime
        self.notified = notified

class Todo:
    todoVar = []
    filteredTodoList = []
    currentTodo = TodoList()
    id_evento = 0
    todoOpz = [("FUTURE",0),("PAST",1),("CURRENT",2)]

    def __init__(self):
        pass

    def addTodo(self, nome_evento, descrizione, alert, date, atTime, notifiedevent):
        self.todoVar.append(TodoList(self.id_evento, nome_evento, descrizione, alert, date, atTime,notifiedevent))
        self.id_evento+=1

    def updateValueEvent(self,id_evento,updateTodoList):
        self.todoVar[id_evento] = updateTodoList

    def updateAlarmNotify(self,id_evento,uwantanotify):
        tmp = self.todoVar[id_evento]
        tmp.alert = uwantanotify

    def getToday(self):
        now = datetime.now()
        return now.strftime("%Y-%m-%d")

    def getNowTimeStr(self):
        now = datetime.now()
        return now.strftime("%H:%M")

    def getRemainEventsCount(self):
        return len(self.filteredTodoList)

    def getTodoList(self):
        return self.todoVar

    def getFilteredTodoList(self):
        return self.filteredTodoList

    def getCurrentTodo(self):
        return self.currentTodo

    def removeEventPast(self,event):
        self.filteredTodoList.remove(event)

    def setForListEvent(self,customdate,customhour,todoopz):
        hour = self.getNowTimeStr()
        date = self.getToday()

        if customhour != "":
            hour = customhour
        if customdate != "":
            date = customdate

        if todoopz == "FUTURE":
            self.filteredTodoList = [todo for todo in self.todoVar if todo.date > date or (todo.date == date and todo.atTime > hour)]
            
        elif todoopz == "PAST":
            self.filteredTodoList = [todo for todo in self.todoVar if todo.date < date or (todo.date == date and todo.atTime < hour)]
           

        elif todoopz == "CURRENT":
            self.filteredTodoList = [todo for todo in self.todoVar if todo.date == date and todo.atTime == hour]
            
        else:
            self.filteredTodoList = [todo for todo in self.todoVar if todo.atTime > ""]
         
    def listenAtTimeEvent(self):
        time = self.getNowTimeStr()

        for item in self.filteredTodoList:
            if item.atTime == time and not item.notified:
                item.notified = True
                self.currentTodo = item
                self.removeEventPast(item)
                return True
        return False

    def executeLoopTodo(self):
        while True:
            if self.listenAtTimeEvent():
                self.manageEvent()

    def manageEvent(self):
        print(f"it's Time! {self.currentTodo.nome_evento} Notified set up to {self.currentTodo.notified}")


class MyTodo(Todo):
    def __init__(self):
        super().__init__()
    def manageEvent(self):
        print(f"it's Time for personal MyTodo! {self.currentTodo.nome_evento} Notified set up to {self.currentTodo.notified}")


# Press the green button in the gutter to run the script.
if __name__ == '__main__':


    todoObj = MyTodo()
    todoObj.addTodo("Evento 1","test",False,"2026-01-06","12:00",False)
    todoObj.addTodo("Evento 2", "test", False, "2026-01-07", "11:20", False)
    todoObj.addTodo("Evento 3", "test", False, "2026-01-07", "18:40", False)
    todoObj.addTodo("Evento 4", "test", False, "2026-01-10", "19:50", False)

    todoObj.setForListEvent("","","FUTURE")
    tmp = todoObj.getFilteredTodoList()
    print(f"\nData/Ora Oggi: {todoObj.getToday()} Ore: {todoObj.getNowTimeStr()}")
    print(f"\nEventi in Programma:")
    for i in tmp:
        print(f"\tNome evento:{i.nome_evento} Data:{i.date} Ora:{i.atTime} ")


    if todoObj.getRemainEventsCount() > 0:
        thread = Thread(target=todoObj.executeLoopTodo(), daemon=True)
        thread.start()
    else:
        print("\nNo there are events for today!")

    strIn = input("Press Enter to continue...")

    if strIn == "":
        print("Pressed")



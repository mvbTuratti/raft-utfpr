from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from Pyro5 import client, api, core
import asyncio
import uvicorn
import subprocess
import signal
import os

from datetime import datetime

app = FastAPI()

app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")


class PyroManager:
    def __init__(self):
        self.name_server_process = None
        self.node_processes = {}
        self.base_node_names = ["PYRO:Server@localhost:9091", "PYRO:Server2@localhost:9092", 
                                "PYRO:Server3@localhost:9093", "PYRO:Server4@localhost:9094"]

    def start_name_server(self):
        if self.name_server_process is None:
            self.name_server_process = subprocess.Popen(['python', '-m', 'Pyro5.nameserver'])
            print("Name server started with PID:", self.name_server_process.pid)
        else:
            print("Name server is already running.")

    def stop_name_server(self):
        if self.name_server_process is not None:
            self.name_server_process.send_signal(signal.SIGINT)
            self.name_server_process.wait()
            print("Name server stopped.")
            self.name_server_process = None
        else:
            print("Name server is not running.")

    def start_node(self, node_id):
        if node_id not in self.node_processes:
            process = subprocess.Popen(['python', 'src/script.py', str(node_id)])
            self.node_processes[node_id] = process
            print(f"Node {node_id} started with PID:", process.pid)
        else:
            print(f"Node {node_id} is already running.")

    def stop_node(self, node_id):
        if node_id in self.node_processes:
            process = self.node_processes[node_id]
            process.send_signal(signal.SIGINT)
            process.wait()
            print(f"Node {node_id} stopped.")
            del self.node_processes[node_id]
        else:
            print(f"Node {node_id} is not running.")

    def stop_all_nodes(self):
        for node_id in list(self.node_processes.keys()):
            self.stop_node(node_id)

    def force_stop_all(self):
        if self.name_server_process is not None:
            self.name_server_process.kill()
            print("Name server forcefully stopped.")
            self.name_server_process = None
        for node_id, process in self.node_processes.items():
            process.kill()
            print(f"Node {node_id} forcefully stopped.")
        self.node_processes.clear()
        
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)
manager = ConnectionManager()

async def run_listener_loop():
    while True:
        await asyncio.sleep(0.5)
        
task = asyncio.create_task(run_listener_loop())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f'received message from websocket: {data}')
            [hash, content] = data.split(" - ", 1)
    except:
        print("client disconnected!")
    finally:
        manager.disconnect(websocket)


@app.get("/", response_class=HTMLResponse )
async def return_app(request: Request):
    return HTMLResponse(content=open("static/index.html", "r").read())

@app.get("/messages/")
async def return_messages():
    return JSONResponse(content={"messages": manager.messages})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
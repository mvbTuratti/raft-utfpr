from __future__ import annotations
from enum import Enum
from Pyro5 import client, api

class Option:
    value: int
    def __init__(self, option:str = 1):
        try:
            number = int(option)
            if number > 0 and number < 5:
                self.value = number
            else: self.value = 1
        except:
            self.value = 1
    def __repr__(self): return f'Server{self.value}'
    def name(self): return str(self)


class Server(Enum):
    FIRST = "PYRO:Server1@localhost:9091"
    SECOND = "PYRO:Server2@localhost:9092"
    THIRD = "PYRO:Server3@localhost:9093"
    FOURTH = "PYRO:Server4@localhost:9094"
    @classmethod
    def create(cls, type: int) -> Server:
        return {1: Server.FIRST, 2: Server.SECOND, 3: Server.THIRD, 4: Server.FOURTH}.get(type, Server.FIRST)
    @classmethod
    def get_port(cls, number: int) -> int:
        return {1: 9091, 2: 9092, 3: 9093, 4: 9094}.get(number, 9091)
    @classmethod
    def get_peers(cls, self: Option) -> dict[str, client.Proxy]:
        peers: dict[str, client.Proxy] = { Server.create(entry).value : api.Proxy(Server.create(entry).value) for entry in range(1,5) if entry != self.value }
        return peers
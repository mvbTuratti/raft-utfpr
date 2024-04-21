from __future__ import annotations
from Pyro5 import core, server
import sys
from enum import Enum


@server.expose
@server.behavior(instance_mode="single")
class Ledger(object):
    def __init__(self):
        self.contents = ["chair", "bike", "flashlight", "laptop", "couch"]

    def list_contents(self):
        return self.contents

    def take(self, name, item):
        self.contents.remove(item)
        print("{0} took the {1}.".format(name, item))

    def store(self, name, item):
        self.contents.append(item)
        print("{0} stored the {1}.".format(name, item))


class Server(Enum):
    FIRST = "PYRO:Server1@localhost:9090"
    SECOND = "PYRO:Server2@localhost:9091"
    THIRD = "PYRO:Server3@localhost:9092"
    FOURTH = "PYRO:Server4@localhost:9093"
    @classmethod
    def create(cls, option: Option) -> Server:
        return {1: Server.FIRST, 2: Server.SECOND, 3: Server.THIRD, 4: Server.FOURTH}.get(option.value, Server.FIRST)
    @classmethod
    def get_port(cls, number: int) -> int:
        return {1: 9090, 2: 9091, 3: 9092, 4: 9093}.get(number, 9090)
    @classmethod
    def get_peers(cls, self: Option):
        peers: list[str] = [ Server.create(entry).value for entry in range(1,5) if entry != self]
        return peers


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


def main(server_number: Option):
    # server_representation: Server = Server.create(server_number)
    daemon = server.Daemon(port=Server.get_port(server_number.value))
    peers: list[str] = Server.get_peers(server_number)
    print("daemon ", daemon)
    uri_object = daemon.register(Ledger, objectId=server_number.name())
    print(uri_object)
    print(peers)

if __name__=="__main__":
    option = sys.argv[1] if len(sys.argv) > 1 else 1
    server_number = Option(option) 
    main(server_number=server_number)
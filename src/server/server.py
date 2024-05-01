from Pyro5 import server, api
import asyncio
import sys
from raft.node import RaftNode
from pyro_configuration.uri_peers import Server, Option

async def main(server_number: Option):
    daemon = server.Daemon(port=Server.get_port(server_number.value))
    peers: list[str] = Server.get_peers(server_number)
    uri = Server.create(server_number.value).value
    print(f'URI - value {server_number} - {uri}')
    name_server = api.locate_ns()
    current_ledger = RaftNode(peers, uri=uri, name_server=name_server)
    uri_object = daemon.register(current_ledger, objectId=server_number.name())
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, daemon.requestLoop)

if __name__=="__main__":
    option = sys.argv[1] if len(sys.argv) > 1 else 1
    server_number = Option(option) 
    asyncio.run(main(server_number=server_number))
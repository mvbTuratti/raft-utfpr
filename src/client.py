from Pyro5 import core, server, api
import asyncio

@server.expose
@server.behavior(instance_mode="single")
class Client:
    name_server: any
    commands: set[str]
    commited_commands: set[str]
    uri: str
    def __init__(self, ns, uri):
        self.name_server = ns
        self.uri = uri
        self.commands = set()
        self.commited_commands = set()
    def send_command(self, cmd):
        leader = self.name_server.lookup("Leader")
        response = api.Proxy(leader).leader_commmand(cmd, self.uri)
        print(response)
        self.commands.add(cmd)
        self.print_send_cmds()

    @server.oneway
    def background_processed(self, cmd):
        print("Received response from server")
        self.commited_commands.add(cmd)
        self.print_commited()

    def print_commited(self): return f"{self.commited_commands}"
    def print_send_cmds(self): return f"{self.commands}"
    def __repr__(self): return f"Client(uri={self.uri})"

async def run_cmds(client: Client):
    while True:
        inp = input()
        client.send_command(inp)


async def main():
    client_name = "PYRO:Client@localhost:10101"
    ns = core.locate_ns()
    daemon = server.Daemon(port=10101)
    client = Client(ns, client_name)
    uri_object = daemon.register(client, objectId="Client")
    loop = asyncio.get_event_loop()
    asyncio.create_task(run_cmds(client))
    await loop.run_in_executor(None, daemon.requestLoop)

if __name__ == "__main__":
    asyncio.run(main())

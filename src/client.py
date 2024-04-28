from Pyro5 import core, server, api, client

if __name__ == "__main__":
    server = "PYRO:Server1@localhost:9091"
    ledger = api.Proxy(server)
    # ledger.heartbeat()
    ledger.log_replication("TEST TEST")
    # a = ledger.request_vote()
    # print(a)

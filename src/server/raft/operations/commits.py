class Ack:
    ack: str
    def __init__(self, uri: str):
        self.ack = uri
    def __hash__(self): return hash(self.ack)

class Commit:
    hash: str
    acks: set[Ack]
    _source_uri: str
    majority: int
    def __init__(self, hash: str,node_uri: str, number_of_servers: int):
        self.acks = set(node_uri)
        self._source_uri = node_uri
        self.hash = hash
        self.majority = number_of_servers // 2
    def _reset_acks(self): self.acks = set(self._source_uri)
    def add_ack(self, ack: Ack,retried: bool = False):
        if retried: self._reset_acks()
        self.acks.add(ack)
        return len(self.acks) > self.majority
    def __hash__(self): return hash(self.hash)
    def __eq__(self, hash: str): return self.hash == hash

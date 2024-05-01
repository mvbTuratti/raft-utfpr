class Ack:
    ack: str
    hash: str
    def __init__(self, hash: str, uri: str):
        self.ack = uri
        self.hash = hash
    def __hash__(self): return hash(self.ack)
    def __repr__(self): return f"ACK - {self.ack} - {self.hash}"

class Commit:
    hash: str
    acks: set[Ack]
    _source_uri: str
    majority: int
    has_commited: bool
    cmd: str
    def __init__(self, hash: str,node_uri: str, number_of_servers: int, cmd: str):
        self.acks = set([Ack(hash, node_uri)])
        self._source_uri = node_uri
        self.hash = hash
        self.majority = number_of_servers // 2
        self.has_commited = False
        self.cmd = cmd
    def _reset_acks(self): self.acks = set(self._source_uri)
    def add_ack(self, ack: Ack,retried: bool = False):
        """ This function adds """
        if retried: self._reset_acks()
        self.acks.add(ack)
        return len(self.acks) > self.majority if not self.has_commited else False
    def __hash__(self): return hash(self.hash)
    def __eq__(self, hash: str | Ack): 
        if isinstance(hash, Ack): return self.hash == hash.hash
        return self.hash == hash
    def __repr__(self): return f"Commit(hash={self.hash}, acks={self.acks}, is_commited={self.has_commited})"
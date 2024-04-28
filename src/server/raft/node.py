from __future__ import annotations
from enum import Enum, auto
from Pyro5 import server, api, client
from random import randint
from raft.operations.key_value import Redis
from raft.votes.voting import Term, Vote
import asyncio

class NodeState(Enum):
    FOLLOWER = auto()
    CANDIDATE = auto()
    LEADER = auto()

@server.expose
@server.behavior(instance_mode="single")
class RaftNode(object):
    state: NodeState
    _heartbeat_received: asyncio.Event | None
    _election_term_responses: asyncio.Event | None
    redis: Redis
    term: Term
    uri: str
    peers: dict[str, api.Proxy]
    
    def __init__(self, peers: dict[str, client.Proxy], timer: int = None):
        self.state = NodeState.FOLLOWER
        self.peers = peers
        self.follower = None
        self.leader = None
        self._timer = timer
        self.redis = Redis()
    def add_uri(self, uri: str): 
        self.uri = uri
        self.initiate_term()

    def initiate_term(self, number_of_servers: int = 4):
        self.term = Term(self.uri, number_of_servers)
    @property
    def state(self):
        return self.state
    
    @state.setter
    def state(self, value):
        if not isinstance(value, NodeState): raise ValueError("the accepted value is only a node state")
        match value:
            case NodeState.FOLLOWER:
                print("setting as FOLLOWER")
                self._heartbeat_received = asyncio.Event()
                self.start()
            case NodeState.CANDIDATE:
                print("setting as candidate")
                asyncio.create_task(self.create_election_term())
            case NodeState.LEADER:
                print("setting as LEADER")
    
    @property
    def timeout(self):
        return self._timer if self._timer else randint(150, 300)
    
    async def _follow_the_leader(self):
        try:
            while True:
                await asyncio.wait_for(self._heartbeat_received.wait(), self.timeout / 1000)
                self._heartbeat_received.clear()
                print(f"Heartbeat received from leader on {self}")
        except asyncio.TimeoutError:
            print("Timeout reached, changing to candidate")
            self.state = NodeState.CANDIDATE

    def start(self):
        self.follower = asyncio.create_task(self._follow_the_leader())
        
    async def create_election_term(self):
        vote_payload = self.term.initiate_votes()
        while self.state == NodeState.CANDIDATE:
            for peer in self.peers:
                self.peers[peer].request_vote(vote_payload)
            await asyncio.sleep(self.timeout / 1000)
            vote_payload = self.term.initiate_votes(retried=True) #reset the payload to only contains self vote, same term
    
    @server.oneway
    def send_vote_result(self, vote: Vote):
        is_leader = self.term.add_vote(vote)
        if is_leader: self.state = NodeState.LEADER

    @server.oneway
    def request_vote(self, vote: tuple[int, str]):
        vote: None | Vote = self.term.compare_election(vote)
        if vote: 
            uri: str = vote.uri
            self.peers[uri].send_vote_result(vote)
    @server.oneway
    def log_replication(self, command: str):
        print(command, self.uri)

    @server.oneway
    def heartbeat(self, command: tuple[str,str] | None = None):
        self._heartbeat_received.set()
        if command:
            print(f"received: {command}")

    def _send_heartbeats(self, command: str | None):
        for peer in self.peers:
            payload = (self.uri, command) if command else None
            self.peers[peer].heartbeat(payload)
        

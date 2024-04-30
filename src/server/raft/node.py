from __future__ import annotations
from enum import Enum, auto
from Pyro5 import server, api, client
from random import randint
from raft.operations.key_value import Redis
from raft.operations.commits import Commit
from raft.votes.voting import Term, Vote
from datetime import datetime
import time
import asyncio

class NodeState(Enum):
    FOLLOWER = auto()
    CANDIDATE = auto()
    LEADER = auto()

@server.expose
@server.behavior(instance_mode="single")
class RaftNode(object):
    _state: NodeState
    _heartbeat_received: asyncio.Event | None
    _election_term_responses: asyncio.Event | None
    redis: Redis
    term: Term
    uri: str
    commits: set[Commit]
    peers: dict[str, api.Proxy]
    leader_messaged: bool
    _callbacks: dict[str, str]
    
    def __init__(self, peers: dict[str, client.Proxy], uri: str,timer: int = None):
        print("Init RaftNode object")
        self.peers = peers
        self._set_peers_timeout()
        self.follower = None
        self._timer = timer
        self.redis = Redis()
        self.commits = set()
        self.leader_messaged = False
        self._callbacks = {}
        self.uri = uri
        self.initiate_term()
        self.state = NodeState.FOLLOWER
        print("Finished init")
    
    def _set_peers_timeout(self):
        """ Sets timeout of 150ms for proxy remote calls """
        for proxy in self.peers:
            self.peers[proxy]._pyroTimeout = 0.15

    def initiate_term(self, number_of_servers: int = 4):
        self.term = Term(self.uri, number_of_servers)

    @property
    def state(self):
        return self._state
    
    @state.setter
    def state(self, value):
        print(f"State setter: {value}")
        if not isinstance(value, NodeState): raise ValueError("the accepted value is only a node state")
        self._state = value
        match value:
            case NodeState.FOLLOWER:
                print("setting as FOLLOWER")
                if not self.follower:
                    self._heartbeat_received = asyncio.Event()
                    self.start()
            case NodeState.CANDIDATE:
                print("setting as CANDIDATE")
                asyncio.create_task(self._create_election_term())
            case NodeState.LEADER:
                print("setting as LEADER")
                asyncio.create_task(self._send_heartbeat_to_followers())
    
    @property
    def timeout(self):
        # return self._timer if self._timer else randint(150, 300)
        return self._timer if self._timer else randint(1500, 3000)
    
    async def _follow_the_leader(self):
        while True:
            try:
                await asyncio.wait_for(self._heartbeat_received.wait(), self.timeout / 1000)
                self._heartbeat_received.clear()
            except asyncio.TimeoutError:
                if self.state == NodeState.FOLLOWER:
                    self.state = NodeState.CANDIDATE
                    await asyncio.sleep(1.5)

    def start(self):
        self.follower = asyncio.create_task(self._follow_the_leader())
        
    async def _create_election_term(self):
        print("Initiated votes...")
        while self.state == NodeState.CANDIDATE:
            self.term.initiate_votes()
            is_leader = await self._gather_election_term()
            if is_leader: self.state = NodeState.LEADER

    async def _gather_election_term(self) -> bool:
        """
        Sends heartbeat to the other servers in parallel with a timeout of 100ms.
        Returns a list of success statuses for each call.
        """
        async def call_proxy(proxy, term: int):
            try:
                return self.peers[proxy].vote_for_leader(term)
            except Exception as e:
                return False

        tasks = [call_proxy(proxy, self.term.term) for proxy in self.peers]
        results = await asyncio.gather(*tasks)
        return len([result for result in results if result ]) + 1 > 2 #checks if has the majority 

    def vote_for_leader(self, term: int):
        self._heartbeat_received.set()
        print(f"{self} received election campaing")
        return self.term.compare_term(term)
    # @server.oneway
    # def send_vote_result(self, vote: Vote):
    #     print(f"{self} - answering send_vote_result - payload: {vote}")
    #     is_leader = self.term.add_vote(vote)
    #     if is_leader: self.state = NodeState.LEADER

    # def _request_vote(self, vote: tuple[int, str]):
    #     (vote_term, uri) = vote
    #     print(f"{self} - answer request_vote - payload {vote} - {self.term}")
    #     # vote: None | Vote = self.term.compare_election(vote)
    #     # print("checked vote", vote)
    #     if self.term.term < vote_term: 
    #         self.peers[uri].send_vote_result(vote)

    def leader_commmand(self, command: str, uri_callback: str):
        print(command, self.uri)
        self._send_heartbeats(("Append Entries", command))
        self._callback = uri_callback
        return True
        
    @server.oneway
    def commit(self, cmd, uri: str, hash:str):
        print(f"{self} - answering commit - payload: {cmd}")
        majority_achieved = False
        if hash in self.commits:
            for commit in self.commits:
                majority_achieved = commit.add_ack(uri)
            if majority_achieved:
                self.redis.action(cmd)
                self.commits.remove(hash)
                self._send_heartbeats("Commit", cmd)
                if hash in self._callback:
                    api.Proxy(self._callback[hash]).background_processed(cmd)
                    del self._callback[hash]

    @server.oneway
    def heartbeat(self, command: tuple[int, str, tuple[str,str], str]):
        self._heartbeat_received.set()
        print(f"{self} - answering command - payload: {command}")
        (term, uri, cmd, hash) = command
        if self.term.compare_term(term):
            self.state = NodeState.FOLLOWER
        (is_command, to_commit, cmd) = self._handle_command(cmd)
        if is_command and to_commit:
            self.redis.action(cmd)
        elif is_command:
            self.peers[uri].commit(cmd, self.uri, hash)
    
    async def _send_heartbeat_to_followers(self):
        while self.state == NodeState.LEADER:
            if not self.leader_messaged: #check if already has send a message with cmd
                self._send_heartbeats()
            await asyncio.sleep(1) #awaits 100ms before next message
            self.leader_messaged = False #reset flag
    
    def _handle_command(self, cmd: tuple[str, str] | None = None):
        if not cmd: return (False, False, None)
        match cmd:
            case ("Append Entries", cmd):
                return (True, False, cmd)
            case ("Commit", cmd):
                return (True, True, cmd)

    def _send_heartbeats(self, command: str | tuple | None = None):
        self.leader_messaged = True
        for peer in self.peers:
            payload = (self.term.term, self.uri, command, str(datetime.now())) if command else (self.term.term, self.uri, None, None)
            try:
                self.peers[peer].heartbeat(payload)
            except Exception as e:
                # print(f"Error when trying to send heartbeat {e}")
                pass

    def __repr__(self): return f"RaftNode({self.uri})"
        

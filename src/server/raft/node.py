from __future__ import annotations
from enum import Enum, auto
from Pyro5 import server, api, client
from random import randint
from raft.operations.key_value import Redis
from raft.operations.commits import Commit, Ack
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
    name_server: any
    
    def __init__(self, peers: dict[str, client.Proxy], uri: str, name_server, timer: int = None):
        self.peers = peers
        self.follower = None
        self._timer = timer
        self.redis = Redis()
        self.commits = set()
        self.leader_messaged = False
        self._callbacks = {}
        self.uri = uri
        self._set_peers_timeout()
        self.initiate_term()
        self.name_server = name_server
        self.state = NodeState.FOLLOWER
    
    ## Initial setup    
    def _set_peers_timeout(self):
        """ Sets timeout of 150ms for proxy remote calls """
        for proxy in self.peers:
            self.peers[proxy]._pyroTimeout = 0.15

    def initiate_term(self, number_of_servers: int = 4):
        self.term = Term(self.uri, number_of_servers)

    # State Machine Configuration
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
                self.name_server.register("Leader", self.uri)
    
    #General Timeout property
    @property
    def timeout(self) -> int:
        """ Timeout in integer between 150 and 300 ms, could it also be a value provided by class instantiation """
        return self._timer if self._timer else randint(150, 300)
        # return self._timer if self._timer else randint(1500, 3000)
    @property
    def leader_timeout(self) -> float: return 0.1

    #Self calling functions for general use
    
    async def _follow_the_leader(self):
        """ An ever running loop that waits for a random interval between the timeout - will check if
         self._heartbeat_received.set() has been called anywhere else in the code before reaching the
         timeout, if it does not receive the set() it will raise an exception that may change to CANDIDATE """
        while True:
            try:
                await asyncio.wait_for(self._heartbeat_received.wait(), self.timeout / 1000)
                self._heartbeat_received.clear()
            except asyncio.TimeoutError:
                if self.state == NodeState.FOLLOWER:
                    self.state = NodeState.CANDIDATE

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
        Sends heartbeat to the other servers in parallel with a timeout of 150ms.
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

    async def _send_heartbeat_to_followers(self):
        while self.state == NodeState.LEADER:
            if not self.leader_messaged: #check if already has send a message with cmd
                self._send_heartbeats()
            await asyncio.sleep(0.1) #awaits 100ms before next message
            self.leader_messaged = False #reset flag
    
    def _handle_command(self, cmd: tuple[str, str] | None = None, hash = None):
        if not cmd: return (False, False, None)
        match cmd:
            case ("Append Entries", cmd):
                return (True, False, cmd)
            case ("Commit", cmd):
                try:
                    commit = [ commit.cmd for commit in self.commits if commit == hash ][0]
                except:
                    commit = ""
                return (True, True, commit)

    def _send_heartbeats(self, command: str | tuple | None = None, hash = None):
        self.leader_messaged = True
        hash = hash or self._create_hash()
        if command: print(f"Leader sending cmd: {command}")
        for peer in self.peers:
            payload = (self.term.term, self.uri, command, hash) if command else (self.term.term, self.uri, None, None)
            try:
                api.Proxy(peer).heartbeat(payload)
            except Exception as e:
                # print(f"Error when trying to send heartbeat {e}")
                if command: print(e)
                pass

    def _create_hash(self) -> str: return str(datetime.now())
    
    # Pyro5 Callbacks
 
    def vote_for_leader(self, term: int):
        self._heartbeat_received.set()
        is_follower = self.term.compare_term(term)
        if is_follower: self.state = NodeState.FOLLOWER
        return is_follower

    def leader_commmand(self, command: str, uri_callback: str):
        print(command, uri_callback)
        hash = self._create_hash()
        self.commits.add(Commit(hash,self.uri, 4, command))
        self._send_heartbeats(("Append Entries", command), hash)
        self._callbacks[hash] = uri_callback

        return True
    
    @server.oneway
    def commit(self, hash, follower_uri):
        print("GOT COMMIT RESPONSE")
        ack: Ack = Ack(hash, follower_uri)
        print(f"{self} - answering commit - payload: {ack}")
        majority_achieved = False
        if ack.hash in self.commits:
            print("hash is in commits")
            try:
                commit: Commit = [ action for action in self.commits if action == ack ][0]
                print("commit", commit)
                majority_achieved = commit.add_ack(ack)
                if majority_achieved:
                    print("majority achieved")
                    self.redis.action(commit)
                    self._send_heartbeats(("Commit", commit.hash))
                    if ack.hash in self._callbacks and ack.hash in self.commits:
                        self.commits.remove(ack.hash)
                        api.Proxy(self._callbacks[ack.hash]).background_processed(commit.cmd)
                        print("sending background process call")
                        del self._callbacks[ack.hash]
            except Exception as e:
                print(f"Commit error {e}")
                pass

    @server.oneway
    def heartbeat(self, command: tuple[int, str, tuple[str,str], str]):
        self._heartbeat_received.set()
        print(f"{self} - answering command - payload: {command}")
        (term, uri, cmd, hash) = command
        if self.term.compare_term(term):
            self.state = NodeState.FOLLOWER
        (is_command, to_commit, cmd) = self._handle_command(cmd, hash)
        if is_command and to_commit:
            self.redis.action(cmd)
            self.commits.remove(hash)
        elif is_command:
            try:
                print("sending commit response", uri)
                api.Proxy(uri).commit(hash, self.uri)
                self.commits.add(Commit(hash,self.uri, 4,cmd))
                print("worked")
            except Exception as e:
                print("Error when responsing command commit ", e)
    
    def __repr__(self): return f"RaftNode({self.uri})"
        

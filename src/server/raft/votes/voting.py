class Vote:
    vote: str
    voter: str
    votee: str
    term: int
    def __init__(self, term:int, voter: str, votee: str):
        self.vote = self._create_vote(voter, votee)
        self.voter = voter
        self.votee = votee
        self.term = term
    def _create_vote(self, voter: str, votee: str):
        self.vote = f"{voter}{votee}"
        return self.vote
    def __hash__(self): return hash(self.vote)
    @property
    def uri(self): return self.votee

class Term:
    term: int
    votes: set[Vote]
    self_vote: str
    user: str
    majority: int
    def __init__(self, user: str, number_of_servers: int):
        self.term = 0
        self.votes = set()
        self.user = user
        self.self_vote = Vote(user, user)
        self.majority = number_of_servers // 2
    def initiate_votes(self, retried: bool = False):
        self.term = self.term + 1 if retried else self.term
        self.votes = set(self.self_vote)
        return (self.term, self.user)
    def compare_election(self, payload: tuple[int, str]) -> None | Vote:
        (term, user) = payload
        if term > self.term:
            self._update_term(term)
            return Vote(self.user, user)
        return None
    def _update_term(self, term):
        self.term = term
        self.votes = set()
    def add_vote(self, vote: Vote) -> bool:
        """ Adds a response from the election to the term, if greater than majority returns True for being a Leader """
        if vote.term == self.term:
            self.votes.add(vote)
            if len(self.votes) > self.majority: return True
        return False
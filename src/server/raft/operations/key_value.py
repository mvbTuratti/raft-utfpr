from .commits import Commit

class Redis:
    content: dict[str,str]
    _commits: list[Commit]
    def __init__(self, value={}):
        self.content = value
        self._commits = []
    def action(self, commit: Commit | str = None) -> dict[str,str] | str | None:
        """
            A completely naive implementation of Redis operations - receives a string as input
            it enables two possible operations:
                SET key value [...]
            where it will set the key pair value and will ignore any further values
                GET [key, [...]]
            and a GET that if no key is provided will return the complete dict, if a key is provided can either 
            return its value (if exists) or no value, ignore further paramenters.
        """
        print("Action commited", commit)
        action = commit.cmd if isinstance(commit, Commit) else commit
        if not action: return None
        match action.split():
            case ["SET", key, value, *remainder]:
                self.content[key] = value
                self._commits.append(commit)
                return value
            case ["GET"]:
                return self.content
            case ["GET", key, *remainder]:
                return self.content.get(key, None)
        print("current redis state", self.content)
        return None
    def check_action(self, action: str):
        if action.startswith("GET"):
            return (True, self.action(action))
        else:
            return (False, None)
    def _capture_last_occurrence(self, commands: list[str]):
        last_occurrences = {}
        for command in commands:
            parts = command.split()
            last_occurrences[parts[1]] = parts[2]
        return [f"SET {key} {value}" for key, value in last_occurrences.items()]    
    def get_series_of_commits(self, timestamp: str = None):
        if not timestamp: return self._capture_last_occurrence([c.cmd for c in self._commits])
        return self._capture_last_occurrence([ commit.cmd for commit in self._commits if commit.hash > timestamp ])
    def apply_series_of_commits(self, commits: list[str]):
        for commit in commits:
            self.action(commit)
    def get_latest_commit_timestamp(self):
        if not self._commits: return None
        return self._commits[-1].hash
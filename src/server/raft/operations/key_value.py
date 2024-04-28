class Redis:
    content: dict[str,str]
    def __init__(self, value={}):
        self.content = value
    def action(self, action: str = "") -> dict[str,str] | str | None:
        """
            A completely naive implementation of Redis operations - receives a string as input
            it enables two possible operations:
                SET key value [...]
            where it will set the key pair value and will ignore any further values
                GET [key, [...]]
            and a GET that if no key is provided will return the complete dict, if a key is provided can either 
            return its value (if exists) or no value, ignore further paramenters.
        """
        if not action: return None
        if not isinstance(action, str): return None 
        match action.split():
            case ["SET", key, value, *remainder]:
                self.content[key] = value
                return value
            case ["GET"]:
                return self.content
            case ["GET", key, *remainder]:
                return self.content.get(key, None)
        return None
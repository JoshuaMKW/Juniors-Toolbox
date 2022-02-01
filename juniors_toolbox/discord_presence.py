import discordsdk

class DiscordPresence():
    def __init__(self, name: str, desc: str = "", icon=None):
        self.name = name
        self.desc = desc
        self.icon = icon

    def connect(self) -> bool:
        """
        Connects the application to Discord
        """
        ...

    def disconnect(self):
        """
        Disconnects the application from Discord
        """
        ...

    def update(self):
        ...
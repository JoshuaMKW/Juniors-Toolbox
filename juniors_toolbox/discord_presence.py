from curses.ascii import CR
import discordsdk
from discordsdk import CreateFlags, Discord, DiscordException, ApplicationManager, ActivityManager, UserManager, Activity, ActivityTimestamps, Presence

from juniors_toolbox import __version__

__client_id__ = 2390478829347098230
__application_id__ = hash(f"Junior's Toolbox v{__version__}")


class DiscordPresence():
    def __init__(self, icon=None, clientID: int = __client_id__, flags: CreateFlags = CreateFlags.default):
        self.icon = icon
        self.__discord = Discord(
            client_id=clientID,
            flags=flags
        )
        acm = ActivityTimestamps()

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

    def update(self, name: str, state: str = "", details: str = ""):
        presence = Presence()
        activity = Activity()

        activity.name = name
        activity.state = state
        activity.details = details
        activity.application_id = __application_id__
        
        activityManager = self.__discord.get_activity_manager()
        activityManager.update_activity(
            Activity(
                application_id=__application_id__,
                name=name,
                state=state,
                details=details,

            )
        )

    # _fields_ = [
    #     ("application_id", int),
    #     ("name", str),
    #     ("state", str),
    #     ("details", str),
    #     ("timestamps", ActivityTimestamps),
    #     ("assets", ActivityAssets),
    #     ("party", ActivityParty),
    #     ("secrets", ActivitySecrets),
    #     ("instance", bool),
    # ]
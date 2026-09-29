from neonize import NewClient
from neonize.utils.log import clientlogger


primary_user_name: str
primary_user_pn: str
primary_user_lid: str


def get_info(client: NewClient):
    user_info = client.get_me()
    primary_user_name = user_info.PushName
    primary_user_pn = user_info.JID.User
    if user_info.LID.ListFields():
        primary_user_lid = user_info.LID.User

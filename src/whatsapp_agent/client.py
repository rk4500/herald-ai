from neonize.client import NewClient
from neonize.events import ConnectedEv


from .config import NEONIZE_PATH

client = NewClient(NEONIZE_PATH)


@client.event(ConnectedEv)
def on_connected(client: NewClient, _: ConnectedEv) -> None:
    print("Connected")

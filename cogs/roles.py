import asyncio
import copy
import json

import discord
from discord import Emoji

REACTION_MSG_ID = '414216008614805505'
REACTION_MSG_CHAN = '414215561967304710'


class Roles:
    def __init__(self, bot):
        self.bot = bot
        if not bot.testing:
            bot.loop.create_task(self.check_reaction_map())
        self.reaction_map = {}

    async def check_reaction_map(self):
        try:
            await self.bot.wait_until_ready()
            while not self.bot.is_closed:
                msg = await self.bot.get_message(self.bot.get_channel(REACTION_MSG_CHAN), REACTION_MSG_ID)
                old_reaction_map = copy.copy(self.reaction_map)
                self.reaction_map = {}
                for line in msg.content.split('\n')[2:]:
                    line = line.strip()
                    reaction = line.split(' ')[0]
                    role = line.split('**')[1]
                    self.reaction_map[reaction] = role
                if not old_reaction_map == self.reaction_map:
                    print(f"New reaction map: {self.reaction_map}")
                await asyncio.sleep(60 * 60)  # every hour
        except asyncio.CancelledError:
            pass

    async def on_socket_raw_receive(self, msg):
        if isinstance(msg, bytes):
            return
        msg = json.loads(msg)
        if msg.get('t') != "MESSAGE_REACTION_ADD":
            return

        data = msg['d']
        if not data.get('guild_id'):
            return

        server = self.bot.get_server(data['guild_id'])
        msg_id = data['message_id']
        member = server.get_member(data['user_id'])
        emoji = self.get_emoji(**data.pop('emoji'))
        await self.handle_reaction(msg_id, member, emoji, server)

    async def handle_reaction(self, msg_id, member, emoji, server):
        if not msg_id == REACTION_MSG_ID:
            return
        elif member.id == '187421759484592128':
            return
        else:
            if str(emoji) in self.reaction_map:
                role = discord.utils.get(server.roles, name=self.reaction_map[str(emoji)])
                print(f"Handling role change: {role.name} on {member}")
                if role in member.roles:
                    await self.bot.remove_roles(member, role)
                    out = "I have removed the {} role.".format(role.name)
                else:
                    await self.bot.add_roles(member, role)
                    out = "You have been given the {} role.".format(role.name)
                try:
                    await self.bot.send_message(member, out)
                except:
                    pass

    def get_emoji(self, **data):
        id_ = data['id']

        if not id_:
            return data['name']

        for server in self.bot.servers:
            for emoji in server.emojis:
                if emoji.id == id_:
                    return emoji
        return Emoji(server=None, **data)


def setup(bot):
    bot.add_cog(Roles(bot))

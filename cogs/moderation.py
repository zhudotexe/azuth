import discord
from discord import Forbidden
from discord.ext import commands
from discord.http import Route

from utils import checks

MUTED_ROLE = "517795608677842945"


class Moderation:
    def __init__(self, bot):
        self.bot = bot
        self.no_ban_logs = set()

    @commands.command(hidden=True, pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def slowmode(self, ctx, timeout: int = 10, channel: discord.Channel = None):
        """Slows a channel."""
        if channel is None:
            channel = ctx.message.channel
        try:
            await self.bot.http.request(Route('PATCH', '/channels/{channel_id}', channel_id=channel.id),
                                        json={"rate_limit_per_user": timeout})
            await self.bot.say(f"Ratelimit set to {timeout} seconds in {channel}.")
        except:
            await self.bot.say("Failed to set ratelimit.")

    @commands.command(hidden=True, pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def purge_bot(self, ctx, limit: int = 50):
        """Purges bot messages from the last [limit] messages (default 50)."""
        deleted = await self.bot.purge_from(ctx.message.channel, check=lambda m: m.author.bot, limit=limit)
        await self.bot.say("Cleaned {} messages.".format(len(deleted)))

    @commands.command(pass_context=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def purge(self, ctx, num: int):
        """Purges messages from the channel.
        Requires: Bot Mod or Manage Messages"""
        try:
            await self.bot.purge_from(ctx.message.channel, limit=(num + 1))
        except Exception as e:
            await self.bot.say('Failed to purge: ' + str(e))

    @commands.command(hidden=True, pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def copyperms(self, ctx, role: discord.Role, source: discord.Channel, overwrite: bool = False):
        """Copies permission overrides for one role from one channel to all others of the same type."""
        source_chan = source
        source_role = role
        source_overrides = source_chan.overwrites_for(source_role)
        skipped = []
        for chan in ctx.message.server.channels:
            if chan.type != source_chan.type:
                continue
            chan_overrides = chan.overwrites_for(source_role)
            if chan_overrides.is_empty() or overwrite:
                await self.bot.edit_channel_permissions(chan, source_role, source_overrides)
            else:
                skipped.append(chan.name)

        if skipped:
            skipped_str = ', '.join(skipped)
            await self.bot.say(f":ok_hand:\n"
                               f"Skipped {skipped_str}; use `.copyperms {role} {source} true` to overwrite existing.")
        else:
            await self.bot.say(f":ok_hand:")

    @commands.command(hidden=True, pass_context=True, no_pm=True)
    @checks.mod_or_permissions(ban_members=True)
    async def raidmode(self, ctx, method='kick'):
        """Toggles raidmode in a server.
        Methods: kick, ban, lockdown"""
        if method not in ("kick", "ban", "lockdown"):
            return await self.bot.say("Raidmode method must be kick, ban, or lockdown.")

        server_settings = await self.get_server_settings(ctx.message.server.id, ['raidmode', 'locked_channels'])

        if server_settings['raidmode']:
            if server_settings['raidmode'] == 'lockdown':
                await self.end_lockdown(ctx, server_settings)
            server_settings['raidmode'] = None
            out = "Raid mode disabled."
        else:
            if method == 'lockdown':
                await self.start_lockdown(ctx, server_settings)
            server_settings['raidmode'] = method
            out = f"Raid mode enabled. Method: {method}"

        await self.set_server_settings(ctx.message.server.id, server_settings)
        await self.bot.say(out)

    @commands.command(hidden=True, pass_context=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def mute(self, ctx, target: discord.Member, *, reason="Unknown reason"):
        """Toggles mute on a member."""
        role = discord.utils.get(ctx.message.server.roles, id=MUTED_ROLE)
        server_settings = await self.get_server_settings(ctx.message.server.id, ['cases', 'casenum'])

        if role in target.roles:
            try:
                self.no_ban_logs.add(ctx.message.server.id)
                await self.bot.remove_roles(target, role)
            except Forbidden:
                return await self.bot.say("Error: The bot does not have `manage_roles` permission.")
            finally:
                self.no_ban_logs.remove(ctx.message.server.id)
            case = Case.new(num=server_settings['casenum'], type_='unmute', user=target.id, username=str(target),
                            reason=reason, mod=str(ctx.message.author))
        else:
            try:
                self.no_ban_logs.add(ctx.message.server.id)
                await self.bot.add_roles(target, role)
            except Forbidden:
                return await self.bot.say("Error: The bot does not have `manage_roles` permission.")
            finally:
                self.no_ban_logs.remove(ctx.message.server.id)
            case = Case.new(num=server_settings['casenum'], type_='mute', user=target.id, username=str(target),
                            reason=reason, mod=str(ctx.message.author))

        await self.post_action(ctx.message.server, server_settings, case)

    @commands.command(hidden=True, pass_context=True)
    @checks.mod_or_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, *, reason='Unknown reason'):
        """Kicks a member and logs it to #mod-log."""
        try:
            await self.bot.kick(user)
        except Forbidden:
            return await self.bot.say('Error: The bot does not have `kick_members` permission.')

        server_settings = await self.get_server_settings(ctx.message.server.id, ['cases', 'casenum'])

        case = Case.new(num=server_settings['casenum'], type_='kick', user=user.id, username=str(user), reason=reason,
                        mod=str(ctx.message.author))
        await self.post_action(ctx.message.server, server_settings, case)

    @commands.command(hidden=True, pass_context=True)
    @checks.mod_or_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, *, reason='Unknown reason'):
        """Bans a member and logs it to #mod-log."""
        try:
            self.no_ban_logs.add(ctx.message.server.id)
            await self.bot.ban(user)
        except Forbidden:
            return await self.bot.say('Error: The bot does not have `ban_members` permission.')
        finally:
            self.no_ban_logs.remove(ctx.message.server.id)

        server_settings = await self.get_server_settings(ctx.message.server.id, ['cases', 'casenum'])

        case = Case.new(num=server_settings['casenum'], type_='ban', user=user.id, username=str(user), reason=reason,
                        mod=str(ctx.message.author))
        await self.post_action(ctx.message.server, server_settings, case)

    @commands.command(hidden=True, pass_context=True)
    @checks.mod_or_permissions(ban_members=True)
    async def forceban(self, ctx, user, *, reason='Unknown reason'):
        """Force-bans a member ID and logs it to #mod-log."""
        member = discord.utils.get(ctx.message.server.members, id=user)
        if member:  # if they're still in the server, normal ban them
            return await ctx.invoke(self.ban, member, reason=reason)

        user_obj = await self.bot.get_user_info(user)

        server_settings = await self.get_server_settings(ctx.message.server.id, ['cases', 'casenum', 'forcebanned'])
        server_settings['forcebanned'].append(user)

        case = Case.new(num=server_settings['casenum'], type_='forceban', user=user, username=str(user_obj),
                        reason=reason, mod=str(ctx.message.author))
        await self.post_action(ctx.message.server, server_settings, case)

    @commands.command(hidden=True, pass_context=True)
    @checks.mod_or_permissions(ban_members=True)
    async def softban(self, ctx, user: discord.Member, *, reason='Unknown reason'):
        """Softbans a member and logs it to #mod-log."""
        try:
            self.no_ban_logs.add(ctx.message.server.id)
            await self.bot.ban(user)
            await self.bot.unban(ctx.message.server, user)
        except Forbidden:
            return await self.bot.say('Error: The bot does not have `ban_members` permission.')
        finally:
            self.no_ban_logs.remove(ctx.message.server.id)

        server_settings = await self.get_server_settings(ctx.message.server.id, ['cases', 'casenum'])

        case = Case.new(num=server_settings['casenum'], type_='softban', user=user.id, username=str(user),
                        reason=reason, mod=str(ctx.message.author))
        await self.post_action(ctx.message.server, server_settings, case)

    @commands.command(hidden=True, pass_context=True)
    @checks.mod_or_permissions(kick_members=True)
    async def reason(self, ctx, case_num: int, *, reason):
        """Sets the reason for a post in mod-log."""
        server_settings = await self.get_server_settings(ctx.message.server.id, ['cases'])
        cases = server_settings['cases']
        case = next((c for c in cases if c['num'] == case_num), None)
        if case is None:
            return await self.bot.say(f"Case {case_num} not found.")

        case = Case.from_dict(case)
        case.reason = reason
        case.mod = str(ctx.message.author)

        mod_log = discord.utils.get(ctx.message.server.channels, name='mod-log')
        if mod_log is not None and case.log_msg:
            log_message = await self.bot.get_message(mod_log, case.log_msg)
            await self.bot.edit_message(log_message, str(case))

        await self.set_server_settings(ctx.message.server.id, server_settings)
        await self.bot.say(':ok_hand:')

    async def post_action(self, server, server_settings, case, no_msg=False):
        """Common function after a moderative action."""
        server_settings['casenum'] += 1
        mod_log = discord.utils.get(server.channels, name='mod-log')

        if mod_log is not None:
            msg = await self.bot.send_message(mod_log, str(case))
            case.log_msg = msg.id

        server_settings['cases'].append(case.to_dict())
        await self.set_server_settings(server.id, server_settings)
        if not no_msg:
            await self.bot.say(':ok_hand:')

    async def start_lockdown(self, ctx, server_settings):
        """Disables Send Messages permission for everyone in every channel."""
        server_settings['locked_channels'] = []
        everyone_role = ctx.message.server.default_role
        for channel in ctx.message.server.channels:
            if not channel.type == discord.ChannelType.text:
                continue
            overwrites = channel.overwrites_for(everyone_role)
            if overwrites.send_messages is not False:  # is not false, since it could be None
                overwrites.send_messages = False
                server_settings['locked_channels'].append(channel.id)
                await self.bot.edit_channel_permissions(channel, everyone_role, overwrite=overwrites)

        await self.bot.say(f"Locked down {len(server_settings['locked_channels'])} channels.")

    async def end_lockdown(self, ctx, server_settings):
        """Reenables Send Messages for everyone in locked-down channels."""
        everyone_role = ctx.message.server.default_role
        for chan in server_settings['locked_channels']:
            channel = discord.utils.get(ctx.message.server.channels, id=chan)
            overwrites = channel.overwrites_for(everyone_role)
            overwrites.send_messages = None
            await self.bot.edit_channel_permissions(channel, everyone_role, overwrite=overwrites)

        await self.bot.say(f"Unlocked {len(server_settings['locked_channels'])} channels.")
        server_settings['locked_channels'] = []

    async def check_raidmode(self, server_settings, member):
        """Checks whether a newly-joined member should be removed due to raidmode."""
        try:
            self.no_ban_logs.add(member.server.id)
            if not server_settings['raidmode']:
                return
            elif server_settings['raidmode'] == 'kick':
                await self.bot.kick(member)
                action = 'kick'
            else:
                await self.bot.ban(member)
                action = 'ban'
        except Forbidden:
            return
        finally:
            self.no_ban_logs.remove(member.server.id)
        case = Case.new(num=server_settings['casenum'], type_=action, user=member.id, username=str(member),
                        reason=f"Raidmode auto{action}", mod=str(self.bot.user))
        await self.post_action(member.server, server_settings, case, no_msg=True)

    async def check_forceban(self, server_settings, member):
        """Checks whether a newly-joined member should be removed due to forceban."""
        if member.id in server_settings['forcebanned']:
            try:
                self.no_ban_logs.add(member.server.id)
                await self.bot.ban(member)
            except Forbidden:
                return
            finally:
                self.no_ban_logs.remove(member.server.id)
            case = Case.new(num=server_settings['casenum'], type_='ban', user=member.id, username=str(member),
                            reason="User forcebanned previously", mod=str(self.bot.user))
            await self.post_action(member.server, server_settings, case, no_msg=True)

    async def on_message_delete(self, message):
        if not message.server:
            return  # PMs
        msg_log = discord.utils.get(message.server.channels, name="message-log")
        if not msg_log:
            return
        embed = discord.Embed()
        embed.title = f"{message.author} deleted a message in {message.channel}."
        if message.content:
            embed.description = message.content
        for attachment in message.attachments:
            embed.add_field(name="Attachment", value=attachment['url'])
        embed.colour = 0xff615b
        embed.set_footer(text="Originally sent")
        embed.timestamp = message.timestamp
        await self.bot.send_message(msg_log, embed=embed)

    async def on_message_edit(self, before, after):
        if not before.server:
            return  # PMs
        msg_log = discord.utils.get(before.server.channels, name="message-log")
        if not msg_log:
            return
        if before.content == after.content:
            return
        embed = discord.Embed()
        embed.title = f"{before.author} edited a message in {before.channel} (below is original message)."
        if before.content:
            embed.description = before.content
        for attachment in before.attachments:
            embed.add_field(name="Attachment", value=attachment['url'])
        embed.colour = 0x5b92ff
        if len(after.content) < 1000:
            new = after.content
        else:
            new = str(after.content)[:1000] + "..."
        embed.add_field(name="New Content", value=new)
        await self.bot.send_message(msg_log, embed=embed)

    async def on_member_join(self, member):
        server_settings = await self.get_server_settings(member.server.id)
        await self.check_raidmode(server_settings, member)
        await self.check_forceban(server_settings, member)

    async def on_member_ban(self, member):
        if member.server.id in self.no_ban_logs:
            return
        server_settings = await self.get_server_settings(member.server.id, ['cases', 'casenum'])

        case = Case.new(num=server_settings['casenum'], type_='ban', user=member.id, username=str(member),
                        reason="Unknown reason")
        await self.post_action(member.server, server_settings, case, no_msg=True)

    async def on_member_unban(self, server, user):
        if server.id in self.no_ban_logs:
            return
        server_settings = await self.get_server_settings(server.id, ['cases', 'casenum'])

        case = Case.new(num=server_settings['casenum'], type_='unban', user=user.id, username=str(user),
                        reason="Unknown reason")
        await self.post_action(server, server_settings, case, no_msg=True)

    async def on_member_update(self, before, after):
        if before.server.id in self.no_ban_logs:
            return
        role = discord.utils.get(before.server.roles, id=MUTED_ROLE)
        if role not in before.roles and role in after.roles:  # just muted
            server_settings = await self.get_server_settings(before.server.id, ['cases', 'casenum'])
            case = Case.new(num=server_settings['casenum'], type_='mute', user=after.id, username=str(after),
                            reason="Unknown reason")
        elif role in before.roles and role not in after.roles:  # just unmuted
            server_settings = await self.get_server_settings(before.server.id, ['cases', 'casenum'])
            case = Case.new(num=server_settings['casenum'], type_='unmute', user=after.id, username=str(after),
                            reason="Unknown reason")
        else:
            return

        await self.post_action(before.server, server_settings, case, no_msg=True)

    async def get_server_settings(self, server_id, projection=None):
        server_settings = await self.bot.mdb.mod.find_one({"server": server_id}, projection)
        if server_settings is None:
            server_settings = get_default_settings(server_id)
        return server_settings

    async def set_server_settings(self, server_id, settings):
        await self.bot.mdb.mod.update_one(
            {"server": server_id},
            {"$set": settings}, upsert=True
        )


def get_default_settings(server):
    return {
        "server": server,
        "raidmode": None,
        "cases": [],
        "casenum": 1,
        "forcebanned": [],
        "locked_channels": []
    }


class Case:
    def __init__(self, num, type_, user, reason, mod=None, log_msg=None, username=None):
        self.num = num
        self.type = type_
        self.user = user
        self.username = username
        self.reason = reason
        self.mod = mod
        self.log_msg = log_msg

    @classmethod
    def new(cls, num, type_, user, reason, mod=None, username=None):
        return cls(num, type_, user, reason, mod=mod, username=username)

    @classmethod
    def from_dict(cls, raw):
        raw['type_'] = raw.pop('type')
        return cls(**raw)

    def to_dict(self):
        return {"num": self.num, "type": self.type, "user": self.user, "reason": self.reason, "mod": self.mod,
                "log_msg": self.log_msg, "username": self.username}

    def __str__(self):
        if self.username:
            user = f"{self.username} ({self.user})"
        else:
            user = self.user

        if self.mod:
            modstr = self.mod
        else:
            modstr = f"Responsible moderator, do `.reason {self.num} <reason>`"

        return f'**{self.type.title()}** | Case {self.num}\n' \
               f'**User**: {user}\n' \
               f'**Reason**: {self.reason}\n' \
               f'**Responsible Mod**: {modstr}'


def setup(bot):
    bot.add_cog(Moderation(bot))

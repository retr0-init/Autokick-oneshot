'''
Automatically kick members who joined the guild over m days and doesn't have more than n messages

Copyright (C) 2024  __retr0.init__

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''
import interactions
from interactions.api.events import MemberRemove, MessageCreate
from collections import deque
import asyncio
import datetime
from config import DEV_GUILD

'''
Autokick module
Base: autokick_conshot
'''
class ExtRetr0initAutokickOneshot(interactions.Extension):
    module_base: interactions.SlashCommand = interactions.SlashCommand(
        name="autokick_oneshot",
        description="AutoKick System to automatically kick members"
    )

    initialised: bool = False
    started: bool = False

    ''' All members
    {
        <member id> : [message],
    }
    '''
    all_members: dict[int, deque[interactions.Message]] = {}

    ignored_roles: list[int] = []

    threshold_message: int = 20
    threshold_days: int = 30

    reference_time: datetime.datetime = datetime.datetime(1970, 1, 1)

    @module_base.subcommand("setup", sub_cmd_description="Setup the autokick feature and generate statistics")
    @interactions.check(interactions.is_owner())
    @interactions.slash_option(
        name = "th_message",
        description = "Message threshold. Default to 20.",
        required = False,
        opt_type = interactions.OptionType.INTEGER,
        min_value = 2
    )
    @interactions.slash_option(
        name = "th_days",
        description = "Threshold of calculation durations. Default to 30.",
        required = False,
        opt_type = interactions.OptionType.INTEGER,
        min_value = 1
    )
    async def command_setup(self, ctx: interactions.SlashContext, th_message: int = 20, th_days: int = 30):
        if self.kick_task.started:
            self.kick_task.stop()
        self.started = False
        self.initialised = False
        now: interactions.Timestamp = interactions.Timestamp.now()
        await ctx.defer()
        self.threshold_message = th_message
        self.threshold_days = th_days
        self.all_members: dict[int: deque[interactions.Message]] = {mem.id: deque([]) for mem in ctx.guild.members if not mem.bot}
        self.passed_members: deque[int] = deque()
        all_channels: list = []
        for cc in ctx.guild.channels:
            if isinstance(cc, interactions.MessageableMixin):
                all_channels.append(cc)
            elif isinstance(cc, interactions.GuildForum):
                posts = await cc.fetch_posts()
                all_channels.extend(posts)
            # else:
            #     print(type(cc))
        # Get all message in the guild within the day threshold
        for channel in all_channels:
            if channel.name == "moderator-only":
                print("No access")
                print(channel.permissions_for(ctx.guild.me))
                continue
            if isinstance(channel, interactions.MessageableMixin):
                print("Has access")
                print(channel.permissions_for(ctx.guild.me))
                async for message in channel.history(limit=0):
                    if message.author.id in self.passed_members or message.author.id not in self.all_members.keys():
                        continue
                    if message.author.id in self.all_members.keys():
                        self.all_members[message.author.id].append(message)
                    if len(self.all_members[message.author.id]) > th_message:
                        self.passed_members.append(message.author.id)
        # Sort the message_id's according to the sent timestamp
        for member in self.all_members.keys():
            self.all_members[member] = deque(sorted(self.all_members[member], key=lambda m: m.timestamp))
        await ctx.send(f"Setup complete! The member who does not send more than {self.threshold_message} messages in {self.threshold_days} days will be kicked.")
        self.reference_time = now
        self.initialised = True

    def role_option_wrapper(name: str, required: bool = False):
        def wrapper(func):
            return interactions.slash_option(
                name = name,
                description = "The role not to be ever kicked",
                opt_type = interactions.OptionType.ROLE,
                required = required
            )(func)
        return wrapper

    @module_base.subcommand("exclude", sub_cmd_description="Exclude specific roles from being kicked")
    @interactions.check(interactions.is_owner())
    @role_option_wrapper("role0", required=True)
    @role_option_wrapper("role1")
    @role_option_wrapper("role2")
    @role_option_wrapper("role3")
    @role_option_wrapper("role4")
    @role_option_wrapper("role5")
    @role_option_wrapper("role6")
    @role_option_wrapper("role7")
    @role_option_wrapper("role8")
    @role_option_wrapper("role9")
    async def command_exclude(
        self,
        ctx: interactions.SlashContext,
        role0: interactions.Role,
        role1: interactions.Role = None,
        role2: interactions.Role = None,
        role3: interactions.Role = None,
        role4: interactions.Role = None,
        role5: interactions.Role = None,
        role6: interactions.Role = None,
        role7: interactions.Role = None,
        role8: interactions.Role = None,
        role9: interactions.Role = None
        ):
        roles: list[interactions.Role] = [role0, role1, role2, role3, role4, role5, role6, role7, role8, role9]
        added_roles: list[str] = []
        for role in roles:
            if role is not None and role not in self.ignored_roles:
                self.ignored_roles.append(role)
                added_roles.append(role.name)
        await ctx.send("The following roles will be ignored:\n- " + '\n- '.join(added_roles))

    async def kick_member(self, user: int):
        u: interactions.Member = await self.bot.fetch_member(user_id=user, guild_id=DEV_GUILD)
        if u is not None:
            # dm_channel: interactions.DMChannel = await u.fetch_dm()
            # if dm_channel is not None:
            #     dm_channel.send(f"您好。由于您在{self.threshold_days}天内在{ctx.guild.name}的发言不足{self.threshold_message}条。根据服务器规则，将把您踢出该服务器。如果您想重返本服务器的话，请重新加入。在此感谢您的理解与支持。祝一切安好。")
            await u.kick(reason=f"From {self.reference_time - datetime.timedelta(days=30)} to {self.reference_time} has less than {self.threshold_message} messages")
            await asyncio.sleep(2)

    @interactions.Task.create(interactions.IntervalTrigger(hours=8))
    async def kick_task(self):
        # Start flag guard
        if not self.started:
            return
        self.reference_time = interactions.Timestamp.now()
        td: datetime.timedelta = datetime.timedelta(days=self.threshold_days)
        for member in self.all_members.keys():
            if member in self.passed_members:
                continue
            member_obj: interactions.Member = await self.bot.fetch_member(member, DEV_GUILD)
            if member_obj.bot:
                continue
            if any(map(member_obj.has_role, self.ignored_roles)):
                continue
            if self.reference_time - member_obj.joined_at < datetime.timedelta(days=self.threshold_days):
                continue
            if len(self.all_members[member]) < self.threshold_message:
                await self.kick_member(member)

    @module_base.subcommand("start", sub_cmd_description="Start the AutoKick system")
    @interactions.check(interactions.is_owner())
    @interactions.slash_option(
        name = "force",
        description = "Force start without role setup",
        required = False,
        opt_type = interactions.OptionType.BOOLEAN
    )
    async def command_start(self, ctx: interactions.SlashContext, force: bool = False):
        if self.kick_task.running:
            await ctx.send("The task has already started!", ephemeral=True)
            return
        if not self.initialised:
            await ctx.send("Please use the `setup` command at first!", ephemeral=True)
            return
        if not force and len(self.ignored_roles) == 0:
            await ctx.send("There is no ignored role configured! Please run `setup_roles` command to set it. If you want to continue, please set `force` parameter to `True`.")
            return
        self.started = True
        self.kick_task.start()
        await ctx.send("AutoKick system started")
        self.kick_task.reschedule(
            interactions.OrTrigger(
                interactions.DateTrigger(
                    datetime.datetime.now() + datetime.timedelta(seconds=30)
                ),
                interactions.IntervalTrigger(hours=8)
            )
        )

    @module_base.subcommand("stop", sub_cmd_description="Stop the Autokick task")
    @interactions.check(interactions.is_owner())
    async def command_stop(self, ctx: interactions.SlashContext):
        if self.kick_task.running:
            self.kick_task.stop()
            self.started = False
            await ctx.send("Autokick System stopped.")
        else:
            await ctx.send("Autokick System has not been started yet")

    @module_base.subcommand("show_kick", sub_cmd_description="Display the members to be kicked")
    @interactions.check(interactions.is_owner())
    async def command_show_kick(self, ctx: interactions.SlashContext):
        if not self.initialised:
            await ctx.send("The Autokick system is not initialised.", ephemeral=True)
            return
        await ctx.defer()
        display_str: str = "## Members to be kicked"
        now: datetime.datetime = interactions.Timestamp.now()
        kicked_members: dict[int, int] = {
            mem: len(self.all_members[mem])
            for mem  in self.all_members.keys()
            if mem not in self.passed_members and len(self.all_members[mem]) <= self.threshold_message
        }
        for mem in kicked_members:
            mem_obj: interactions.Member = await ctx.guild.fetch_member(mem)
            display_str += f"\n- {mem_obj.display_name} ({mem_obj.username})"
        await ctx.send(display_str)

    @interactions.listen(MemberRemove)
    async def on_memberremove(self, event: MemberRemove):
        '''
        When the member is deleted from the server, remove the user from all_users dictionary
        '''
        if self.initialised:
            member_obj: interactions.Member = event.member
            if member_obj.id in self.all_members:
                self.all_members.pop(member_obj.id)
            if member_obj.id in self.passed_members:
                self.passed_members.remove(member_obj.id)

    @interactions.listen(MessageCreate)
    async def on_messagecreate(self, event: MessageCreate):
        '''
        Prepend message to the list
        '''
        if self.initialised:
            if not event.message.author.bot and event.message.author.id not in self.passed_members and not any(map(event.message.author.has_role, self.ignored_roles)):
                if event.message.author.id not in self.all_members.keys():
                    self.all_members[event.message.author.id] = deque()
                self.all_members[event.message.author.id].append(event.message)
                if len(self.all_members[event.message.author.id]) > self.threshold_message:
                    self.passed_members.append(event.message.author.id)
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
from interactions.ext.paginators import Paginator
from collections import deque
import asyncio
import datetime
from config import DEV_GUILD
from typing import Optional, Union
import tempfile
import os
import asyncio
import csv

import aiofiles
import aiofiles.ospath
import aiofiles.os
import aioshutil
from aiocsv import AsyncReader, AsyncDictReader, AsyncWriter, AsyncDictWriter

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

    folder_name: str = "logs"

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
        temp_folder_name: str = f"{os.path.dirname(__file__)}/{self.folder_name}"
        if await aiofiles.ospath.exists(temp_folder_name):
            await aioshutil.rmtree(temp_folder_name)
        await aiofiles.os.mkdir(temp_folder_name)
        self.threshold_message = th_message
        self.threshold_days = th_days
        self.all_members: dict[int: deque[interactions.Message]] = {mem.id: deque([]) for mem in ctx.guild.members if not mem.bot and not any(map(mem.has_role, self.ignored_roles))}
        self.passed_members: deque[int] = deque()
        all_channels: list[interactions.GuildChannel] = []
        fetched_channels: list[interactions.BaseChannel] = await ctx.guild.fetch_channels()
        for cc in fetched_channels:
            if isinstance(cc, interactions.MessageableMixin):
                all_channels.append(cc)
            elif isinstance(cc, interactions.GuildForum):
                posts = await cc.fetch_posts()
                posts = cc.get_posts(exclude_archived=False)
                all_channels.extend(posts)
            # else:
            #     print(type(cc))
        channel_count: int = len(all_channels)
        channel_index: int = 1
        channel_str_list: list[str] = [f"{ch.name} ({ch.mention})" for ch in all_channels]
        channel_display_str: str = "- " + '\n- '.join(channel_str_list)
        paginator: Paginator = Paginator.create_from_string(self.bot, channel_display_str, prefix="### Examined channels", page_size=1000)
        await paginator.send(ctx)
        temp_count: int = 0
        temp_msg: interactions.Message = await ctx.send("Autokick setup process started.")
        temp_channel: interactions.TYPE_MESSAGEABLE_CHANNEL = ctx.channel
        # Get all message in the guild within the day threshold
        for channel in all_channels:
            temp_count = 0
            if temp_msg is None:
                temp_msg = await temp_channel.send(content=f"Autokick setup process: {channel_index:04d}/{channel_count}: {channel.name}({channel.mention})")
            else:
                await self.bot.wait_until_ready()
                temp_msg = await temp_msg.edit(content=f"Autokick setup process: {channel_index:04d}/{channel_count}: {channel.name}({channel.mention})")
            # channel_display_str += f"- {channel.name} ({channel.mention})\n"
            perm: interactions.Permissions = ctx.guild.me.channel_permissions(channel)
            if (perm & interactions.Permissions.VIEW_CHANNEL) == 0:
                continue
            if isinstance(channel, interactions.MessageableMixin):
                async with aiofiles.open(temp_folder_name + f"/{channel.id}.csv", mode="a", encoding="utf-8", newline="") as afp:
                    writer = AsyncDictWriter(afp, ["user", "content", "timestamp"], restval="NULL", quoting=csv.QUOTE_ALL)
                    await writer.writeheader()
                    await writer.writerow({"user": "", "content": channel.name, "timestamp": channel.created_at.timestamp()})
                    try:
                        async for message in channel.history(limit=0):
                            await writer.writerow({"user": message.author.username, "content": message.content, "timestamp": message.timestamp.timestamp()})
                            temp_count += 1
                            if temp_count % 100 == 0:
                                if temp_msg is None:
                                    temp_msg = await temp_channel.send(content=f"Autokick setup process: {channel_index:04d}/{channel_count}: {channel.name}({channel.mention})")
                                else:
                                    await self.bot.wait_until_ready()
                                    temp_msg = await temp_msg.edit(content=f"Autokick setup process: {channel_index:04d}/{channel_count}: {channel.name}({channel.mention}) \
                                        \nMessage count: {temp_count}({message.jump_url}) \
                                            \n> {message.content[:100 if len(message.content) > 100 else len(message.content)]}{'...' if len(message.content) > 100 else ''}")
                            if message.author.id in self.passed_members or message.author.id not in self.all_members.keys():
                                continue
                            if message.author.id in self.all_members.keys():
                                self.all_members[message.author.id].append(message)
                            if len(self.all_members[message.author.id]) > th_message:
                                self.passed_members.append(message.author.id)
                            await self.bot.wait_until_ready()
                    except:
                        pass
            channel_index += 1
        temp_msg = await temp_msg.edit(content="Autokick setup process done!")
        # Sort the message_id's according to the sent timestamp
        for member in self.all_members.keys():
            self.all_members[member] = deque(sorted(self.all_members[member], key=lambda m: m.timestamp))
        # paginator: Paginator = Paginator.create_from_string(self.bot, channel_display_str, prefix="### Examined channels", page_size=1000)
        # await paginator.send(ctx)
        await temp_msg.reply(f"Setup complete! The member who does not send more than {self.threshold_message} messages in {self.threshold_days} days will be kicked.")
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
            await asyncio.sleep(1)

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
            if self.reference_time - member_obj.joined_at < td:
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
        temp_channel: interactions.TYPE_MESSAGEABLE_CHANNEL = ctx.channel
        temp_filename: str = ""
        if not self.initialised:
            await ctx.send("The Autokick system is not initialised.", ephemeral=True)
            return
        await ctx.defer()
        display_str: str = ""
        now: datetime.datetime = interactions.Timestamp.now()
        tdo: datetime.timedelta = datetime.timedelta(days=self.threshold_days)
        kicked_members: dict[int, int] = {
            mem: len(self.all_members[mem])
            for mem  in self.all_members.keys()
            if mem not in self.passed_members and len(self.all_members[mem]) < self.threshold_message
        }
        for mem in kicked_members:
            mem_obj: Optional[interactions.Member] = await ctx.guild.fetch_member(mem)
            while mem_obj is None:
                mem_obj = await ctx.guild.fetch_member(mem)
            if now - mem_obj.joined_at >= tdo:
                display_str += f"\n- {mem_obj.display_name} ({mem_obj.username}) ({len(self.all_members[mem])} messages)"
        paginator: Paginator = Paginator.create_from_string(self.bot, display_str, prefix="## Members to be kicked", page_size=1000)
        try:
            await paginator.send(ctx)
            async with aiofiles.tempfile.NamedTemporaryFile(suffix=".txt", prefix="kicked_members_", delete=False) as fp:
                await fp.write(str.encode(display_str))
                temp_filename = fp.name
            if await aiofiles.ospath.exists(temp_filename):
                await ctx.send("Members to be kicked", file=temp_filename)
                await aiofiles.os.remove(temp_filename)
        except:
            async with aiofiles.tempfile.NamedTemporaryFile(suffix=".txt", prefix="kicked_members_", delete=False) as fp:
                await fp.write(str.encode(display_str))
                temp_filename = fp.name
            if await aiofiles.ospath.exists(temp_filename):
                await temp_channel.send("Members to be kicked", file=temp_filename)
                await aiofiles.os.remove(temp_filename)

    @module_base.subcommand("download_log", sub_cmd_description="Download the channel message history")
    @interactions.check(interactions.is_owner())
    async def command_download_log(self, ctx: interactions.SlashContext):
        await ctx.defer()
        filename: str = ""
        async with aiofiles.tempfile.NamedTemporaryFile(prefix="AutoKick-log_", suffix=".tar.gz", delete=False) as afp:
            await aioshutil.make_archive(afp.name[:-7], "gztar", f"{os.path.dirname(__file__)}/{self.folder_name}")
            filename = afp.name
        await ctx.send("AutoKick message logs as attached.", file=filename)

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
            temp_folder_name: str = f"{os.path.dirname(__file__)}/{self.folder_name}"
            async with aiofiles.open(temp_folder_name + f"/{channel.id}.csv", mode="a+", encoding="utf-8", newline="") as afp:
                writer = AsyncDictWriter(afp, ["user", "content", "timestamp"], restval="NULL", quoting=csv.QUOTE_ALL)
                if await afp.tell() == 0:
                    await writer.writeheader()
                    await writer.writerow({"user": "", "content": event.message.channel.name, "timestamp": event.message.channel.created_at.timestamp()})
                await writer.writerow({"user": event.message.author.username, "content": event.message.content, "timestamp": event.message.timestamp.timestamp()})
            if not event.message.author.bot and event.message.author.id not in self.passed_members and not any(map(event.message.author.has_role, self.ignored_roles)):
                if event.message.author.id not in self.all_members.keys():
                    self.all_members[event.message.author.id] = deque()
                self.all_members[event.message.author.id].append(event.message)
                if len(self.all_members[event.message.author.id]) > self.threshold_message:
                    self.passed_members.append(event.message.author.id)
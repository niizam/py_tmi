from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from .client_base import ClientBase
from .exceptions import AnonymousMessageError, CommandFailed, CommandTimedOut
from . import utils


class Client(ClientBase):
    """High-level Twitch chat client mirroring the tmi.js commands API."""

    async def action(self, channel: str, message: str, tags: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
        formatted = f"\u0001ACTION {message}\u0001"
        await super().say(channel, formatted, tags)
        return utils.channel(channel), message

    async def announce(self, channel: str, message: str) -> Tuple[str, str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, f"/announce {message}")
        return channel_name, message

    async def ban(self, channel: str, username: str, reason: Optional[str] = None) -> Tuple[str, str, str]:
        username = utils.username(username)
        reason = reason or ""
        command = f"/ban {username} {reason}".strip()
        await self._send_command(utils.channel(channel), command)
        await self._await_success("_promiseBan", command)
        return utils.channel(channel), username, reason

    async def clear(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/clear")
        await self._await_success("_promiseClear", "/clear")
        return (channel_name,)

    async def color(self, color: str) -> Tuple[str]:
        command = f"/color {color}"
        await self._send_command(self._global_default_channel, command)
        await self._await_success("_promiseColor", command)
        return (color,)

    async def commercial(self, channel: str, seconds: int = 30) -> Tuple[str, int]:
        channel_name = utils.channel(channel)
        seconds = int(seconds)
        command = f"/commercial {seconds}"
        await self._send_command(channel_name, command)
        await self._await_success("_promiseCommercial", command)
        return channel_name, seconds

    async def deletemessage(self, channel: str, message_uuid: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, f"/delete {message_uuid}")
        await self._await_success("_promiseDeletemessage", "/delete")
        return (channel_name,)

    async def emoteonly(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/emoteonly")
        await self._await_success("_promiseEmoteonly", "/emoteonly")
        return (channel_name,)

    async def emoteonlyoff(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/emoteonlyoff")
        await self._await_success("_promiseEmoteonlyoff", "/emoteonlyoff")
        return (channel_name,)

    async def followersonly(self, channel: str, minutes: int = 30) -> Tuple[str, int]:
        channel_name = utils.channel(channel)
        command = f"/followers {int(minutes)}"
        await self._send_command(channel_name, command)
        await self._await_success("_promiseFollowers", command)
        return channel_name, int(minutes)

    async def followersonlyoff(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/followersoff")
        await self._await_success("_promiseFollowersoff", "/followersoff")
        return (channel_name,)

    async def host(self, channel: str, target: str) -> Tuple[str, str, int]:
        channel_name = utils.channel(channel)
        target_name = utils.username(target)
        command = f"/host {target_name}"
        await self._send_command(channel_name, command)
        _, remaining = await self._await_success("_promiseHost", command)
        return channel_name, target_name, int(remaining or 0)

    async def join(self, channel: str) -> Tuple[str]:
        channel_name, = await super().join(channel)

        def predicate(args: Tuple[object, ...]) -> bool:
            return len(args) > 1 and utils.channel(args[1]) == channel_name

        result = await self._await_success("_promiseJoin", f"JOIN {channel_name}", predicate=predicate)
        if result and len(result) > 1:
            return (utils.channel(result[1]),)
        return (channel_name,)

    async def mod(self, channel: str, username: str) -> Tuple[str, str]:
        channel_name = utils.channel(channel)
        username = utils.username(username)
        await self._send_command(channel_name, f"/mod {username}")
        await self._await_success("_promiseMod", "/mod")
        return channel_name, username

    async def mods(self, channel: str) -> Iterable[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/mods")
        _, mods = await self._await_success("_promiseMods", "/mods")
        if mods:
            for name in mods:
                mod_list = self.moderators.setdefault(channel_name, [])
                if name not in mod_list:
                    mod_list.append(name)
        return mods or []

    async def part(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(None, f"PART {channel_name}")
        await self._await_success("_promisePart", f"PART {channel_name}")
        return (channel_name,)

    async def ping(self) -> float:
        self._latency_start = self.loop.time()
        await self._send_raw("PING")
        latency, = await self.wait_for("_promisePing")
        return float(latency)

    async def r9kbeta(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/r9kbeta")
        await self._await_success("_promiseR9kbeta", "/r9kbeta")
        return (channel_name,)

    async def r9kbetaoff(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/r9kbetaoff")
        await self._await_success("_promiseR9kbetaoff", "/r9kbetaoff")
        return (channel_name,)

    async def raw(self, command: str, tags: Optional[Dict[str, str]] = None) -> Tuple[str]:
        await self._send_command(None, command, tags=tags)
        return (command,)

    async def reply(self, channel: str, message: str, reply_parent_msg_id, tags: Optional[Dict[str, str]] = None):
        tags = dict(tags or {})
        if isinstance(reply_parent_msg_id, dict):
            reply_parent_msg_id = reply_parent_msg_id.get("id")
        if not reply_parent_msg_id or not isinstance(reply_parent_msg_id, str):
            raise ValueError("replyParentMsgId is required.")
        tags["reply-parent-msg-id"] = reply_parent_msg_id
        return await self.say(channel, message, tags)

    async def say(self, channel: str, message: str, tags: Optional[Dict[str, str]] = None):
        channel_name = utils.channel(channel)
        if (message.startswith(".") and not message.startswith("..")) or message.startswith("/") or message.startswith("\\"):
            if message[1:4] == "me ":
                return await self.action(channel_name, message[4:], tags)
            await self._send_command(channel_name, message, tags=tags or {})
            return channel_name, message
        return await super().say(channel_name, message, tags)

    async def slow(self, channel: str, seconds: int = 300) -> Tuple[str, int]:
        channel_name = utils.channel(channel)
        seconds = int(seconds)
        await self._send_command(channel_name, f"/slow {seconds}")
        await self._await_success("_promiseSlow", "/slow")
        return channel_name, seconds

    async def slowoff(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/slowoff")
        await self._await_success("_promiseSlowoff", "/slowoff")
        return (channel_name,)

    async def subscribers(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/subscribers")
        await self._await_success("_promiseSubscribers", "/subscribers")
        return (channel_name,)

    async def subscribersoff(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/subscribersoff")
        await self._await_success("_promiseSubscribersoff", "/subscribersoff")
        return (channel_name,)

    async def timeout(self, channel: str, username: str, seconds: int = 300, reason: Optional[str] = None) -> Tuple[str, str, int, str]:
        channel_name = utils.channel(channel)
        username = utils.username(username)
        reason = reason or ""
        await self._send_command(channel_name, f"/timeout {username} {int(seconds)} {reason}".strip())
        await self._await_success("_promiseTimeout", "/timeout")
        return channel_name, username, int(seconds), reason

    async def unban(self, channel: str, username: str) -> Tuple[str, str]:
        channel_name = utils.channel(channel)
        username = utils.username(username)
        await self._send_command(channel_name, f"/unban {username}")
        await self._await_success("_promiseUnban", "/unban")
        return channel_name, username

    async def unhost(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/unhost")
        await self._await_success("_promiseUnhost", "/unhost")
        return (channel_name,)

    async def unmod(self, channel: str, username: str) -> Tuple[str, str]:
        channel_name = utils.channel(channel)
        username = utils.username(username)
        await self._send_command(channel_name, f"/unmod {username}")
        await self._await_success("_promiseUnmod", "/unmod")
        return channel_name, username

    async def unvip(self, channel: str, username: str) -> Tuple[str, str]:
        channel_name = utils.channel(channel)
        username = utils.username(username)
        await self._send_command(channel_name, f"/unvip {username}")
        await self._await_success("_promiseUnvip", "/unvip")
        return channel_name, username

    async def vip(self, channel: str, username: str) -> Tuple[str, str]:
        channel_name = utils.channel(channel)
        username = utils.username(username)
        await self._send_command(channel_name, f"/vip {username}")
        await self._await_success("_promiseVip", "/vip")
        return channel_name, username

    async def vips(self, channel: str):
        channel_name = utils.channel(channel)
        await self._send_command(channel_name, "/vips")
        _, vips = await self._await_success("_promiseVips", "/vips")
        return vips or []

    async def whisper(self, username: str, message: str) -> Tuple[str, str]:
        username = utils.username(username)
        if username == self.get_username():
            raise AnonymousMessageError("Cannot send a whisper to the same account.")
        command = f"/w {username} {message}"
        await self._send_command(self._global_default_channel, command)
        try:
            result = await self.wait_for("_promiseWhisper", timeout=5.0)
            if result and isinstance(result[0], str) and result[0]:
                raise CommandFailed(command, result[0])
        except CommandTimedOut:
            pass
        whisper_channel = utils.channel(username)
        userstate = dict(self.globaluserstate)
        userstate.update(
            {
                "message-type": "whisper",
                "message-id": None,
                "thread-id": None,
                "username": self.get_username(),
            }
        )
        self.emit_many(["whisper", "message"], [(whisper_channel, userstate, message, True)])
        return username, message

    async def _await_success(
        self,
        event: str,
        command: str,
        *,
        predicate=None,
        timeout: float = 15.0,
    ):
        result = await self.wait_for(event, predicate=predicate, timeout=timeout)
        if result:
            error = result[0]
            if isinstance(error, str) and error:
                raise CommandFailed(command, error)
        return result


Client.followersmode = Client.followersonly  # type: ignore[attr-defined]
Client.followersmodeoff = Client.followersonlyoff  # type: ignore[attr-defined]
Client.leave = Client.part  # type: ignore[attr-defined]
Client.slowmode = Client.slow  # type: ignore[attr-defined]
Client.r9kmode = Client.r9kbeta  # type: ignore[attr-defined]
Client.uniquechat = Client.r9kbeta  # type: ignore[attr-defined]
Client.r9kmodeoff = Client.r9kbetaoff  # type: ignore[attr-defined]
Client.uniquechatoff = Client.r9kbetaoff  # type: ignore[attr-defined]
Client.slowmodeoff = Client.slowoff  # type: ignore[attr-defined]

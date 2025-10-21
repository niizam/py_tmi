from __future__ import annotations

import asyncio
import ssl
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .event_emitter import EventEmitter
from .exceptions import AnonymousMessageError, AuthenticationError, CommandTimedOut, ConnectionError, NotConnectedError
from .logger import Logger
from .message_queue import MessageQueue
from .options import ClientOptions, ConnectionOptions, IdentityOptions
from .parser import IRCMessage, form_tags, parse_badge_info, parse_badges, parse_emotes, parse_message
from . import utils

DEFAULT_HOST = "irc.chat.twitch.tv"
DEFAULT_PORT = 6697
PING_PAYLOAD = "PING :tmi.twitch.tv"
PONG_PAYLOAD = "PONG :tmi.twitch.tv"
PRIVMSG_LIMIT = 500

class ClientBase(EventEmitter):
    """Core Twitch IRC client that mirrors the behaviour of ClientBase in tmi.js."""

    def __init__(self, options: Optional[ClientOptions] = None, *, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        super().__init__()
        self.loop = loop or asyncio.get_event_loop()
        self.options = options or ClientOptions()

        self.opts_channels = [utils.channel(ch) for ch in self.options.channels]
        self.connection: ConnectionOptions = self.options.connection
        self.identity: IdentityOptions = self.options.identity

        self.log = Logger("py_tmi")
        self.log.set_level(self.options.logging.level)
        self.messages_log_level = self.options.logging.messages_level

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._read_task: Optional[asyncio.Task[None]] = None
        self._ping_task: Optional[asyncio.Task[None]] = None
        self._disconnect_event = asyncio.Event()

        self._command_queue = MessageQueue(self.connection.command_rate_limit, loop=self.loop)
        self._message_queue = MessageQueue(self.connection.message_rate_limit, loop=self.loop)
        self._join_queue = MessageQueue(self.connection.join_rate_limit, loop=self.loop)

        self.server: str = self.connection.server or DEFAULT_HOST
        self.port: int = self.connection.port or DEFAULT_PORT

        self.client_id: Optional[str] = None
        self.username: str = ""
        self.globaluserstate: Dict[str, Any] = {}
        self.userstate: Dict[str, Dict[str, Any]] = {}
        self.channels: List[str] = []
        self.last_joined: str = ""
        self.moderators: Dict[str, List[str]] = {}
        self._skip_membership = self.options.skip_membership
        self._global_default_channel = utils.channel(self.options.global_default_channel)
        self.reconnect = self.connection.reconnect
        self.reconnections = 0
        self.max_reconnect_attempts = self.connection.max_reconnect_attempts
        self.max_reconnect_interval = self.connection.max_reconnect_interval
        self.reconnect_interval = self.connection.reconnect_interval
        self.reconnect_decay = self.connection.reconnect_decay
        self.reconnecting = False
        self.reconnect_timer = self.reconnect_interval

        self.current_latency: float = 0.0
        self._latency_start: float = time.monotonic()
        self.was_close_called = False
        self.reason = ""
        self.emotes = ""
        self.emotesets: Dict[str, Any] = {}

    # --------------------------------------------------------------------- #
    # Connection management
    # --------------------------------------------------------------------- #
    async def connect(self) -> Tuple[str, int]:
        if self.is_connected:
            return (self.server, self.port)

        await self._establish_connection()
        self.was_close_called = False
        self._disconnect_event.clear()

        self.log.info("Connected to %s:%s", self.server, self.port)
        self.emit("connected", self.server, self.port)
        return (self.server, self.port)

    async def disconnect(self) -> Tuple[str, int]:
        if not self._writer:
            raise NotConnectedError("Cannot disconnect: socket is not open.")

        self.was_close_called = True
        self.log.info("Disconnecting from server..")
        await self._close("Client disconnect requested")
        await self._disconnect_event.wait()
        return (self.server, self.port)

    async def _establish_connection(self) -> None:
        try:
            ssl_context: Optional[ssl.SSLContext] = None
            if self.connection.secure:
                ssl_context = ssl.create_default_context()

            self._reader, self._writer = await asyncio.open_connection(
                self.server, self.port, ssl=ssl_context
            )
        except Exception as exc:  # pragma: no cover - network errors are environment-specific
            raise ConnectionError(f"Failed to connect to {self.server}:{self.port}") from exc

        self._read_task = self.loop.create_task(self._reader_loop())
        self._ping_task = self.loop.create_task(self._ping_loop())

        await self._authenticate()

        if self.options.join_existing_channels:
            for channel in self.opts_channels:
                await self.join(channel)

    async def _authenticate(self) -> None:
        username = utils.username(self.identity.username) if self.identity.username else utils.justinfan()
        password = utils.password(self.identity.password)
        self.username = username

        if password:
            await self._send_raw(f"PASS {password}", immediate=True)
        await self._send_raw(f"NICK {username}", immediate=True)

        caps: List[str] = []
        if self.options.request_tags:
            caps.append("twitch.tv/tags")
        if self.options.request_commands:
            caps.append("twitch.tv/commands")
        if not self._skip_membership and self.options.request_membership:
            caps.append("twitch.tv/membership")

        if caps:
            await self._send_raw(f"CAP REQ :{' '.join(caps)}", immediate=True)

    async def _close(self, reason: str) -> None:
        self.reason = reason
        if self._read_task:
            self._read_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()
        self._command_queue.stop()
        self._message_queue.stop()
        self._join_queue.stop()

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        self._disconnect_event.set()

    async def _reader_loop(self) -> None:
        assert self._reader is not None
        try:
            while not self._reader.at_eof():
                raw = await self._reader.readline()
                if not raw:
                    break
                data = raw.decode(errors="ignore").strip("\r\n")
                if not data:
                    continue
                message = parse_message(data)
                if message:
                    await self._handle_message(message)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.emit("error", exc)
            await self._handle_disconnect("Read error")
        finally:
            await self._handle_disconnect("Connection closed")

    async def _ping_loop(self) -> None:
        interval = max(30.0, self.connection.ping_interval)
        try:
            while True:
                await asyncio.sleep(interval)
                if not self.is_connected:
                    continue
                self._latency_start = time.monotonic()
                await self._send_raw(PING_PAYLOAD, immediate=True)
                self.emit("ping")
        except asyncio.CancelledError:
            return

    async def _handle_disconnect(self, reason: str) -> None:
        if self.was_close_called:
            await self._close(reason)
            return

        await self._close(reason)
        self.emit("disconnected", reason)

        if not self.reconnect:
            return

        if self.max_reconnect_attempts is not None and self.reconnections >= self.max_reconnect_attempts:
            self.emit("reconnect_failed", reason)
            return

        self.reconnecting = True
        self.reconnections += 1
        delay = min(self.reconnect_timer, self.max_reconnect_interval)
        self.reconnect_timer *= self.reconnect_decay
        self.log.warn("Reconnecting in %.2f seconds (attempt %s)", delay, self.reconnections)
        await asyncio.sleep(delay)
        try:
            await self._establish_connection()
            self.reconnecting = False
            self.reconnect_timer = self.connection.reconnect_interval
            self.reconnections = 0
            self.emit("reconnected", self.server, self.port)
        except ConnectionError as exc:
            self.emit("error", exc)

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #
    @property
    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    def ready_state(self) -> str:
        if self._writer is None:
            return "CLOSED"
        transport = self._writer.transport
        if transport.is_closing():
            return "CLOSING"
        return "OPEN"

    def get_username(self) -> str:
        return self.username

    def get_options(self) -> ClientOptions:
        return self.options

    def get_channels(self) -> List[str]:
        return list(self.channels)

    def is_mod(self, channel: str, username: str) -> bool:
        chan = utils.channel(channel)
        mods = self.moderators.setdefault(chan, [])
        return utils.username(username) in mods

    # ------------------------------------------------------------------ #
    # Sending commands and messages
    # ------------------------------------------------------------------ #
    async def say(self, channel: str, message: str, tags: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        channel_name = utils.channel(channel)

        if not self.is_connected:
            raise NotConnectedError("Not connected to server.")
        if utils.is_justinfan(self.username):
            raise AnonymousMessageError("Cannot send anonymous messages.")

        async def dispatch() -> None:
            await self._send_privmsg(channel_name, message, tags or {})

        await self._message_queue.add(dispatch)
        return (channel_name, message)

    async def join(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        self.last_joined = channel_name

        async def dispatch() -> None:
            await self._send_raw(f"JOIN {channel_name}", immediate=True)

        await self._join_queue.add(dispatch)
        return (channel_name,)

    async def part(self, channel: str) -> Tuple[str]:
        channel_name = utils.channel(channel)
        await self._send_raw(f"PART {channel_name}")
        return (channel_name,)

    async def whisper(self, username: str, message: str) -> Tuple[str, str]:
        target = utils.username(username)
        if target == self.username:
            raise ValueError("Cannot send a whisper to the same account.")
        command = f"/w {target} {message}"
        await self._send_command(self._global_default_channel, command)
        return (target, message)

    async def _send_privmsg(self, channel: str, message: str, tags: Dict[str, Any]) -> None:
        payload_tags = form_tags(tags)
        for chunk in utils.paginate_message(message, PRIVMSG_LIMIT):
            line = f"{payload_tags + ' ' if payload_tags else ''}PRIVMSG {channel} :{chunk}"
            await self._send_raw(line)
            action_match = utils.action_message(chunk)
            merged_state = dict(self.userstate.get(channel, {}))
            merged_state["emotes"] = None
            message_type = "action" if action_match else "chat"
            merged_state["message-type"] = message_type
            log_message = action_match.group(1) if action_match else chunk
            getattr(self.log, self.messages_log_level, self.log.info)(
                f"[{channel}] <{self.username}>: {log_message}"
            )
            self.emit_many(
                ["action", "message"] if action_match else ["chat", "message"],
                [
                    (channel, merged_state, log_message, True),
                ],
            )

    async def _send_command(
        self,
        channel: Optional[str],
        command: str,
        *,
        tags: Optional[Dict[str, Any]] = None,
    ) -> None:
        async def dispatch() -> None:
            payload_tags = form_tags(tags or {})
            if channel:
                line = f"{payload_tags + ' ' if payload_tags else ''}PRIVMSG {channel} :{command}"
            else:
                line = f"{payload_tags + ' ' if payload_tags else ''}{command}"
            await self._send_raw(line)

        if channel:
            await self._command_queue.add(dispatch)
        else:
            await dispatch()

    async def _send_raw(self, payload: str, *, immediate: bool = False) -> None:
        if not self._writer:
            raise NotConnectedError("Socket is not open.")
        data = f"{payload}\r\n".encode("utf-8")
        self._writer.write(data)
        await self._writer.drain()

    # ------------------------------------------------------------------ #
    # Await helpers
    # ------------------------------------------------------------------ #
    async def wait_for(
        self,
        event: str,
        predicate: Optional[Callable[[Tuple[Any, ...]], bool]] = None,
        *,
        timeout: float = 15.0,
    ) -> Tuple[Any, ...]:
        future: asyncio.Future = self.loop.create_future()

        def listener(*args: Any) -> None:
            if predicate and not predicate(args):
                return
            if not future.done():
                future.set_result(args)

        self.on(event, listener)
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError as exc:
            raise CommandTimedOut(f"Timed out waiting for event '{event}'.") from exc
        finally:
            self.off(event, listener)

    # ------------------------------------------------------------------ #
    # Message handling
    # ------------------------------------------------------------------ #
    async def _handle_message(self, message: IRCMessage) -> None:
        if not message.command:
            return

        if self.listener_count("raw_message"):
            self.emit("raw_message", dict(message.__dict__), message)

        message.tags = parse_emotes(parse_badge_info(parse_badges(message.tags)))

        for key, value in list(message.tags.items()):
            if key in {"emote-sets", "ban-duration", "bits"}:
                continue
            if isinstance(value, str):
                if value == "1":
                    message.tags[key] = True
                elif value == "0":
                    message.tags[key] = False
                else:
                    message.tags[key] = utils.unescape_irc(value)
            elif value is True:
                message.tags[key] = None

        if message.prefix is None:
            await self._handle_server_message(message)
        else:
            await self._handle_user_message(message)

    async def _handle_server_message(self, message: IRCMessage) -> None:
        command = message.command
        if command == "PING":
            await self._send_raw(PONG_PAYLOAD, immediate=True)
            self.emit("pong")
        elif command == "PONG":
            self.current_latency = time.monotonic() - self._latency_start
            self.emit_many(["pong", "_promisePing"], [ (self.current_latency,), ])

    async def _handle_user_message(self, message: IRCMessage) -> None:
        command = message.command
        if command == "PRIVMSG":
            await self._handle_privmsg(message)
        elif command == "WHISPER":
            await self._handle_whisper(message)
        elif command == "NOTICE":
            await self._handle_notice(message)
        elif command == "USERNOTICE":
            await self._handle_usernotice(message)
        elif command == "CLEARCHAT":
            await self._handle_clearchat(message)
        elif command == "CLEARMSG":
            await self._handle_clearmsg(message)
        elif command == "ROOMSTATE":
            await self._handle_roomstate(message)
        elif command == "USERSTATE":
            await self._handle_userstate(message)
        elif command == "GLOBALUSERSTATE":
            await self._handle_globaluserstate(message)
        elif command == "RECONNECT":
            await self._handle_reconnect(message)
        elif command == "JOIN":
            await self._handle_join(message)
        elif command == "PART":
            await self._handle_part(message)
        elif command == "MODE":
            await self._handle_mode(message)
        elif command == "353":
            await self._handle_names(message)
        elif command == "366":
            await self._handle_endofnames(message)
        elif command == "001":
            self.emit("connected", self.server, self.port)
        elif command in {"002", "003", "004", "375", "372", "376"}:
            pass
        elif command == "421":
            self.log.warn("Unsupported IRC command reported: %s", message.params)

    async def _handle_privmsg(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        msg = message.param(1) or ""
        username = utils.username(message.prefix.split("!")[0])

        if message.tags.get("emotes-raw"):
            self.emotes = message.tags["emotes-raw"]  # type: ignore[assignment]

        message.tags["username"] = username
        action_match = utils.action_message(msg)
        message.tags["message-type"] = "action" if action_match else "chat"
        cleaned_msg = action_match.group(1) if action_match else msg

        if username == "jtv":
            name = utils.username(msg.split(" ")[0])
            autohost = "auto" in msg
            if "hosting you for" in msg:
                count = 0
                for part in msg.split():
                    if utils.is_integer(part):
                        count = int(part)
                        break
                self.emit("hosted", channel, name, count, autohost)
            elif "hosting you" in msg:
                self.emit("hosted", channel, name, 0, autohost)
            return

        log_func = getattr(self.log, self.messages_log_level, self.log.info)

        if "bits" in message.tags:
            self.emit("cheer", channel, message.tags, cleaned_msg)
        else:
            reward_id = None
            if "msg-id" in message.tags and message.tags["msg-id"] in {"highlighted-message", "skip-subs-mode-message"}:
                reward_id = message.tags["msg-id"]
            elif "custom-reward-id" in message.tags:
                reward_id = message.tags["custom-reward-id"]
            if reward_id:
                self.emit("redeem", channel, username, reward_id, message.tags, cleaned_msg)

        if action_match:
            log_func(f"[{channel}] *<{username}>: {cleaned_msg}")
            self.emit_many(
                ["action", "message"],
                [(channel, message.tags, cleaned_msg, False)],
            )
        else:
            log_func(f"[{channel}] <{username}>: {cleaned_msg}")
            self.emit_many(
                ["chat", "message"],
                [(channel, message.tags, cleaned_msg, False)],
            )

    async def _handle_whisper(self, message: IRCMessage) -> None:
        username = utils.username(message.prefix.split("!")[0])
        msg = message.param(1) or ""
        userstate = dict(message.tags)
        userstate["message-type"] = "whisper"
        userstate["username"] = username
        self.log.info(f"[WHISPER] <{username}>: {msg}")
        self.emit_many(
            ["whisper", "message"],
            [
                (username, userstate, msg, False),
            ],
        )

    async def _handle_notice(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        msg = message.param(1) or ""
        msgid = message.tags.get("msg-id")

        notice_payload = (channel, msgid, msg)
        null_payload = (None,)
        msgid_payload = (msgid,)
        channel_true = (channel, True)
        channel_false = (channel, False)
        basic_log = f"[{channel}] {msg}"

        if msgid == "subs_on":
            self.log.info(f"[{channel}] This room is now in subscribers-only mode.")
            self.emit_many(["subscriber", "subscribers", "_promiseSubscribers"], [channel_true, channel_true, (None,)])
        elif msgid == "subs_off":
            self.log.info(f"[{channel}] This room is no longer in subscribers-only mode.")
            self.emit_many(["subscriber", "subscribers", "_promiseSubscribersoff"], [channel_false, channel_false, (None,)])
        elif msgid == "emote_only_on":
            self.log.info(f"[{channel}] This room is now in emote-only mode.")
            self.emit_many(["emoteonly", "_promiseEmoteonly"], [channel_true, (None,)])
        elif msgid == "emote_only_off":
            self.log.info(f"[{channel}] This room is no longer in emote-only mode.")
            self.emit_many(["emoteonly", "_promiseEmoteonlyoff"], [channel_false, (None,)])
        elif msgid in {"slow_on", "slow_off", "followers_on_zero", "followers_on", "followers_off"}:
            return
        elif msgid == "r9k_on":
            self.log.info(f"[{channel}] This room is now in r9k mode.")
            self.emit_many(["r9kmode", "r9kbeta", "_promiseR9kbeta"], [channel_true, channel_true, (None,)])
        elif msgid == "r9k_off":
            self.log.info(f"[{channel}] This room is no longer in r9k mode.")
            self.emit_many(["r9kmode", "r9kbeta", "_promiseR9kbetaoff"], [channel_false, channel_false, (None,)])
        elif msgid == "room_mods":
            parts = msg.split(": ")
            mods = (parts[1] if len(parts) > 1 else "").lower().split(", ")
            mods = [name for name in mods if name]
            self.emit_many(["_promiseMods", "mods"], [(None, mods), (channel, mods)])
        elif msgid == "no_mods":
            self.emit_many(["_promiseMods", "mods"], [(None, []), (channel, [])])
        elif msgid == "vips_success":
            trimmed = msg[:-1] if msg.endswith(".") else msg
            parts = trimmed.split(": ")
            vips = (parts[1] if len(parts) > 1 else "").lower().split(", ")
            vips = [name for name in vips if name]
            self.emit_many(["_promiseVips", "vips"], [(None, vips), (channel, vips)])
        elif msgid == "no_vips":
            self.emit_many(["_promiseVips", "vips"], [(None, []), (channel, [])])
        elif msgid in {
            "already_banned",
            "bad_ban_admin",
            "bad_ban_anon",
            "bad_ban_broadcaster",
            "bad_ban_global_mod",
            "bad_ban_mod",
            "bad_ban_self",
            "bad_ban_staff",
            "usage_ban",
        }:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseBan"], [notice_payload, msgid_payload])
        elif msgid == "ban_success":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseBan"], [notice_payload, null_payload])
        elif msgid == "usage_clear":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseClear"], [notice_payload, msgid_payload])
        elif msgid == "usage_mods":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseMods"], [notice_payload, (msgid, [])])
        elif msgid == "mod_success":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseMod"], [notice_payload, null_payload])
        elif msgid == "usage_vips":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseVips"], [notice_payload, (msgid, [])])
        elif msgid == "usage_vip":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseVip"], [notice_payload, msgid_payload])
        elif msgid in {"bad_vip_grantee_banned", "bad_vip_grantee_already_vip", "bad_vip_max_vips_reached", "bad_vip_achievement_incomplete"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseVip"], [notice_payload, msgid_payload])
        elif msgid == "vip_success":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseVip"], [notice_payload, null_payload])
        elif msgid == "usage_mod":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseMod"], [notice_payload, msgid_payload])
        elif msgid in {"bad_mod_banned", "bad_mod_mod"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseMod"], [notice_payload, msgid_payload])
        elif msgid == "unmod_success":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseUnmod"], [notice_payload, null_payload])
        elif msgid == "unvip_success":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseUnvip"], [notice_payload, null_payload])
        elif msgid == "usage_unmod":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseUnmod"], [notice_payload, msgid_payload])
        elif msgid == "bad_unmod_mod":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseUnmod"], [notice_payload, msgid_payload])
        elif msgid == "usage_unvip":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseUnvip"], [notice_payload, msgid_payload])
        elif msgid == "bad_unvip_grantee_not_vip":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseUnvip"], [notice_payload, msgid_payload])
        elif msgid == "color_changed":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseColor"], [notice_payload, null_payload])
        elif msgid in {"usage_color", "turbo_only_color"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseColor"], [notice_payload, msgid_payload])
        elif msgid == "commercial_success":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseCommercial"], [notice_payload, null_payload])
        elif msgid in {"usage_commercial", "bad_commercial_error"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseCommercial"], [notice_payload, msgid_payload])
        elif msgid == "hosts_remaining":
            remaining = 0
            try:
                remaining = int("".join(filter(str.isdigit, msg)))
            except ValueError:
                remaining = 0
            self.emit_many(["notice", "_promiseHost"], [notice_payload, (None, remaining)])
        elif msgid in {"bad_host_hosting", "bad_host_rate_exceeded", "bad_host_error", "usage_host"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseHost"], [notice_payload, msgid_payload])
        elif msgid in {"already_r9k_on", "usage_r9k_on"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseR9kbeta"], [notice_payload, msgid_payload])
        elif msgid in {"already_r9k_off", "usage_r9k_off"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseR9kbetaoff"], [notice_payload, msgid_payload])
        elif msgid == "timeout_success":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseTimeout"], [notice_payload, null_payload])
        elif msgid == "delete_message_success":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseDeletemessage"], [notice_payload, null_payload])
        elif msgid in {"already_subs_off", "usage_subs_off", "already_subs_on", "usage_subs_on"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseSubscribers"], [notice_payload, msgid_payload])
        elif msgid in {"already_emote_only_off", "usage_emote_only_off", "already_emote_only_on", "usage_emote_only_on"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseEmoteonly"], [notice_payload, msgid_payload])
        elif msgid == "usage_slow_on":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseSlow"], [notice_payload, msgid_payload])
        elif msgid == "usage_slow_off":
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseSlowoff"], [notice_payload, msgid_payload])
        elif msgid in {
            "usage_timeout",
            "bad_timeout_admin",
            "bad_timeout_anon",
            "bad_timeout_broadcaster",
            "bad_timeout_duration",
            "bad_timeout_global_mod",
            "bad_timeout_mod",
            "bad_timeout_self",
            "bad_timeout_staff",
        }:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseTimeout"], [notice_payload, msgid_payload])
        elif msgid in {"untimeout_success", "unban_success"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseUnban"], [notice_payload, null_payload])
        elif msgid in {"usage_unban", "bad_unban_no_ban"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseUnban"], [notice_payload, msgid_payload])
        elif msgid in {"usage_delete", "bad_delete_message_error", "bad_delete_message_broadcaster", "bad_delete_message_mod"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseDeletemessage"], [notice_payload, msgid_payload])
        elif msgid in {"usage_unhost", "not_hosting"}:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseUnhost"], [notice_payload, msgid_payload])
        elif msgid in {
            "whisper_invalid_login",
            "whisper_invalid_self",
            "whisper_limit_per_min",
            "whisper_limit_per_sec",
            "whisper_restricted",
            "whisper_restricted_recipient",
        }:
            self.log.info(basic_log)
            self.emit_many(["notice", "_promiseWhisper"], [notice_payload, msgid_payload])
        elif msgid in {
            "no_permission",
            "msg_banned",
            "msg_room_not_found",
            "msg_channel_suspended",
            "tos_ban",
            "invalid_user",
        }:
            self.log.info(basic_log)
            events = [
                "notice",
                "_promiseBan",
                "_promiseClear",
                "_promiseUnban",
                "_promiseTimeout",
                "_promiseDeletemessage",
                "_promiseMods",
                "_promiseMod",
                "_promiseUnmod",
                "_promiseVips",
                "_promiseVip",
                "_promiseUnvip",
                "_promiseCommercial",
                "_promiseHost",
                "_promiseUnhost",
                "_promiseJoin",
                "_promisePart",
                "_promiseR9kbeta",
                "_promiseR9kbetaoff",
                "_promiseSlow",
                "_promiseSlowoff",
                "_promiseFollowers",
                "_promiseFollowersoff",
                "_promiseSubscribers",
                "_promiseSubscribersoff",
                "_promiseEmoteonly",
                "_promiseEmoteonlyoff",
                "_promiseWhisper",
            ]
            payloads = [notice_payload, (msgid, channel)]
            self.emit_many(events, payloads)
        elif msgid in {"msg_rejected", "msg_rejected_mandatory"}:
            self.log.info(basic_log)
            self.emit("automod", channel, msgid, msg)
        elif msgid == "unrecognized_cmd":
            self.log.info(basic_log)
            self.emit("notice", channel, msgid, msg)
        elif msgid in {
            "cmds_available",
            "host_target_went_offline",
            "msg_censored_broadcaster",
            "msg_duplicate",
            "msg_emoteonly",
            "msg_verified_email",
            "msg_ratelimit",
            "msg_subsonly",
            "msg_timedout",
            "msg_bad_characters",
            "msg_channel_blocked",
            "msg_facebook",
            "msg_followersonly",
            "msg_followersonly_followed",
            "msg_followersonly_zero",
            "msg_slowmode",
            "msg_suspended",
            "no_help",
            "usage_disconnect",
            "usage_help",
            "usage_me",
            "unavailable_command",
        }:
            self.log.info(basic_log)
            self.emit("notice", channel, msgid, msg)
        elif msgid in {"host_on", "host_off"}:
            return
        else:
            if "Login unsuccessful" in msg or "Login authentication failed" in msg:
                self.was_close_called = False
                self.reconnect = False
                self.reason = msg
                self.log.error(self.reason)
                await self._handle_disconnect(msg)
            elif "Error logging in" in msg or "Improperly formatted auth" in msg:
                self.was_close_called = False
                self.reconnect = False
                self.reason = msg
                self.log.error(self.reason)
                await self._handle_disconnect(msg)
            elif "Invalid NICK" in msg:
                self.was_close_called = False
                self.reconnect = False
                self.reason = "Invalid NICK."
                self.log.error(self.reason)
                await self._handle_disconnect(self.reason)
            else:
                self.log.warn(f"Could not parse NOTICE from tmi.twitch.tv: {message.raw}")
                self.emit("notice", channel, msgid, msg)

    async def _handle_usernotice(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        msg = message.param(1)
        tags = message.tags
        msgid = tags.get("msg-id")
        username = tags.get("display-name") or tags.get("login")
        plan = tags.get("msg-param-sub-plan", "")
        plan_name_raw = tags.get("msg-param-sub-plan-name") or ""
        plan_name = utils.unescape_irc(plan_name_raw) if plan_name_raw else None
        prime = "Prime" in plan if isinstance(plan, str) else False
        methods = {"prime": prime, "plan": plan, "plan_name": plan_name}
        streak_months = int(tags.get("msg-param-streak-months") or 0)
        recipient = tags.get("msg-param-recipient-display-name") or tags.get("msg-param-recipient-user-name")
        gift_sub_count = int(tags.get("msg-param-mass-gift-count") or 0)
        tags["message-type"] = msgid

        if msgid == "resub":
            self.emit_many(
                ["resub", "subanniversary"],
                [(channel, username, streak_months, msg, tags, methods)],
            )
        elif msgid == "sub":
            self.emit_many(
                ["subscription", "sub"],
                [(channel, username, methods, msg, tags)],
            )
        elif msgid == "subgift":
            self.emit("subgift", channel, username, streak_months, recipient, methods, tags)
        elif msgid == "anonsubgift":
            self.emit("anonsubgift", channel, streak_months, recipient, methods, tags)
        elif msgid == "submysterygift":
            self.emit("submysterygift", channel, username, gift_sub_count, methods, tags)
        elif msgid == "anonsubmysterygift":
            self.emit("anonsubmysterygift", channel, gift_sub_count, methods, tags)
        elif msgid == "primepaidupgrade":
            self.emit("primepaidupgrade", channel, username, methods, tags)
        elif msgid == "giftpaidupgrade":
            sender = tags.get("msg-param-sender-name") or tags.get("msg-param-sender-login")
            self.emit("giftpaidupgrade", channel, username, sender, tags)
        elif msgid == "anongiftpaidupgrade":
            self.emit("anongiftpaidupgrade", channel, username, tags)
        elif msgid == "announcement":
            color = tags.get("msg-param-color")
            self.emit("announcement", channel, tags, msg, False, color)
        elif msgid == "raid":
            raider = tags.get("msg-param-displayName") or tags.get("msg-param-login")
            viewers = int(tags.get("msg-param-viewerCount") or 0)
            self.emit("raided", channel, raider, viewers, tags)
        else:
            self.emit("usernotice", msgid, channel, tags, msg)

    async def _handle_clearchat(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        username = utils.username(message.param(1) or "")
        duration = message.tags.get("ban-duration")
        reason = message.tags.get("ban-reason")
        if username:
            if duration is None:
                self.log.info(f"[{channel}] {username} has been banned.")
                self.emit("ban", channel, username, reason, message.tags)
            else:
                seconds = int(duration)
                self.log.info(f"[{channel}] {username} has been timed out for {seconds} seconds.")
                self.emit("timeout", channel, username, reason, seconds, message.tags)
        else:
            self.log.info(f"[{channel}] Chat was cleared by a moderator.")
            self.emit_many(["clearchat", "_promiseClear"], [(channel,), (None,)])

    async def _handle_clearmsg(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        deleted_message = message.param(1) or ""
        tags = dict(message.tags)
        username = tags.get("login")
        tags["message-type"] = "messagedeleted"
        self.log.info(f"[{channel}] {username}'s message has been deleted.")
        self.emit("messagedeleted", channel, username, deleted_message, tags)

    async def _handle_hosttarget(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        payload = message.param(1) or ""
        parts = payload.split(" ")
        target = parts[0] if parts else "-"
        viewers = 0
        if len(parts) > 1:
            try:
                viewers = int(parts[1])
            except ValueError:
                viewers = 0
        if target == "-":
            self.log.info(f"[{channel}] Exited host mode.")
            self.emit_many(["unhost", "_promiseUnhost"], [(channel, viewers), (None,)])
        else:
            self.log.info(f"[{channel}] Now hosting {target} for {viewers} viewer(s).")
            self.emit("hosting", channel, target, viewers)

    async def _handle_roomstate(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        tags = dict(message.tags)
        if utils.channel(self.last_joined) == channel:
            self.emit("_promiseJoin", None, channel)

        tags["channel"] = channel
        self.emit("roomstate", channel, tags)

        if "subs-only" not in tags:
            if "slow" in tags:
                slow_value = tags["slow"]
                if isinstance(slow_value, bool) and not slow_value:
                    disabled = (channel, False, 0)
                    self.log.info(f"[{channel}] This room is no longer in slow mode.")
                    self.emit_many(["slow", "slowmode", "_promiseSlowoff"], [disabled, disabled, (None,)])
                else:
                    try:
                        seconds = int(slow_value)
                    except (TypeError, ValueError):
                        seconds = 0
                    enabled = (channel, True, seconds)
                    self.log.info(f"[{channel}] This room is now in slow mode.")
                    self.emit_many(["slow", "slowmode", "_promiseSlow"], [enabled, enabled, (None,)])

            if "followers-only" in tags:
                value = tags["followers-only"]
                if value == "-1":
                    disabled = (channel, False, 0)
                    self.log.info(f"[{channel}] This room is no longer in followers-only mode.")
                    self.emit_many(["followersonly", "followersmode", "_promiseFollowersoff"], [disabled, disabled, (None,)])
                else:
                    if isinstance(value, bool) and not value:
                        minutes = 0
                    else:
                        try:
                            minutes = int(value)
                        except (TypeError, ValueError):
                            minutes = 0
                    enabled = (channel, True, minutes)
                    self.log.info(f"[{channel}] This room is now in follower-only mode.")
                    self.emit_many(["followersonly", "followersmode", "_promiseFollowers"], [enabled, enabled, (None,)])

    async def _handle_userstate(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        tags = dict(message.tags)
        tags["username"] = self.username

        if tags.get("user-type") == "mod":
            mods = self.moderators.setdefault(channel, [])
            if self.username not in mods:
                mods.append(self.username)

        if not utils.is_justinfan(self.username) and channel not in self.userstate:
            self.userstate[channel] = tags
            self.last_joined = channel
            if channel not in self.channels:
                self.channels.append(channel)
            if channel not in self.opts_channels:
                self.opts_channels.append(channel)
            self.log.info(f"Joined {channel}")
            self.emit("join", channel, utils.username(self.username), True)

        if tags.get("emote-sets") and tags["emote-sets"] != self.emotes:
            self.emotes = tags["emote-sets"]
            self.emit("emotesets", self.emotes, None)

        self.userstate[channel] = tags
        self.emit("userstate", channel, tags)

    async def _handle_globaluserstate(self, message: IRCMessage) -> None:
        self.globaluserstate = dict(message.tags)
        self.emit("globaluserstate", self.globaluserstate)
        emote_sets = message.tags.get("emote-sets")
        if emote_sets and emote_sets != self.emotes:
            self.emotes = emote_sets
            self.emit("emotesets", self.emotes, None)

    async def _handle_reconnect(self, _message: IRCMessage) -> None:
        self.log.info("Received RECONNECT request from Twitch..")
        await self._handle_disconnect("Server requested reconnect")

    async def _handle_join(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        username = utils.username(message.prefix.split("!")[0])
        is_self = username == self.username
        if is_self:
            if channel not in self.channels:
                self.channels.append(channel)
            if channel not in self.opts_channels:
                self.opts_channels.append(channel)
        self.emit("join", channel, username, is_self)

    async def _handle_part(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        username = utils.username(message.prefix.split("!")[0])
        is_self = username == self.username
        if is_self:
            self.userstate.pop(channel, None)
            if channel in self.channels:
                self.channels.remove(channel)
            if channel in self.opts_channels:
                self.opts_channels.remove(channel)
            self.log.info(f"Left {channel}")
            self.emit("_promisePart", None)
        self.emit("part", channel, username, is_self)

    async def _handle_names(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(2))
        names = message.param(3) or ""
        moderators: List[str] = []
        users: List[str] = []
        for name in names.split():
            clean = utils.username(name.lstrip("@"))
            users.append(clean)
            if name.startswith("@") and clean not in moderators:
                moderators.append(clean)
        if moderators:
            self.moderators[channel] = moderators
        self.emit("_names", channel, users)

    async def _handle_endofnames(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(1))
        self.emit("names", channel)

    async def _handle_mode(self, message: IRCMessage) -> None:
        channel = utils.channel(message.param(0))
        mode = message.param(1)
        username = utils.username(message.param(2))
        mods = self.moderators.setdefault(channel, [])
        if mode == "+o":
            if username not in mods:
                mods.append(username)
            self.emit("mod", channel, username)
        elif mode == "-o":
            if username in mods:
                mods.remove(username)
            self.emit("unmod", channel, username)


__all__ = ["ClientBase"]

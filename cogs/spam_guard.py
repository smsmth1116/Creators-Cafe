from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))


class SpamGuard(commands.Cog):
    WINDOW_SECONDS = 30
    TARGET_CHANNEL_COUNT = 4
    RAPID_WINDOW_SECONDS = 10
    RAPID_MESSAGE_COUNT = 5
    TIMEOUT_HOURS = 24

    def __init__(self, bot):
        self.bot = bot
        self.user_messages = defaultdict(deque)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return

        now = datetime.now(timezone.utc)
        user_id = message.author.id
        history = self.user_messages[user_id]
        history.append((message, now))
        self._trim_history(history, now)

        detection = self._detect_spam(history, message.channel.id, now)
        if detection is None:
            return

        spam_messages, timeout_reason = detection

        await self._forward_spam_messages(spam_messages, message.author)
        await self._delete_spam_messages(spam_messages)
        history.clear()

        try:
            await message.author.timeout(
                timedelta(hours=self.TIMEOUT_HOURS),
                reason=timeout_reason
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        await self._notify_timed_out_user(message.author, spam_messages)

    def _trim_history(self, history, now):
        cutoff = now - timedelta(seconds=self.WINDOW_SECONDS)
        while history and history[0][1] < cutoff:
            history.popleft()

    def _detect_spam(self, history, current_channel_id, now):
        unique_channel_count = len({msg.channel.id for msg, _ in history})
        is_multi_channel_spam = unique_channel_count >= self.TARGET_CHANNEL_COUNT

        rapid_cutoff = now - timedelta(seconds=self.RAPID_WINDOW_SECONDS)
        rapid_messages = [
            msg for msg, sent_at in history
            if sent_at >= rapid_cutoff and msg.channel.id == current_channel_id
        ]
        is_rapid_spam = len(rapid_messages) >= self.RAPID_MESSAGE_COUNT

        if is_rapid_spam:
            return rapid_messages, "10秒以内に同一チャンネルへ5件以上連投したため"
        if is_multi_channel_spam:
            return [msg for msg, _ in history], "30秒以内に4つ以上のチャンネルで発言したため"
        return None

    async def _forward_spam_messages(self, messages, member):
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if log_channel is None:
            return

        embed = discord.Embed(title="Spam検知", color=0xd9a3cd)
        embed.add_field(
            name="ユーザー",
            value=f"{member.mention} (`{member}` / `{member.id}`)",
            inline=False
        )

        attachment_files = []
        for i, msg in enumerate(messages, start=1):
            content = self._normalized_content(msg)

            attachment_names = []
            for attachment in msg.attachments:
                attachment_names.append(attachment.filename)
                try:
                    attachment_files.append(await attachment.to_file())
                except (discord.Forbidden, discord.HTTPException):
                    continue

            if attachment_names:
                attachment_text = ", ".join(attachment_names)
                value = (
                    f"チャンネル: {msg.channel.mention}\n"
                    f"```{content}```\n"
                    f"添付: {attachment_text}"
                )
            else:
                value = (
                    f"チャンネル: {msg.channel.mention}\n"
                    f"```{content}```"
                )

            embed.add_field(
                name=f"メッセージ{i}",
                value=self._truncate_field(value),
                inline=False
            )

        try:
            await log_channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            return

        if not attachment_files:
            return

        for i in range(0, len(attachment_files), 10):
            chunk = attachment_files[i:i + 10]
            try:
                await log_channel.send(files=chunk)
            except (discord.Forbidden, discord.HTTPException):
                continue

    async def _delete_spam_messages(self, messages):
        for msg in messages:
            try:
                await msg.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                continue

    async def _notify_timed_out_user(self, member, messages):
        embed = discord.Embed(
            title="スパム検知による一時対応",
            description=(
                "スパムの可能性があるため、24時間のタイムアウトを適用し、該当のメッセージを削除しました。\n"
                "24時間以内に管理者が内容を確認のうえ、対応を判断いたします。\n"
                ""
            ),
            color=0xd9a3cd
        )

        embed.add_field(
            name="異議申し立て",
            value="誤りだと思われる場合は、<@1042736116912103485> までご連絡ください。",
            inline=False
        )

        for i, msg in enumerate(messages, start=1):
            content = self._normalized_content(msg)

            value = self._truncate_field(f"```{content}```")
            embed.add_field(name=f"メッセージ{i}", value=value, inline=False)

        try:
            await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    def _normalized_content(self, message):
        content = message.content.strip() if message.content else ""
        return content if content else "(本文なし)"

    def _truncate_field(self, value):
        if len(value) <= 1024:
            return value
        return value[:1021] + "..."


async def setup(bot):
    await bot.add_cog(SpamGuard(bot))

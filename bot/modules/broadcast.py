from asyncio import sleep
from time import time
from secrets import token_hex

from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked

from ..core.config_manager import Config
from ..core.tg_client import TgClient
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.db_handler import database
from ..helper.ext_utils.status_utils import get_readable_time
from ..helper.telegram_helper.message_utils import (
    edit_message,
    send_message,
)

bc_cache = {}


@new_task
async def broadcast(_, message):
    bc_id, forwarded, quietly, deleted, edited = "", False, False, False, False
    if not Config.DATABASE_URL:
        return await send_message(
            message, "DATABASE_URL not provided to fetch PM Users!"
        )
    rply = message.reply_to_message
    if len(message.command) > 1:
        if not message.command[1].startswith("-"):
            bc_id = (
                message.command[1] if bc_cache.get(message.command[1], False) else ""
            )
            if not bc_id:
                return await send_message(
                    message,
                    "<i>Broadcast ID not found! After Restart, you can't edit or delete broadcasted messages...</i>",
                )
        for arg in message.command:
            if arg in ["-f", "-forward"] and rply:
                forwarded = True
            if arg in ["-q", "-quiet"] and rply:
                quietly = True
            elif arg in ["-d", "-delete"] and bc_id:
                deleted = True
            elif arg in ["-e", "-edit"] and bc_id and rply:
                edited = True
    if not bc_id and not rply:
        return await send_message(
            message,
            """<b>By replying to msg to Broadcast:</b>
/broadcast bc_id -d -e -f -q

<b>Forward Broadcast with Tag:</b> -f or -forward
/cmd [reply_msg] -f

<b>Quietly Broadcast msg:</b> -q or -quiet
/cmd [reply_msg] -q -f

<b>Edit Broadcast msg:</b> -e or -edit
/cmd [reply_edited_msg] broadcast_id -e

<b>Delete Broadcast msg:</b> -d or -delete
/bc broadcast_id -d

<b>Notes:</b>
1. Broadcast msgs can be only edited or deleted until restart.
2. Forwarded msgs can't be Edited""",
        )
    t, s, b, d, u = 0, 0, 0, 0, 0
    if deleted:
        temp_wait = await send_message(
            message, "<i>Deleting the Broadcasted Message! Please Wait ...</i>"
        )
        for uid, msg_id in (msgs := bc_cache[bc_id]):
            try:
                await (await TgClient.bot.get_messages(uid, msg_id)).delete()
                await sleep(0.2)
                msgs.remove((uid, msg_id))
                s += 1
            except Exception:
                u += 1
            t += 1
        return await edit_message(
            temp_wait,
            f"""⌬  <b><i>Broadcast Deleted Stats :</i></b>
┠ <b>Total Users:</b> <code>{t}</code>
┠ <b>Success:</b> <code>{s}</code>
┖ <b>Unsuccess Attempt:</b> <code>{u}</code>

<b>Broadcast ID:</b> <code>{bc_id}</code>""",
        )
    elif edited:
        temp_wait = await send_message(
            message, "<i>Editing the Broadcasted Message! Please Wait ...</i>"
        )
        for uid, msg_id in bc_cache[bc_id]:
            msg = await TgClient.bot.get_messages(uid, msg_id)
            if hasattr(msg, "forward_from"):
                return await edit_message(
                    temp_wait,
                    "<i>Forwarded Messages can't be Edited, Only can be Deleted !</i>",
                )
            try:
                await msg.edit(
                    text=rply.text,
                    entities=rply.entities,
                    reply_markup=rply.reply_markup,
                )
                await sleep(0.3)
                s += 1
            except FloodWait as e:
                await sleep(e.value)
                await msg.edit(
                    text=rply.text,
                    entities=rply.entities,
                    reply_markup=rply.reply_markup,
                )
            except Exception:
                u += 1
            t += 1
        return await edit_message(
            temp_wait,
            f"""⌬  <b><i>Broadcast Edited Stats :</i></b>
┠ <b>Total Users:</b> <code>{t}</code>
┠ <b>Success:</b> <code>{s}</code>
┖ <b>Unsuccess Attempt:</b> <code>{u}</code>

<b>Broadcast ID:</b> <code>{bc_id}</code>""",
        )
    start_time = time()
    status = """⌬  <b><i>Broadcast Stats :</i></b>
┠ <b>Total Users:</b> <code>{t}</code>
┠ <b>Success:</b> <code>{s}</code>
┠ <b>Blocked Users:</b> <code>{b}</code>
┠ <b>Deleted Accounts:</b> <code>{d}</code>
┖ <b>Unsuccess Attempt:</b> <code>{u}</code>"""
    updater = time()
    bc_hash, bc_msgs = token_hex(5), []
    pls_wait = await send_message(message, status.format(**locals()))
    for uid in await database.get_pm_uids():
        try:
            bc_msg = (
                await rply.forward(uid, disable_notification=quietly)
                if forwarded
                else await rply.copy(uid, disable_notification=quietly)
            )
            s += 1
        except FloodWait as e:
            await sleep(e.value * 1.1)
            bc_msg = (
                await rply.forward(uid, disable_notification=quietly)
                if forwarded
                else await rply.copy(uid, disable_notification=quietly)
            )
            s += 1
        except UserIsBlocked:
            await database.rm_pm_user(uid)
            b += 1
        except InputUserDeactivated:
            await database.rm_pm_user(uid)
            d += 1
        except Exception:
            u += 1
        if bc_msg:
            bc_msgs.append((uid, bc_msg.id))
        t += 1
        if (time() - updater) > 10:
            await edit_message(pls_wait, status.format(**locals()))
            updater = time()
    bc_cache[bc_hash] = bc_msgs
    await edit_message(
        pls_wait,
        f"{status.format(**locals())}\n\n<b>Elapsed Time:</b> <code>{get_readable_time(time() - start_time)}</code>\n<b>Broadcast ID:</b> <code>{bc_hash}</code>",
    )

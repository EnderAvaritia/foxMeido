"""
auto_pull.py - 自动拉取仓库更新插件

定时或手动执行 git pull，检测到新提交后自动重启机器人以加载新代码。

命令：
  update              — 手动触发 git pull
  update force        — 强制拉取（丢弃本地未提交更改）

配置（.env）：
  GIT_AUTO_PULL_ENABLED=false          # 是否启用自动检查（默认 false）
  GIT_AUTO_PULL_INTERVAL=30            # 间隔模式：每 N 分钟检查一次
  GIT_AUTO_PULL_TIME=06:00             # 定时模式：每天检查时间（HH:MM）
  GIT_AUTO_PULL_SCHEDULE_TYPE=both     # cron / interval / both（默认 both）
  GIT_AUTO_PULL_NOTIFY_GROUP=          # 拉取结果通知的目标群号（可选）
  GIT_AUTO_PULL_REMOTE=origin          # 远程仓库名或 URL（如 origin 或 https://github.com/user/repo.git）
  GIT_AUTO_PULL_GIT_PATH=git           # git 可执行文件路径（默认 git，用绝对路径如 C:/Program Files/Git/bin/git.exe）
  GIT_AUTO_PULL_RESTART_CMD=           # 自定义重启命令（如 systemctl restart bot；仅在 FORCE_EXIT=true 时生效）
  GIT_AUTO_PULL_FORCE_EXIT=false       # 是否主动退出进程（默认 false：交给 NoneBot 自动重载；true：拉取成功后强制退出，由 restart_cmd/进程管理器接管）
  GIT_AUTO_PULL_BRANCH=                # 目标分支（留空则自动检测当前分支）
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from nonebot import require, get_bot, get_driver
from nonebot.exception import FinishedException
from nonebot.log import logger
from nonebot.plugin import on_command

from plugins.message_reaction import reaction_cleanup, extract_group_id

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler  # noqa: E402


# ── 常量 ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CST = timezone(timedelta(hours=8))

# 发送消息的超时上限（秒）。git pull 落盘新代码后，nb run 的自动重载
# 可能已开始关闭与 OneBot 的连接，此时 API 调用会一直挂到适配器超时
# （默认 30s）。这里统一用更短的上限，避免消息发送拖慢重载流程。
SEND_TIMEOUT: float = 10.0

# 在 getConfig() 后由模块初始化时更新
_GIT_EXECUTABLE: str = "git"


# ── 配置读取 ──────────────────────────────────────────────────────
def _readDotenv(key: str) -> str:
    """从 os.environ 或 .env 文件读配置。"""
    val = os.environ.get(key, "")
    if val:
        return val.split("#")[0].strip()
    env_path = BASE_DIR / ".env"
    if not env_path.is_file():
        return ""
    try:
        text = env_path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"export\s+", line)
            if m:
                line = line[m.end():]
            m = re.match(rf"({re.escape(key)})\s*=\s*(.*)", line)
            if m:
                val = m.group(2).strip().strip('"').strip("'")
                val = val.split("#")[0].strip()
                return val
    except OSError:
        pass
    return ""


def getConfig() -> dict[str, Any]:
    """读取插件所需的所有配置项。"""
    enabled = _readDotenv("GIT_AUTO_PULL_ENABLED") in ("true", "1", "yes")
    interval_str = _readDotenv("GIT_AUTO_PULL_INTERVAL") or "30"
    check_time = _readDotenv("GIT_AUTO_PULL_TIME") or "06:00"
    schedule_type = (_readDotenv("GIT_AUTO_PULL_SCHEDULE_TYPE") or "both").lower()
    notify_group = _readDotenv("GIT_AUTO_PULL_NOTIFY_GROUP")
    remote = _readDotenv("GIT_AUTO_PULL_REMOTE") or "origin"
    git_path = _readDotenv("GIT_AUTO_PULL_GIT_PATH") or "git"
    restart_cmd = _readDotenv("GIT_AUTO_PULL_RESTART_CMD") or ""
    force_exit = _readDotenv("GIT_AUTO_PULL_FORCE_EXIT") in ("true", "1", "yes")
    branch = _readDotenv("GIT_AUTO_PULL_BRANCH") or ""

    try:
        interval = int(interval_str)
    except ValueError:
        interval = 30

    if schedule_type not in ("cron", "interval", "both"):
        schedule_type = "both"

    return {
        "enabled": enabled,
        "interval": interval,
        "check_time": check_time,
        "schedule_type": schedule_type,
        "notify_group": notify_group,
        "remote": remote,
        "git_path": git_path,
        "restart_cmd": restart_cmd,
        "force_exit": force_exit,
        "branch": branch,
    }


# ── Git 操作 ──────────────────────────────────────────────────────
def _decodeBytes(data: bytes) -> str:
    """解码 git 进程输出，避免 Windows GBK 编码崩溃。

    Windows 中文环境下 git 可能按 GBK(cp936) 输出文本（如含中文的
    提交信息、分支名），直接按 UTF-8 严格解码会抛 UnicodeDecodeError
    （它继承自 ValueError，现有的 except OSError 捕获不到，会导致
    命令处理崩溃）。这里依次尝试 UTF-8 → GBK，最后用
    errors='replace' 兜底，保证任何字节序列都不会抛异常。
    """
    if not data:
        return ""
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _git(*args: str, timeout: int = 60) -> tuple[str, str, int]:
    """执行 git 命令，返回 (stdout, stderr, returncode)。"""
    try:
        result = subprocess.run(
            [_GIT_EXECUTABLE] + list(args),
            capture_output=True,
            cwd=str(BASE_DIR),
            timeout=timeout,
        )
        return (
            _decodeBytes(result.stdout).strip(),
            _decodeBytes(result.stderr).strip(),
            result.returncode,
        )
    except subprocess.TimeoutExpired:
        return "", "git 命令超时", -1
    except FileNotFoundError:
        return "", f"git 未找到: {_GIT_EXECUTABLE}，请检查 GIT_AUTO_PULL_GIT_PATH", -1
    except OSError as e:
        return "", f"执行 git 失败: {e}", -1


def _isUrl(value: str) -> bool:
    """判断字符串是 URL 还是 remote 名称。"""
    return "://" in value or value.startswith("git@")


def _fetchRef(remote: str, branch: str) -> str:
    """返回 fetch 后可用的 ref（URL 模式用 FETCH_HEAD，remote 模式用 remote/branch）。"""
    if _isUrl(remote):
        return "FETCH_HEAD"
    return f"{remote}/{branch}"


def getCurrentBranch() -> str:
    """获取当前分支名。"""
    stdout, _, rc = _git("rev-parse", "--abbrev-ref", "HEAD")
    return stdout if rc == 0 else ""


def gitFetch(remote: str, branch: str) -> bool:
    """git fetch 远程（支持 remote 名称或 URL），返回是否成功。"""
    stdout, stderr, rc = _git("fetch", remote, branch)
    if rc != 0:
        logger.warning("git fetch 失败: {}", stderr)
        return False
    return True


def countBehind(remote: str, branch: str) -> int:
    """获取落后远程的 commit 数（支持 remote 名称或 URL）。"""
    ref = _fetchRef(remote, branch)
    stdout, stderr, rc = _git("rev-list", "--count", f"HEAD..{ref}")
    if rc == 0 and stdout.isdigit():
        return int(stdout)
    return 0


def hasLocalChanges() -> bool:
    """检查是否有未提交的本地更改。"""
    stdout, _, rc = _git("status", "--porcelain")
    if rc == 0 and stdout:
        return True
    return False


def gitPull(remote: str, branch: str, force: bool = False) -> tuple[bool, str]:
    """
    执行 git pull。

    Args:
        remote: 远程仓库名或 URL。
        branch: 目标分支。
        force: 是否强制拉取（丢弃本地更改）。

    Returns:
        (是否有更新, 消息字符串)
    """
    # 如有本地更改且非 force 模式，放弃
    if hasLocalChanges() and not force:
        return (
            False,
            "存在未提交的本地更改，请先 commit/stash 或使用「update force」强制拉取",
        )

    # fetch
    if not gitFetch(remote, branch):
        return False, "git fetch 失败，请检查网络连接"

    # 检查落后 commit 数
    behind = countBehind(remote, branch)
    if behind == 0:
        return False, "已经是最新"

    ref = _fetchRef(remote, branch)

    # force 模式下先 reset
    if force:
        _git("reset", "--hard", ref)
    else:
        stdout, stderr, rc = _git("pull", remote, branch)
        if rc != 0:
            return False, f"git pull 失败: {stderr}"

    # 拉取后获取新 commit 的简短信息
    log_stdout, _, _ = _git(
        "log", f"HEAD~{behind}..HEAD", "--oneline", "--no-decorate",
    )
    commits = log_stdout.splitlines() if log_stdout else []
    commit_lines = "\n".join(f"  • {c}" for c in commits[:10])
    if len(commits) > 10:
        commit_lines += f"\n  ... 及其他 {len(commits) - 10} 个提交"

    msg = f"成功拉取 {behind} 个新提交（{branch} 分支）\n{commit_lines}"
    return True, msg


# ── 机器人重启 ────────────────────────────────────────────────────
def _restartViaExecv() -> None:
    """方式 A：os.execv 原地替换当前进程（仅 Linux，Windows 上不可靠）。"""
    logger.info("通过 os.execv 重启...")
    args = [sys.executable, "-m", "nb_cli", "run"]
    os.execv(sys.executable, args)


def _restartViaCommand(cmd: str) -> None:
    """方式 B：执行自定义命令后退出当前进程。"""
    import shlex

    logger.info("通过自定义命令重启: {}", cmd)
    try:
        parts = shlex.split(cmd)
        subprocess.Popen(parts, shell=False)
    except Exception as e:
        logger.error("自定义重启命令失败: {}", e)
    # 无论如何都退出，让进程管理器或新进程接管
    os._exit(0)


def restartBot() -> None:
    """决定是否主动退出进程以加载更新。

    GIT_AUTO_PULL_FORCE_EXIT=false（默认）：
        不退出。NoneBot 的自动重载（nb run 默认开启）会检测到
        git pull 后的代码文件变化并优雅重启，本函数只打日志。

    GIT_AUTO_PULL_FORCE_EXIT=true：
        主动退出。配置了 GIT_AUTO_PULL_RESTART_CMD 时先拉起外部重启命令；
        否则 Windows 直接 os._exit(0)，Linux 尝试 os.execv 原地替换。

    注意：必须在所有响应消息发送完成（await 返回）后调用，
    本函数退出时不会等待事件循环中未完成的任务。
    """
    cfg = getConfig()

    if not cfg["force_exit"]:
        logger.info("GIT_AUTO_PULL_FORCE_EXIT=false，不主动退出，等待 NoneBot 自动重载")
        return

    cmd = cfg.get("restart_cmd", "").strip()
    if cmd:
        _restartViaCommand(cmd)
        return

    if os.name == "nt":
        # Windows 没有 POSIX exec，直接干净退出，
        # 由进程管理器 / 启动脚本接管拉起。
        logger.info("Windows 环境且未配置 GIT_AUTO_PULL_RESTART_CMD，直接退出进程")
        os._exit(0)
    try:
        _restartViaExecv()
    except Exception as e:
        logger.error("os.execv 重启失败，退出进程: {}", e)
        os._exit(1)


# ── 更新状态恢复（.lock）────────────────────────────────────────
def getCurrentHead() -> str:
    """获取当前 HEAD commit 完整哈希。"""
    stdout, _, rc = _git("rev-parse", "HEAD")
    return stdout if rc == 0 else ""


def getCommitLog(old_head: str, new_head: str, limit: int = 10) -> str:
    """列出 old_head..new_head 之间的提交（用于更新完成通知）。"""
    if not old_head or not new_head or old_head == new_head:
        return "（无新增提交）"
    stdout, _, rc = _git(
        "log", f"{old_head}..{new_head}", "--oneline", "--no-decorate",
        f"-{limit}",
    )
    if rc != 0 or not stdout:
        return "（无法获取提交记录）"
    lines = [f"  • {c}" for c in stdout.splitlines()]
    return "新提交：\n" + "\n".join(lines)


def writeUpdateLock(
    old_head: str,
    trigger_group_id: int | None,
    trigger_user_id: int | None = None,
) -> None:
    """在退出前把更新状态落盘，重启后 on_bot_connect 会补发通知。

    trigger_group_id / trigger_user_id 记录触发来源：群聊触发记群号，
    私聊触发记用户 QQ，重启后据此补发更新完成通知，保证触发者一定能
    收到结果。
    """
    payload = {
        "start_time": time.time(),
        "old_head": old_head,
        "trigger_group_id": trigger_group_id,
        "trigger_user_id": trigger_user_id,
    }
    lock_path = BASE_DIR / ".lock"
    try:
        lock_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        logger.info(
            "已写入 .lock 更新标记 (old_head={}, group={}, user={})",
            old_head, trigger_group_id, trigger_user_id,
        )
    except OSError as e:
        logger.error("写入 .lock 失败: {}", e)


@get_driver().on_bot_connect
async def onBotConnect() -> None:
    """机器人连接成功后：若存在 .lock 说明上次更新触发了退出，补发完成通知。"""
    lock_path = BASE_DIR / ".lock"
    if not lock_path.is_file():
        return
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        lock_path.unlink(missing_ok=True)
        start_time = float(payload.get("start_time") or 0)
        old_head = str(payload.get("old_head") or "")
        group_id = payload.get("trigger_group_id")
        user_id = payload.get("trigger_user_id")

        elapsed = int(time.time() - start_time) if start_time else 0
        commits = getCommitLog(old_head, getCurrentHead())
        message = f"✅ 更新完成！用时 {elapsed} 秒\n{commits}"

        if group_id:
            await sendToGroup(str(group_id), message)
        elif user_id:
            await sendToUser(str(user_id), message)
        else:
            logger.info("更新完成，但无触发群/用户信息，未发送通知: {}", message)
    except Exception as e:
        # 恢复失败不能影响 bot 正常运行
        logger.warning("发送更新完成通知失败: {}", e)


# ── 消息发送 ──────────────────────────────────────────────────────
async def _safeCleanup(cleanup: Any | None) -> None:
    """移除表情回应；连接正在关闭时静默失败（仅记日志）。"""
    if not cleanup:
        return
    try:
        await asyncio.wait_for(cleanup(), timeout=SEND_TIMEOUT)
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("移除表情回应超时（连接可能在重载中被关闭）")
    except Exception as e:
        logger.warning("移除表情回应失败: {}", e)


async def _safeSend(matcher, message: str, **kwargs) -> bool:
    """发送消息，失败时只记日志并返回 False。

    git pull 成功后新代码已落盘，NoneBot 自动重载可能正在关闭连接，
    此时发送失败是**预期行为**——.lock 已落盘，重启后 onBotConnect
    会补发完成通知，因此调用方不应把发送失败当作命令异常处理。
    """
    try:
        await asyncio.wait_for(matcher.send(message, **kwargs), timeout=SEND_TIMEOUT)
        return True
    except FinishedException:
        raise
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("发送消息超时（连接可能在重载中被关闭）")
        return False
    except Exception as e:
        logger.warning("发送消息失败: {}", e)
        return False


async def _safeFinish(matcher, message: str, **kwargs) -> None:
    """发送最终消息并结束事件处理；发送失败时只记日志，不再补发错误通知。

    与 finish() 一致：发送成功后抛出 FinishedException 结束事件处理；
    发送失败（连接已被重载关闭）时静默降级，避免留下无意义的报错堆栈。
    """
    try:
        await matcher.finish(message, **kwargs)
    except FinishedException:
        raise
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("发送最终消息超时（连接可能在重载中被关闭）")
    except Exception as e:
        logger.warning("发送最终消息失败: {}", e)


async def sendToGroup(group_id: str, message: str) -> None:
    """向指定 QQ 群发送消息。"""
    try:
        bot = get_bot()
        await asyncio.wait_for(
            bot.call_api("send_group_msg", group_id=int(group_id), message=message),
            timeout=SEND_TIMEOUT,
        )
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("发送群消息超时 (group={}): 连接可能在重载中被关闭", group_id)
    except Exception as e:
        logger.error("发送群消息失败 (group={}): {}", group_id, e)


async def sendToUser(user_id: str, message: str) -> None:
    """向指定 QQ 用户私聊发送消息。"""
    try:
        bot = get_bot()
        await asyncio.wait_for(
            bot.call_api("send_private_msg", user_id=int(user_id), message=message),
            timeout=SEND_TIMEOUT,
        )
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("发送私聊消息超时 (user={}): 连接可能在重载中被关闭", user_id)
    except Exception as e:
        logger.error("发送私聊消息失败 (user={}): {}", user_id, e)


async def sendNotification(message: str) -> None:
    """如果有配置通知群，发送通知。"""
    cfg = getConfig()
    group = cfg["notify_group"]
    if group:
        await sendToGroup(group, message)


# ── 核心检查逻辑 ──────────────────────────────────────────────────
async def runPull(force: bool = False) -> tuple[bool, str]:
    """
    执行一次完整的 pull 检查流程。

    Returns:
        (是否有更新, 给用户的消息文本)。调用方负责在消息发送完成后触发重启。
    """
    cfg = getConfig()
    remote = cfg["remote"]
    branch = cfg["branch"] or getCurrentBranch() or "main"

    logger.info("检查仓库更新 (remote={}, branch={}, force={})", remote, branch, force)
    return gitPull(remote, branch, force=force)


# ── 命令 ──────────────────────────────────────────────────────────
update_cmd = on_command("update", aliases={"pull"}, priority=20, block=True)


@update_cmd.handle()
async def handleUpdate(bot, event):
    """手动触发 git pull 并重启。"""
    cleanup = await reaction_cleanup(bot, event)

    # 解析参数
    raw_msg = event.get_plaintext() if hasattr(event, "get_plaintext") else str(event)
    args = raw_msg.strip().split()
    force = len(args) > 1 and args[1] == "force"

    try:
        old_head = getCurrentHead()
        has_update, msg = await runPull(force=force)

        if not has_update:
            result = f"✅ {msg}"
            await _safeCleanup(cleanup)
            await _safeFinish(update_cmd, result, at_sender=False)
            return

        # 先落盘更新标记：重启后 onBotConnect 会据此补发完成通知，
        # 避免“消息发一半进程被强杀 / 重启后无任何反馈”。
        group_id = extract_group_id(event)
        user_id = getattr(event, "user_id", None)
        writeUpdateLock(
            old_head=old_head,
            trigger_group_id=group_id,
            trigger_user_id=user_id,
        )

        # 发送成功消息，再清理表情、缓冲后退出
        cfg = getConfig()
        if cfg["force_exit"]:
            notice = "⚠️ 正在退出进程以加载更新，完成后会在此群收到通知"
        else:
            notice = "✅ 已拉取新代码，NoneBot 将自动重载，生效后在此群收到通知"
        result = f"🔄 {msg}\n\n{notice}"

        # 关键：git pull 把新代码落盘后，nb run 的自动重载可能已经/即将
        # 关闭与 OneBot 的连接，此时发送失败是**预期行为**——.lock 已保证
        # 重启后 onBotConnect 会补发完成通知。因此发送失败只记日志，绝不
        # 走进 except 分支误报「命令异常」（否则错误通知本身也发不出去，
        # 只会留下难看的双份堆栈并拖慢整个重载流程）。
        sent = await _safeSend(update_cmd, result, at_sender=False)
        if not sent:
            logger.warning(
                "更新通知未能送达（连接可能在重载中被关闭），"
                "重启后 onBotConnect 将补发完成通知"
            )
        await _safeCleanup(cleanup)
        # 给消息 / 表情移除的发送留出缓冲，避免同步退出时截断
        await asyncio.sleep(1)

        logger.info("更新拉取完成，进入收尾（force_exit={}）", cfg["force_exit"])
        restartBot()
        # restartBot() 在 GIT_AUTO_PULL_FORCE_EXIT=false 时不退出，直接返回；
        # 完成消息已由上方 _safeSend 发出，无需再 finish 一次造成重复消息。
    except FinishedException:
        # finish() 正常结束事件处理，交给 NoneBot，不作异常处理
        raise
    except Exception as e:
        logger.exception("update 命令异常")
        await _safeCleanup(cleanup)
        await _safeFinish(update_cmd, f"❌ 命令异常: {e}", at_sender=False)
        return


# ── 定时任务 ──────────────────────────────────────────────────────
async def scheduledPull():
    """定时任务：检查更新，有更新则通知并重启。"""
    cfg = getConfig()
    if not cfg["enabled"]:
        return

    logger.info("定时拉取检查：开始执行")
    try:
        remote = cfg["remote"]
        branch = cfg["branch"] or getCurrentBranch() or "main"
        old_head = getCurrentHead()
        has_update, msg = gitPull(remote, branch, force=False)

        if has_update:
            if cfg["force_exit"]:
                full_msg = f"🔄 自动更新: {msg}\n\n⚠️ 正在退出进程以加载更新"
            else:
                full_msg = f"🔄 自动更新: {msg}\n\n✅ 已拉取新代码，NoneBot 自动重载后生效"
            logger.info("定时拉取到更新（force_exit={}）", cfg["force_exit"])
            # 先落盘更新标记，重启后 onBotConnect 会补发完成通知
            notify_group = cfg["notify_group"].strip()
            writeUpdateLock(
                old_head=old_head,
                trigger_group_id=int(notify_group) if notify_group.isdigit() else None,
            )
            # 通知必须先 await 完成，再退出进程，避免消息被截断
            await sendNotification(full_msg)
            await asyncio.sleep(1)
            restartBot()
        else:
            logger.info("定时拉取检查完成: {}", msg)
    except Exception as e:
        logger.exception("定时拉取检查异常: {}", e)
        await sendNotification(f"❌ 自动拉取检查异常: {e}")


# ── 解析定时时间 ──────────────────────────────────────────────────
def _parseTime(time_str: str) -> tuple[int, int]:
    """解析 'HH:MM' 格式的时间字符串。"""
    parts = time_str.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return hour, minute


# ── 插件初始化 ────────────────────────────────────────────────────
_cfg = getConfig()

# 设置 git 可执行文件路径
_GIT_EXECUTABLE = _cfg["git_path"]

if _cfg["enabled"]:
    _schedule_type = _cfg["schedule_type"]
    _branch = _cfg["branch"] or getCurrentBranch() or "main"

    logger.info(
        "自动拉取已启用: schedule={}, interval={}min, time={}, branch={}",
        _schedule_type, _cfg["interval"], _cfg["check_time"], _branch,
    )

    # 定时模式（每天固定时间）
    if _schedule_type in ("cron", "both"):
        _hour, _minute = _parseTime(_cfg["check_time"])
        scheduler.add_job(
            scheduledPull,
            "cron",
            hour=_hour,
            minute=_minute,
            id="auto_pull_cron",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("定时拉取已注册: 每天 {:02d}:{:02d}", _hour, _minute)

    # 间隔模式（每 N 分钟）
    if _schedule_type in ("interval", "both"):
        scheduler.add_job(
            scheduledPull,
            "interval",
            minutes=_cfg["interval"],
            id="auto_pull_interval",
            replace_existing=True,
            misfire_grace_time=120,
        )
        logger.info("间隔拉取已注册: 每 {} 分钟", _cfg["interval"])

else:
    logger.info("自动拉取未启用（GIT_AUTO_PULL_ENABLED=false），仅支持手动 update 命令")

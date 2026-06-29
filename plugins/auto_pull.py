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
  GIT_AUTO_PULL_REMOTE=origin          # 远程仓库名（默认 origin）
  GIT_AUTO_PULL_BRANCH=                # 目标分支（留空则自动检测当前分支）
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from nonebot import require, get_bot
from nonebot.log import logger
from nonebot.plugin import on_command

from plugins.message_reaction import reaction_cleanup

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler  # noqa: E402


# ── 常量 ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CST = timezone(timedelta(hours=8))


# ── 配置读取 ──────────────────────────────────────────────────────
def _read_dotenv(key: str) -> str:
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


def get_config() -> dict[str, Any]:
    """读取插件所需的所有配置项。"""
    enabled = _read_dotenv("GIT_AUTO_PULL_ENABLED") in ("true", "1", "yes")
    interval_str = _read_dotenv("GIT_AUTO_PULL_INTERVAL") or "30"
    check_time = _read_dotenv("GIT_AUTO_PULL_TIME") or "06:00"
    schedule_type = (_read_dotenv("GIT_AUTO_PULL_SCHEDULE_TYPE") or "both").lower()
    notify_group = _read_dotenv("GIT_AUTO_PULL_NOTIFY_GROUP")
    remote = _read_dotenv("GIT_AUTO_PULL_REMOTE") or "origin"
    branch = _read_dotenv("GIT_AUTO_PULL_BRANCH") or ""

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
        "branch": branch,
    }


# ── Git 操作 ──────────────────────────────────────────────────────
def _git(*args: str, timeout: int = 60) -> tuple[str, str, int]:
    """执行 git 命令，返回 (stdout, stderr, returncode)。"""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
            timeout=timeout,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "git 命令超时", -1
    except FileNotFoundError:
        return "", "git 未安装或不在 PATH 中", -1
    except OSError as e:
        return "", f"执行 git 失败: {e}", -1


def get_current_branch() -> str:
    """获取当前分支名。"""
    stdout, _, rc = _git("rev-parse", "--abbrev-ref", "HEAD")
    return stdout if rc == 0 else ""


def get_remote_url(remote: str) -> str:
    """获取远程仓库 URL。"""
    stdout, _, rc = _git("remote", "get-url", remote)
    return stdout if rc == 0 else ""


def git_fetch(remote: str, branch: str) -> bool:
    """git fetch 远程，返回是否成功。"""
    stdout, stderr, rc = _git("fetch", remote, branch)
    if rc != 0:
        logger.warning("git fetch 失败: %s", stderr)
        return False
    return True


def count_behind(remote: str, branch: str) -> int:
    """获取落后远程的 commit 数。"""
    stdout, stderr, rc = _git("rev-list", "--count", f"HEAD..{remote}/{branch}")
    if rc == 0 and stdout.isdigit():
        return int(stdout)
    return 0


def has_local_changes() -> bool:
    """检查是否有未提交的本地更改。"""
    stdout, _, rc = _git("status", "--porcelain")
    if rc == 0 and stdout:
        return True
    return False


def git_pull(remote: str, branch: str, force: bool = False) -> tuple[bool, str]:
    """
    执行 git pull。

    Args:
        remote: 远程仓库名。
        branch: 目标分支。
        force: 是否强制拉取（丢弃本地更改）。

    Returns:
        (是否有更新, 消息字符串)
    """
    # 如有本地更改且非 force 模式，放弃
    if has_local_changes() and not force:
        return (
            False,
            "存在未提交的本地更改，请先 commit/stash 或使用「update force」强制拉取",
        )

    # fetch
    if not git_fetch(remote, branch):
        return False, "git fetch 失败，请检查网络连接"

    # 检查落后 commit 数
    behind = count_behind(remote, branch)
    if behind == 0:
        return False, "已经是最新"

    # force 模式下先 reset
    if force:
        _git("reset", "--hard", f"{remote}/{branch}")
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
def _restart_process() -> None:
    """替换当前进程以重启机器人。"""
    logger.info("正在重启机器人...")
    # 使用与启动时相同的 Python 解释器和参数
    args = [sys.executable, "-m", "nb_cli", "run"]
    os.execv(sys.executable, args)


async def restart_with_delay(delay: int = 3) -> None:
    """延迟后重启机器人，确保响应消息发送完毕。"""
    logger.info("将在 %d 秒后重启...", delay)
    await asyncio.sleep(delay)
    _restart_process()


# ── 消息发送 ──────────────────────────────────────────────────────
async def send_to_group(group_id: str, message: str) -> None:
    """向指定 QQ 群发送消息。"""
    try:
        bot = get_bot()
        await bot.call_api("send_group_msg", group_id=int(group_id), message=message)
    except Exception as e:
        logger.error("发送群消息失败 (group=%s): %s", group_id, e)


async def send_notification(message: str) -> None:
    """如果有配置通知群，发送通知。"""
    cfg = get_config()
    group = cfg["notify_group"]
    if group:
        await send_to_group(group, message)


# ── 核心检查逻辑 ──────────────────────────────────────────────────
async def run_pull(force: bool = False) -> str:
    """
    执行一次完整的 pull 检查流程。

    Returns:
        给用户的消息文本。
    """
    cfg = get_config()
    remote = cfg["remote"]
    branch = cfg["branch"] or get_current_branch() or "main"

    logger.info("检查仓库更新 (remote=%s, branch=%s, force=%s)", remote, branch, force)
    has_update, msg = git_pull(remote, branch, force=force)

    if has_update:
        # 异步触发延迟重启
        asyncio.ensure_future(restart_with_delay(delay=3))
        result = f"🔄 {msg}\n\n⚠️ 机器人将在 3 秒后自动重启以加载更新"
    else:
        result = f"✅ {msg}"

    return result


# ── 命令 ──────────────────────────────────────────────────────────
update_cmd = on_command("update", aliases={"pull"}, priority=20, block=True)


@update_cmd.handle()
async def handle_update(bot, event):
    """手动触发 git pull 并重启。"""
    cleanup = await reaction_cleanup(bot, event)

    # 解析参数
    raw_msg = event.get_plaintext() if hasattr(event, "get_plaintext") else str(event)
    args = raw_msg.strip().split()
    force = len(args) > 1 and args[1] == "force"

    try:
        msg = await run_pull(force=force)
        if cleanup:
            await cleanup()
        await update_cmd.finish(msg, at_sender=False)
    except Exception as e:
        logger.exception("update 命令异常")
        if cleanup:
            await cleanup()
        await update_cmd.finish(f"❌ 命令异常: {e}", at_sender=False)


# ── 定时任务 ──────────────────────────────────────────────────────
async def scheduled_pull():
    """定时任务：检查更新并推送通知。"""
    cfg = get_config()
    if not cfg["enabled"]:
        return

    logger.info("定时拉取检查：开始执行")
    try:
        remote = cfg["remote"]
        branch = cfg["branch"] or get_current_branch() or "main"
        has_update, msg = git_pull(remote, branch, force=False)

        if has_update:
            full_msg = f"🔄 自动更新: {msg}\n\n⚠️ 机器人将在 3 秒后重启"
            logger.info("定时拉取到更新，即将重启")
            # 通知群（如配置）
            await send_notification(full_msg)
            # 重启
            await restart_with_delay(delay=3)
        else:
            logger.info("定时拉取检查完成: %s", msg)
    except Exception as e:
        logger.exception("定时拉取检查异常: %s", e)
        await send_notification(f"❌ 自动拉取检查异常: {e}")


# ── 解析定时时间 ──────────────────────────────────────────────────
def _parse_time(time_str: str) -> tuple[int, int]:
    """解析 'HH:MM' 格式的时间字符串。"""
    parts = time_str.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return hour, minute


# ── 插件初始化 ────────────────────────────────────────────────────
_cfg = get_config()

if _cfg["enabled"]:
    _schedule_type = _cfg["schedule_type"]
    _branch = _cfg["branch"] or get_current_branch() or "main"

    logger.info(
        "自动拉取已启用: schedule=%s, interval=%dmin, time=%s, branch=%s",
        _schedule_type, _cfg["interval"], _cfg["check_time"], _branch,
    )

    # 定时模式（每天固定时间）
    if _schedule_type in ("cron", "both"):
        _hour, _minute = _parse_time(_cfg["check_time"])
        scheduler.add_job(
            scheduled_pull,
            "cron",
            hour=_hour,
            minute=_minute,
            id="auto_pull_cron",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("定时拉取已注册: 每天 %02d:%02d", _hour, _minute)

    # 间隔模式（每 N 分钟）
    if _schedule_type in ("interval", "both"):
        scheduler.add_job(
            scheduled_pull,
            "interval",
            minutes=_cfg["interval"],
            id="auto_pull_interval",
            replace_existing=True,
            misfire_grace_time=120,
        )
        logger.info("间隔拉取已注册: 每 %d 分钟", _cfg["interval"])

else:
    logger.info("自动拉取未启用（GIT_AUTO_PULL_ENABLED=false），仅支持手动 update 命令")

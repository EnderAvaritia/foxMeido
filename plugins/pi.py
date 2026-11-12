"""
pi.py - 调用 pi 命令行 AI agent（https://github.com/earendil-works/pi）

用法：
    pi <问题>       让 pi（完整 agent：可读写文件、执行 shell 命令）解决问题
                    未启用或未安装 pi 时静默忽略，不回复任何消息

按群持久记忆：每个群/私聊一个独立 session（--session-id），跨消息保留上下文。
权限说明：pi 以 agent 模式运行，具备文件读写与命令执行能力，安全风险较高。
         默认仅 NoneBot SUPERUSERS 可用；可用 PI_ALLOW_GROUPS / PI_ALLOW_USERS 开放。

配置（.env）：
    PI_ENABLED        是否启用（默认 true）
    PI_CLI            pi 可执行文件路径（默认 pi；Windows 若无法直接调用请指向 exe/wrapper）
    PI_MODEL          指定模型（可选，如 sonnet:high；留空用 pi 默认模型）
    PI_WORKDIR        pi 工作目录（默认项目根目录，agent 可读写该目录下的文件）
    PI_TIMEOUT        单次调用超时秒数（默认 300）
    PI_MAX_OUTPUT     返回文本最大字符数（默认 2000，超出截断）
    PI_APPROVE        是否信任项目本地配置/资源，等价 --approve（默认 true）
    PI_ALLOW_GROUPS   允许使用 pi 的群号，逗号分隔（可选；留空仅 SUPERUSERS）
    PI_ALLOW_USERS    允许使用 pi 的 QQ 号，逗号分隔（可选）

依赖：服务器需先安装 pi（Node ≥ 22.19）：
    npm install -g @earendil-works/pi-coding-agent
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import threading

from nonebot import get_driver, on_command
from nonebot.adapters import Message
from nonebot.log import logger
from nonebot.params import CommandArg

from plugins.env_utils import _env_bool, _read_dotenv
from plugins.message_reaction import extract_group_id, reaction_cleanup
from plugins.protocol import user_id

# 项目根目录：此文件位于 plugins/，往上级 1 层
_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 同一 session（群/私聊）串行化，避免并发写入同一 session 文件导致损坏
_pi_locks: dict[str, asyncio.Lock] = {}
_pi_locks_guard = threading.Lock()

pi_cmd = on_command("pi", priority=10, block=True)


def _get_lock(key: str) -> asyncio.Lock:
    """按会话维度取得 asyncio.Lock（惰性创建，避免并发写同一 session）。"""
    with _pi_locks_guard:
        lock = _pi_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _pi_locks[key] = lock
        return lock


def _parse_ids(raw: str) -> set[int]:
    """解析逗号/空格分隔的数字列表（群号 / QQ 号）。"""
    result: set[int] = set()
    for part in re.split(r"[,，\s]+", raw.strip()):
        part = part.strip()
        if part.lstrip("-").isdigit():
            result.add(int(part))
    return result


def _session_id(group_id: int | None, user_id: int) -> str:
    """生成 pi session id：群聊按群号，私聊按用户号（前缀保证以字母开头）。

    pi 要求 id 以字母或数字开头结尾，只允许字母/数字/``.``/``_``/``-``。
    """
    if group_id is not None:
        return f"g{abs(group_id)}"
    return f"u{abs(user_id)}"


def _authorize(group_id: int | None, user_id: int) -> str | None:
    """鉴权：返回 None 表示放行，否则返回拒绝提示文本。"""
    superusers = set(get_driver().config.superusers or ())
    if str(user_id) in superusers:
        return None

    allow_users = _parse_ids(_read_dotenv("PI_ALLOW_USERS"))
    if user_id in allow_users:
        return None

    allow_groups = _parse_ids(_read_dotenv("PI_ALLOW_GROUPS"))
    if group_id is not None and group_id in allow_groups:
        return None

    return (
        "⛔ pi 是完整 agent（可读写文件 / 执行命令），安全风险较高，当前未授权使用。\n"
        "管理员可在 .env 中配置 PI_ALLOW_GROUPS（群号）或 PI_ALLOW_USERS（QQ 号）开放，"
        "或把使用者加进 SUPERUSERS。"
    )


def _resolve_cli(cli: str) -> str:
    """解析 pi 可执行文件路径（兼容 PATH / 绝对路径；找不到时回退原值）。"""
    return shutil.which(cli) or cli


def _cli_available(cli: str) -> bool:
    """判断 pi 是否可用：PATH 中能找到，或传入的是存在的文件路径。"""
    return bool(shutil.which(cli)) or os.path.isfile(cli)


def _run_pi(
    question: str,
    session_id: str,
    cli: str,
    model: str,
    workdir: str,
    timeout: int,
    approve: bool,
    max_output: int,
) -> str:
    """在子进程中以 print 模式运行 pi，返回最终答复文本。

    使用 --print：pi 运行一次，结束后把最终 assistant 文本写到 stdout 并退出；
    过程日志 / 诊断走 stderr，不会被当成答案回传 QQ。
    """
    argv = [_resolve_cli(cli), "--print"]
    if model:
        argv += ["--model", model]
    argv += ["--session-id", session_id]
    if approve:
        argv += ["--approve"]
    # "--" 之后的内容视为消息本体，允许问题以 "-" 开头
    argv += ["--", question]

    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return (
            "❌ 找不到 pi 命令。请先在服务器安装：\n"
            "npm install -g @earendil-works/pi-coding-agent\n"
            "或设置 PI_CLI 指向可执行文件。"
        )
    except subprocess.TimeoutExpired:
        return f"⏱️ pi 执行超过 {timeout} 秒已超时。可调大 PI_TIMEOUT。"

    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        hint = err[-1500:] if len(err) > 1500 else err
        logger.warning(f"pi 退出码 {proc.returncode}，stderr: {err[:500]}")
        return (
            f"❌ pi 运行出错（退出码 {proc.returncode}）。\n"
            + (f"详情：{hint}" if hint else "（无错误输出）")
        )

    out = (proc.stdout or "").strip()
    if not out:
        return "（pi 没有返回文本）"
    if len(out) > max_output:
        return out[:max_output] + "…（输出过长已截断）"
    return out


@pi_cmd.handle()
async def handle_function(bot, event, args: Message = CommandArg()):
    cfg = {
        "cli": _read_dotenv("PI_CLI") or "pi",
        "model": _read_dotenv("PI_MODEL"),
        "workdir": _read_dotenv("PI_WORKDIR") or _PROJECT_ROOT,
        "timeout": int(_read_dotenv("PI_TIMEOUT") or "300"),
        "approve": _env_bool("PI_APPROVE", "true"),
        "max_output": int(_read_dotenv("PI_MAX_OUTPUT") or "2000"),
    }

    # 未启用或未安装 pi：静默忽略，不回复任何消息
    if not _env_bool("PI_ENABLED", "true"):
        logger.debug("pi 功能未启用（PI_ENABLED=false），忽略请求")
        return
    if not _cli_available(cfg["cli"]):
        logger.debug("pi 未安装或路径不可用（PI_CLI={}），忽略请求", cfg["cli"])
        return

    cleanup = await reaction_cleanup(bot, event)

    text = args.extract_plain_text().strip()
    if not text:
        if cleanup:
            await cleanup()
        await pi_cmd.finish("用法：pi <问题>，例：pi 帮我看下项目里有没有内存泄漏")

    group_id = extract_group_id(event)
    user_id_value = user_id(event)

    denied = _authorize(group_id, user_id_value)
    if denied:
        if cleanup:
            await cleanup()
        await pi_cmd.finish(denied)

    sid = _session_id(group_id, user_id_value)

    await pi_cmd.send("🧠 pi 处理中…（agent 模式，可能需要较久）")

    try:
        lock = _get_lock(sid)
        async with lock:
            result = await asyncio.to_thread(_run_pi, text, sid, **cfg)
    except Exception as e:  # noqa: BLE001 - 兜底避免 handler 崩溃导致无回音
        logger.exception("pi 调用异常")
        result = f"❌ pi 调用异常：{type(e).__name__}: {e}"

    if cleanup:
        await cleanup()
    await pi_cmd.finish(result)
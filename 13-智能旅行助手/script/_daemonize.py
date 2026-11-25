#!/usr/bin/env python3
"""以守护进程方式启动命令：双 fork + setsid + 重定向日志 + 写 pid 文件。

避免父 shell 退出（或 IDE 命令结束）时子进程被回收，适用于本机常驻服务。
"""
import argparse
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--pid", required=True)
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        sys.exit("缺少要执行的命令")

    os.chdir(args.cwd)

    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)

    log_fd = os.open(args.log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(log_fd, 1)
    os.dup2(log_fd, 2)
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)

    with open(args.pid, "w", encoding="utf-8") as fh:
        fh.write(f"{os.getpid()}\n")

    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()

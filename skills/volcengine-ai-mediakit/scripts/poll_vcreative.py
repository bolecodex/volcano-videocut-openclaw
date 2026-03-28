#!/usr/bin/env python3
"""
poll_vcreative.py — 重启编辑类任务轮询

用法:
  python <SKILL_DIR>/scripts/poll_vcreative.py <VCreativeId> [space_name]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import ensure_deps, load_credentials, build_service, get_space_name, poll_vcreative, out, bail

def main():
    if len(sys.argv) < 2:
        bail("用法: python <SKILL_DIR>/scripts/poll_vcreative.py <VCreativeId> [space_name]")
    vcreative_id = sys.argv[1]
    ensure_deps()
    ak, sk = load_credentials()
    client = build_service(ak, sk)
    space_name = get_space_name(argv_pos=2)
    result = poll_vcreative(client, vcreative_id, space_name)
    out(result)

if __name__ == "__main__":
    main()

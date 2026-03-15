#!/usr/bin/env python3
"""
xskill-ai HTTP API CLI wrapper.
Replaces MCP tool calls with direct HTTP requests.

Usage:
  python xskill_api.py generate --model MODEL --prompt PROMPT [--image_url URL] [--image_size SIZE] [--aspect_ratio RATIO] [--duration SEC] [--options JSON]
  python xskill_api.py get_result [--task_id ID] [--status STATUS] [--limit N]
  python xskill_api.py speak --action ACTION [--text TEXT] [--voice_id ID] [--prompt DESC] [--audio_url URL]
  python xskill_api.py search_models [--query Q] [--category CAT] [--capability CAP] [--model_id ID]
  python xskill_api.py parse_video --url URL
  python xskill_api.py transfer_url --url URL [--type TYPE]
  python xskill_api.py account [--action ACTION] [--package_id ID]
  python xskill_api.py guide [--query Q] [--skill_id ID] [--category CAT]
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error


def _load_dotenv():
    """Load .env from project root if env vars are not already set."""
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    env_path = os.path.normpath(env_path)
    if not os.path.isfile(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

API_URL = os.environ.get('XSKILL_MCP_URL', 'https://api.xskill.ai/api/v3/mcp-http')
API_KEY = os.environ.get('XSKILL_API_KEY', '')

session_id = None


def mcp_post(method, params=None, req_id=1):
    global session_id
    url = f'{API_URL}?api_key={API_KEY}' if API_KEY else API_URL

    is_notification = method.startswith('notifications/')
    payload = {'jsonrpc': '2.0', 'method': method, 'params': params or {}}
    if not is_notification:
        payload['id'] = req_id

    data = json.dumps(payload).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'xskill-cli/1.0',
    }
    if session_id:
        headers['Mcp-Session-Id'] = session_id

    req = urllib.request.Request(url, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            new_session = resp.headers.get('Mcp-Session-Id')
            if new_session:
                session_id = new_session
            if is_notification:
                return None
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(json.dumps({'error': f'HTTP {e.code}', 'detail': body}), file=sys.stderr)
        sys.exit(1)


def ensure_session():
    global session_id
    if session_id:
        return
    mcp_post('initialize', {
        'protocolVersion': '2024-11-05',
        'capabilities': {},
        'clientInfo': {'name': 'xskill-cli', 'version': '1.0.0'},
    }, req_id=0)
    mcp_post('notifications/initialized')


def call_tool(tool_name, arguments):
    ensure_session()
    result = mcp_post('tools/call', {'name': tool_name, 'arguments': arguments})
    if result and 'error' in result:
        print(json.dumps(result['error'], ensure_ascii=False, indent=2))
        sys.exit(1)
    if result and 'result' in result:
        content = result['result'].get('content', [])
        for item in content:
            if item.get('type') == 'text':
                try:
                    parsed = json.loads(item['text'])
                    print(json.dumps(parsed, ensure_ascii=False, indent=2))
                except (json.JSONDecodeError, TypeError):
                    print(item['text'])
            else:
                print(json.dumps(item, ensure_ascii=False, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description='xskill-ai API CLI')
    subparsers = parser.add_subparsers(dest='command')

    p_gen = subparsers.add_parser('generate')
    p_gen.add_argument('--model', required=True)
    p_gen.add_argument('--prompt', required=True)
    p_gen.add_argument('--image_url')
    p_gen.add_argument('--image_size')
    p_gen.add_argument('--aspect_ratio')
    p_gen.add_argument('--duration')
    p_gen.add_argument('--options', help='JSON string of extra options')

    p_res = subparsers.add_parser('get_result')
    p_res.add_argument('--task_id')
    p_res.add_argument('--status', default='all')
    p_res.add_argument('--limit', type=int, default=10)

    p_speak = subparsers.add_parser('speak')
    p_speak.add_argument('--action', default='synthesize')
    p_speak.add_argument('--text')
    p_speak.add_argument('--voice_id')
    p_speak.add_argument('--prompt')
    p_speak.add_argument('--audio_url')
    p_speak.add_argument('--model', default='speech-2.8-hd')
    p_speak.add_argument('--speed', type=float, default=1.0)

    p_search = subparsers.add_parser('search_models')
    p_search.add_argument('--query')
    p_search.add_argument('--category')
    p_search.add_argument('--capability')
    p_search.add_argument('--model_id')

    p_parse = subparsers.add_parser('parse_video')
    p_parse.add_argument('--url', required=True)

    p_transfer = subparsers.add_parser('transfer_url')
    p_transfer.add_argument('--url', required=True)
    p_transfer.add_argument('--type', default='image')

    p_account = subparsers.add_parser('account')
    p_account.add_argument('--action', default='balance')
    p_account.add_argument('--package_id', type=int)

    p_guide = subparsers.add_parser('guide')
    p_guide.add_argument('--query')
    p_guide.add_argument('--skill_id')
    p_guide.add_argument('--category')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    arguments = {}
    skip_keys = {'command'}

    for k, v in vars(args).items():
        if k in skip_keys or v is None:
            continue
        if k == 'options' and v:
            arguments[k] = json.loads(v)
        else:
            arguments[k] = v

    call_tool(args.command, arguments)


if __name__ == '__main__':
    main()

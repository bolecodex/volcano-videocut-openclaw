#!/usr/bin/env python3
"""
vod_common.py — 公共基础模块（被各工具脚本 import）

提供：
  - ensure_deps()       依赖检测与自动安装
  - load_credentials()  AK/SK 读取（环境变量 → .env 文件）
  - VodClient           VodService 封装（替代 monkey-patch，提供 skill_get/skill_post/state 管理）
  - build_service()     构建 VodClient 实例
  - get_space_name()    space_name 读取（命令行参数 → VOD_SPACE_NAME 环境变量）
  - init_and_parse()    统一入口：解析 JSON 参数 + 初始化 VodClient
  - log() / bail()      日志与错误输出
  - get_play_url()      通过 FileName 获取播放链接（完整 CDN 域名 + TypeA 签名逻辑）
  - build_media_input() 构建 SkillStartExecution 的 Input 字段
  - fmt_src()           为 vid/directurl 添加协议前缀
  - poll_vcreative()    编辑类任务轮询（SkillGetVCreativeTaskResult）
  - poll_media()        媒体类任务轮询（SkillGetExecution）
  - submit_vcreative()  提交编辑类任务并轮询
  - submit_media()      提交媒体类任务并轮询
"""

import sys
import os
import json
import time
import hashlib
import secrets
import subprocess
import importlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote


# ══════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════

def log(msg: str):
    print(f"[vod] {msg}", file=sys.stderr, flush=True)

def bail(msg: str):
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(1)

def out(data):
    print(json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data)


# ══════════════════════════════════════════════════════
# 依赖检测与自动安装
# ══════════════════════════════════════════════════════

def ensure_deps():
    needs = []
    try:
        from volcengine.vod.VodService import VodService  # noqa
    except (ImportError, ModuleNotFoundError):
        needs.append("volcengine")
    try:
        import dotenv  # noqa
    except (ImportError, ModuleNotFoundError):
        needs.append("python-dotenv")

    if not needs:
        return

    log(f"缺少依赖 {needs}，正在自动安装...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--user", "--quiet"] + needs,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        bail(f"自动安装失败，请手动执行：pip install {' '.join(needs)}")

    import site
    importlib.invalidate_caches()
    user_site = site.getusersitepackages() if callable(getattr(site, "getusersitepackages", None)) else ""
    if user_site and user_site not in sys.path:
        sys.path.insert(0, user_site)
    log("依赖安装完成。")


# ══════════════════════════════════════════════════════
# AK/SK 读取
# ══════════════════════════════════════════════════════

def load_credentials():
    """
    读取顺序：
      1. 依次尝试 cwd/.env → 脚本目录/.env → ~/.env，用 dotenv.load_dotenv() 加载
         （override=False 保证系统环境变量优先，不被 .env 覆盖）
      2. 从 os.environ 读取 AK/SK
    dotenv 会把 .env 中所有变量注入 os.environ，VOLCENGINE_REGION、
    VOD_SPACE_NAME、VOD_POLL_INTERVAL 等配置也因此一并生效。
    """
    from dotenv import load_dotenv

    ak_keys = ["VOLCENGINE_ACCESS_KEY_ID", "VOLC_ACCESSKEY", "VOLCENGINE_ACCESS_KEY"]
    sk_keys = ["VOLCENGINE_ACCESS_KEY_SECRET", "VOLC_SECRETKEY", "VOLCENGINE_SECRET_KEY"]

    # 按优先级逐级尝试加载 .env（override=False：系统环境变量更优先）
    for base in [os.getcwd(), os.path.dirname(os.path.abspath(__file__)), os.path.expanduser("~")]:
        env_path = os.path.join(base, ".env")
        if os.path.isfile(env_path):
            load_dotenv(env_path, override=False)
            log(f"已加载 .env：{env_path}")
            break  # 只加载第一个找到的 .env，与原逻辑一致

    ak = next((os.environ[k] for k in ak_keys if k in os.environ), None)
    sk = next((os.environ[k] for k in sk_keys if k in os.environ), None)

    if ak and sk:
        return ak, sk
    bail("未找到 AK/SK。请设置环境变量 VOLCENGINE_ACCESS_KEY_ID / VOLCENGINE_ACCESS_KEY_SECRET，或放置 .env 文件。")


def get_space_name(argv_pos: int = 3) -> str:
    """
    space_name 读取优先级：
      1. 命令行第 argv_pos 个参数（默认第 4 个，即 sys.argv[3]）
      2. VOD_SPACE_NAME 环境变量
    """
    if len(sys.argv) > argv_pos:
        return sys.argv[argv_pos]
    sp = os.environ.get("VOD_SPACE_NAME", "")
    if not sp:
        bail("未指定 space_name：请通过命令行第三个参数或环境变量 VOD_SPACE_NAME 提供。")
    return sp


# ══════════════════════════════════════════════════════
# 统一入口：JSON 参数解析 + VodClient 初始化
# ══════════════════════════════════════════════════════

def init_and_parse(argv_pos: int = 1, sp_pos: int = None):
    """
    统一前置流程，返回 (client, space_name, args_dict)。

    - argv_pos:  sys.argv 中 JSON 参数的位置（默认 1）
    - sp_pos:    sys.argv 中 space_name 的位置（默认 argv_pos + 1，
                 即 JSON 后面一个；未传则从环境变量读取）
    """
    if len(sys.argv) < argv_pos + 1:
        bail(f"用法: python {sys.argv[0]} '<json_args>'")

    raw = sys.argv[argv_pos]
    # 支持 @file.json 语法：从文件读取 JSON，避免 shell 转义问题
    if raw.startswith("@"):
        fpath = raw[1:]
        if not os.path.isfile(fpath):
            bail(f"参数文件不存在：{fpath}")
        with open(fpath, "r", encoding="utf-8") as f:
            raw = f.read()

    try:
        args = json.loads(raw)
    except json.JSONDecodeError as e:
        bail(f"json_args 解析失败: {e}")

    ensure_deps()
    ak, sk = load_credentials()
    client = build_service(ak, sk)
    sp = get_space_name(argv_pos=sp_pos if sp_pos is not None else argv_pos + 1)
    return client, sp, args


# ══════════════════════════════════════════════════════
# VodClient — VodService 封装类（替代 monkey-patch）
# ══════════════════════════════════════════════════════

class VodClient:
    """
    封装 VodService，提供：
      - skill_get / skill_post：带空响应检测的 API 调用
      - set_state / get_state：CDN 域名与 storage_config 缓存
      - svc 属性：底层 VodService 实例（供 upload_media 等直接调用）
    """

    def __init__(self, svc):
        self.svc = svc
        self._state = {}

    def set_state(self, state: dict):
        self._state = {**self._state, **state}

    def get_state(self) -> dict:
        return self._state

    def skill_get(self, action, params=None, body=None):
        res = self.svc.get(action, params or {}, body or 0)
        if res == "" or res is None:
            raise RuntimeError(f"{action}: empty response")
        if isinstance(res, str):
            return json.loads(res)
        return json.loads(json.dumps(res))

    def skill_post(self, action, params=None, body=None):
        res = self.svc.json(action, params or {}, body or {})
        if res == "" or res is None:
            raise RuntimeError(f"{action}: empty response")
        if isinstance(res, str):
            return json.loads(res)
        return json.loads(json.dumps(res))


def build_service(ak: str, sk: str) -> VodClient:
    """
    构建 VodClient。
    - region: 默认 cn-north-1，VOLCENGINE_REGION 可覆盖
    - 注入 x-tt-skill: volc header
    - VOLCENGINE_HOST 可覆盖接入域名
    """
    from volcengine.vod.VodService import VodService
    from volcengine.ApiInfo import ApiInfo

    ## 接口定义
    api_info = {
        "SkillAsyncVCreativeTask": ApiInfo(
            "POST", "/", {"Action": "AsyncVCreativeTask", "Version": "2018-01-01"}, {}, {}
        ),
        "SkillGetVCreativeTaskResult": ApiInfo(
            "GET",
            "/",
            {"Action": "GetVCreativeTaskResult", "Version": "2018-01-01"},
            {},
            {},
        ),
        "SkillGetVideoPlayInfo": ApiInfo("GET", "/", {"Action": "GetVideoPlayInfo", "Version": "2018-01-01"}, {}, {}),
        "SkillUpdateMediaPublishStatus": ApiInfo("POST", "/", {"Action": "UpdateMediaPublishStatus", "Version": "2020-08-01"}, {}, {}),
        "SkillStartExecution": ApiInfo("POST", "/", {"Action": "StartExecution", "Version": "2025-01-01"}, {}, {}),
        "SkillGetExecution": ApiInfo("GET", "/", {"Action": "GetExecution", "Version": "2025-01-01"}, {}, {}),
        "SkillQueryUploadTaskInfo": ApiInfo("GET", "/", {"Action": "QueryUploadTaskInfo", "Version": "2020-08-01"}, {}, {}),
        "SkillListDomain": ApiInfo("GET", "/", {"Action": "ListDomain", "Version": "2023-01-01"}, {}, {}),
        "SkillDescribeDomainConfig": ApiInfo("GET", "/", {"Action": "DescribeDomainConfig", "Version": "2023-07-01"}, {}, {}),
        "SkillGetStorageConfig": ApiInfo("GET", "/", {"Action": "GetStorageConfig", "Version": "2023-07-01"}, {}, {}),
    }

    region = os.environ.get("VOLCENGINE_REGION", "cn-north-1")
    svc = VodService(region=region)
    svc.set_ak(ak)
    svc.set_sk(sk)
    # volcengine SDK 只认识内置 api_info，这里把 Skill 脚本需要的 Action 注册进去
    svc.api_info.update(api_info)
    svc.service_info.header["x-tt-skill"] = "volc"

    custom_host = os.environ.get("VOLCENGINE_HOST")
    if custom_host:
        svc.set_host(custom_host)

    return VodClient(svc)


# ══════════════════════════════════════════════════════
# 播放 URL 内部辅助函数（对齐 video_play.py）
# ══════════════════════════════════════════════════════

def _random_string(length: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _encode_path_str(s: str = "") -> str:
    return quote(s, safe="-_.~$&+,/:;=@")


def _encode_rfc3986_uri_component(s: str) -> str:
    return quote(s, safe=":/?&=%-_.~")


def _is_https_available(certificate: dict) -> bool:
    if certificate and certificate.get("HttpsStatus") == "enable":
        exp_raw = certificate.get("ExpiredAt")
        try:
            if isinstance(exp_raw, (int, float)):
                exp = datetime.fromtimestamp(float(exp_raw), tz=timezone.utc)
            elif isinstance(exp_raw, str):
                v = exp_raw.replace("Z", "+00:00") if "Z" in exp_raw else exp_raw
                exp = datetime.fromisoformat(v)
            else:
                return False
            return exp > datetime.now(timezone.utc)
        except Exception:
            return False
    return False


def _get_domain_config(client: VodClient, domain: str, space_name: str) -> dict:
    """
    查询域名鉴权配置（SkillDescribeDomainConfig）。
    只返回 TypeA 鉴权信息；无签名规则时返回空 dict。
    对齐 video_play.py _get_Domain_config。
    """
    try:
        detail = client.skill_get(
            "SkillDescribeDomainConfig",
            {"SpaceName": space_name, "Domain": domain, "DomainType": "play"},
        )
        if isinstance(detail, str):
            detail = json.loads(detail)
        result      = detail.get("Result", {})
        cdn_config  = result.get("Config") or {}
        auth_ctrl   = cdn_config.get("SignedUrlAuthControl") or {}
        rules       = (auth_ctrl.get("SignedUrlAuth") or {}).get("SignedUrlAuthRules", [])
        if not rules:
            return {}
        action      = rules[0].get("SignedUrlAuthAction", {})
        base_domain = result.get("Domain", {})
        status      = "enable" if base_domain.get("ConfigStatus") == "online" else base_domain.get("ConfigStatus", "")
        return {
            "AuthType": action.get("URLAuthType"),
            "AuthKey":  action.get("MasterSecretKey") or action.get("BackupSecretKey") or "",
            "Status":   status,
            "Domain":   base_domain.get("Domain", ""),
        }
    except Exception as e:
        log(f"_get_domain_config({domain}) 失败: {e}")
        return {}


def _get_available_domains(client: VodClient, space_name: str) -> list:
    """
    获取空间下可用的 CDN 播放域名列表（含 TypeA 鉴权信息），带缓存。
    注意：缓存仅在同一进程生命周期内有效（脚本模式下每次执行都是新进程，
    缓存不跨进程持久化；仅在 daemon 模式下避免重复请求）。
    对齐 video_play.py _get_available_domain。
    """
    state = client.get_state()
    cached = (state.get("available_domains") or {}).get(space_name)
    if cached:
        return cached

    offset, total, domain_list = 0, 1, []
    while offset < total:
        try:
            data = client.skill_get(
                "SkillListDomain",
                {"SpaceName": space_name, "SourceStationType": 1, "DomainType": "play", "Offset": offset},
            )
            if isinstance(data, str):
                data = json.loads(data)
            offset   = int(data.get("Offset", 0))
            total    = int(data.get("Total", 0))
            result   = data.get("Result", {})
            instances = ((result.get("PlayInstanceInfo") or {}).get("ByteInstances") or [])
            for item in instances:
                for d in (item.get("Domains") or []):
                    d2 = dict(d)
                    d2["SourceStationType"] = 1
                    d2["DomainType"]        = "play"
                    domain_list.append(d2)
        except Exception as e:
            log(f"SkillListDomain 失败: {e}")
            break

    # 只保留 CDN 状态为 enable 的域名，并查询其鉴权配置
    domain_list = [d for d in domain_list if d.get("CdnStatus") == "enable"]
    enriched = []
    for d in domain_list:
        auth_info = _get_domain_config(client, d.get("Domain", ""), space_name)
        d2 = dict(d)
        d2["AuthInfo"] = auth_info
        enriched.append(d2)

    # 只保留无鉴权或 TypeA 鉴权的域名
    available = [
        d for d in enriched
        if not d.get("AuthInfo") or (d.get("AuthInfo") or {}).get("AuthType") == "typea"
    ]
    client.set_state({"available_domains": {space_name: available}})
    return available


def _gen_url(domain_obj: dict, file_name: str, expired_minutes: int = 60) -> str:
    """
    用 CDN 域名生成播放 URL，支持 TypeA 签名。
    对齐 video_play.py _gen_url。
    """
    is_https   = _is_https_available(domain_obj.get("Certificate"))
    scheme     = "https" if is_https else "http"
    file_path  = f"/{file_name}"
    auth_info  = domain_obj.get("AuthInfo") or {}

    if auth_info.get("AuthType") == "typea":
        expire_ts = int(
            (datetime.now(timezone.utc) + timedelta(minutes=expired_minutes)).timestamp()
        )
        rand_str  = _random_string(16)
        key       = auth_info.get("AuthKey") or ""
        md5_input = f"{_encode_path_str(file_path)}-{expire_ts}-{rand_str}-0-{key}".encode()
        md5_str   = hashlib.md5(md5_input).hexdigest()
        url       = f"{scheme}://{domain_obj.get('Domain')}{file_path}?auth_key={expire_ts}-{rand_str}-0-{md5_str}"
    else:
        url = f"{scheme}://{domain_obj.get('Domain')}{file_path}"

    return _encode_rfc3986_uri_component(url)


def _gen_wild_url(storage_config: dict, file_name: str) -> str:
    """
    降级方案：通过 StorageHost 拼接 URL，支持 cdn_typea 签名。
    对齐 video_play.py _gen_wild_url。
    """
    file_path = f"/{file_name}"
    conf      = storage_config.get("StorageUrlAuthConfig") or {}

    if storage_config.get("StorageType") == "volc" and conf.get("Type") == "cdn_typea" and conf.get("Status") == "enable":
        type_a    = conf.get("TypeAConfig") or {}
        expire_s  = int(type_a.get("ExpireTime") or 0)
        expire_ts = int((datetime.now(timezone.utc) + timedelta(seconds=expire_s)).timestamp())
        rand_str  = _random_string(16)
        key       = type_a.get("MasterKey") or type_a.get("BackupKey") or ""
        md5_input = f"{_encode_path_str(file_path)}-{expire_ts}-{rand_str}-0-{key}".encode()
        md5_str   = hashlib.md5(md5_input).hexdigest()
        sig_arg   = type_a.get("SignatureArgs") or "auth_key"
        signed    = (
            f"{storage_config.get('StorageHost')}{file_path}"
            f"?{sig_arg}={expire_ts}-{rand_str}-0-{md5_str}&preview=1"
        )
        return _encode_rfc3986_uri_component(signed)

    elif storage_config.get("StorageType") == "volc" and conf.get("Status") == "disable":
        signed = f"{storage_config.get('StorageHost')}{file_path}?preview=1"
        return _encode_rfc3986_uri_component(signed)

    return ""


def _get_storage_config(client: VodClient, space_name: str) -> dict:
    """调用 SkillGetStorageConfig，结果带缓存。"""
    state  = client.get_state()
    cached = (state.get("storage_config") or {}).get(space_name)
    if cached:
        return cached
    try:
        raw = client.skill_get("SkillGetStorageConfig", {"SpaceName": space_name})
        if isinstance(raw, str):
            raw = json.loads(raw)
        cfg = raw.get("Result") or {}
        client.set_state({"storage_config": {space_name: cfg}})
        return cfg
    except Exception as e:
        log(f"SkillGetStorageConfig({space_name}) 失败: {e}")
        return {}


def get_play_url(client: VodClient, space_name: str, file_name: str, expired_minutes: int = 60) -> str:
    """
    通过 FileName 获取播放链接。
    优先级（对齐 video_play.py get_play_directurl）：
      1. SkillListDomain → CdnStatus=enable 的域名 → TypeA 签名 URL
      2. 降级：SkillGetStorageConfig → _gen_wild_url（支持 cdn_typea）
    """
    if not file_name:
        return ""
    try:
        available = _get_available_domains(client, space_name)
        if available:
            return _gen_url(available[0], file_name, expired_minutes)
        # 降级
        cfg = _get_storage_config(client, space_name)
        return _gen_wild_url(cfg, file_name)
    except Exception as e:
        log(f"get_play_url 失败（{file_name}）: {e}")
        return ""


# ══════════════════════════════════════════════════════
# 格式化工具
# ══════════════════════════════════════════════════════

def fmt_src(type_: str, source: str) -> str:
    """为 vid/directurl 类型自动添加协议前缀（与 _format_source 逻辑一致）"""
    if not source:
        return source
    if source.startswith(("vid://", "directurl://", "http://", "https://")):
        return source
    if type_ == "vid":
        return f"vid://{source}"
    if type_ == "directurl":
        return f"directurl://{source}"
    return source


def build_media_input(type_: str, source: str, space_name: str) -> dict:
    """
    构建 SkillStartExecution 的 Input 字段。
    对齐 transcode.py _build_media_input：
      Vid 模式：   {"Type": "Vid",       "Vid": "xxx"}
      DirectUrl：  {"Type": "DirectUrl", "DirectUrl": {"FileName": "xxx", "SpaceName": "yyy"}}
    """
    if type_ not in ("Vid", "DirectUrl"):
        bail(f"type 必须为 Vid 或 DirectUrl，得到：{type_!r}")
    if not source:
        bail("media source 不能为空")
    if not space_name:
        bail("space_name 不能为空")
    if type_ == "Vid":
        return {"Type": "Vid", "Vid": source}
    return {"Type": "DirectUrl", "DirectUrl": {"FileName": source, "SpaceName": space_name}}


def _handle_transcode_data(client: VodClient, data: dict, space_name: str) -> dict:
    """
    从 enhance 类任务输出解析 FileId/DirectUrl/Url。
    对齐 transcode.py handle_transcode_data。
    """
    file_id   = data.get("FileId")
    store_uri = data.get("StoreUri", "")
    file_name = ""
    if store_uri and isinstance(store_uri, str):
        parsed   = urlparse(store_uri)
        # 对齐旧逻辑：去掉路径开头的 '/'，保留其余目录结构
        parts    = parsed.path.split('/')[1:]
        file_name = '/'.join(parts)
    return {
        "FileId":    file_id,
        "DirectUrl": file_name,
        "Url":       get_play_url(client, space_name, file_name),
    }


# ══════════════════════════════════════════════════════
# 轮询配置
# ══════════════════════════════════════════════════════

POLL_INTERVAL = float(os.environ.get("VOD_POLL_INTERVAL", "5"))
POLL_MAX      = int(os.environ.get("VOD_POLL_MAX", "360"))   # 360×5s = 1800 秒 = 30 分钟


# ══════════════════════════════════════════════════════
# 编辑类轮询（VCreativeId → SkillGetVCreativeTaskResult）
# 对齐 skill_server.py get_play_video_info（含 PublishStatus 检查）
# ══════════════════════════════════════════════════════

def _ensure_published(client: VodClient, vid: str, space_name: str) -> str:
    """
    确保视频已发布，返回播放 URL。
    对齐 skill_server.py get_play_video_info：
      - 若 PublishStatus != 'Published'，先调 SkillUpdateMediaPublishStatus 发布，
        再以 OutputType='Origin' 重取 URL。
    """
    def _fetch(output_type: str) -> dict:
        raw = client.skill_get("SkillGetVideoPlayInfo", {
            "Space": space_name, "Vid": vid,
            "DataType": 0, "OutputType": output_type,
        })
        if isinstance(raw, str):
            raw = json.loads(raw)
        result          = raw.get("Result", {})
        video_detail    = result.get("VideoDetail", {})
        detail_info     = video_detail.get("VideoDetailInfo", {})
        play_info       = detail_info.get("PlayInfo", {})
        publish_status  = detail_info.get("PublishStatus", "")
        url             = play_info.get("MainPlayURL") or play_info.get("BackupPlayUrl", "")
        return {"url": url, "publish_status": publish_status}

    info = _fetch("CDN")
    if info["publish_status"] == "Published":
        url = info["url"]
        # CDN URL 为空时降级 Origin
        if not url:
            info2 = _fetch("Origin")
            url   = info2["url"]
        return url

    # 未发布 → 先发布再取 Origin URL
    try:
        client.skill_post("SkillUpdateMediaPublishStatus", {}, json.dumps({
            "Vid": vid, "Status": "Published",
        }))
    except Exception as e:
        log(f"SkillUpdateMediaPublishStatus 失败: {e}")
    info2 = _fetch("Origin")
    return info2["url"]


def poll_vcreative(client: VodClient, vcreative_id: str, space_name: str) -> dict:
    """
    轮询编辑类任务，终态：Status == "success" 或 "failed_run"。
    超时后返回含 resume_hint 字段，供用户重启轮询。
    """
    for i in range(1, POLL_MAX + 1):
        log(f"轮询编辑任务 [{i}/{POLL_MAX}] VCreativeId={vcreative_id}")
        raw    = client.skill_get("SkillGetVCreativeTaskResult", {"VCreativeId": vcreative_id})
        result = raw.get("Result", raw)
        status = result.get("Status", "")

        if status == "success":
            output_json = result.get("OutputJson", {})
            if isinstance(output_json, str):
                try:
                    output_json = json.loads(output_json)
                except Exception:
                    output_json = {}
            vid      = output_json.get("vid", "")
            play_url = ""
            if vid and space_name:
                try:
                    play_url = _ensure_published(client, vid, space_name)
                except Exception as e:
                    log(f"获取播放链接失败: {e}")
            return {
                "Status":     "success",
                "OutputJson": {
                    "vid":        vid,
                    "url":        play_url,
                    "resolution": output_json.get("resolution"),
                    "duration":   output_json.get("duration"),
                    "filename":   output_json.get("filename"),
                },
            }

        if status == "failed_run":
            return {"Status": "failed_run", "detail": result}

        time.sleep(POLL_INTERVAL)

    return {
        "error": f"轮询超时（{POLL_MAX} 次 × {POLL_INTERVAL}s），任务仍在处理中",
        "resume_hint": {
            "description": "任务尚未完成，可用以下命令重启轮询",
            "command":     f"python <SKILL_DIR>/scripts/poll_vcreative.py '{vcreative_id}' {space_name}",
        },
    }


# ══════════════════════════════════════════════════════
# 媒体类轮询（RunId → SkillGetExecution）
# 对齐 transcode.py _get_media_execution_task_result
# ══════════════════════════════════════════════════════

def poll_media(client: VodClient, task_type: str, run_id: str, space_name: str) -> dict:
    """
    轮询媒体处理任务，完整状态机（对齐官方 GetExecution 五种状态）：

      ""           → 刚提交尚无状态，继续等待
      PendingStart → 任务排队中，继续等待
      Running      → 任务执行中，继续等待
      Success      → 终态成功，解析产物返回
      Failed       → 终态失败，返回错误信息（附 resume_hint 供重试）
      Terminated   → 任务被终止，返回错误（不建议重启轮询）

    产物解析结构对齐 transcode.py _get_media_execution_task_result。
    """
    PENDING_STATUSES  = {"", "PendingStart", "Running"}
    TERMINAL_FAIL     = {"Failed", "Terminated"}
    enhance_types     = {"enhanceVideo", "videSuperResolution", "videoInterlacing", "audioNoiseReduction"}

    for i in range(1, POLL_MAX + 1):
        log(f"轮询媒体任务 [{i}/{POLL_MAX}] type={task_type} RunId={run_id} ...")
        raw = client.skill_get("SkillGetExecution", {"RunId": run_id})
        if isinstance(raw, str):
            raw = json.loads(raw)
        result = raw.get("Result", raw)
        status = result.get("Status", "")
        sp     = result.get("Meta", {}).get("SpaceName", space_name)
        code   = result.get("Code", "")

        # ── 进行中：继续等待 ──────────────────────────────────────
        if status in PENDING_STATUSES:
            log(f"  状态={status!r}，等待 {POLL_INTERVAL}s ...")
            time.sleep(POLL_INTERVAL)
            continue

        # ── 终态失败 ──────────────────────────────────────────────
        if status in TERMINAL_FAIL:
            ret = {
                "Status":    status,
                "Code":      code,
                "SpaceName": sp,
            }
            # Failed 可能可重试；Terminated 是主动终止，不建议重启
            if status == "Failed":
                ret["resume_hint"] = {
                    "description": "任务执行失败，可检查参数后重新提交，或用以下命令重启轮询",
                    "command":     f"python <SKILL_DIR>/scripts/poll_media.py '{task_type}' '{run_id}' {sp}",
                }
            else:  # Terminated
                ret["note"] = "任务已被终止，请重新提交任务"
            return ret

        # ── 终态成功 ──────────────────────────────────────────────
        if status == "Success":
            output     = result.get("Output", {}).get("Task", {})
            video_urls = []
            audio_urls = []
            texts      = []

            if task_type in enhance_types:
                video_urls.append(
                    _handle_transcode_data(client, output.get("Enhance", {}), sp)
                )

            elif task_type == "voiceSeparation":
                audio_extract = output.get("AudioExtract", {})
                voice_f       = audio_extract.get("Voice", {})
                bg_f          = audio_extract.get("Background", {})
                v_name        = voice_f.get("FileName", "")
                bg_name       = bg_f.get("FileName", "")
                audio_urls.append({
                    "DirectUrl": v_name,
                    "Vid":       voice_f.get("Vid", ""),
                    "Type":      "voice",
                    "Url":       get_play_url(client, sp, v_name),
                })
                audio_urls.append({
                    "DirectUrl": bg_name,
                    "Vid":       bg_f.get("Vid", ""),
                    "Type":      "background",
                    "Url":       get_play_url(client, sp, bg_name),
                })

            # Texts 字段对齐 transcode.py（OCR/ASR 任务路径，当前工具集不触发）
            return {
                "Status":    "Success",
                "Code":      code,
                "SpaceName": sp,
                "VideoUrls": video_urls,
                "AudioUrls": audio_urls,
                "Texts":     texts,
            }

        # ── 未知状态（防御）：记录日志后继续等待 ─────────────────
        log(f"  未知状态={status!r}，继续等待 ...")
        time.sleep(POLL_INTERVAL)

    # ── 轮询超时 ──────────────────────────────────────────────────
    return {
        "error": f"轮询超时（{POLL_MAX} 次 × {POLL_INTERVAL}s），任务仍在处理中",
        "resume_hint": {
            "description": "任务尚未完成，可用以下命令重启轮询",
            "command":     f"python <SKILL_DIR>/scripts/poll_media.py '{task_type}' '{run_id}' {sp}",
        },
    }


# ══════════════════════════════════════════════════════
# 一步提交 + 轮询
# ══════════════════════════════════════════════════════

def submit_vcreative(client: VodClient, workflow_id: str, param_obj: dict, space_name: str) -> dict:
    """提交 SkillAsyncVCreativeTask，解析 VCreativeId，自动轮询到终态。"""
    payload = {
        "ParamObj":   param_obj,
        "Uploader":   space_name,
        "WorkflowId": workflow_id,
    }
    raw = client.skill_post("SkillAsyncVCreativeTask", {}, json.dumps(payload))
    if isinstance(raw, str):
        raw = json.loads(raw)

    result    = raw.get("Result", {})
    base_resp = result.get("BaseResp", {})
    sc        = base_resp.get("StatusCode", 0)
    if sc != 0:
        bail(f"提交任务失败：StatusCode={sc} msg={base_resp.get('StatusMessage', '')}")

    vcreative_id = result.get("VCreativeId", "")
    if not vcreative_id:
        bail(f"提交任务未返回 VCreativeId，原始响应：{json.dumps(raw)}")

    log(f"任务已提交，VCreativeId={vcreative_id}，开始轮询...")
    return poll_vcreative(client, vcreative_id, space_name)


def submit_media(client: VodClient, params: dict, task_type: str, space_name: str) -> dict:
    """提交 SkillStartExecution，解析 RunId，自动轮询到终态。"""
    raw = client.skill_post("SkillStartExecution", {}, json.dumps(params))
    if isinstance(raw, str):
        raw = json.loads(raw)

    result = raw.get("Result", raw)
    run_id = result.get("RunId", "")
    if not run_id:
        bail(f"提交任务未返回 RunId，原始响应：{json.dumps(raw)}")

    log(f"任务已提交，RunId={run_id}，开始轮询...")
    return poll_media(client, task_type, run_id, space_name)

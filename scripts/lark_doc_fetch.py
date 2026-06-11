#!/usr/bin/env python3
"""Lark international (larksuite.com) document fetcher using app tenant_access_token.
Resolves wiki/docx/sheet URLs and returns text + structural signals (board/table/image).
Reads app_id/app_secret from a .env file. Never prints secrets."""
import json, urllib.request, urllib.parse, re, sys, time, os
from collections import Counter

ENV = ".env"
ENV_CANDIDATES = [
    ".env.local",
    "/Users/gabriel/Downloads/weexpr/eff/.env",
]
BASE = "https://open.larksuite.com"


def _read_env_file(env_path):
    c = {}
    for line in open(env_path):
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            c[k.strip().lower()] = v.strip().strip('"').strip("'")
    return c


def _has_lark_keys(env_path):
    if not os.path.exists(env_path):
        return False
    creds = _read_env_file(env_path)
    return bool(creds.get('app_id') and creds.get('app_secret'))


def resolve_env_path(env_path=None):
    requested_path = env_path or ENV
    requested = os.path.expanduser(requested_path)
    if _has_lark_keys(requested):
        return requested
    if requested_path not in (".env", ".env.local") and os.path.exists(requested):
        return requested
    for candidate in ENV_CANDIDATES:
        expanded = os.path.expanduser(candidate)
        if _has_lark_keys(expanded):
            return expanded
    return requested


def load_creds(env_path=None):
    env_path = resolve_env_path(env_path or ENV)
    c = _read_env_file(env_path)
    return c.get('app_id'), c.get('app_secret')

_tok = {'v': None, 'exp': 0}
def token():
    if _tok['v'] and time.time() < _tok['exp']:
        return _tok['v']
    app_id, app_secret = load_creds()
    req = urllib.request.Request(BASE+"/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id":app_id,"app_secret":app_secret}).encode(),
        headers={'Content-Type':'application/json'})
    r = json.load(urllib.request.urlopen(req, timeout=30))
    if r.get('code') != 0:
        raise SystemExit(f"auth failed: {r.get('msg')}")
    _tok['v'] = r['tenant_access_token']; _tok['exp'] = time.time() + r.get('expire',7200) - 120
    return _tok['v']

def api_get(path, params=None):
    qs = ('?'+urllib.parse.urlencode(params)) if params else ''
    req = urllib.request.Request(BASE+path+qs, headers={'Authorization':'Bearer '+token()})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8','replace'))

URL_RE = re.compile(r'https?://[\w.-]*larksuite\.com/(wiki|docx|docs|sheets|base|file|wiki/wiki)/(\w+)')

def parse_url(url):
    m = URL_RE.search(url)
    if not m: return None, None
    return m.group(1), m.group(2)

def resolve_wiki(node_token):
    st, r = api_get("/open-apis/wiki/v2/spaces/get_node", {"token":node_token})
    if r.get('code')==0:
        n = r['data']['node']
        return n.get('obj_type'), n.get('obj_token'), n.get('title')
    return None, None, f"[wiki err {r.get('code')}:{r.get('msg')}]"

def docx_text(doc_id):
    st, r = api_get(f"/open-apis/docx/v1/documents/{doc_id}/raw_content")
    if r.get('code')==0:
        return r['data']['content'], None
    return None, f"docx raw err {r.get('code')}:{r.get('msg')}"

def docx_blocks_signal(doc_id):
    st, r = api_get(f"/open-apis/docx/v1/documents/{doc_id}/blocks", {"page_size":500})
    if r.get('code')!=0:
        return {"err": f"{r.get('code')}:{r.get('msg')}"}
    items = r['data']['items']
    types = Counter(b.get('block_type') for b in items)
    # 43=board(whiteboard) 31/32=table/cell 27=image 30=sheet 14/15/17 list
    return {"n_blocks": len(items), "has_board": types.get(43,0)>0,
            "has_table": types.get(31,0)>0, "has_image": types.get(27,0)>0,
            "histogram": dict(types)}

def fetch(url):
    typ, tok_ = parse_url(url)
    if not typ:
        return {"url":url, "ok":False, "note":"not a larksuite doc url"}
    obj_type, doc_id, title = typ, tok_, None
    if typ in ("wiki",):
        obj_type, doc_id, title = resolve_wiki(tok_)
        if not doc_id:
            return {"url":url, "ok":False, "kind":"wiki", "note":title}
    out = {"url":url, "kind":typ, "obj_type":obj_type, "doc_id":doc_id, "title":title}
    if obj_type in ("docx","doc","docs"):
        txt, err = docx_text(doc_id)
        if err: out["ok"]=False; out["note"]=err; return out
        out["ok"]=True; out["text"]=txt; out["text_len"]=len(txt)
        out["blocks"]=docx_blocks_signal(doc_id)
    elif obj_type=="sheet":
        out["ok"]=False; out["note"]="sheet (not fetched as text)"
    else:
        out["ok"]=False; out["note"]=f"unhandled obj_type {obj_type}"
    return out

if __name__ == "__main__":
    for u in sys.argv[1:]:
        r = fetch(u)
        print(json.dumps(r, ensure_ascii=False)[:500])

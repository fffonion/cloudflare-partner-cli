#coding: utf-8
import os
import json
import sys
PY3K = sys.version_info[0] == 3
if not PY3K:
    import urllib2
    from urllib import urlencode
else:
    import urllib.request as urllib2
    from urllib.parse import urlencode
    raw_input = input
    _map = map
    map = lambda *a, **k: list(_map(*a, **k))
import locale
LOCALE = locale.getdefaultlocale()

HOSTKEY = None # HOSTKEY_ANCHOR

CFARG = {
    'user_auth': ("cloudflare_email", "cloudflare_pass"),
    'zone_set': ("zone_name", "subdomains", "resolve_to"),
    'zone_delete': ("zone_name",),
    'zone_list': (),
    'zone_lookup': ("zone_name",),
    'add_subdomain':("zone_name", "subdomains", "resolve_to"),
    'delete_subdomain': ("zone_name", "subdomains"),
    'ssl_verfication': ("zone",),
    'host_key_regen': (),
}
CFHOST_FILE = ".cfhost"

I18N = {
    "zone_list": "显示所有接入的域名",
    "zone_set": "接入域名",
    "zone_lookup": "显示DNS记录",
    "zone_delete": "删除接入的域名",
    "host_key_regen": "重新生成host key",
    "user_auth": "登录",
    "add_subdomain": "添加/修改DNS记录",
    "delete_subdomain": "删除DNS记录",
    "logout": "退出当前帐号",
    "ssl_verfication": "开通SSL",
    "zone_name": "根域名",
    "resolve_to": "源站地址",
    "subdomains": "子域名",
    "cloudflare_email": "邮箱",
    "cloudflare_pass": "密码",
    "zone": "根域名",
    "subdomain": "子域名",
    "Zone": "根域名",
    "User": "用户",
    "Subdomain": "子域名",
    "Resolve to": "源站地址",
    "Login as %s": "%s 已登录",
    "vetting": "审批中",
    "validating": "等待验证",
    "ready": "已启用",
    "Select your action:": "选择所需的操作，输入数字：",
    "Missing required arg \"%s\". (act:%s)": "缺少参数 \"%s\". (act:%s)",
    "Login failed, msg: %s": "登录失败: %s",
    "Success! Please set CNAME record of %s to %s": "设置成功! 请将%s的CNAME记录设置为%s",
    "Domain %s has been removed from partner": "域名%s已取消接入",
    "%s (act: %s)": "报错: %s (act: %s) ",
    "Please enter your Cloudflare partner hostkey (https://partners.cloudflare.com/api-management)> ":
        "请输入 Cloudflare hostkey (https://partners.cloudflare.com/api-management)> ",
    "SSL status: %s": "SSL状态: %s",
    "Please login first. (uri: %s)": "请先登录. (uri: %s)",
    "Please login first. (act: %s)": "请先登录. (act: %s)",
    "No zone found matching %s. Please use zone_set first.": "账户中不存在域名%s, 请先添加域名",
    "SSL for domain %s has already been activated.": "域名%s已开通SSL, 无需操作",
    "??? %s": "喵喵喵？ %s",
    "Please set CNAME record of %s to %s and run this option again after record become effective":
        "请将%s的CNAME记录设置为%s, 然后在解析生效后再运行一次\"开通SSL\"",
    "Can't delete root record": "不能删除根域名",
    "Record %s is deleted": "DNS记录%s已删除",
    "Record %s is not found in zone %s": "记录%s不存在于域名%s中",
    "If you want to activate SSL, please set CNAME record of %s to %s and " \
        "run this \"ssl_verfication\" after record become effective":
            "如果需要启用SSL, 请将%s的CNAME记录设置为%s, 然后在解析生效后运行一次\"开通SSL\"",
    "Zone %s not exists or is not under user %s": "域名%s不存在，或者不属于用户%s",
    "Host key has been changed to %s": "Hostkey已更新为 %s",
}

def i18n(s):
    _ = I18N[s] if LOCALE[1] and LOCALE[1].lower() in ("utf-8", "cp936") and s in I18N else s
    if LOCALE[1].lower() == "cp936" and not PY3K: # windows with simplified Chinese locale
        return _.decode('utf-8').encode('gb18030')
    return _

def log(fmt, arg = (), level = "INFO"):
    if PY3K:
        if not (isinstance(arg, list) or isinstance(arg, tuple)):
            arg = (arg, )
        arg = tuple([a.decode('ascii') if isinstance(a, bytes) else a for a in arg])
    print("%-4s - %s" % (level, i18n(fmt) % arg))

def catch_err(func):
    def _(instance, j, *arg):
        if j['result'] == 'error':
            log("%s (act: %s)", (j['msg'].encode('utf-8'), j['request']['act'].encode('utf-8')), "ERR")
            return
        return func(instance, j, *arg)
    return _

class CF(object):
    def __init__(self):
        self.user_email = None
        self.user_key = None
        self.user_api_key = None
        if os.path.exists(CFHOST_FILE):
            r = open(CFHOST_FILE).read()
            _ = r.split(",")
            if len(_) != 3:
                try:
                    os.remove(CFHOST_FILE)
                except:
                    pass
            else:
                _ = map(lambda x:x.strip(), _)
                self.user_email, self.user_key, self.user_api_key = _
                log("Login as %s", self.user_email)

    def _hostapi(self, act, extra={}):
        if not self.user_key and act not in ("user_auth", "host_key_regen"):
            log("Please login first. (act: %s)", act, "ERR")
            return
        payload = {
            "act": act,
            "host_key": HOSTKEY,
        }
        if act not in ("user_auth", "host_key_regen"):
            payload.update({"user_key": self.user_key})
        if extra:
            payload.update(extra)
        if act in CFARG:
            for k in CFARG[act]:
                if k not in payload:
                    log("Missing required arg \"%s\". (act:%s)", (k, act), "ERR")
                    return
        if PY3K:
            payload = urlencode(payload).encode('ascii')
        else:
            payload = urlencode(payload)
        req  = urllib2.Request("https://api.cloudflare.com/host-gw.html", payload)
        r = urllib2.urlopen(req).read()
        if PY3K and isinstance(r, bytes):
            r = r.decode('ascii')
        return json.loads(r)
    
    def _userapi(self, uri, method="GET", extra={}):
        if not self.user_api_key:
            log("Please login first. (uri: %s)", uri, "ERR")
            return
        headers = {
            'X-Auth-Email': self.user_email,
            'X-Auth-Key': self.user_api_key,
            'Content-Type': "application/json",
        }
        if extra:
            headers.update(extra)
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        req  = urllib2.Request("https://api.cloudflare.com/client/v4%s" % uri)
        for k, v in headers.items():
            req.add_header(k, v)
        req.get_method = lambda: method
        r = opener.open(req).read()
        if PY3K and isinstance(r, bytes):
            r = r.decode('ascii')
        return json.loads(r)

        return json.loads(r.read())

    def user_auth(self, arg):
        ret = self._hostapi("user_auth", arg)
        if not ret:
            return False
        if 'response' not in ret or 'user_key' not in ret['response']:
            log("Login failed, msg: %s", ret['msg'].encode('utf-8'), "ERR")
            return False
        log("Login as %s", arg['cloudflare_email'])
        self.user_key = ret['response']['user_key']
        self.user_api_key = ret['response']['user_api_key']
        if not PY3K:
            self.user_email = arg['cloudflare_email']
            self.user_key = self.user_key.encode('utf-8')
            self.user_api_key = self.user_api_key.encode('utf-8')
        open(CFHOST_FILE, "w").write("%s,%s,%s" % (self.user_email, self.user_key, self.user_api_key))
        return True
    
    def logout(self, *arg):
        try:
            os.remove(CFHOST_FILE)
        except:
            pass
        os._exit(0)
    
    def ssl_verfication(self, arg):
        r = self._userapi("/zones?name=%s&match=all" % arg['zone'])
        if len(r['result']) < 1:
            log("No zone found matching %s. Please use zone_set first.", arg['zone'], "ERR")
            return
        zone_id = r['result'][0]['id']
        r = self._userapi("/zones/%s/ssl/verification?retry=true" % zone_id)
        if len(r['result']) < 1:
            log("??? %s", r, "ERR")
            return
        if r['result'][0]['certificate_status'] == "active":
            log("SSL for domain %s has already been activated.", arg['zone'])
            return True
        verification_info = r['result'][0]['verification_info']
        log("Please set CNAME record of %s to %s and run this option again after record become effective", (
            verification_info['record_name'].encode('utf-8'), verification_info['record_target'].encode('utf-8')))
    
    def add_subdomain(self, arg):
        r = self._hostapi("zone_lookup", {"zone_name": arg['zone_name']})
        if 'hosted_cnames' not in r['response'] or not r['response']['hosted_cnames']:
            log("No zone found matching %s. Please use zone_set first.", arg['zone_name'], "ERR")
            return
        hosted = r['response']['hosted_cnames']
        # concat a real subdomain
        if arg['subdomains'] == "@":
            subdomain = arg['zone_name']
        elif arg['subdomains'].lower().endswith(arg['zone_name'].lower()):
            subdomain = arg['subdomains']
        else:
            subdomain = "%s.%s" % (arg['subdomains'], arg['zone_name'])
        hosted[subdomain] = arg['resolve_to']
        # make the subdomain to @ to avoid it being changed
        arg['resolve_to'] = hosted[arg['zone_name']]
        arg['subdomains'] = "@,%s" % (",".join(["%s:%s" % (k, v) for k, v in hosted.items() if k != arg['zone_name']]))
        r = self._hostapi("zone_set", arg)
        self._zone_set(r, subdomain)

    def delete_subdomain(self, arg):
        if arg['subdomains'] == "@":
            log("Can't delete root record", (), "ERR")
            return
        r = self._hostapi("zone_lookup", {"zone_name": arg['zone_name']})
        if 'hosted_cnames' not in r['response'] or not r['response']['hosted_cnames']:
            log("No zone found matching %s. Please use zone_set first.", arg['zone_name'], "ERR")
            return
        hosted = r['response']['hosted_cnames']
        # concat a real subdomain
        if arg['subdomains'] == "@":
            subdomain = arg['zone_name']
        elif arg['subdomains'].lower().endswith(arg['zone_name'].lower()):
            subdomain = arg['subdomains']
        else:
            subdomain = "%s.%s" % (arg['subdomains'], arg['zone_name'])
        if subdomain not in hosted:
            log("Record %s is not found in zone %s", (subdomain, arg['zone_name']))
            return
        # make the subdomain to @ to avoid it being changed
        arg['resolve_to'] = hosted[arg['zone_name']]
        arg['subdomains'] = "@,%s" % (",".join(["%s:%s" % (k, v) for k, v in hosted.items() if k != arg['zone_name'] and k != subdomain]))
        r = self._hostapi("zone_set", arg)
        log("Record %s is deleted", subdomain)
    
    @catch_err
    def _zone_list(self, j):
        print("%-24s%-24s" % (i18n("Zone"), i18n("User")))
        print("-" * 80)
        for z in j['response']:
            print("%-24s%-24s" % (z['zone_name'], z['user_email']))
    
    @catch_err
    def _zone_set(self, j, resolve=None):
        if 'forward_tos' in j['response']:
            resolve = resolve if resolve else list(j['response']['forward_tos'].keys())[0]
            cname = j['response']['forward_tos'][resolve]
            log("Success! Please set CNAME record of %s to %s", (resolve.encode('utf-8'), cname.encode('utf-8')))
    
    @catch_err
    def _zone_delete(self, j):
        log("Domain %s has been removed from partner", j['request']['zone_name'].encode('utf-8'))

    @catch_err
    def _zone_lookup(self, j):
        if not j['response']['zone_exists']:
            log("Zone %s not exists or is not under user %s",
                (j['request']['zone_name'].encode('utf-8'), self.user_email))
            return
        log("SSL status: %s", (i18n(j['response']['ssl_status'].encode('utf-8').decode('ascii'))))
        print("%-32s%-24s%-32s" % (i18n("Subdomain"), i18n("Resolve to"), i18n("CNAME")))
        print("-" * 80)
        tos = j['response']['forward_tos']
        hosted = j['response']['hosted_cnames']
        if not tos or not hosted:
            return
        ssl_cname, ssl_resolve_to = None, None
        for z in tos.keys():
            if hosted[z].endswith("comodoca.com"):
                ssl_cname = z.encode('utf-8')
                ssl_resolve_to = hosted[z].encode('utf-8')
                continue
            print("%-32s%-24s%-32s" % (z, hosted[z], tos[z]))
        if ssl_cname:
            print("")
            log("If you want to activate SSL, please set CNAME record of %s to %s and " \
                "run this \"ssl_verfication\" after record become effective", (ssl_cname, ssl_resolve_to))
    
    @catch_err
    def _host_key_regen(self, j):
        global HOSTKEY
        HOSTKEY = j['request']['host_key']['__host_key'].encode('utf-8')
        check_hostkey(force = True)
        log("Host key has been changed to %s", HOSTKEY)
    
    def __getattr__(self, act, handle=True):
        if act not in CFARG:
            raise AttributeError("'CF' object has no attribute '%s'" % act)
        return lambda k={}:getattr(self, "_%s" % act)(self._hostapi(act, k))

def check_hostkey(force = False):
    global HOSTKEY
    if HOSTKEY and len(HOSTKEY) == 32 and not force:
        return
    while not HOSTKEY or len(HOSTKEY) != 32:
        HOSTKEY = raw_input(i18n("Please enter your Cloudflare partner hostkey (https://partners.cloudflare.com/api-management)> ")).strip()
    import re
    with open(__file__) as f:
        script = f.read()
    script = re.sub("HOSTKEY.+HOSTKEY_ANCHOR", "HOSTKEY = \"%s\" # HOSTKEY_ANCHOR" % HOSTKEY, script, count = 1)
    with open(__file__, 'w') as f:
        f.write(script)

def menu(act = None):
    if not act:
        acts = [k for k in CFARG.keys() if k != "user_auth"] + ["logout"]
        print("=" * 32)
        print(i18n("Select your action:"))
        for i in range(len(acts)):
            print("%d. %s" % (i + 1, i18n(acts[i])))
        s = raw_input("> ").strip()
        if not s.isdigit() or int(s) not in range(1, len(acts) + 1):
            return None, None
        act = acts[int(s) - 1]
    arg = {}
    if act in CFARG:
        for k in CFARG[act]:
            while True:
                arg[k] = raw_input("%s > " % i18n(k))
                if arg[k]:
                    break
    return act, arg
    
if __name__ == '__main__':
    try:
        check_hostkey()
        cf = CF()
        while not cf.user_key:
            act, arg = menu(act = "user_auth")
            cf.user_auth(arg)
        while True:
            act, arg = menu()
            if not act:
                continue
            getattr(cf, act)(arg)
    except (KeyboardInterrupt, EOFError):
        os._exit(0)

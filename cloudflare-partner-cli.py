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
import locale
LOCALE = locale.getdefaultlocale()

HOSTKEY = None # HOSTKEY_ANCHOR

CFARG = {
    'user_auth': ("cloudflare_email", "cloudflare_pass"),
    'zone_set': ("zone_name", "resolve_to", "subdomains"),
    'zone_lookup': ("zone_name",),
    'zone_delete': ("zone_name",),
    'zone_list': (),
}
CFHOST_FILE = ".cfhost"

I18N = {
    "zone_list": "显示所有接入的域名",
    "zone_set": "添加/修改域名",
    "zone_lookup": "显示所有子域名",
    "zone_delete": "删除接入的域名",
    "user_auth": "登录",
    "logout": "退出当前帐号",
    "zone_name": "根域名",
    "resolve_to": "源站地址",
    "subdomains": "子域名",
    "cloudflare_email": "邮箱",
    "cloudflare_pass": "密码",
    "Zone": "根域名",
    "User": "用户",
    "Subdomain": "子域名",
    "Resolve to": "源站地址",
    "Login as %s": "%s 已登陆",
    "Select your action:": "选择所需的操作，输入数字：",
    "Missing required arg \"%s\". (act:%s)": "缺少参数 \"%s\". (act:%s)",
    "Login failed, msg: %s": "登录失败: %s",
    "Success! Please set CNAME record of %s to %s": "设置成功! 请将%s的CNAME记录设置为%s",
    "Domain %s has been removed from partner": "域名%s已取消托管",
    "%s (act: %s)": "报错: %s (act: %s) ",
    "Please enter your Cloudflare partner hostkey (https://partners.cloudflare.com/api-management)> ":
        "请输入 Cloudflare hostkey (https://partners.cloudflare.com/api-management)> ",
}

def i18n(s):
    return I18N[s] if LOCALE[1] and LOCALE[1].lower() == "utf-8" and s in I18N else s

def log(fmt, arg = (), level = "INFO"):
    if PY3K:
        if not (isinstance(arg, list) or isinstance(arg, tuple)):
            arg = (arg, )
        arg = tuple([a.decode('ascii') if isinstance(a, bytes) else a for a in arg])
    print("%-4s - %s" % (level, i18n(fmt) % arg))

def catch_err(func):
    def _(instance, j):
        if j['result'] == 'error':
            log("%s (act: %s)", (j['msg'].encode('utf-8'), j['request']['act'].encode('utf-8')), "ERR")
            return
        return func(instance, j)
    return _

class CF(object):
    def __init__(self):
        self.user_key = None
        self.host_key = HOSTKEY
        if os.path.exists(CFHOST_FILE):
            r = open(CFHOST_FILE).read()
            _ = r.split(",")
            if len(_) != 2:
                try:
                    os.remove(CFHOST_FILE)
                except:
                    pass
            else:
                email, self.user_key = _
                log("Login as %s", email)

    def _api(self, act, extra={}):
        if not self.user_key and act != "user_auth":
            log("Please login first. (act: %s)", act, "ERR")
            return
        payload = {
            "act": act,
            "host_key": self.host_key,
        }
        if act != "user_auth":
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
        r = urllib2.urlopen(req)
        return json.loads(r.read())

    def user_auth(self, arg):
        ret = self._api("user_auth", arg)
        if not ret:
            return False
        if 'response' not in ret or 'user_key' not in ret['response']:
            log("Login failed, msg: %s", ret['msg'].encode('utf-8'), "ERR")
            return False
        log("Login as %s", arg['cloudflare_email'])
        self.user_key = ret['response']['user_key']
        if not PY3K:
            self.user_key = self.user_key.encode('utf-8')
        open(CFHOST_FILE, "w").write("%s,%s" % (arg['cloudflare_email'], self.user_key))
        return True
    
    def logout(self, *arg):
        try:
            os.remove(CFHOST_FILE)
        except:
            pass
        os._exit(0)
    
    @catch_err
    def _zone_list(self, j):
        print("%24s%24s" % (i18n("Zone"), i18n("User")))
        print("-" * 80)
        for z in j['response']:
            print("%24s%24s" % (z['zone_name'], z['user_email']))
    
    @catch_err
    def _zone_set(self, j):
        if 'forward_tos' in j['response']:
            resolve = list(j['response']['forward_tos'].keys())[0]
            cname = j['response']['forward_tos'][resolve]
            log("Success! Please set CNAME record of %s to %s", (resolve.encode('utf-8'), cname.encode('utf-8')))
    
    @catch_err
    def _zone_delete(self, j):
        log("Domain %s has been removed from partner", j['request']['zone_name'].encode('utf-8'))

    @catch_err
    def _zone_lookup(self, j):
        print("%-32s%-24s%-32s" % (i18n("Subdomain"), i18n("Resolve to"), i18n("CNAME")))
        print("-" * 80)
        tos = j['response']['forward_tos']
        hosted = j['response']['hosted_cnames']
        if not tos or not hosted:
            return
        for z in tos.keys():
            print("%-32s%-24s%-32s" % (z, hosted[z], tos[z]))
    
    def __getattr__(self, act):
        if act not in CFARG:
            raise AttributeError("'CF' object has no attribute '%s'" % act)
        return lambda k={}:getattr(self, "_%s" % act)(self._api(act, k))

def check_hostkey():
    global HOSTKEY
    if HOSTKEY and len(HOSTKEY) == 32:
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
        acts = [k for k in CFARG.keys() if k != "user_auth"] + ["logout", ]
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
    check_hostkey()
    cf = CF()
    try:
        while not cf.user_key:
            act, arg = menu(act = "user_auth")
            cf.user_auth(arg)
        while True:
            act, arg = menu()
            if not act:
                continue
            getattr(cf, act)(arg)
    except KeyboardInterrupt:
        os._exit(0)

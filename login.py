import os
import time
import requests
import cloudscraper
from bs4 import BeautifulSoup

EMAIL          = os.environ["LUNESHOST_EMAIL"]
PASSWORD       = os.environ["LUNESHOST_PASSWORD"]
TWOCAPTCHA_KEY = os.environ["TWOCAPTCHA_KEY"]

BASE_URL   = "https://betadash.lunes.host"
LOGIN_URL  = f"{BASE_URL}/login"
SERVER_ID  = "48195"
SERVER_URL = f"{BASE_URL}/servers/{SERVER_ID}"

def get_login_page(session):
    print("[1] 正在获取登录页面...")
    resp = session.get(LOGIN_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_input = soup.find("input", {"name": "_csrf_token"}) or soup.find("input", {"name": "csrf_token"})
    csrf_token = csrf_input["value"] if csrf_input else ""
    hcaptcha_div = soup.find(class_="h-captcha")
    sitekey = hcaptcha_div["data-sitekey"] if hcaptcha_div else None
    print(f"    CSRF token: {csrf_token[:20]}..." if csrf_token else "    CSRF token: 未找到")
    print(f"    hCaptcha sitekey: {sitekey}" if sitekey else "    hCaptcha: 未检测到")
    return csrf_token, sitekey

def solve_hcaptcha(sitekey, page_url):
    print("[2] 正在提交 hCaptcha 到 2Captcha...")
    resp = requests.post("http://2captcha.com/in.php", data={
        "key": TWOCAPTCHA_KEY, "method": "hcaptcha",
        "sitekey": sitekey, "pageurl": page_url, "json": 1,
    })
    data = resp.json()
    if data.get("status") != 1:
        raise Exception(f"2Captcha 提交失败: {data}")
    captcha_id = data["request"]
    print(f"    任务 ID: {captcha_id}，等待解答...")
    for attempt in range(36):
        time.sleep(5)
        result = requests.get("http://2captcha.com/res.php", params={
            "key": TWOCAPTCHA_KEY, "action": "get", "id": captcha_id, "json": 1,
        }).json()
        if result.get("status") == 1:
            print(f"    解答成功！（等待了约 {(attempt+1)*5} 秒）")
            return result["request"]
        if result.get("request") != "CAPCHA_NOT_READY":
            raise Exception(f"2Captcha 返回错误: {result}")
        print(f"    第 {attempt+1} 次等待...")
    raise TimeoutError("hCaptcha 解答超时")

def do_login(session, csrf_token, captcha_token):
    print("[3] 正在登录...")
    payload = {"email": EMAIL, "password": PASSWORD, "h-captcha-response": captcha_token or ""}
    if csrf_token:
        payload["_csrf_token"] = csrf_token

    resp = session.post(LOGIN_URL, data=payload, headers={
        "Referer": LOGIN_URL,
        "Content-Type": "application/x-www-form-urlencoded",
    }, allow_redirects=True)

    print(f"    POST 后 URL: {resp.url}")
    print(f"    Cookies: {list(session.cookies.keys())}")

    # 只信任 URL 跳转，不信任页面内容
    if "login" not in resp.url.lower():
        print(f"    ✅ 登录成功！当前页面: {resp.url}")
        return True
    else:
        print(f"    ❌ 仍在登录页，登录失败")
        # 打印错误提示
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all(class_=lambda c: c and ("error" in c.lower() or "alert" in c.lower())):
            txt = tag.get_text(strip=True)
            if txt:
                print(f"    页面提示: {txt}")
        return False

def visit_server(session):
    print(f"[4] 正在进入服务器页面 (ID: {SERVER_ID})...")
    resp = session.get(SERVER_URL, allow_redirects=True)
    print(f"    最终 URL: {resp.url}")
    print(f"    状态码: {resp.status_code}")

    if "login" in resp.url.lower():
        raise Exception("访问服务器页面被重定向到登录页，session 未正确保持")

    if resp.status_code != 200:
        raise Exception(f"服务器页面返回 {resp.status_code}")

    print("    ✅ 成功进入，开始停留计时...")
    STAY_SECONDS = 35
    for i in range(STAY_SECONDS // 5):
        time.sleep(5)
        print(f"    已停留 {(i+1)*5} / {STAY_SECONDS} 秒")
    print(f"    ✅ 已停留 {STAY_SECONDS} 秒")

import random

def human_delay(min_s=1.5, max_s=4.0):
    t = random.uniform(min_s, max_s)
    print(f"    (等待 {t:.1f} 秒...)")
    time.sleep(t)

def main():
    print("=" * 50)
    print("  LunesHost 自动登录保活脚本")
    print("=" * 50)

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )

    # 打开登录页，停一下再操作
    csrf_token, sitekey = get_login_page(scraper)
    human_delay(2.0, 5.0)   # 模拟用户在页面上停留、阅读

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    })
    for cookie in scraper.cookies:
        session.cookies.set(cookie.name, cookie.value, domain=cookie.domain)
    print(f"    转移的 CF cookies: {list(session.cookies.keys())}")

    captcha_token = None
    if sitekey:
        captcha_token = solve_hcaptcha(sitekey, LOGIN_URL)
        human_delay(1.5, 3.0)   # 验证码完成后停一下再点提交
    else:
        print("[2] 无验证码，跳过")
        human_delay(1.0, 2.5)   # 模拟填写表单的时间

    if not do_login(session, csrf_token, captcha_token):
        print("\n❌ 登录失败")
        raise SystemExit(1)

    human_delay(2.0, 4.0)   # 模拟登录后页面加载、用户看 dashboard

    visit_server(session)
    print("\n✅ 保活完成！")

if __name__ == "__main__":
    main()

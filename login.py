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
    print(f"    hCaptcha sitekey: {sitekey}" if sitekey else "    hCaptcha: 未检测到（可能无验证码）")
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
    raise TimeoutError("hCaptcha 解答超时（超过 3 分钟）")

def do_login(session, csrf_token, captcha_token):
    print("[3] 正在登录...")
    payload = {"email": EMAIL, "password": PASSWORD, "h-captcha-response": captcha_token or ""}
    if csrf_token:
        payload["_csrf_token"] = csrf_token
    resp = session.post(LOGIN_URL, data=payload, headers={
        "Referer": LOGIN_URL, "Content-Type": "application/x-www-form-urlencoded",
    }, allow_redirects=True)
    if resp.url != LOGIN_URL and "login" not in resp.url.lower():
        print(f"    ✅ 登录成功！当前页面: {resp.url}")
        return True
    elif "logout" in resp.text.lower() or "dashboard" in resp.text.lower():
        print("    ✅ 登录成功！（页面含 dashboard/logout 关键词）")
        return True
    else:
        print(f"    ❌ 登录失败，当前 URL: {resp.url}")
        soup = BeautifulSoup(resp.text, "html.parser")
        err = soup.find(class_=lambda c: c and "error" in c.lower())
        if err:
            print(f"    错误信息: {err.get_text(strip=True)}")
        return False

def visit_server(session):
    print(f"[4] 正在进入服务器页面 (ID: {SERVER_ID})...")
    
    # 打印当前 cookies，确认 session 存在
    cookies = dict(session.cookies)
    print(f"    当前 cookies: {list(cookies.keys())}")
    
    resp = session.get(SERVER_URL, allow_redirects=True)
    print(f"    最终 URL: {resp.url}")
    print(f"    状态码: {resp.status_code}")

    if resp.status_code != 200:
        raise Exception(f"服务器页面返回 {resp.status_code}")

    # 不再依赖 URL 判断，改为检查页面内容
    page_text = resp.text.lower()
    if "login" in resp.url.lower() or ("<title>" in page_text and "login" in page_text[:500]):
        # 尝试重新登录后再访问
        print("    ⚠️  Session 丢失，尝试重新登录...")
        csrf_token, sitekey = get_login_page(session)
        captcha_token = None
        if sitekey:
            captcha_token = solve_hcaptcha(sitekey, LOGIN_URL)
        if not do_login(session, csrf_token, captcha_token):
            raise Exception("重新登录失败")
        resp = session.get(SERVER_URL, allow_redirects=True)
        print(f"    重试后状态码: {resp.status_code}, URL: {resp.url}")
        if resp.status_code != 200 or "login" in resp.url.lower():
            raise Exception("重新登录后仍无法访问服务器页面")

    print("    ✅ 成功进入服务器页面，开始停留计时...")
    STAY_SECONDS = 35
    for i in range(STAY_SECONDS // 5):
        time.sleep(5)
        print(f"    已停留 {(i+1)*5} 秒 / {STAY_SECONDS} 秒")
    print(f"    ✅ 已在服务器页面停留 {STAY_SECONDS} 秒")

def main():
    print("=" * 50)
    print("  LunesHost 自动登录保活脚本")
    print("=" * 50)
    session = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    csrf_token, sitekey = get_login_page(session)
    captcha_token = None
    if sitekey:
        captcha_token = solve_hcaptcha(sitekey, LOGIN_URL)
    else:
        print("[2] 无验证码，跳过")
    if not do_login(session, csrf_token, captcha_token):
        print("\n❌ 登录失败，请检查账号密码。")
        raise SystemExit(1)
    visit_server(session)
    print("\n✅ 保活完成！")

if __name__ == "__main__":
    main()

import os
import time
import requests
from bs4 import BeautifulSoup

# ============================================================
# 配置（从环境变量读取，不要硬编码密码！）
# ============================================================
EMAIL          = os.environ["LUNESHOST_EMAIL"]       # 你的 LunesHost 账号邮箱
PASSWORD       = os.environ["LUNESHOST_PASSWORD"]    # 你的密码
TWOCAPTCHA_KEY = os.environ["TWOCAPTCHA_KEY"]        # 2Captcha API Key

BASE_URL  = "https://betadash.lunes.host"
LOGIN_URL = f"{BASE_URL}/login"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ============================================================
# 第一步：获取登录页面，提取 CSRF token 和 hCaptcha sitekey
# ============================================================
def get_login_page(session):
    print("[1] 正在获取登录页面...")
    resp = session.get(LOGIN_URL, headers=HEADERS)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # 提取 CSRF token（Flask 通常藏在 <input name="_csrf_token"> 或 <meta name="csrf-token">）
    csrf_input = soup.find("input", {"name": "_csrf_token"})
    if not csrf_input:
        csrf_input = soup.find("input", {"name": "csrf_token"})
    csrf_token = csrf_input["value"] if csrf_input else ""

    # 提取 hCaptcha sitekey
    hcaptcha_div = soup.find(class_="h-captcha")
    sitekey = hcaptcha_div["data-sitekey"] if hcaptcha_div else None

    print(f"    CSRF token: {csrf_token[:20]}..." if csrf_token else "    CSRF token: 未找到")
    print(f"    hCaptcha sitekey: {sitekey}" if sitekey else "    hCaptcha: 未检测到（可能无验证码）")

    return csrf_token, sitekey

# ============================================================
# 第二步：用 2Captcha 解决 hCaptcha
# ============================================================
def solve_hcaptcha(sitekey, page_url):
    print("[2] 正在提交 hCaptcha 到 2Captcha...")

    # 提交任务
    resp = requests.post("http://2captcha.com/in.php", data={
        "key":     TWOCAPTCHA_KEY,
        "method":  "hcaptcha",
        "sitekey": sitekey,
        "pageurl": page_url,
        "json":    1,
    })
    data = resp.json()
    if data.get("status") != 1:
        raise Exception(f"2Captcha 提交失败: {data}")

    captcha_id = data["request"]
    print(f"    任务 ID: {captcha_id}，等待解答...")

    # 轮询结果（最多等 3 分钟）
    for attempt in range(36):
        time.sleep(5)
        result = requests.get("http://2captcha.com/res.php", params={
            "key":    TWOCAPTCHA_KEY,
            "action": "get",
            "id":     captcha_id,
            "json":   1,
        }).json()

        if result.get("status") == 1:
            token = result["request"]
            print(f"    解答成功！（等待了约 {(attempt+1)*5} 秒）")
            return token

        if result.get("request") != "CAPCHA_NOT_READY":
            raise Exception(f"2Captcha 返回错误: {result}")

        print(f"    第 {attempt+1} 次等待...")

    raise TimeoutError("hCaptcha 解答超时（超过 3 分钟）")

# ============================================================
# 第三步：发送登录请求
# ============================================================
def do_login(session, csrf_token, captcha_token):
    print("[3] 正在登录...")

    payload = {
        "email":             EMAIL,
        "password":          PASSWORD,
        "h-captcha-response": captcha_token or "",
    }
    if csrf_token:
        payload["_csrf_token"] = csrf_token

    resp = session.post(LOGIN_URL, data=payload, headers={
        **HEADERS,
        "Referer": LOGIN_URL,
        "Content-Type": "application/x-www-form-urlencoded",
    }, allow_redirects=True)

    # 判断是否登录成功（跳转到 dashboard 或页面内有用户信息）
    if resp.url != LOGIN_URL and "login" not in resp.url.lower():
        print(f"    ✅ 登录成功！当前页面: {resp.url}")
        return True
    elif "logout" in resp.text.lower() or "dashboard" in resp.text.lower():
        print("    ✅ 登录成功！（页面含 dashboard/logout 关键词）")
        return True
    else:
        print(f"    ❌ 登录可能失败，当前 URL: {resp.url}")
        # 打印页面中的错误信息（如果有）
        soup = BeautifulSoup(resp.text, "html.parser")
        err = soup.find(class_=lambda c: c and "error" in c.lower())
        if err:
            print(f"    错误信息: {err.get_text(strip=True)}")
        return False

# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 50)
    print("  LunesHost 自动登录保活脚本")
    print("=" * 50)

    session = requests.Session()

    # 1. 获取登录页
    csrf_token, sitekey = get_login_page(session)

    # 2. 解决验证码（如有）
    captcha_token = None
    if sitekey:
        captcha_token = solve_hcaptcha(sitekey, LOGIN_URL)
    else:
        print("[2] 无验证码，跳过")

    # 3. 登录
    success = do_login(session, csrf_token, captcha_token)

    if success:
        # 4. 额外访问一下 dashboard 确保活跃
        print("[4] 访问 Dashboard 确认活跃...")
        dash = session.get(BASE_URL, headers=HEADERS)
        print(f"    Dashboard 状态码: {dash.status_code}")
        print("\n✅ 保活完成！")
    else:
        print("\n❌ 登录失败，请检查账号密码或验证码配置。")
        raise SystemExit(1)

if __name__ == "__main__":
    main()

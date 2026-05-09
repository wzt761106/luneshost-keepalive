# LunesHost 自动登录保活

自动定期登录 LunesHost 控制面板，防止账号因长期不活跃而被重置密码。

## 工作原理

GitHub Actions 按计划（每 5 天）自动运行一个 Python 脚本：
1. 访问 `betadash.lunes.host/login`
2. 提取 CSRF token 和 hCaptcha sitekey
3. 调用 2Captcha API 解决验证码
4. 提交登录表单，完成保活

## 快速开始

### 第一步：Fork 或创建仓库

将本项目上传到你自己的 GitHub 仓库。

### 第二步：添加 Secrets

在 GitHub 仓库页面点击 **Settings → Secrets and variables → Actions → New repository secret**，添加以下三个：

| Secret 名称          | 内容                       |
|---------------------|--------------------------|
| `LUNESHOST_EMAIL`   | 你的 LunesHost 登录邮箱     |
| `LUNESHOST_PASSWORD`| 你的登录密码               |
| `TWOCAPTCHA_KEY`    | 你的 2Captcha API Key     |

### 第三步：启用 Actions

在 GitHub 仓库点击顶部 **Actions** 标签页，点击 **Enable GitHub Actions**（如果有提示）。

之后可以点击 **Run workflow** 手动测试一次。

## 文件结构

```
├── login.py                        # 主脚本
├── requirements.txt                # Python 依赖
└── .github/
    └── workflows/
        └── keepalive.yml           # 定时任务配置
```

## 获取 2Captcha API Key

1. 注册 [2captcha.com](https://2captcha.com)
2. 充值（最低约 $3）
3. 在控制台首页复制 API Key

## 注意事项

- **不要**把密码直接写进代码，必须用 GitHub Secrets。
- LunesHost 提示账号 **6 个月**不活跃会重置密码，每 5 天登录一次绰绰有余。
- 如果登录失败，在 GitHub Actions 的日志里可以看到详细错误。

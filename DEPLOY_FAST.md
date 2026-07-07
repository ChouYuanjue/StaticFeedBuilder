# 最快部署清单

## 1. 推到 GitHub

```bash
cd E:\\static-feed-builder
git init
git add .
git commit -m "init Static Feed Builder"
git branch -M main
git remote add origin https://github.com/你的用户名/static-feed-builder.git
git push -u origin main
```

## 2. 打开 GitHub Pages

仓库页面：

```text
Settings -> Pages -> Build and deployment -> Source -> GitHub Actions
```

## 3. 添加手机推送 Secrets，可选但推荐

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

最简单只加 ntfy：

```text
NTFY_TOPIC=competition-radar-换成一串随机字符
```

手机安装 ntfy App，订阅同一个 topic。

可选 Telegram：

```text
TELEGRAM_BOT_TOKEN=你的 Telegram bot token
TELEGRAM_CHAT_ID=你的 chat id
```

可选 DeepSeek：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API key
```

## 4. 手动运行一次

```text
Actions -> Static Feed Builder -> Run workflow
```

成功后 GitHub Pages 会生成：

```text
https://你的用户名.github.io/static-feed-builder/
https://你的用户名.github.io/static-feed-builder/feed.xml
https://你的用户名.github.io/static-feed-builder/calendar.ics
```

手机 RSS 阅读器订阅 feed.xml，手机日历订阅 calendar.ics。


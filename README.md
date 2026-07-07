# Static Feed Builder

一个很小的个人自动化工具：定时读取若干公开页面，把其中需要稍后查看的条目整理成静态网页、RSS、日历文件和简单摘要。

它的定位很普通：

- 定期检查公开页面；
- 生成一个静态索引页；
- 生成 RSS 订阅源；
- 生成日历文件；
- 可选发送一条手机通知；
- 不需要常驻服务器。

## 输出

运行后会生成：

```text
out/index.html
out/feed.xml
out/calendar.ics
out/items.json
out/latest_digest.md
```

这些文件可以直接放到 GitHub Pages 或其他静态托管服务上。

## 本地运行

```bash
cd static-feed-builder
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
copy .env.example .env

python -m feed_builder.cli init-db
python -m feed_builder.cli crawl
python -m feed_builder.cli digest
python -m feed_builder.cli export-site
```

## 免费自动运行

项目内置 GitHub Actions 工作流：

```text
.github/workflows/feed.yml
```

使用方式：

1. 新建一个 GitHub 仓库。
2. 推送本项目。
3. 在仓库设置里打开 GitHub Pages，并选择 GitHub Actions 作为来源。
4. 在 Actions 页面手动运行一次工作流。
5. 之后它会按计划自动更新静态文件。

## 手机端查看

部署到 GitHub Pages 后，可以订阅：

```text
https://你的用户名.github.io/你的仓库名/feed.xml
https://你的用户名.github.io/你的仓库名/calendar.ics
```

前者用于 RSS 阅读器，后者用于手机日历。

## 可选通知

可以使用常见的手机通知服务或聊天机器人作为提醒通道。相关配置放在本地环境文件或 GitHub Actions 的仓库变量中，不要写进代码仓库。

## 可选文本清理

默认不调用外部模型。只有显式加参数时，才会对少量较难清理的文本做整理：

```bash
python -m feed_builder.cli crawl --llm-clean
python -m feed_builder.cli digest --llm-summary
```

## 常用命令

```bash
# 初始化本地数据库
python -m feed_builder.cli init-db

# 读取公开页面并整理条目
python -m feed_builder.cli crawl

# 生成摘要
python -m feed_builder.cli digest

# 导出 RSS
python -m feed_builder.cli export-rss --output out/feed.xml

# 导出日历文件
python -m feed_builder.cli export-ics --output out/calendar.ics

# 导出完整静态页面
python -m feed_builder.cli export-site
```

## 配置

主要配置文件：

```text
config/sources.yaml
config/preferences.yaml
```

如果只想先做很小的测试，可以使用：

```text
config/sources.ctftime_only.yaml
```

## 说明

这个项目刻意保持简单：一次运行、生成静态文件、发布出去。没有后台服务，也不需要数据库长期在线。


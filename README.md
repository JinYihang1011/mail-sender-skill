# Mail Sender Skill

一个可供支持 `SKILL.md` 的 AI 助手使用的 SMTP 邮件发送 Skill。它提供命令行发送器、可填写的配置模板，以及跨进程共享的限频记录。仅依赖 Python 标准库。

## 给 AI 助手的快速入口

1. 导入本目录作为 `mail-sender` Skill，先阅读 [SKILL.md](SKILL.md)。
2. 引导用户在仓库外复制并填写 [config.example.json](config.example.json)。不要在聊天中索取密码或授权码，也不要把它写入仓库。
3. 请用户在运行环境中设置配置项 `password_env` 指定的环境变量。
4. 确认用户指定的收件人、主题和正文，先运行 `--dry-run`；获得发送授权后才实际发送。
5. 检查 JSON 结果。`sent` 表示 SMTP 服务器接受，不能保证收件箱已收到；`blocked` 是限频，`error` 是失败或结果不确定。

## 导入 Skill

对支持文件系统 Skill 的 Codex，在终端将整个目录复制到 Codex 技能目录，目录名可用 `mail-sender`。例如，先克隆仓库到本地，再使用以下命令（将路径替换为实际克隆路径）：

PowerShell：

```powershell
Copy-Item -Recurse -LiteralPath '<克隆目录>' -Destination "$env:USERPROFILE\.codex\skills\mail-sender"
```

其他支持 `SKILL.md` 的 AI 应用可按该应用的导入方式导入整个目录；是否支持脚本执行取决于应用环境，不能保证所有应用都可直接运行。Skill 本身不会注册定时任务，也不会自动发送邮件。

## 配置

将 `config.example.json` 复制到仓库外的私有目录，例如 `<私有目录>/config.json`，按自己的邮箱服务商填写：

- `smtp_host`、`smtp_port`、`transport`：邮箱服务商提供的 SMTP 地址、端口，以及 `ssl` 或 `starttls`。
- `username`、`sender`：SMTP 登录名和发件邮箱；`display_name` 和 `signature` 可按用途填写。
- `default_to`：可留空，每次运行时用 `--to` 指定；也可填写默认收件邮箱。
- `password_env`：存放 SMTP 密码或授权码的环境变量名称；配置文件只写变量名，不写密钥。
- `state_path`：SQLite 状态文件路径；相对路径相对于配置文件所在目录。需要共享限频的调用必须指向同一个状态文件。
- `limits`：最短间隔、每自然小时与自然日上限、重复内容抑制时间、服务端拒绝后的冷却时间。示例值是保守的本地设置，并非服务商承诺的额度。

请在运行它的终端中安全设置环境变量 `MAIL_SENDER_PASSWORD`，具体做法取决于操作系统和部署环境。不要将密钥写入命令行历史、项目文件或版本控制。运行进程需要能读取该环境变量；不同会话或计划任务可能不会继承。

## 示例：使用 QQ 邮箱别名给自己发邮件

这个示例使用已在 QQ 邮箱中开通的地址作为发件别名，收件地址填写自己的 QQ 邮箱。示例地址均为占位符；请替换为自己实际拥有的地址，不要直接使用示例地址。

1. 登录 [QQ 邮箱](https://mail.qq.com/)，确认所用别名已经开通，并在设置中找到 IMAP/SMTP 服务，按页面提示开启服务并生成**授权码**。授权码不是 QQ 登录密码，具体入口和验证方式以 QQ 邮箱页面为准。可参考[获取授权码的说明](https://support.huaweicloud.com/usermanual-roma/roma_03_5025.html)。
2. 将 `config.example.json` 复制到仓库外的私有目录，例如 `C:\MailSenderPrivate\config.json`。在副本中保留其他字段及 `limits`，将下列字段替换为自己的值：

   ```json
   {
     "smtp_host": "smtp.qq.com",
     "smtp_port": 465,
     "transport": "ssl",
     "username": "123456789@qq.com",
     "sender": "my-alias@qq.com",
     "default_to": "123456789@qq.com",
     "password_env": "MAIL_SENDER_PASSWORD"
   }
   ```

   上面只是需要修改的字段，不是完整配置文件。`username` 是用于 SMTP 登录的完整 QQ 邮箱地址；`sender` 是该账号已启用并允许用于 SMTP 发信的别名；`default_to` 是自己要收信的地址。示例将收件地址设为 QQ 数字账号，也可填写自己的其他有效地址。QQ 邮箱对登录地址与发件别名的支持以账号实际设置和服务器验证为准；若别名被拒绝，改用与 `username` 相同的发件地址并检查邮箱设置。
3. 在运行脚本的 PowerShell 会话中安全输入授权码，不要将它写入配置文件或命令历史：

   ```powershell
   $secret = Read-Host '请输入 QQ 邮箱 SMTP 授权码' -AsSecureString
   $env:MAIL_SENDER_PASSWORD = [System.Net.NetworkCredential]::new('', $secret).Password
   Remove-Variable secret
   ```

   环境变量仅对当前进程及其后启动的子进程有效。不要把授权码提交到仓库或发送给 AI 助手。
4. 将邮件正文保存为仓库外的 UTF-8 文件，例如 `C:\MailSenderPrivate\body.txt`。在仓库目录运行下列命令，先进行干跑：

   ```powershell
   python scripts/send_mail.py --config 'C:\MailSenderPrivate\config.json' --subject '发给自己的测试邮件' --body-file 'C:\MailSenderPrivate\body.txt' --dry-run
   ```

   该命令使用配置中的 `default_to`；也可以用 `--to` 指定自己的收件地址。干跑不会连接 QQ 邮箱，因此不能验证授权码、别名或实际投递。确认收件地址和内容后，去掉 `--dry-run` 再运行一次；返回 `sent` 仅表示 SMTP 服务器已接受，请到收件箱（必要时检查垃圾邮件）确认。

## 使用

正文保存在仓库外的 UTF-8 文本文件中，以下路径和收件地址均为占位符：

```text
python scripts/send_mail.py --config <私有配置文件> --to <收件邮箱> --subject <主题> --body-file <正文文件> --dry-run
```

验证通过且确认发送后，去掉 `--dry-run` 运行相同命令。发送可能需要网络访问权限。`--dry-run` 会创建或读取本地状态数据库，但不连接 SMTP 或发信。退出码：0 为已发送或干跑通过；2 为限频拦截；1 为错误。

限频默认包括相邻成功发送间隔 600 秒、每自然小时最多 6 封、每日最多 30 封、相同收件人及内容 24 小时内去重；遇到指定 SMTP 拒绝码时冷却 30 分钟。相同数据库的调用会串行执行检查和发送，以避免并发绕过限频。发送遇到连接异常时结果可能不确定，先核对后再决定是否重试。

## 定时提醒

按需要使用操作系统计划任务或支持该 Skill 的 AI 应用调度。计划任务必须能访问配置、正文、状态数据库、环境变量和网络。电脑关机、本地程序未运行或环境变量未配置时，不能保证执行；云端运行不能直接访问本机配置和密钥。

## 本地检查

```text
python -m unittest discover -s tests
```

项目不包含发信账号、收件账号、真实凭据或运行日志。

# 明察鼠毫 Windows 桌面版

桌面版在不重写业务界面的前提下，将 Streamlit 工作台嵌入 Windows 原生窗口，并自动管理
FastAPI 后端、Agent 和前端三个本地服务。用户只需双击一个程序，不再需要打开浏览器或三个
PowerShell 窗口。

## 运行行为

- 双击 `MingChaShuHao.exe` 后显示启动页。
- 依次检查或启动研究数据服务、Agent 服务和桌面研究工作台。
- 服务就绪后在 WebView2 桌面窗口中进入系统，不显示浏览器地址栏。
- 关闭主窗口后，只结束由当前桌面程序创建的后台服务；已经存在的合法服务不会被误关。
- 数据库连接失败、端口冲突或服务异常时显示中文说明，并提供配置文件和日志入口。
- 程序使用单实例锁，重复双击不会再次启动一套服务。

## 构建桌面版

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File desktop/build.ps1
```

脚本会通过当前 Python 创建 `desktop/.venv` 专用构建环境，安装项目和桌面依赖、
生成软件图标，并使用 PyInstaller 生成目录版程序：

```text
desktop/dist/MingChaShuHao/MingChaShuHao.exe
```

目录版必须连同同目录的 `_internal` 一起使用，不能只复制单个 EXE。若电脑安装了 Inno Setup
6，构建脚本还会生成 `desktop/dist/MingChaShuHao-Setup-3.0.0.exe` 安装包。

构建脚本同时生成可迁移到其他 Windows 电脑的便携包：

```text
desktop/dist/MingChaShuHao-Portable-3.0.0.zip
```

解压整个压缩包后双击 `MingChaShuHao.exe`，不要在压缩包内部直接运行，也不要单独复制 EXE。

## 安装到本机

在项目根目录执行以下命令，可将成品安装到当前 Windows 用户的软件目录，导入当前
`agent/.env` 配置，并创建桌面与开始菜单快捷方式：

```powershell
powershell -ExecutionPolicy Bypass -File desktop/install.ps1
```

安装位置为 `%LOCALAPPDATA%\Programs\MingChaShuHao`，运行配置位于
`%LOCALAPPDATA%\MingChaShuHao\config\.env`。安装过程不会将 API 密钥写入 EXE、压缩包或
Git 仓库。

依赖已安装时可缩短构建时间：

```powershell
powershell -ExecutionPolicy Bypass -File desktop/build.ps1 -SkipInstall
```

## 本地配置与数据

首次运行自动创建：

```text
%LOCALAPPDATA%\MingChaShuHao\config\.env
```

数据库连接和百炼密钥均在该文件中配置。软件不会将密钥写入安装目录，也不会把本地配置打包
进 EXE。

运行数据按 Windows 应用约定保存：

```text
%LOCALAPPDATA%\MingChaShuHao\cache   视频、NWB 和 RAG 索引缓存
%LOCALAPPDATA%\MingChaShuHao\logs    三个服务的启动与运行日志
```

## 运行前提

- Windows 10 或 Windows 11；
- Microsoft Edge WebView2 Runtime，现代 Windows 通常已经内置；
- PostgreSQL 服务已启动，并存在 `IOT` 数据库；
- 使用 DANDI 远程资料和百炼 Agent 时需要网络；
- 完整 Agent 能力需要有效的 `DASHSCOPE_API_KEY`。

PostgreSQL 仍作为独立数据库服务使用，当前安装包不会静默安装或修改数据库软件。这样可以保留
现有数据，并避免安装程序在用户不知情时创建数据库管理员账号。

## 开发诊断

未构建 EXE 时可以直接运行桌面壳：

```powershell
python desktop/launcher.py
```

检查资源、依赖和端口状态：

```powershell
python desktop/launcher.py --diagnose
```

# 安装、运行与复现

## 1. 不调用模型的检查

安装 Python 3.12+、Git，并克隆仓库。评分工具与任务测试只使用标准库，不需要安装模型依赖。

```bash
git clone https://github.com/brakerham/mini-swe-agent-ability-test.git
cd mini-swe-agent-ability-test
python -m unittest discover -s tests -v
python -m benchmark validate
python -m benchmark selftest --output runs/selftest.json
python -m benchmark list
```

在 Windows PowerShell 中，`python` 可替换为指定版本的 `py -3.12`。如果某个步骤失败，先修复环境或基准；不要开始付费评测。

## 2. 建立独立的模型客户端环境

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-agent.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_mini_adapter.py -v
```

Linux/macOS：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-agent.txt
.venv/bin/python -m unittest discover -s tests -p test_mini_adapter.py -v
```

后续模型运行命令中的 `python` 使用上述虚拟环境的 Python。直接依赖固定为 mini-swe-agent 2.4.6、LiteLLM 1.93.1、OpenAI 客户端 2.26.0。这里的 OpenAI 客户端用于 DeepSeek 兼容接口，不需要 OpenAI API 密钥。`requirements-agent.txt` 固定直接依赖，未锁定全部间接依赖；每个实验会保存实际安装的完整版本清单 `packages.txt`。严格复现时应复用同一套完整依赖版本，比较不同实验时不要临时升级依赖。

适配器沿用 mini-swe-agent 的 `DefaultAgent` 和文本命令解析，通过其 Model 接口调用官方兼容 SDK。LiteLLM 是上游依赖，本配置不经过它发送请求。适配器测试使用伪造 HTTP 响应并阻断网络套接字，不需要密钥，不调用付费模型。尚未安装这些依赖时，标准库测试会跳过真实库适配器检查；安装后应重新运行这项检查。CI 分别运行标准库检查和安装固定依赖后的适配器检查。

## 3. 设置 DeepSeek 密钥

只使用 `DEEPSEEK_API_KEY` 环境变量，配置文件保留模型名称与非敏感参数。不要把密钥写进 `configs/`、脚本、命令行参数、候选目录或 Git。

PowerShell 可通过隐藏输入设置当前进程的环境变量：

```powershell
$deepseekSecret = Read-Host 'DeepSeek API key' -AsSecureString
$deepseekCredential = [System.Net.NetworkCredential]::new('', $deepseekSecret)
$env:DEEPSEEK_API_KEY = $deepseekCredential.Password
Remove-Variable deepseekCredential, deepseekSecret
```

Bash：

```bash
read -rsp 'DeepSeek API key: ' DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
printf '\n'
```

不要打印该变量。运行结束后，在 PowerShell 中用 `Remove-Item Env:DEEPSEEK_API_KEY`，Bash 中用 `unset DEEPSEEK_API_KEY` 清除当前会话值。

官方 API 文档列出的模型名为 `deepseek-v4-pro`，地址为 `https://api.deepseek.com`。参考 [DeepSeek API 文档](https://api-docs.deepseek.com/)。服务端模型可更新，因此每次实验都保留模型名、时间与配置摘要。

## 4. 准备 Docker 任务环境

Windows 使用 Docker Desktop 的 Linux 容器模式。运行下面的命令只构建代码执行环境，不调用模型：

```bash
docker version
docker build -f Dockerfile.task -t mini-swe-benchmark:v1 .
python -m benchmark selftest --docker --output runs/selftest-docker.json
```

可选的完整容器链路检查不调用模型。PowerShell 使用 `$env:BENCHMARK_DOCKER_TESTS='1'`，Bash 使用 `export BENCHMARK_DOCKER_TESTS=1`，随后运行：

```bash
python -m unittest discover -s tests -p test_docker_runtime.py -v
python -m benchmark selftest --docker --output runs/docker-selftest.json
```

完成后清除 `BENCHMARK_DOCKER_TESTS`。前一条命令检查实际任务复制、非特权用户、只读根目录、导出和独立评分；后一条校准全部六项任务。

模型客户端在主机运行，任务命令在容器运行。容器不联网、不接收密钥，独立验收测试和参考修复不挂载到 agent 容器。镜像 ID 和平台应随结果保存；首次构建可能下载基础镜像，正式实验不要在不同系统间混用未记录的镜像。

基础镜像标签不能永久固定内容。实验会解析实际镜像 ID，并在整批运行中使用同一 ID。长期复现还需要保存该镜像，例如用 `docker save -o task-image.tar mini-swe-benchmark:v1` 归档，迁移时用 `docker load -i task-image.tar` 恢复；镜像文件不要提交 Git。完整间接依赖同样以本批次的 `packages.txt` 为准。

## 5. 先跑一项，再跑完整批次

以下命令开始调用付费模型。默认配置使用非思考模式、temperature 0、每次最多输出 4096 token、最多 60 步、请求超时 90 秒、命令超时 30 秒、每次任务总时限 900 秒。适配器关闭模型 API 自动重试。先阅读配置并确定预算：

```bash
python -m benchmark run --task 01-money --output runs/deepseek-v4-pro-smoke --config configs/deepseek-v4-pro.json --repetitions 1 --allow-paid
python -m benchmark report --runs runs/deepseek-v4-pro-smoke --output runs/deepseek-v4-pro-smoke/report.json
```

确认运行链路、模型身份、终止状态与独立评分结果后，使用新的输出目录运行完整批次：

```bash
python -m benchmark run --task all --output runs/deepseek-v4-pro-3reps --config configs/deepseek-v4-pro.json --repetitions 3 --allow-paid
python -m benchmark report --runs runs/deepseek-v4-pro-3reps --output runs/deepseek-v4-pro-3reps/report.json
```

完整批次是 6 项 × 3 次，即 18 次独立尝试。不要复用旧输出目录覆盖失败记录。不要向 agent 透露前一次验收失败的信息；每次都使用初始任务与新对话。

不要把 `--allow-paid` 加到 CI、自动安装步骤或离线自检中。步数和超时不能保证准确的费用上限；如需控制实际支出，在供应商账户另设额度。

## 6. 手动提交与评分

准备一个任务：

```bash
python -m benchmark prepare --task 01-money --output runs/manual-money
```

将生成的候选项目交给 agent，需求位于其中的 `ISSUE.md`。源码修改范围以 `tasks/manifest.json` 的 `allowed_paths` 为准；另允许在 `tests/` 下编写、修改或删除 Python 测试，作为过程证据。评分时始终恢复原版公开测试，不给 agent 自写测试计分。其他文件不允许改动。完成后在评测仓库根目录执行：

```bash
python -m benchmark grade --task 01-money --candidate runs/manual-money --output runs/manual-money-result.json
```

该命令的本机模式会执行候选代码，只用于可信代码。对于模型生成或其他不可信提交，构建任务镜像后使用隔离评分：

```bash
python -m benchmark grade --task 01-money --candidate runs/manual-money --output runs/manual-money-result.json --docker
```

评分器从干净初始项目应用允许的源码变更，再使用原版公开测试和独立验收测试。候选目录中的测试改动不会成为评分依据。

## 7. 发布实验结果

报告至少包含基准提交号、六项任务的逐次结果、resolved 分子/分母、部分分、配置、重复次数、版本、镜像信息、耗时、终止原因及可获得的用量。`plan.json` 保存固定的任务计划与环境摘要；每项重复目录保存候选项目、提交、补丁、模型轨迹和结果。`report.json` 依据计划汇总，结果缺失的尝试保留在分母中。没有实际模型运行时，只能报告基准工具的验证状态。

| 文件 | 用途 |
| --- | --- |
| `plan.json` | 预定分母、任务和工具摘要、模型配置、版本与镜像信息 |
| `packages.txt` | 本批次实际安装的完整依赖版本 |
| `<任务 ID>/rep-XX/result.json` | 本次自主完成状态、独立测试结果、用量和耗时 |
| `<任务 ID>/rep-XX/agent.json` | agent 终止原因与模型返回的用量摘要 |
| `<任务 ID>/rep-XX/trajectory.json` | agent 命令、观察结果及模型轨迹 |
| `<任务 ID>/rep-XX/submission.diff` | 候选修改的可审阅补丁 |
| `report.json` | 按全部计划尝试汇总的主要与辅助指标 |

如果某次运行在生成某份证据前中断，该文件可能不存在；汇总中的异常和缺失项应照常报告。

保留失败尝试和异常；无法运行的尝试标为缺失或 `not_run`。如果修改了基础设施后重跑，使用新目录并解释影响范围。分享前检查轨迹、命令输出和补丁，避免泄露密钥或私人代码。

## 常见问题

| 现象 | 检查方法 |
| --- | --- |
| 找不到 `benchmark` | 在本仓库根目录执行命令，检查当前 Python 环境 |
| 找不到模型依赖 | 使用虚拟环境的 Python 安装 `requirements-agent.txt` |
| Docker 无法连接 | 启动 Docker Desktop，并确认使用 Linux 容器 |
| API 认证失败 | 检查当前进程是否设置 `DEEPSEEK_API_KEY`，不要打印值 |
| 模型名或参数被拒绝 | 核对官方模型文档和冻结配置；不要静默改模型 |
| 输出目录已存在 | 使用新的实验名称，保留旧记录 |
| agent 超时或用尽步数 | 保留失败结果，若调整预算则对完整比较批次统一调整 |
| 本机评分通过但 Docker 失败 | 检查路径大小写、依赖与 Python 版本，以正式实验环境为准 |
| 费用未知 | 保留未知值，在供应商账单核实，不能推断为零费用 |

# mini-swe-agent × DeepSeek V4 Pro 能力评测

这套基准用六个独立的 Python 工程任务，检查 agent 能否阅读代码、定位问题、修改实现、运行测试，并在边界条件下保持原有行为。它包含任务代码、公开测试、独立验收测试、参考修复和评分工具；准备、评分与自检均可离线完成，无需 API 密钥。

这是一个可复现的、小规模合成工程基准。它适合比较相同条件下的 agent 配置、发现能力短板；结果不能换算成 SWE-bench 成绩，也不能代表所有真实仓库的工程能力。仓库中的验收测试和参考修复是公开资料，正式运行时只把任务目录交给 agent。详见[评测协议](docs/PROTOCOL.md)。

## 先验证评测工具

需要 Python 3.12+ 和 Git。以下命令不会调用模型：

```bash
git clone https://github.com/brakerham/mini-swe-agent-ability-test.git
cd mini-swe-agent-ability-test
python -m unittest discover -s tests -v
python -m benchmark validate
python -m benchmark selftest --output runs/selftest.json
python -m benchmark list
```

`selftest` 检查每个任务的公开测试在初始版本通过、验收测试能够发现缺陷、参考修复满足全部要求。它证明评测任务和评分链路可用，不代表模型已经完成任何任务。

## 任务范围

| 任务 | 主要观察能力 |
| --- | --- |
| `01-money` | 金额计算、精度与边界处理 |
| `02-config` | 配置合并、默认值与兼容性 |
| `03-pagination` | 分页接口、游标与稳定行为 |
| `04-dependencies` | 依赖图、顺序与错误处理 |
| `05-cache` | 缓存语义、有效期与状态变化 |
| `06-records` | 数据记录处理、校验与输入边界 |

每个任务的完整需求以 `tasks/<任务 ID>/issue.md` 为准。每次尝试从同一份初始代码开始，各任务互不继承补丁或对话。

## 手动试跑一个任务

```bash
python -m benchmark prepare --task 01-money --output runs/manual-money
```

把生成的任务需求和候选目录交给 agent，在候选目录中进行修改。不要把整个评测仓库作为 agent 的工作目录。完成后评分：

```bash
python -m benchmark grade --task 01-money --candidate runs/manual-money --output runs/manual-money-result.json
```

手动模式在本机执行候选代码，仅适合你信任的代码。运行模型或处理不可信候选时使用 Docker，具体步骤见[运行手册](docs/RUNBOOK.md)。

## 使用 DeepSeek V4 Pro

正式运行需要 Docker 的 Linux 容器、单独的 Python 环境、`requirements-agent.txt` 中固定版本的依赖，以及由你设置的 `DEEPSEEK_API_KEY` 环境变量。密钥只在主机上的模型客户端使用，不会传给任务容器。不要把密钥写进配置、命令参数、Git 或评测结果。

```bash
python -m pip install -r requirements-agent.txt
docker build -f Dockerfile.task -t mini-swe-benchmark:v1 .
python -m benchmark run --task all --output runs/deepseek-v4-pro-r1 --config configs/deepseek-v4-pro.json --repetitions 1 --allow-paid
python -m benchmark report --runs runs/deepseek-v4-pro-r1 --output runs/deepseek-v4-pro-r1/report.json
```

**最后两条中的 `run --allow-paid` 会调用付费 API。** 本仓库的测试和 CI 不会执行它。建议先评测一个任务，确认接口与成本记录，再按预先确定的配置运行全部六项。正式对比建议每项至少三次独立尝试，完整报告所有尝试，不挑选最好的一次。

配置中的官方模型名为 `deepseek-v4-pro`，接口地址为 `https://api.deepseek.com`，来自 [DeepSeek 官方文档](https://api-docs.deepseek.com/)。mini-swe-agent 的接口以固定依赖版本为准，升级后应重新执行适配器测试和自检。详见[安装与复现步骤](docs/RUNBOOK.md)。

## 结果怎么读

主要指标是 **resolved rate**：所有预定任务尝试中，agent 在预算内主动提交、提交完整合规，并同时通过公开测试、功能验收和回归验收的比例。另报告功能测试部分分、逐项任务表现、耗时、终止原因及实际可获得的用量记录。未知费用保留为未知，不用估算值冒充账单。

[评分规则](docs/SCORING.md)规定完整通过、部分完成、失败、超时和基础设施错误的区别。[评测协议](docs/PROTOCOL.md)说明预算、公平比较、污染风险与证据保留方式。

## 仓库结构

```text
benchmark/                 准备、运行、隔离评分和汇总工具
configs/                   无密钥模型配置
tasks/manifest.json        任务 ID、权重和允许修改的文件
tasks/<id>/candidate/      agent 可见的初始项目与公开测试
tasks/<id>/issue.md        任务需求
tasks/<id>/evaluator/      仅评分阶段使用的独立验收测试
tasks/<id>/gold/           参考修复，供基准自检使用
tests/                     评测工具与任务集的自动化测试
docs/                      协议、评分与运行手册
Dockerfile.task            无模型密钥的任务运行环境
requirements-agent.txt     固定版本的模型运行依赖
.github/workflows/ci.yml   不调用模型的自动检查
```

不要把 `runs/`、本地环境变量文件、模型凭据或完整未审阅轨迹提交到仓库。分享结果前检查补丁、日志和轨迹中是否包含敏感信息。

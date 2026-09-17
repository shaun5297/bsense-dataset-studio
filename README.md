# BSense Dataset Studio

面向“脑状态安检”研究的多模态认知准备度采集与数据集构建平台。

当前 `0.2.0` 目标是支持**小规模端到端试采**，不是未经验证的正式批量采集工具，也不输出“正常、建议复测、建议休息”等岗位建议。

## 当前采集入口

- `deviceqc`：设备质量检查，不作为认知状态训练样本；
- `m6_readiness_reference`：正式参考采集，默认包含完整背景、采前/采后 KSS、60 秒睁眼基线、12 个 SART 练习、180 个正式 SART 试次和 PVT-B；

桌面默认选择 `m6_readiness_reference`，用于本轮正式研究数据的试采。现场短流程 `m6_readiness_field` 已停用，不再出现在协议列表或预设中，也不能从代码入口启动。PVT-B 固定保留。

让同学采集时使用不同匿名被试编号；同一人重复采集时更换 Session/Run。先按下方试采验收要求完成 3–5 人真实设备验证，再扩大采集。协议名称中的“正式参考”不代表设备或研究标签已经完成验证。

SART 正式任务使用 8 套可复现的平衡序列，按匿名被试、Session 和 Run 确定性轮换。每个 Run 会记录 `sequence_set_id`、随机种子和 No-Go 位置。

## 快速开始

```bash
bash "macos/setup.sh"
bash "macos/run.sh"
```

桌面界面支持：

1. 设置匿名被试、Session、Run 和数据根目录；
2. 选择研究协议并预览完整阶段；
3. 扫描 LSL 设备；
4. 点击“开始试采”，创建 Marker 流并启动 8 路 XDF 录制；
5. 按状态机执行表单、基线、SART 和 PVT；
6. 保存 SART/PVT 试次级 Marker 和区间人工标注；
7. 停止录制并生成 context 与分窗质量报告。

默认数据根目录：

```text
~/BSenseDatasets/braincheck
```

也可以在启动时指定：

```bash
bsense-dataset-studio --dataset-root "/Volumes/BCI-DATA/braincheck"
```

## 数据集构建

```bash
bsense-dataset-build --dataset-root "/path/to/dataset_root"
bsense-dataset-validate --dataset-root "/path/to/dataset_root"
```

构建命令输出：

- `derived/features/records.csv`：Run 级清单、背景、KSS、SART、PVT、质量和参考标签；
- `derived/labels/*_reference_label.json`：版本化、可追溯的研究参考标签；
- `derived/eegnet/eeg_windows.npz`：`X[N,C,T]` 与二分类 `y`；
- `derived/eegnet/eeg_windows.jsonl`：每个 EEG 窗口的被试、阶段、质量与标签来源；
- `manifests/dataset_manifest.json`：数据清单和被试级 train/validation/test 划分。

EEGNet 默认使用 4 秒窗口、2 秒步长和 250 Hz 目标采样率，只保留：

```text
baseline_open 或 sart_assessment
+ reference_state_label 为 alert/impaired
+ Run 与窗口 EEG 质量合格
+ 无 Motion 伪迹
+ 不与人工排除区间重叠
```

如设备 EEG 采样率不是 250 Hz：

```bash
bsense-dataset-build \
  --dataset-root "/path/to/dataset_root" \
  --target-srate 你的目标采样率
```

## EEGNet 训练与导出

已实现两通道 EEGNet 训练、模型导出及 BrainCheck 推理协议。

```bash
python -m pip install -e ".[training]"
bsense-eegnet-train --dataset "/path/eeg_windows.npz" --output "/path/new-model"
```

默认要求被试互斥且两类齐全的 train/validation/test，验证集用于早停和校准。
显式 `--pilot-fit-only --epochs 20` 可进行全数据工程拟合，不生成独立验证成绩或校准阈值。
`bsense-dataset-build --quality-profile pilot_clean_windows` 可从仅因整体运动比例被拒的记录提取逐窗合格数据，保留原始 QC。

本次真实数据拟合使用 3 位受试者、4 次记录、363 个窗口，模型已接入 BrainCheck。
该规模不支持独立性能结论。完整参数、来源和两种训练模式见 [训练与导出说明](docs/EEGNET_TRAINING.md)。

## 标签边界

`reference-label-v1-provisional` 仅使用 KSS、PVT、SART、睡眠与连续清醒信息，不使用 EEG 特征，避免循环定义。该规则仍需通过试采和统计分析校准，`uncertain` 样本默认不进入二分类训练。

质量标签只决定 Run、模态或窗口是否可用，不是疲劳或清醒标签。详细定义见 [数据与标签说明](docs/DATA_AND_LABELS.md)。

## 正式采集门槛

代码测试通过不等于硬件链路通过。开始批量招募前，必须使用真实设备完成至少 3–5 人试采，并逐项满足 [小规模试采验收清单](docs/PILOT_ACCEPTANCE.md)。

## 数据目录

```text
dataset_root/
├── restricted/participants/     # 直接身份信息，受限访问
├── raw/sub-*/ses-*/             # XDF、事件和 context，只追加
├── quality/                     # Run 与 4 秒窗口质量报告
├── annotations/                 # 区间人工标注 JSONL
├── derived/
│   ├── features/                # Run 级汇总
│   ├── labels/                  # 研究参考标签
│   └── eegnet/                  # EEG 窗口数组与元数据
└── manifests/                   # 清单与被试级划分
```

原项目中的运动想象、N-Back、疲劳诱导、意图、目标注意和 P300 等独立协议不属于当前比赛项目，已从本工程移除。详细迁移边界见 [MIGRATION.md](MIGRATION.md)。

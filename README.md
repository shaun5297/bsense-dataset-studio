# BSense Dataset Studio

面向“脑状态安检”项目的多模态认知准备度数据采集平台。

本工程只提供两个采集入口：

- 设备质量检查；
- 脑安检研究采集。

脑安检研究采集包含背景信息、信号质量检查、睁眼基线、3 分钟 SART 和结束记录。PVT-B 仅作为可选研究参照，默认关闭。

本工程的产出是可复现、可审计、可训练的数据集，不输出“正常、建议复测、建议休息”等岗位建议。产品推理与结果展示由独立的 `braincheck-readiness` 负责。

## 快速开始

```bash
bash "macos/setup.sh"
bash "macos/run.sh"
```

常用入口：

```bash
bsense-dataset-monitor
bsense-dataset-build --dataset-root ./dataset_root
bsense-dataset-validate --dataset-root ./dataset_root
```

预览默认脑安检采集流程：

```bash
bsense-dataset-studio --preview m6_readiness_study
```

仅在需要独立行为参照时启用 PVT-B：

```bash
bsense-dataset-studio --preview m6_readiness_study --include-pvt
```

桌面界面采用左右两栏：左侧管理实验标识、协议和设备状态，右侧以可滚动阶段表显示预计时长、阶段说明和选中详情。SART 的练习及 180 个正式试次会聚合显示，不会逐条占满预览区域。

原项目中的运动想象、N-Back、疲劳诱导、意图、目标注意和 P300 等独立协议不属于当前比赛项目，已从本工程移除；历史实现仍完整保留在原始 `bsense-lsl` 仓库。

## 数据边界

```text
dataset_root/
├── restricted/participants/     # 直接身份信息，受限访问
├── raw/sub-*/ses-*/             # XDF、事件和上下文，只追加
├── quality/                     # 与受试状态解耦的质量报告
├── annotations/                 # 实验员人工标注 JSONL
├── derived/                     # 可重建的行为、特征和窗口
└── manifests/                   # 数据清单与被试级划分
```

详细迁移边界见 [MIGRATION.md](MIGRATION.md)。

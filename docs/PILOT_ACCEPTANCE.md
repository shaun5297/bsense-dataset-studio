# 小规模试采验收清单

在正式批量招募前，至少完成 3–5 名受试者、多个独立 Session 的真实设备试采。

## 每个 Run 必须满足

- [ ] XDF 可由 `pyxdf` 正常打开；
- [ ] EEG、fNIRS、Motion、Metric、Heart Rate、BioMultiLite Marker、General Metric、Experiment Marker 共 8 路流齐全且唯一；
- [ ] EEG 恰好为预期 2 通道，通道名称和顺序明确；
- [ ] 实际采样率与 nominal srate 合理一致；
- [ ] 每路流包含 clock offset 记录，时间戳无倒序；
- [ ] `experiment_start` 与 `experiment_end` 各一条；
- [ ] SART 正式 `sart_trial_result` 恰好 180 条，trial 为 1–180 且无重复；
- [ ] 正式参考协议的 PVT start/end 和 trial result 完整；
- [ ] 所有 Marker 位于 XDF 时间范围内；
- [ ] context 与文件名中的 participant/session/task/run 一致；
- [ ] KSS、睡眠、连续清醒、班次、条件和首测/复测字段完整；
- [ ] quality 报告存在且包含分窗质量；
- [ ] 人工区间标注可以保存并正确排除重叠窗口；
- [ ] 研究参考标签包含版本、来源、置信度和理由；
- [ ] EEGNet 文件形状为 `[N,2,T]`，元数据行数与 N 一致；
- [ ] train/validation/test 被试无交叉。

## 自动检查

```bash
bsense-dataset-build --dataset-root "/path/to/dataset_root"
bsense-dataset-validate --dataset-root "/path/to/dataset_root"
```

自动校验通过后，仍需人工抽查至少一个 Run 的：

1. EEG 波形和通道顺序；
2. SART 刺激、按键和 result Marker 对齐；
3. PVT 刺激与反应时间；
4. Motion 伪迹与人工标注区间；
5. `alert/impaired/uncertain` 标签的独立来源。

## 停止条件

任一 Run 出现 XDF 无法回读、流缺失、Marker 数不一致、时间越界、覆盖旧 Run、标签来源不可追溯时，应停止正式采集并修复，不得用后处理静默填补。

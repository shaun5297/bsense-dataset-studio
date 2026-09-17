# 自采 EEGNet 训练与 BrainCheck 导出

## 最新状态：先导训练已完成

2026-09-17新增显式 `pilot_clean_windows` 配置：整run仅因运动比例被拒时，允许重新提取逐窗EEG/Motion门控合格的数据，原始QC报告不改写。
主批次实际得到363窗（alert110、impaired253），3位受试者、4次run。
使用 `bsense-eegnet-train --pilot-fit-only --epochs 20` 完成真实数据固定轮次拟合，导出并装入BrainCheck。
此模式明确把全部合格窗口用于拟合，包括旧划分中的数据，因此旧test不再是此模型的独立留出集。没有验证集、测试成绩、温度或决策阈值校准，不报告泛化准确率。
训练导出默认只允许shadow推理。用户随后授权参与四态判断，部署清单添加了明确标记的pilot_assisted工程策略，详见BrainCheck部署文档；没有生成验证集校准阈值。严格模式原有的三组被试检查保持不变。
输出在 `/Users/shaun/BCI/outputs/readiness_eegnet/20260917-pilot-relaxed/`。
下文“本地数据核验”记录的是放宽前的严格模式结果。

这条链路使用非 EEG 的 provisional reference label。训练命令不会把睁/闭眼、
N-back 难度或 `uncertain` 改写为 alert/impaired，严格配置保留已有 run 级质量门控；pilot_clean_windows采用上文注明的放宽策略。

## 命令

在独立虚拟环境安装本仓库 `.[training]`，先运行已有的 `bsense-dataset-build`。
随后执行：

```bash
bsense-eegnet-train --dataset "/path/derived/eegnet/eeg_windows.npz" --output "/path/new-model-export"
```

NPZ 旁必须保留同名 `.jsonl` 与 `.summary.json`。需要重新构建旧版未声明
`data_origin` 的导出。输出目录必须为空，已有模型不会被覆盖。

## 严格模式的准入与评估

- 输入固定为 `[N,2,1000]`、250 Hz、4 s 窗、2 s 步长及一致的通道顺序。
- 三组被试必须互不重叠，train/validation/test 各自必须覆盖两类。
  这只是软件最低条件，不表示样本量已足以支持推广。
- 训练采用紧凑 EEGNet 变体、随机初始化、CPU 可复现训练；不是预训练微调。
  通道缩放仅从训练组估计。加权抽样平衡被试-类别贡献。
- 验证集按每 run 的平均窗口概率、再按被试等权统计选择 epoch。
  温度与二分类阈值也只在验证集拟合。不能将重叠窗口当成独立被试。
- 权重与校准参数写出后才评估一次 test；测试结果不反过来选模型或阈值。
  测试集缺少双类时直接拒绝，而不是报告貌似正常的二分类 BA。

导出 `braincheck_eegnet.pt`、`model_manifest.json`、`training_report.json`。
`.pt` 是 TorchScript 推理包，包含去均值、1–40 Hz FFT 带通、训练通道缩放及
验证集温度；推理包从重采样后的 `[N,2,1000]` 原始波形计算两类参考概率。
通道名、预处理、被试划分、模型/数据 SHA256 与运行版本保存在 manifest。
目前使用 TorchScript 兼容路径（PyTorch 已弃用该导出 API）；部署应使用与
训练相同的 PyTorch 版本并做导出一致性测试，不承诺任意版本互通。

## 接入 BrainCheck

将完整导出目录复制到部署机，在 BrainCheck 的独立环境安装 `.[inference]`：

```bash
braincheck --model-manifest "/path/model_manifest.json" --eegnet-mode shadow
```

`shadow` 记录模型证据，但四态仍采用现有规则。显式选择 `assisted` 后，
验证集校准 BA 必须大于机会水平，模型才可增加风险证据；该条件不是部署
有效性的证明。低 EEG 风险不能覆盖高规则风险，首测不会因模型直接变为
建议休息，质量失败优先输出无法评估。

当前 `fNIRS` 保留特征与质量门控作用，未新增没有校准依据的疲劳评分。
Motion 只承担数据可靠性判断。模型概率对应参考标签，不是医学诊断概率。

## 2026-09-17 本地数据核验

核验 `/Users/shaun/BCI/data/braincheck/raw/BRAINDATA1` 与 `BRAINDATA2`：
12 次参考采集的现有 QC 报告均为 reject，实际构建得到 0 个训练窗口。
标签共 impaired 3、alert 1、uncertain 8。alert 只来自 P0086，当前无法在
被试互斥的三组中覆盖两类；两个批次的 P001 身份对应关系也未确认，未混合。

因此最初严格模式未生成训练权重。后续显式先导配置已完成拟合并部署，见本文开头。
严格模式的审计与拒绝日志在
`/Users/shaun/BCI/outputs/readiness_eegnet/20260917/`。
运动阈值须结合设备单位与现场伪迹核验；不要仅为得到训练数据而上调阈值。
补采应使每个划分都有来自不同被试的两类有效参考记录，并保留 uncertain。

工程测试使用显式 `synthetic_test_fixture`。此类模型被默认现场加载器拒绝，
不能用于论文性能、答辩自采训练成果或现场判断。

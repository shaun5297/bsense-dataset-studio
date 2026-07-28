# 数据与标签说明

## 五层标签

### 1. 实验条件

`study_condition` 描述采集条件，不等于脑状态真值：

- `rested_control`
- `natural_fatigue`
- `post_night_shift`
- `post_shift`
- `post_rest_retest`
- `sleep_restricted`
- `unknown_naturalistic`

同时记录 `condition_source`，区分实验员分配、排班推导和受试者报告。

### 2. 任务阶段

EEGNet 第一版只使用：

- `baseline_open`
- `sart_assessment`

表单、设备调整、练习、切换和 PVT 不混入 EEG 分类窗口。

### 3. 试次级行为

SART 的唯一聚合来源是 `sart_trial_result`。每条结果包含：

- trial、stimulus、trial_kind；
- should_respond、responded、response_count；
- outcome、correct、false_start、multiple_response；
- stimulus/response/result timestamp；
- valid 与 invalid_reason。

PVT 使用 `pvt_trial_result`，显式区分 `responded`、`lapse`、`timeout` 和 `false_start`。

### 4. 质量

质量报告采用 `quality_schema_version=1.1`，同时保存 Run 级汇总和 4 秒窗口记录。质量只控制数据是否可用，不作为认知状态分类目标。

### 5. 研究参考状态

`reference-label-v1-provisional` 输出：

- `alert`
- `impaired`
- `uncertain`

来源限于 KSS、PVT、SART、睡眠和连续清醒信息，明确不使用 EEG。规则属于待校准研究标签，不是医学诊断、岗位结论或已验证量表。

第一版 EEGNet 只训练 `alert` 与 `impaired`；`uncertain` 保留用于误差分析。

## 数据划分

训练、验证和测试必须按受试者划分。不得随机拆分同一受试者的相邻 EEG 窗口。

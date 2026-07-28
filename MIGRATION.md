# 从 bsense-lsl 的迁移

| 原职责 | 新模块 | 处理 |
|---|---|---|
| `app.py` | `app/`、`acquisition/`、`protocols/` | UI、录制、协议与标注分离 |
| `protocols.py` | `protocols/device_qc.py`、`protocols/readiness_study.py` | 只保留设备质检和脑安检研究采集 |
| `live.py` | `acquisition/live_streams.py` | 保留无 GUI 的线程安全缓存 |
| `embedded_recorder.py` | `acquisition/recorder.py` | 固定流选择，禁止覆盖 |
| `xdf_writer.py` | `acquisition/xdf_writer.py` | 保留 XDF 写入边界 |
| `participant.py` | `participants/` | 身份、同意与匿名编号分离 |
| `readiness.py` | `behavior/sart.py` | 只迁移行为分类和聚合 |
| `pvt.py` | `behavior/pvt.py` | 作为研究参照保留 |
| `monitor.py` | `app/operator_view.py` | 仅面向实验员 |

原 `rules_v1_provisional` 不进入采集端公开结果，也不作为唯一标签来源。产品化判定、个人基线和复测闭环迁入独立的 `braincheck-readiness`。

以下独立协议已从 Dataset Studio 删除：

- M0 独立基线；
- M1 运动想象；
- M2 N-Back；
- M3A 安全动作；
- M3B 疲劳诱导；
- M4A 提示后意图；
- M4B 目标注意；
- M5 独立结束问卷；
- M7 P300。

原 `m6_readiness_study` 在 `0.2.0` 中拆分为：

- `m6_readiness_reference`：训练与验证参考采集，PVT-B 固定启用；
- `m6_readiness_field`：现场外部验证与领域适配，PVT-B 固定关闭。

`build("m6_readiness_study")` 仅保留为代码迁移兼容入口，不再出现在桌面协议列表中。

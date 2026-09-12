# 真实数仓架构识别

Warehouse Agent 可以基于从 DolphinScheduler MySQL 导出到 `data/source/` 的真实 SQL，识别现有数仓分层、主题域、主题和表级血缘。

## 使用顺序

1. 在“DolphinScheduler”页面同步真实 SQL。
2. 在“现有代码”确认 SQL 已经可查看。
3. 打开“数仓架构”。
4. 点击“重新识别数仓”。
5. 查看 ODS / DWD / DWS / ADS / DIM / UNKNOWN 数量。
6. 点击主题域筛选模型。
7. 点击具体模型查看识别依据和上下游。

## API

```text
POST /api/warehouse/scan
GET  /api/warehouse/overview
GET  /api/warehouse/domains
GET  /api/warehouse/models
GET  /api/warehouse/models/{id}
GET  /api/warehouse/lineage?table=dwd.dwd_xxx
```

### 扫描

```bash
curl -X POST http://127.0.0.1:8000/api/warehouse/scan
```

扫描会先重建 SQL 表级血缘，然后重新生成 `warehouse_model` 识别结果。

## 识别逻辑

### 分层

优先根据数据库名和表名前缀识别：

- `ods_` / `ods.` / `stg_` → ODS
- `dwd_` / `dwd.` → DWD
- `dws_` / `dws.` → DWS
- `ads_` / `ads.` → ADS
- `dim_` / `dim.` → DIM
- 无法识别 → UNKNOWN

### 主题域和主题

结合以下上下文：

- DS 项目名
- DS 工作流名
- DS Task 名
- 目标表名
- 上游表名
- 下游 SQL 使用关系

第一版使用可解释规则进行识别，例如：

- order / payment / refund / 订单 / 支付 / 退款 → 交易域
- user / member / 用户 / 会员 → 用户域
- product / sku / 商品 / 类目 / 品牌 → 商品域
- campaign / coupon / 营销 / 活动 / 优惠券 → 营销域
- inventory / purchase / 库存 / 采购 → 供应链域
- finance / cost / revenue / 财务 / 成本 / 收入 → 财务域
- region / date / city / 地区 / 日期 / 城市 → 公共域

主题会继续细分，例如交易域下的订单主题、支付主题、退款主题、售后主题、结算主题。

## 为什么先不用 LLM

第一轮识别先使用确定性的规则，因为：

- 容易验证；
- 同样输入得到同样结果；
- 可以明确展示推断依据；
- 不会因为模型波动直接改变现有数仓归类。

后续可以增加 LLM 二次识别，只处理 `UNKNOWN` 或低置信度模型，并要求人工确认后持久化。

## 数据边界

扫描只分析 `source/` 和 Warehouse Agent 自己的元数据库，不修改 DolphinScheduler，也不修改生产数仓表。

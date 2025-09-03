# ISIM 电费查询系统 API 文档

## 概述

ISIM（Integrated Student Information Management）电费查询系统是为安徽财经大学学生提供的后勤电费查询服务。通过该系统，学生可以：

- 选择和绑定宿舍房间
- 查询电费余额和用电记录
- 查看充值记录

## API 端点

### 认证

所有API都需要通过认证令牌（authme_token）进行身份验证。认证信息通过依赖注入自动处理。

### 房间选择器 API

#### 1. 获取楼栋列表

**POST** `/api/v1/isim/picker/building/get`

获取所有可选择的楼栋信息。

**响应示例：**
```json
{
  "code": 0,
  "message": "楼栋列表获取成功",
  "data": [
    {
      "code": "11",
      "name": "北苑11号学生公寓"
    },
    {
      "code": "12", 
      "name": "北苑12号学生公寓"
    }
  ]
}
```

#### 2. 设置楼栋并获取楼层列表

**POST** `/api/v1/isim/picker/building/set`

设置楼栋并获取对应的楼层列表。

**请求参数：**
```json
{
  "building_code": "11"
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "楼层列表获取成功",
  "data": [
    {
      "code": "010101",
      "name": "1-1层"
    },
    {
      "code": "010102",
      "name": "1-2层"
    }
  ]
}
```

#### 3. 设置楼层并获取房间列表

**POST** `/api/v1/isim/picker/floor/set`

设置楼层并获取对应的房间列表。

**请求参数：**
```json
{
  "floor_code": "010101"
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "房间列表获取成功",
  "data": [
    {
      "code": "01",
      "name": "1-101"
    },
    {
      "code": "02",
      "name": "1-102"
    }
  ]
}
```

#### 4. 绑定房间

**POST** `/api/v1/isim/picker/room/set`

绑定房间到用户账户。

**请求参数：**
```json
{
  "building_code": "11",
  "floor_code": "010101", 
  "room_code": "01"
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "房间绑定成功",
  "data": {
    "building": {
      "code": "11",
      "name": "北苑11号学生公寓"
    },
    "floor": {
      "code": "010101",
      "name": "1-1层"
    },
    "room": {
      "code": "01", 
      "name": "1-101"
    },
    "room_id": "01",
    "display_text": "北苑11号学生公寓/1-1层/1-101"
  }
}
```

### 电费查询 API

#### 5. 获取电费信息

**POST** `/api/v1/isim/electricity/info`

获取电费余额和用电记录信息。

**响应示例：**
```json
{
  "code": 0,
  "message": "电费信息获取成功",
  "data": {
    "balance": {
      "remaining_purchased": 815.30,
      "remaining_subsidy": 2198.01
    },
    "usage_records": [
      {
        "record_time": "2025-08-29 00:04:58",
        "usage_amount": 0.00,
        "meter_name": "1-101"
      },
      {
        "record_time": "2025-08-29 00:04:58", 
        "usage_amount": 0.00,
        "meter_name": "1-101空调"
      }
    ]
  }
}
```

#### 6. 获取充值信息

**POST** `/api/v1/isim/payment/info`

获取电费余额和充值记录信息。

**响应示例：**
```json
{
  "code": 0,
  "message": "充值信息获取成功",
  "data": {
    "balance": {
      "remaining_purchased": 815.30,
      "remaining_subsidy": 2198.01
    },
    "payment_records": [
      {
        "payment_time": "2025-02-21 11:30:08",
        "amount": 71.29,
        "payment_type": "下发补助"
      },
      {
        "payment_time": "2024-09-01 15:52:40",
        "amount": 71.29, 
        "payment_type": "下发补助"
      }
    ]
  }
}
```

#### 7. 检查房间绑定状态

**POST** `/api/v1/isim/room/binding/status`

检查用户是否已绑定宿舍房间。

**已绑定响应示例：**
```json
{
  "code": 0,
  "message": "用户已绑定宿舍房间",
  "data": {
    "is_bound": true,
    "binding_info": {
      "building": {
        "code": "35",
        "name": "西校荆苑5号学生公寓"
      },
      "floor": {
        "code": "3501",
        "name": "荆5-1层"
      },
      "room": {
        "code": "350116",
        "name": "J5-116"
      },
      "room_id": "350116",
      "display_text": "西校荆苑5号学生公寓/荆5-1层/J5-116"
    }
  }
}
```

**未绑定响应示例：**
```json
{
  "code": 0,
  "message": "用户未绑定宿舍房间",
  "data": {
    "is_bound": false,
    "binding_info": null
  }
}
```

## 错误处理

### 标准错误响应

```json
{
  "code": 1,
  "message": "错误描述信息"
}
```

### 认证错误响应

```json
{
  "code": 401,
  "message": "Cookie已失效或不在VPN/校园网环境，请重新登录"
}
```

### 常见错误代码

- `0`: 成功
- `1`: 一般业务错误
- `400`: 请求参数错误或未绑定房间
- `401`: 认证失败
- `500`: 服务器内部错误

### 特殊错误情况

#### 未绑定房间错误

当用户尝试查询电费或充值信息但未绑定房间时，会返回特定错误：

```json
{
  "code": 400,
  "message": "请先绑定宿舍房间后再查询电费信息"
}
```

或

```json
{
  "code": 400, 
  "message": "请先绑定宿舍房间后再查询充值信息"
}
```

## 使用流程

### 房间绑定流程
1. **检查绑定状态**：调用房间绑定状态API检查是否已绑定
2. **首次绑定**（如果未绑定）：
   - 调用楼栋列表API获取所有楼栋
   - 调用楼栋设置API获取楼层列表
   - 调用楼层设置API获取房间列表
   - 调用房间绑定API完成房间绑定

### 查询流程
1. **确认绑定**：确保用户已绑定房间（必需）
2. **查询信息**：调用电费信息或充值信息API获取数据

## 注意事项

- 所有接口都需要有效的认证令牌
- 数据实时从后勤系统获取，不会在数据库中缓存
- 房间绑定信息会保存在数据库中以便下次使用
- 系统需要VPN或校园网环境才能正常访问
- **电费查询和充值查询需要先绑定房间**，否则会返回400错误
- 访问`/go`端点会返回302重定向，系统会自动处理并提取JSESSIONID

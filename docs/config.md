# 配置指南

LoveACE使用JSON格式的配置文件来管理各种设置。本文档详细介绍了所有可用的配置选项。

## 配置文件位置

配置文件应位于项目根目录下，命名为`config.json`。您可以从`config.example.json`复制并修改。

## 完整配置示例

```json
{
  "database": {
    "url": "mysql+aiomysql://username:password@host:port/database",
    "echo": false,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 3600
  },
  "aufe": {
    "default_timeout": 30,
    "max_retries": 3,
    "max_reconnect_retries": 2,
    "activity_timeout": 300,
    "monitor_interval": 60,
    "retry_base_delay": 1.0,
    "retry_max_delay": 60.0,
    "retry_exponential_base": 2.0,
    "uaap_base_url": "http://uaap-aufe-edu-cn.vpn2.aufe.edu.cn:8118/cas",
    "uaap_login_url": "http://uaap-aufe-edu-cn.vpn2.aufe.edu.cn:8118/cas/login?service=http%3A%2F%2Fjwcxk2.aufe.edu.cn%2Fj_spring_cas_security_check",
    "default_headers": {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
  },
  "s3": {
    "access_key_id": "YOUR_ACCESS_KEY_ID",
    "secret_access_key": "YOUR_SECRET_ACCESS_KEY",
    "endpoint_url": null,
    "region_name": "us-east-1",
    "bucket_name": "YOUR_BUCKET_NAME",
    "use_ssl": true,
    "signature_version": "s3v4"
  },
  "log": {
    "level": "INFO",
    "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    "file_path": "logs/app.log",
    "rotation": "10 MB",
    "retention": "30 days",
    "compression": "zip",
    "backtrace": true,
    "diagnose": true,
    "console_output": true,
    "additional_loggers": [
      {
        "file_path": "logs/debug.log",
        "level": "DEBUG",
        "rotation": "10 MB"
      },
      {
        "file_path": "logs/error.log",
        "level": "ERROR",
        "rotation": "10 MB"
      }
    ]
  },
  "app": {
    "title": "LoveAC API",
    "description": "LoveACAPI API",
    "version": "1.0.0",
    "debug": false,
    "cors_allow_origins": ["*"],
    "cors_allow_credentials": true,
    "cors_allow_methods": ["*"],
    "cors_allow_headers": ["*"],
    "host": "0.0.0.0",
    "port": 8000,
    "workers": 1
  }
}
```

## 配置项详解

### 数据库配置 (database)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | string | - | 数据库连接URL，支持MySQL、SQLite等 |
| `echo` | boolean | false | 是否打印SQL语句到日志 |
| `pool_size` | integer | 10 | 连接池大小 |
| `max_overflow` | integer | 20 | 连接池最大溢出数量 |
| `pool_timeout` | integer | 30 | 获取连接超时时间（秒） |
| `pool_recycle` | integer | 3600 | 连接回收时间（秒） |

#### 数据库URL格式

**MySQL**:
```
mysql+aiomysql://用户名:密码@主机:端口/数据库名
```

**SQLite**:
```
sqlite+aiosqlite:///path/to/database.db
```

### AUFE配置 (aufe)

安徽财经大学教务系统相关配置。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `default_timeout` | integer | 30 | 默认请求超时时间（秒） |
| `max_retries` | integer | 3 | 最大重试次数 |
| `max_reconnect_retries` | integer | 2 | 最大重连次数 |
| `activity_timeout` | integer | 300 | 活动超时时间（秒） |
| `monitor_interval` | integer | 60 | 监控间隔（秒） |
| `retry_base_delay` | float | 1.0 | 重试基础延迟（秒） |
| `retry_max_delay` | float | 60.0 | 重试最大延迟（秒） |
| `retry_exponential_base` | float | 2.0 | 重试指数基数 |
| `uaap_base_url` | string | - | UAAP基础URL |
| `uaap_login_url` | string | - | UAAP登录URL |
| `default_headers` | object | - | 默认HTTP请求头 |

### S3存储配置 (s3)

用于文件存储的S3兼容服务配置。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `access_key_id` | string | - | S3访问密钥ID |
| `secret_access_key` | string | - | S3访问密钥 |
| `endpoint_url` | string | null | 自定义端点URL（用于S3兼容服务） |
| `region_name` | string | us-east-1 | 区域名称 |
| `bucket_name` | string | - | 存储桶名称 |
| `use_ssl` | boolean | true | 是否使用SSL |
| `signature_version` | string | s3v4 | 签名版本 |

### 日志配置 (log)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `level` | string | INFO | 日志级别 |
| `format` | string | - | 日志格式 |
| `file_path` | string | logs/app.log | 主日志文件路径 |
| `rotation` | string | 10 MB | 日志轮转大小 |
| `retention` | string | 30 days | 日志保留时间 |
| `compression` | string | zip | 压缩格式 |
| `backtrace` | boolean | true | 是否包含回溯信息 |
| `diagnose` | boolean | true | 是否包含诊断信息 |
| `console_output` | boolean | true | 是否输出到控制台 |
| `additional_loggers` | array | - | 额外的日志记录器配置 |

#### 日志级别

- `DEBUG`: 调试信息
- `INFO`: 一般信息
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `CRITICAL`: 严重错误

### 应用配置 (app)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `title` | string | LoveAC API | 应用标题 |
| `description` | string | - | 应用描述 |
| `version` | string | 1.0.0 | 应用版本 |
| `debug` | boolean | false | 是否启用调试模式 |
| `cors_allow_origins` | array | ["*"] | 允许的CORS源 |
| `cors_allow_credentials` | boolean | true | 是否允许携带凭证 |
| `cors_allow_methods` | array | ["*"] | 允许的HTTP方法 |
| `cors_allow_headers` | array | ["*"] | 允许的HTTP头 |
| `host` | string | 0.0.0.0 | 绑定主机 |
| `port` | integer | 8000 | 绑定端口 |
| `workers` | integer | 1 | 工作进程数 |

## 环境特定配置

### 开发环境

```json
{
  "app": {
    "debug": true,
    "workers": 1
  },
  "log": {
    "level": "DEBUG",
    "console_output": true
  },
  "database": {
    "echo": true
  }
}
```

### 生产环境

```json
{
  "app": {
    "debug": false,
    "workers": 4,
    "cors_allow_origins": ["https://yourdomain.com"]
  },
  "log": {
    "level": "INFO",
    "console_output": false
  },
  "database": {
    "echo": false,
    "pool_size": 20
  }
}
```

## 配置验证

启动应用时，系统会自动验证配置文件的格式和必需参数。如果配置有误，应用将无法启动并显示相应的错误信息。

## 动态配置

某些配置项支持运行时修改，无需重启服务：

- 日志级别
- CORS设置
- 部分AUFE配置

动态配置修改可通过管理API进行（需要管理员权限）。
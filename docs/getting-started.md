# 快速开始

本指南将帮助您快速设置并运行LoveACE教务系统自动化工具。

## 前置条件

在开始之前，请确保您的系统已安装：

- **Python 3.12**
- **PDM** (Python Dependency Manager)
- **MySQL** 或其他支持的数据库

## 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/LoveACE-Team/LoveACE.git
cd LoveACE
```

### 2. 安装依赖

使用PDM安装项目依赖：

```bash
pdm install
```

### 3. 配置环境

启动 App 生成配置文件并编辑：

```bash
python main.py
```

编辑`config.json`文件，配置以下关键参数：

```json
{
  "database": {
    "url": "mysql+aiomysql://username:password@host:port/database"
  },
  "app": {
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

### 4. 初始化数据库

项目会在首次运行时自动创建数据库表结构。

### 5. 启动服务

```bash
python main.py --reload
```

服务启动后，您可以访问：

- **API服务**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **Redoc文档**: http://localhost:8000/redoc

## 验证安装

访问健康检查接口验证服务是否正常运行：

```bash
curl http://localhost:8000/health
```

如果一切正常，您应该看到类似以下的响应：

```json
{
  "code": 200,
  "message": "服务运行正常",
  "data": {
    "status": "healthy",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

## 下一步

- 查看 [配置指南](/config) 了解详细配置选项
- 阅读 [API文档](/api/) 了解可用接口
- 参考 [部署指南](/deploy) 进行生产环境部署

## 常见问题

### 数据库连接失败

检查`config.json`中的数据库配置是否正确，确保：
- 数据库服务已启动
- 用户名密码正确
- 网络连接正常

### 端口被占用

如果8000端口被占用，可以在配置文件中修改端口：

```json
{
  "app": {
    "port": 8080
  }
}
```

### 依赖安装失败

确保使用Python 3.12，并尝试清理缓存：

```bash
pdm cache clear
pdm install
```
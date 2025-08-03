# LoveACE - 财大教务自动化工具

<div align="center">

<img src="logo.jpg" alt="LoveAC Logo" width="120" height="120" />

**简化学生教务操作，提高使用效率**

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Documentation](https://img.shields.io/badge/docs-VitePress-brightgreen.svg)]


</div>

## 🚀 项目简介

LoveACE 是一个面向安徽财经大学的教务系统自动化工具，专为安徽财经大学教务OA系统设计。通过RESTful API接口，提供自动评教(开发中)、课表查询、成绩查询等功能，大幅简化学生的教务操作流程。

### ✨ 主要特性

- **🔐 安全认证**: 基于邀请码的用户注册系统，确保使用安全
- **📚 教务集成**: 深度集成教务系统，支持学业信息、培养方案查询
- **⭐ 智能评教**: 全自动评教系统，支持任务管理和进度监控
- **💯 积分查询**: 爱安财系统集成，实时查询积分和明细
- **🚀 高性能**: 基于FastAPI构建，支持异步处理和高并发
- **📖 完整文档**: 提供详细的API文档和部署指南

### 🛠️ 技术栈

- **后端框架**: [FastAPI](https://fastapi.tiangolo.com/) - 现代、快速的Python Web框架
- **数据库**: [SQLAlchemy](https://sqlalchemy.org/) (异步) - 强大的ORM工具
- **HTTP客户端**: 基于[aiohttp](https://aiohttp.readthedocs.io/)的自定义异步客户端
- **日志系统**: [richuru](https://github.com/GreyElaina/richuru) - rich + loguru的完美结合
- **文档系统**: [VitePress](https://vitepress.dev/) - 现代化的文档生成工具

## 📦 快速开始

### 前置条件

- **Python 3.12+**
- **PDM**
- **MySQL** 数据库

### 安装部署

```bash
# 1. 克隆项目
git clone https://github.com/LoveACE-Team/LoveACE.git
cd LoveACE

# 2. 安装依赖
pdm install

# 3. 配置环境
python main.py
# 首次启动会生成默认配置，随后自行编辑 config.json 填写数据库配置和其他设置

# 4. 启动服务
python main.py
```

服务启动后访问(以实际为准)：
- **API服务**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## 📚 文档

### 在线文档
访问我们的在线文档获取完整指南：**https://LoveACE-team.github.io/LoveACE**

### 文档内容
- **📖 快速开始**: 安装和基本使用指南
- **⚙️ 配置指南**: 详细的配置选项说明
- **🚀 部署指南**: 生产环境部署教程
- **📡 API文档**: 交互式API文档 (基于OpenAPI)
- **🤝 贡献指南**: 如何参与项目开发
- **⚖️ 免责声明**: 使用须知和免责条款

### 本地构建文档

```bash
# 安装文档依赖
yarn install

# 启动开发服务器
yarn docs:dev

# 构建静态文档
yarn docs:build
```

## 🏗️ 项目结构

```
LoveAC/
├── 📁 database/           # 数据库相关代码
│   ├── creator.py        # 数据库会话管理
│   ├── base.py          # 基础模型定义
│   └── user.py          # 用户数据模型
├── 📁 provider/           # 服务提供者
│   ├── aufe/            # 安徽财经大学服务
│   │   ├── client.py    # 基础HTTP客户端
│   │   ├── jwc/         # 教务系统集成
│   │   └── aac/         # 爱安财系统集成
│   └── loveac/          # 内部服务
├── 📁 router/             # API路由定义
│   ├── common_model.py  # 通用响应模型
│   ├── invite/          # 邀请码相关路由
│   ├── login/           # 登录认证路由
│   ├── jwc/             # 教务系统路由
│   └── aac/             # 爱安财系统路由
├── 📁 utils/              # 工具函数
├── 📁 config/             # 配置管理
├── 📁 docs/               # 项目文档
├── 📄 main.py             # 应用入口文件
├── 📄 config.json         # 配置文件
├── 📄 openapi.json        # OpenAPI规范文件(FastAPI生成)
└── 📄 pyproject.toml      # 项目依赖配置
```

## 🔧 配置说明

### 数据库配置
```json
{
  "database": {
    "url": "mysql+aiomysql://username:password@host:port/database",
    "pool_size": 10,
    "max_overflow": 20
  }
}
```

### 应用配置
```json
{
  "app": {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": false,
    "cors_allow_origins": ["*"]
  }
}
```

完整配置选项请参考 [配置指南](https://LoveACE-team.github.io/LoveACE/config)。

## 🚀 部署

详细部署指南请参考 [部署文档](https://LoveACE-team.github.io/LoveACE/deploy)。

## 🤝 贡献

我们欢迎所有形式的贡献！在参与之前，请阅读我们的 [贡献指南](https://LoveACE-team.github.io/LoveACE/contributing)。

### 贡献方式

- 🐛 **Bug报告**: [创建Issue](https://github.com/LoveACE-Team/LoveACE/issues/new)
- 💡 **功能建议**: [发起Issue](https://github.com/LoveACE-Team/LoveACE/issues/new)
- 📝 **代码贡献**: 提交Pull Request
- 📖 **文档改进**: 帮助完善文档

## ⚖️ 免责声明

**重要提醒**: 本软件仅供学习和个人使用，请在使用前仔细阅读 [免责声明](https://LoveACE-team.github.io/LoveACE/disclaimer)。

- ✅ 本软件为教育目的开发的开源项目
- ⚠️ 使用时请遵守学校相关规定和法律法规
- 🛡️ 请妥善保管个人账户信息
- ❌ 不得用于任何商业用途

## 📞 支持与联系

- 📧 **邮箱**: [sibuxiang@proton.me](mailto:sibuxiang@proton.me)
- 🐛 **Bug报告**: [GitHub Issues](https://github.com/LoveACE-Team/LoveACE/issues)
- 💬 **讨论交流**: [GitHub Discussions](https://github.com/LoveACE-Team/LoveACE/discussions)
- 📖 **在线文档**: [项目文档](https://LoveACE-team.github.io/LoveACE)

## 📄 许可证

本项目采用 [MIT许可证](LICENSE) 开源。

---

<div align="center">

**如果这个项目对你有帮助，请给它一个 ⭐️**

Made with ❤️ by [Sibuxiangx](https://github.com/Sibuxiangx)

</div>
# astrbot_plugin_lingya_video

AstrBot 视频生成插件，基于灵芽API (lingyaai.cn) 调用万相 Wan2.7 系列模型生成视频。

## ✨ 功能特性

- 🎬 文生视频 (wan2.7-t2v) - 根据文字描述生成视频
- 🖼️ 图生视频 (wan2.7-i2v) - 根据图片生成视频
- 🎥 参考生视频 (wan2.7-r2v) - 参考视频生成新视频
- ✂️ 视频编辑 (wan2.7-videoedit) - 编辑现有视频
- 🔧 支持 720P / 1080P 分辨率
- ⏱️ 可配置视频时长 (2-15秒)
- 🚀 异步任务处理，支持并发控制
- 🌐 Web UI 设置页面

## 📦 安装

1. 进入 AstrBot 插件目录
2. 克隆或下载本仓库
3. 在 AstrBot 中启用插件

```bash
cd /path/to/astrbot/plugins
git clone https://github.com/maomaosamaqwq/astrbot_plugin_lingya_video.git
```

## ⚙️ 配置

在 AstrBot WebUI 中配置以下选项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api_key` | 灵芽API密钥 | 无 (必填) |
| `api_base` | API地址 | `https://api.lingyaai.cn` |
| `model` | 默认模型 | `wan2.7-t2v` |
| `resolution` | 默认分辨率 | `720P` |
| `duration` | 默认时长(秒) | `5` |
| `max_concurrent` | 最大并发数 | `3` |
| `poll_timeout` | 轮询超时(秒) | `300` |
| `poll_interval` | 轮询间隔(秒) | `15` |

## 🚀 使用方法

### 基本使用

在聊天中发送指令即可生成视频：

```
/video 一只可爱的小猫在草地上玩耍
```

### 指定模型

```
/video --model wan2.7-i2v --image https://example.com/cat.jpg 一只小猫变成动画
```

### 参数说明

- `--model` - 指定模型 (t2v/i2v/r2v/videoedit)
- `--duration` - 视频时长 (2-15秒)
- `--resolution` - 分辨率 (720P/1080P)

## 📝 API 接口

插件提供以下 Web API：

- `GET /astrbot_plugin_lingya_video/settings` - 获取当前设置
- `POST /astrbot_plugin_lingya_video/config/update` - 更新配置

## 🔑 获取 API Key

1. 访问 [灵芽AI](https://lingyaai.cn)
2. 注册账号并登录
3. 在控制台获取 API Key

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

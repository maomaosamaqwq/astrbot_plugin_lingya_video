"""
灵芽视频生成插件 - AstrBot
基于灵芽API(lingyaai.cn)调用万相Wan2.7系列模型生成视频
"""

import asyncio
import logging
from typing import Optional

import aiohttp
from quart import jsonify

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig

logger = logging.getLogger("astrbot")


@register(
    name="astrbot_plugin_lingya_video",
    desc="基于灵芽API的万相Wan2.7视频生成插件",
    author="maomaosamaqwq",
    version="0.1.0",
)
class LingyaVideoPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._semaphore = asyncio.Semaphore(config.get("max_concurrent", 3))
        self._api_base = config.get("api_base", "https://api.lingyaai.cn").rstrip("/")
        self._api_key = config.get("api_key", "")
        self._active_tasks: dict[str, asyncio.Task] = {}

        # 注册 Web API
        context.register_web_api(
            "/astrbot_plugin_lingya_video/settings",
            self.api_get_settings,
            ["GET"],
            "获取当前设置",
        )
        context.register_web_api(
            "/astrbot_plugin_lingya_video/config/update",
            self.api_update_config,
            ["POST"],
            "更新插件配置",
        )

    # ─────────────────── Tool ───────────────────

    @filter.llm_tool()
    async def generate_video(
        self,
        event: AstrMessageEvent,
        prompt: str,
        model: Optional[str] = None,
        duration: Optional[int] = None,
        resolution: Optional[str] = None,
    ):
        """基于灵芽API调用万相Wan2.7模型生成视频。
        Args:
            prompt(string): 视频描述提示词，详细描述期望的视频内容和视觉风格，支持中英文
            model(string): 模型名称。可选: wan2.7-t2v(文生视频,默认), wan2.7-i2v(图生视频), wan2.7-r2v(参考生视频), wan2.7-videoedit(视频编辑)
            duration(number): 视频时长(秒)。t2v/i2v:2-15, 默认5
            resolution(string): 分辨率。可选: 720P(默认), 1080P
        """
        if not self._api_key:
            yield event.plain_result("未配置 API Key，请在 WebUI 设置中填写。")
            return

        model = model or self.config.get("model", "wan2.7-t2v")
        duration = duration or self.config.get("duration", 5)
        resolution = resolution or self.config.get("resolution", "720P")

        # 保存event对象，用于后台任务发送消息
        asyncio.create_task(
            self._run_generation(event, model, prompt, duration, resolution)
        )
        yield event.plain_result(
            f"视频生成任务已提交！\n"
            f"模型: {model}\n"
            f"提示: {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n"
            f"时长: {duration}s | 分辨率: {resolution}\n"
            f"生成中，请稍候..."
        )

    # ─────────────────── 核心逻辑 ───────────────────

    async def _run_generation(
        self,
        event: AstrMessageEvent,
        model: str,
        prompt: str,
        duration: int,
        resolution: str,
    ):
        """异步执行视频生成"""
        async with self._semaphore:
            try:
                task_id = await self._create_video_task(
                    model, prompt, duration, resolution
                )
                await event.send(event.plain_result(f"任务已创建，ID: `{task_id}`，正在生成中..."))

                video_url = await self._poll_task(task_id)
                if video_url:
                    await event.send(event.plain_result(
                        f"视频生成完成！\n"
                        f"下载链接(24h有效): {video_url}\n"
                        f"建议尽快下载保存到本地。"
                    ))
                else:
                    await event.send(event.plain_result("视频生成失败，请稍后重试。"))

            except Exception as e:
                logger.error(f"Lingya video generation error: {e}")
                try:
                    await event.send(event.plain_result(f"视频生成出错: {str(e)[:200]}"))
                except Exception as send_exc:
                    logger.error(f"无法发送错误消息给用户: {send_exc}")

    async def _create_video_task(
        self, model: str, prompt: str, duration: int, resolution: str
    ) -> str:
        """创建视频生成任务，返回 task_id"""
        url = f"{self._api_base}/v1/videos"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {
                "resolution": resolution,
                "duration": duration,
                "prompt_extend": True,
                "watermark": False,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    msg = data.get("message", data.get("code", "Unknown error"))
                    raise Exception(f"API error ({resp.status}): {msg}")
                return data["id"]

    async def _poll_task(self, task_id: str) -> Optional[str]:
        """轮询任务直到完成或超时，返回 video_url 或 None"""
        url = f"{self._api_base}/v1/videos/{task_id}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        timeout = self.config.get("poll_timeout", 300)
        interval = self.config.get("poll_interval", 15)
        elapsed = 0

        async with aiohttp.ClientSession() as session:
            while elapsed < timeout:
                await asyncio.sleep(interval)
                elapsed += interval

                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    status = data.get("status", "")

                    if status == "completed":
                        return data.get("video_url")
                    elif status == "failed":
                        logger.error(f"Video task {task_id} failed: {data}")
                        return None

            logger.warning(f"Video task {task_id} timed out after {timeout}s")
            return None

    # ─────────────────── Web API ───────────────────

    async def api_update_config(self):
        """更新插件配置（通过 POST JSON body）"""
        from quart import request

        data = await request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        changes = []
        for key in [
            "api_base", "api_key", "model", "resolution", "duration",
            "max_concurrent", "poll_timeout", "poll_interval",
        ]:
            if key in data:
                self.config.put(key, data[key])
                changes.append(key)

        self.config.save_config()

        if "api_base" in data:
            self._api_base = self.config.get("api_base", "https://api.lingyaai.cn").rstrip("/")
        if "api_key" in data:
            self._api_key = self.config.get("api_key", "")
        if "max_concurrent" in data:
            self._semaphore = asyncio.Semaphore(self.config.get("max_concurrent", 3))

        return jsonify({
            "ok": True,
            "changed": changes,
            "message": f"更新了 {len(changes)} 个配置项",
        })

    async def api_get_settings(self):
        """返回当前插件设置"""
        return jsonify({
            "api_base": self._api_base,
            "model": self.config.get("model", "wan2.7-t2v"),
            "resolution": self.config.get("resolution", "720P"),
            "duration": self.config.get("duration", 5),
            "max_concurrent": self.config.get("max_concurrent", 3),
            "poll_timeout": self.config.get("poll_timeout", 300),
            "poll_interval": self.config.get("poll_interval", 15),
            "has_api_key": bool(self._api_key),
        })

    async def terminate(self):
        """插件卸载时清理"""
        for task in self._active_tasks.values():
            task.cancel()
        self._active_tasks.clear()

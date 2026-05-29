"""
鐏佃娊瑙嗛鐢熸垚鎻掍欢 - AstrBot
鍩轰簬鐏佃娊API(lingyaai.cn)璋冪敤涓囩浉Wan2.7绯诲垪妯″瀷鐢熸垚瑙嗛
"""

import asyncio
import logging
from typing import Optional

import aiohttp
from quart import jsonify

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig

logger = logging.getLogger("astrbot")


@register(
    name="astrbot_plugin_lingya_video",
    desc="鍩轰簬鐏佃娊API鐨勪竾鐩竁an2.7瑙嗛鐢熸垚鎻掍欢",
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

        # 娉ㄥ唽 Web API
        context.register_web_api(
            "/astrbot_plugin_lingya_video/settings",
            self.api_get_settings,
            ["GET"],
            "鑾峰彇褰撳墠璁剧疆",
        )
        context.register_web_api(
            "/astrbot_plugin_lingya_video/config/update",
            self.api_update_config,
            ["POST"],
            "鏇存柊鎻掍欢閰嶇疆",
        )

    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€ Tool 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @filter.llm_tool()
    async def generate_video(
        self,
        event: AstrMessageEvent,
        prompt: str,
        model: Optional[str] = None,
        duration: Optional[int] = None,
        resolution: Optional[str] = None,
    ):
        """鍩轰簬鐏佃娊API璋冪敤涓囩浉Wan2.7妯″瀷鐢熸垚瑙嗛銆?
        Args:
            prompt(string): 瑙嗛鎻忚堪鎻愮ず璇嶏紝璇︾粏鎻忚堪鏈熸湜鐨勮棰戝唴瀹瑰拰瑙嗚椋庢牸锛屾敮鎸佷腑鑻辨枃
            model(string): 妯″瀷鍚嶇О銆傚彲閫? wan2.7-t2v(鏂囩敓瑙嗛,榛樿), wan2.7-i2v(鍥剧敓瑙嗛), wan2.7-r2v(鍙傝€冪敓瑙嗛), wan2.7-videoedit(瑙嗛缂栬緫)
            duration(number): 瑙嗛鏃堕暱(绉?銆倀2v/i2v:2-15, 榛樿5
            resolution(string): 鍒嗚鲸鐜囥€傚彲閫? 720P(榛樿), 1080P
        """
        if not self._api_key:
            yield event.plain_result("鏈厤缃?API Key锛岃鍦?WebUI 璁剧疆涓～鍐欍€?)
            return

        model = model or self.config.get("model", "wan2.7-t2v")
        duration = duration or self.config.get("duration", 5)
        resolution = resolution or self.config.get("resolution", "720P")

        asyncio.create_task(
            self._run_generation(event, model, prompt, duration, resolution)
        )
        yield event.plain_result(
            f"瑙嗛鐢熸垚浠诲姟宸叉彁浜わ紒\n"
            f"妯″瀷: {model}\n"
            f"鎻愮ず: {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n"
            f"鏃堕暱: {duration}s | 鍒嗚鲸鐜? {resolution}\n"
            f"鐢熸垚涓紝璇风◢鍊?.."
        )

    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€ 鏍稿績閫昏緫 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    async def _run_generation(
        self,
        event: AstrMessageEvent,
        model: str,
        prompt: str,
        duration: int,
        resolution: str,
    ):
        """寮傛鎵ц瑙嗛鐢熸垚"""
        async with self._semaphore:
            try:
                task_id = await self._create_video_task(
                    model, prompt, duration, resolution
                )
                await event.send(f"浠诲姟宸插垱寤猴紝ID: `{task_id}`锛屾鍦ㄧ敓鎴愪腑...")

                video_url = await self._poll_task(task_id)
                if video_url:
                    await event.send(
                        f"瑙嗛鐢熸垚瀹屾垚锛乗n"
                        f"涓嬭浇閾炬帴(24h鏈夋晥): {video_url}\n"
                        f"寤鸿灏藉揩涓嬭浇淇濆瓨鍒版湰鍦般€?
                    )
                else:
                    await event.send("瑙嗛鐢熸垚澶辫触锛岃绋嶅悗閲嶈瘯銆?)

            except Exception as e:
                logger.error(f"Lingya video generation error: {e}")
                await event.send(f"瑙嗛鐢熸垚鍑洪敊: {str(e)[:200]}")

    async def _create_video_task(
        self, model: str, prompt: str, duration: int, resolution: str
    ) -> str:
        """鍒涘缓瑙嗛鐢熸垚浠诲姟锛岃繑鍥?task_id"""
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
        """杞浠诲姟鐩村埌瀹屾垚鎴栬秴鏃讹紝杩斿洖 video_url 鎴?None"""
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

    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€ Web API 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    async def api_update_config(self):
        """鏇存柊鎻掍欢閰嶇疆锛堥€氳繃 POST JSON body锛?""
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
            "message": f"鏇存柊浜?{len(changes)} 涓厤缃」",
        })

    async def api_get_settings(self):
        """杩斿洖褰撳墠鎻掍欢璁剧疆"""
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
        """鎻掍欢鍗歌浇鏃舵竻鐞?""
        for task in self._active_tasks.values():
            task.cancel()
        self._active_tasks.clear()

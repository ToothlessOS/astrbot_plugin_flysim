from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from .utils.weather import fetch_metar, fetch_taf, parse_metar


class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command_group("weather")
    def weather(self):
        """获取实时航空天气"""
        pass

    @weather.command("metar")
    async def get_metar(self, event: AstrMessageEvent, icao_code: str):
        """获取机场 METAR 天气信息, 用法: /weather metar ZSSS"""
        icao_code = icao_code.upper()

        # 验证 ICAO 码格式 (4位字母)
        if not icao_code.isalpha() or len(icao_code) != 4:
            yield event.plain_result(
                "❌ ICAO 机场代码格式错误，请输入4位字母（如 ZSSS）"
            )
            return

        result = await fetch_metar(icao_code)

        if result["success"]:
            metar_text = parse_metar(result["data"][0])
            logger.info(
                f"astrbot-flysim-plugin: Successfully fetched METAR for {icao_code}"
            )
            yield event.plain_result(
                f"{metar_text} \n\n  !!!解读仅供参考，请以原始报文为准!!!"
            )
        else:
            yield event.plain_result(f"❌ {result['error']}")

    @weather.command("taf")
    async def get_taf(self, event: AstrMessageEvent, icao_code: str):
        """获取机场 TAF 天气预报, 用法: /weather taf ZSSS"""
        icao_code = icao_code.upper()

        # 验证 ICAO 码格式 (4位字母)
        if not icao_code.isalpha() or len(icao_code) != 4:
            yield event.plain_result(
                "❌ ICAO 机场代码格式错误，请输入4位字母（如 ZSSS）"
            )
            return

        result = await fetch_taf(icao_code)

        if result["success"]:
            # 仅返回原始报文
            raw_taf = result["data"][0].get("rawTAF", "无TAF报文")
            logger.info(
                f"astrbot-flysim-plugin: Successfully fetched TAF for {icao_code}"
            )
            yield event.plain_result(f"📄 报文:\n{raw_taf} \n\n")
        else:
            yield event.plain_result(f"❌ {result['error']}")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""

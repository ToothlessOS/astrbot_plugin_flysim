"""Aviation Weather API 工具模块"""

import aiohttp
import re
from typing import Optional

BASE_URL = "https://aviationweather.gov/api/data"

# ===== 天气现象翻译字典 =====

# 修饰词
MODIFIERS = {
    "-": "轻微",
    "": "",
    "+": "强",
    "VC": "附近",
    "MI": "浅",
    "BC": "散片",
    "PR": "部分",
    "DR": "低吹",
    "BL": "高吹",
    "SH": "阵性",
    "TS": "雷暴",
    "FZ": "冻",
}

# 天气现象
WEATHER_PHENOMENA = {
    # 降水
    "DZ": "毛毛雨",
    "RA": "雨",
    "SN": "雪",
    "SG": "米雪",
    "IC": "冰针",
    "PE": "冰粒",
    "GR": "冰雹",
    "GS": "小冰粒",
    # 视程障碍
    "BR": "轻雾",
    "FG": "雾",
    "FU": "烟",
    "VA": "火山灰",
    "DU": "浮尘",
    "SA": "沙",
    "HZ": "霾",
    # 其他
    "PO": "尘卷风",
    "FC": "漏斗云",
    "DS": "尘暴",
    "SQ": "飑",
    "SS": "沙暴",
}

# 云量翻译
CLOUD_COVER = {
    "FEW": "少云(1-2/8)",
    "SCT": "疏云(3-4/8)",
    "BKN": "多云(5-7/8)",
    "OVC": "阴天(8/8)",
    "SKC": "晴空",
    "NSC": "无重要云",
    "CLR": "无云",
    "NCD": "无云",
}

# 特殊云型
CLOUD_TYPES = {
    "TCU": "塔状积云",
    "CB": "积雨云",
}

# 运行标准分类 (Flight Categories)
FLT_CAT = {
    "VFR": ("VFR 目视", "🟢"),
    "MVFR": ("MVFR 边缘", "🔵"),
    "IFR": ("IFR 仪表", "🔴"),
    "LIFR": ("LIFR 低仪表", "🟣"),
}


def parse_weather(wx_string: str) -> str:
    """解析天气现象字符串为中文

    Args:
        wx_string: 天气现象字符串，如 "MIFG", "+TSRA", "VCFG" 等

    Returns:
        中文翻译
    """
    if not wx_string:
        return ""

    # 尝试解析 METAR 格式的天气字符串
    # 格式: [修饰词][描述符][天气现象]
    # 例如: +TSRA = 强雷阵雨, MIFG = 浅雾, VCFG = 附近有雾

    # 使用正则匹配天气现象组
    # 格式: (强度)(描述符)(现象)(现象)...
    # 例如: +TSRA = +TS + RA
    #      MIFG = MI + FG
    #      VCFG = VC + FG

    # 先尝试完整匹配
    if wx_string in WEATHER_PHENOMENA:
        return WEATHER_PHENOMENA[wx_string]

    # 分解天气字符串
    # 修饰词: -, +, VC
    # 描述符: MI, BC, PR, DR, BL, SH, TS, FZ

    modifiers_match = re.match(r"^(VC|MI|BC|PR|DR|BL|SH|TS|FZ|\+|-)?(.*)$", wx_string)
    if not modifiers_match:
        return wx_string

    prefix = modifiers_match.group(1) or ""
    rest = modifiers_match.group(2)

    # 翻译修饰词前缀
    prefix_cn = ""
    if prefix in MODIFIERS:
        prefix_cn = MODIFIERS[prefix]

    # 解析剩余部分
    # 可能包含多个天气现象
    phenomena_cn = []
    remaining = rest

    while remaining:
        # 尝试匹配2位或3位代码
        matched = False

        # 先尝试3位
        if len(remaining) >= 3:
            code3 = remaining[:3]
            if code3 in WEATHER_PHENOMENA:
                phenomena_cn.append(WEATHER_PHENOMENA[code3])
                remaining = remaining[3:]
                matched = True

        # 再尝试2位
        if not matched and len(remaining) >= 2:
            code2 = remaining[:2]
            if code2 in WEATHER_PHENOMENA:
                phenomena_cn.append(WEATHER_PHENOMENA[code2])
                remaining = remaining[2:]
                matched = True

        # 检查是否有描述符需要处理
        if not matched:
            # 可能是描述符+现象的组合
            for desc_len in [2, 3]:
                if len(remaining) >= desc_len + 2:
                    desc = remaining[:desc_len]
                    phen = remaining[desc_len : desc_len + 2]
                    if desc in MODIFIERS and phen in WEATHER_PHENOMENA:
                        # 描述符已经通过整体解析处理了
                        break
            # 如果无法解析，保留原样
            if not matched and remaining:
                phenomena_cn.append(remaining)
                break

    # 组合结果
    if prefix_cn and phenomena_cn:
        return prefix_cn + "".join(phenomena_cn)
    elif phenomena_cn:
        return "".join(phenomena_cn)
    else:
        # 如果无法解析，尝试直接查找
        return wx_string


def parse_clouds(clouds: list) -> str:
    """解析云层信息为中文

    Args:
        clouds: 云层列表，每个元素包含 cover, base, type 等字段

    Returns:
        中文云层描述
    """
    if not clouds:
        return "无云"

    cloud_info = []

    for c in clouds:
        cover = c.get("cover", "")
        base = c.get("base", "")
        cloud_type = c.get("cloudType", "")

        # 翻译云量
        cover_cn = CLOUD_COVER.get(cover, cover)

        # 高度转换 (百英尺 -> 米/英尺)
        height_str = ""
        if base and base != "N/A":
            try:
                base_int = int(base)
                # base 单位为百英尺 (hectofeet)
                height_str = f" 云底 {base_int}ft ({base_int * 0.3048:.0f}m)"
            except (ValueError, TypeError):
                height_str = f" 云底 {base}"

        # 翻译特殊云型
        type_str = ""
        if cloud_type in CLOUD_TYPES:
            type_str = f" {CLOUD_TYPES[cloud_type]}"
        elif cover in CLOUD_TYPES:
            # 有些 API 把 CB 放在 cover 字段
            type_str = f" {CLOUD_TYPES[cover]}"

        # 组合云层信息
        cloud_info.append(f"{cover_cn}{height_str}{type_str}")

    return " / ".join(cloud_info)


async def fetch_metar(icao_code: str) -> dict:
    """获取机场 METAR 报文"""
    url = f"{BASE_URL}/metar?ids={icao_code}&format=json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await _handle_response(response)


async def fetch_taf(icao_code: str) -> dict:
    """获取机场 TAF 预报"""
    url = f"{BASE_URL}/taf?ids={icao_code}&format=json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await _handle_response(response)


async def _handle_response(response: aiohttp.ClientResponse) -> dict:
    """处理 API 响应和错误"""
    status = response.status

    error_messages = {
        204: "未找到该机场的天气数据",
        400: "请求格式错误，请检查 ICAO 机场代码",
        404: "未找到该机场",
        429: "请求过于频繁，请稍后再试",
        500: "服务器内部错误",
        502: "网关错误，请稍后再试",
        504: "网关超时，请稍后再试",
    }

    if status == 200:
        try:
            data = await response.json()
            if not data:
                return {"success": False, "error": "未找到该机场的天气数据"}
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": f"数据解析失败: {str(e)}"}

    error_msg = error_messages.get(status, f"请求失败，状态码: {status}")
    return {"success": False, "error": error_msg}


def parse_metar(metar_data: dict) -> str:
    """解析 METAR 数据为易读格式"""
    try:
        # 原始报文
        raw_ob = metar_data.get("rawOb", "")

        # 基础信息
        icao = metar_data.get("icaoId", "N/A")
        name = metar_data.get("name", "N/A")
        reportTime = metar_data.get("reportTime", "N/A")

        # 解析观测时间（使用 reportTime）
        if reportTime != "N/A":
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(reportTime.replace("Z", "+00:00"))
                reportTime = dt.strftime("%Y-%m-%d %H:%M UTC")
            except:
                pass

        # 风速风向
        windDir = metar_data.get("wdir", "N/A")
        windSpeed = metar_data.get("wspd", "N/A")
        gust = metar_data.get("wgst", "")
        if windDir == "VRB":
            wind = "风向不定"
        elif windDir == "N/A" or windSpeed == "N/A":
            wind = "无风"
        else:
            gust_str = f" 阵风 {gust}kt" if gust else ""
            wind = f"{windDir}°/{windSpeed}kt{gust_str}"

        # 能见度
        vis = metar_data.get("visib", "N/A")
        if vis != "N/A":
            vis = f"{vis} statute miles"

        # 天气现象
        wx_raw = metar_data.get("wxString", "")
        wx = parse_weather(wx_raw) if wx_raw else ""

        # 云量
        clouds = metar_data.get("clouds", [])
        clouds_str = parse_clouds(clouds)

        # 温度和露点
        temp = metar_data.get("temp", "N/A")
        dewp = metar_data.get("dewp", "N/A")
        if temp != "N/A":
            temp_str = f"{temp}°C"
        if dewp != "N/A":
            dewp_str = f"{dewp}°C"

        # 气压
        altim = metar_data.get("altim", "N/A")
        altim_str = "N/A"
        if altim != "N/A":
            # 尝试从 rawOb 中提取英尺制修正海压
            us_altim_match = re.search(r"A(\d{4})", raw_ob)
            if us_altim_match:
                us_altim = us_altim_match.group(1)
                us_altim_inhg = f"{int(us_altim) / 100:.2f}"
                altim_str = f"{altim:.2f} inHg A{us_altim_inhg}"
            else:
                altim_str = f"{altim:.2f} inHg"

        # 组装输出
        lines = []

        if raw_ob:
            lines.append(f"📄 原始报文: {raw_ob}")

        lines.extend(
            [
                f"📍 {name} ({icao})",
                f"⏰ 观测时间: {reportTime}",
                f"💨 风向风速: {wind}",
                f"👁️ 能见度: {vis}",
            ]
        )

        if wx:
            lines.append(f"🌤️ 天气: {wx}")

        lines.append(f"☁️ 云量: {clouds_str}")

        if temp != "N/A":
            lines.append(f"🌡️ 温度: {temp_str}")

        if dewp != "N/A":
            lines.append(f"💧 露点: {dewp_str}")

        if altim != "N/A":
            lines.append(f"📊 气压: {altim_str}")

        # 运行标准 (fltCat)
        flt_cat = metar_data.get("fltCat", "")
        if flt_cat and flt_cat in FLT_CAT:
            cat_name, cat_emoji = FLT_CAT[flt_cat]
            lines.append(f"✈️ 运行标准: {cat_emoji} {cat_name}")

        return "\n".join(lines)

    except Exception as e:
        return f"解析失败: {str(e)}"

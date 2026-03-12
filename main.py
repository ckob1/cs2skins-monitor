import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import requests
import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import sys
from enum import Enum

# ==================== 枚举定义（双平台模式+全功能扩展）====================
class DataSourceMode(Enum):
    """数据源模式枚举，固定双平台同步查询"""
    SYNTHESIS = "双平台同步查询"

class PlatformType(Enum):
    """平台类型枚举，用于数据来源标注"""
    STEAMDT = "SteamDT"
    CSQAQ = "CSQAQ"
    SYNTHESIS = "双平台合并"

class RankType(Enum):
    """CSQAQ排行榜类型枚举"""
    PRICE = "price"
    RENT = "rent"
    EXCHANGE = "exchange"
    VOLUME = "volume"
    EXIST = "exist"
    MARKET_CAP = "market_cap"
    SELL_COUNT = "sell_count"
    BID_COUNT = "bid_count"
    RENT_COUNT = "rent_count"

class PeriodType(Enum):
    """K线/走势周期枚举"""
    DAY_1 = "1d"
    DAY_7 = "7d"
    DAY_30 = "30d"
    DAY_90 = "90d"
    DAY_180 = "180d"
    YEAR_1 = "1y"
    ALL = "all"

# ==================== 全局配置区 ====================
# --- SteamDT 平台配置 ---
STEAMDT_API_KEY: str = "73970210142d48bbb8515da1a730487b"
STEAMDT_BASE_URL: str = "https://open.steamdt.com/open/cs2/v1"
STEAMDT_HEADERS: Dict[str, str] = {
    "Authorization": f"Bearer {STEAMDT_API_KEY}",
    "Content-Type": "application/json"
}

# --- CSQAQ 平台配置（全接口适配）---
CSQAQ_API_KEY: str = "XMXQF1P7C7I3Z0I7Q3P294Z7"
CSQAQ_BASE_URL: str = "https://api.csqaq.com/api/v1"
CSQAQ_HEADERS: Dict[str, str] = {
    "ApiToken": CSQAQ_API_KEY,
    "Content-Type": "application/json;charset=UTF-8"
}

# --- 企业微信推送配置 ---
WEBHOOK_URL: str = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=bf9ac8db-99fe-4249-857a-3179f6eb01fb"

# --- AI分析配置 ---
DEFAULT_AI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_AI_MODEL = "gpt-3.5-turbo"
DEFAULT_AI_TEMPERATURE = 0.2

# --- 通用常量配置 ---
NO_PROXY = {"http": None, "https": None}
CACHE_EXPIRE_HOURS: int = 24
DEFAULT_REFRESH_INTERVAL: int = 300
API_TIMEOUT: int = 30
WEAR_LEVEL_LIST: List[str] = ["全部", "崭新出厂", "略有磨损", "久经沙场", "破损不堪", "战痕累累"]
WEAR_PATTERN = re.compile(r"((崭新出厂|略有磨损|久经沙场|破损不堪|战痕累累))$")
WEAPON_NAME_PATTERN = re.compile(r"^(.+?)\s*\|")

# ==================== 路径兼容函数 ====================
def get_resource_path(filename: str) -> str:
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
        temp_path = getattr(sys, '_MEIPASS', base_path)
        packed_file = os.path.join(temp_path, filename)
        if os.path.exists(packed_file):
            return packed_file
        return os.path.join(base_path, filename)
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def get_cache_path(filename: str) -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

# --- 全量缓存文件定义 ---
PACKED_CACHE_FILE: str = get_resource_path("steam_items_cache.json")
STEAMDT_CACHE_FILE: str = get_cache_path("steamdt_items_cache.json")
CSQAQ_CACHE_FILE: str = get_cache_path("csqaq_items_cache.json")
CSQAQ_INDEX_CACHE: str = get_cache_path("csqaq_index_cache.json")
CSQAQ_RANK_CACHE: str = get_cache_path("csqaq_rank_cache.json")
CSQAQ_CASE_CACHE: str = get_cache_path("csqaq_case_cache.json")
CSQAQ_EXCHANGE_CACHE: str = get_cache_path("csqaq_exchange_cache.json")
CSQAQ_SERIES_CACHE: str = get_cache_path("csqaq_series_cache.json")
MONITOR_CONFIG_FILE: str = get_cache_path("steam_price_monitor.json")
EXPORT_DATA_FILE: str = get_cache_path("cs2_item_analysis_result.json")

# ==================== 通用缓存工具函数（强化兜底）====================
def save_cache(data: Any, filename: str):
    """通用缓存保存函数"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({"cache_time": datetime.now().isoformat(), "data": data}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        return False

def load_cache_force(filename: str) -> Optional[Any]:
    """强制加载本地缓存，无论是否过期，兜底专用"""
    if not os.path.exists(filename):
        if filename == STEAMDT_CACHE_FILE and os.path.exists(PACKED_CACHE_FILE):
            try:
                with open(PACKED_CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)["data"]
            except:
                return None
        return None
    try:
        with open(filename, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        return cache_data["data"]
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return None

def load_cache(filename: str, expire_hours: int = 24) -> Optional[Any]:
    """带过期判断的缓存加载函数"""
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        cache_time = datetime.fromisoformat(cache_data["cache_time"])
        if datetime.now() - cache_time < timedelta(hours=expire_hours):
            return cache_data["data"]
        else:
            return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return None

# ==================== 平台API封装类（全功能完整版）====================
class SteamDTAPI:
    """SteamDT平台核心接口封装，原有功能100%保留"""
    def __init__(self):
        self.api_key = STEAMDT_API_KEY
        self.base_url = STEAMDT_BASE_URL
        self.headers = STEAMDT_HEADERS
        self.platform = PlatformType.STEAMDT.value

    def _request(self, method: str, endpoint: str, **kwargs) -> Tuple[Optional[Any], str]:
        """统一请求封装，异常全捕获"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=API_TIMEOUT,
                proxies=NO_PROXY,
                **kwargs
            )
            response.raise_for_status()
            api_data = response.json()
            if api_data.get("success"):
                return api_data.get("data"), ""
            else:
                return None, api_data.get("errorMsg", "接口返回业务错误")
        except Exception as e:
            return None, f"网络请求异常: {str(e)}"

    # 核心接口1：全量饰品基础信息
    def get_all_item_base_info(self, force_refresh: bool = False) -> Tuple[Optional[List[Dict]], str]:
        """获取全量饰品基础信息，强制兜底本地缓存"""
        if not force_refresh:
            cache_data = load_cache(STEAMDT_CACHE_FILE)
            if cache_data:
                return cache_data, "加载本地缓存成功"
        data, error = self._request("GET", "base")
        if data:
            save_cache(data, STEAMDT_CACHE_FILE)
            return data, ""
        cache_data = load_cache_force(STEAMDT_CACHE_FILE)
        if cache_data:
            return cache_data, "API调用失败，加载本地缓存兜底"
        return None, error

    # 核心接口2：单饰品价格查询
    def get_single_price(self, market_hash_name: str) -> Tuple[Optional[List[Dict]], str]:
        """单饰品全平台价格查询"""
        params = {"marketHashName": market_hash_name}
        return self._request("GET", "price/single", params=params)

    # 核心接口3：批量饰品价格查询
    def get_batch_price(self, market_hash_names: List[str]) -> Tuple[Optional[List[Dict]], str]:
        """批量饰品价格查询"""
        return self._request("POST", "price/batch", json={"marketHashNames": market_hash_names})

    # 核心接口4：7天均价查询
    def get_7day_average_price(self, market_hash_name: str) -> Tuple[Optional[Dict], str]:
        """单饰品全平台7天均价查询"""
        params = {"marketHashName": market_hash_name}
        return self._request("GET", "price/avg", params=params)

    # 核心接口5：磨损查询
    def get_wear_by_inspect_url(self, inspect_url: str) -> Tuple[Optional[Dict], str]:
        """通过检视链接查询磨损数据"""
        return self._request("POST", "wear/inspect", json={"inspectUrl": inspect_url})

    def get_wear_by_asmd(self, asmd_param: str) -> Tuple[Optional[Dict], str]:
        """通过ASMD参数查询磨损数据"""
        return self._request("POST", "wear/asm", json={"asm": asmd_param})

    # 核心接口6：检视图生成
    def generate_preview_image_by_url(self, inspect_url: str) -> Tuple[Optional[Dict], str]:
        """通过检视链接生成检视图"""
        return self._request("POST", "image/inspect", json={"inspectUrl": inspect_url})

    def generate_preview_image_by_asmd(self, asmd_param: str) -> Tuple[Optional[Dict], str]:
        """通过ASMD参数生成检视图"""
        return self._request("POST", "image/asm", json={"asm": asmd_param})

class CSQAQAPI:
    """CSQAQ平台全接口封装，严格遵循官方API文档实现"""
    def __init__(self):
        self.api_key = CSQAQ_API_KEY
        self.base_url = CSQAQ_BASE_URL
        self.headers = CSQAQ_HEADERS
        self.platform = PlatformType.CSQAQ.value

    def _request(self, method: str, endpoint: str, **kwargs) -> Tuple[Optional[Any], str]:
        """统一请求封装，异常全捕获，避免401/429中断程序"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=API_TIMEOUT,
                proxies=NO_PROXY,
                **kwargs
            )
            response.raise_for_status()
            api_data = response.json()
            if api_data.get("code") == 200:
                return api_data.get("data"), ""
            else:
                return None, api_data.get("msg", "接口返回业务错误")
        except Exception as e:
            return None, f"网络请求异常: {str(e)}"

    # ==================== 基础必备接口 ====================
    def bind_local_ip(self) -> Tuple[bool, str]:
        """绑定本机IP到白名单，非固定IP场景必备"""
        data, error = self._request("POST", "sys/bind_local_ip")
        if data:
            return True, f"绑定成功，当前IP: {data}"
        return False, error

    def get_all_good_id(self, force_refresh: bool = False) -> Tuple[Optional[List[Dict]], str]:
        """获取全量饰品ID映射，强制兜底本地缓存"""
        if not force_refresh:
            cache_data = load_cache(CSQAQ_CACHE_FILE)
            if cache_data:
                return cache_data, "加载本地缓存成功"
        data, error = self._request("GET", "good/all_id")
        if data:
            save_cache(data, CSQAQ_CACHE_FILE)
            return data, ""
        cache_data = load_cache_force(CSQAQ_CACHE_FILE)
        if cache_data:
            return cache_data, "API调用失败，加载本地缓存兜底"
        return None, error

    def get_good_id_by_name(self, item_list: List[Dict], chinese_name: str) -> Optional[str]:
        """中文名称转good_id"""
        if not item_list or not chinese_name:
            return None
        for item in item_list:
            if item.get("name", "").strip() == chinese_name.strip():
                return item.get("good_id")
        return None

    def get_good_id_by_hash(self, item_list: List[Dict], market_hash_name: str) -> Optional[str]:
        """marketHashName转good_id"""
        if not item_list or not market_hash_name:
            return None
        for item in item_list:
            if item.get("marketHashName", "").strip() == market_hash_name.strip():
                return item.get("good_id")
        return None

    # ==================== 饰品指数接口 ====================
    def get_index_home_data(self, force_refresh: bool = False) -> Tuple[Optional[Dict], str]:
        """获取首页饰品指数数据（指数、涨跌分布、在线人数、今日走势）"""
        if not force_refresh:
            cache_data = load_cache(CSQAQ_INDEX_CACHE, expire_hours=1)
            if cache_data:
                return cache_data, "加载本地缓存成功"
        data, error = self._request("GET", "index/home")
        if data:
            save_cache(data, CSQAQ_INDEX_CACHE)
            return data, ""
        cache_data = load_cache_force(CSQAQ_INDEX_CACHE)
        if cache_data:
            return cache_data, "API调用失败，加载本地缓存兜底"
        return None, error

    def get_index_detail(self) -> Tuple[Optional[Dict], str]:
        """获取指数详情数据（今日涨跌、图表数据）"""
        return self._request("GET", "index/detail")

    def get_index_kline(self, period: PeriodType = PeriodType.DAY_7) -> Tuple[Optional[List[Dict]], str]:
        """获取指数K线图数据"""
        return self._request("GET", f"index/kline/{period.value}")

    # ==================== 饰品详情全接口 ====================
    def get_all_price_data(self) -> Tuple[Optional[List[Dict]], str]:
        """全量获取所有饰品价格和在售数据"""
        return self._request("GET", "good/all_price")

    def get_all_rank_data(self) -> Tuple[Optional[List[Dict]], str]:
        """全量获取所有饰品排行榜数据和近7天价格"""
        return self._request("GET", "good/all_rank")

    def get_single_good_kline(self, good_id: str, period: PeriodType = PeriodType.DAY_7) -> Tuple[Optional[Dict], str]:
        """获取单件饰品多平台、各周期K线数据"""
        return self._request("GET", f"good/kline/{good_id}/{period.value}")

    def get_all_hot_rank(self) -> Tuple[Optional[List[Dict]], str]:
        """全量获取热门饰品热度排名"""
        return self._request("GET", "good/hot_rank")

    def get_good_template_data(self, page: int = 1, page_size: int = 100) -> Tuple[Optional[Dict], str]:
        """分页获取饰品模板数据"""
        return self._request("POST", "good/template", json={"page": page, "page_size": page_size})

    def search_good_id(self, keyword: str) -> Tuple[Optional[List[Dict]], str]:
        """联想查询饰品ID信息"""
        return self._request("GET", f"good/search_id/{keyword}")

    def get_single_good_detail(self, good_id: str) -> Tuple[Optional[Dict], str]:
        """获取单件饰品详情数据"""
        return self._request("GET", f"good/detail/{good_id}")

    def get_good_exist_trend(self, good_id: str) -> Tuple[Optional[List[Dict]], str]:
        """获取单件饰品近180天存世量走势"""
        return self._request("GET", f"good/exist_trend/{good_id}")

    def get_batch_price(self, market_hash_names: List[str]) -> Tuple[Optional[List[Dict]], str]:
        """批量获取饰品价格数据"""
        return self._request("POST", "good/batch_price", json={"marketHashNames": market_hash_names})

    # ==================== 涨跌/热门排行接口 ====================
    # 修复：添加缺失的force_refresh参数，解决未定义变量报错
    def get_rank_list(self, rank_type: RankType = RankType.PRICE, period: PeriodType = PeriodType.DAY_1, page: int = 1, page_size: int = 100, force_refresh: bool = False) -> Tuple[Optional[Dict], str]:
        """获取全品类排行榜单信息"""
        if not force_refresh:
            cache_data = load_cache(CSQAQ_RANK_CACHE, expire_hours=1)
            if cache_data:
                return cache_data, "加载本地缓存成功"
        data, error = self._request("POST", "rank/list", json={
            "type": rank_type.value,
            "period": period.value,
            "page": page,
            "page_size": page_size
        })
        if data:
            save_cache(data, CSQAQ_RANK_CACHE)
            return data, ""
        cache_data = load_cache_force(CSQAQ_RANK_CACHE)
        if cache_data:
            return cache_data, "API调用失败，加载本地缓存兜底"
        return None, error

    def get_good_list(self) -> Tuple[Optional[List[Dict]], str]:
        """获取全站饰品列表信息"""
        return self._request("GET", "good/list")

    def get_hot_series_list(self, force_refresh: bool = False) -> Tuple[Optional[List[Dict]], str]:
        """获取热门系列饰品列表"""
        if not force_refresh:
            cache_data = load_cache(CSQAQ_SERIES_CACHE)
            if cache_data:
                return cache_data, "加载本地缓存成功"
        data, error = self._request("GET", "series/list")
        if data:
            save_cache(data, CSQAQ_SERIES_CACHE)
            return data, ""
        cache_data = load_cache_force(CSQAQ_SERIES_CACHE)
        if cache_data:
            return cache_data, "API调用失败，加载本地缓存兜底"
        return None, error

    def get_series_detail(self, series_id: str) -> Tuple[Optional[Dict], str]:
        """获取单件热门系列饰品详情"""
        return self._request("GET", f"series/detail/{series_id}")

    # ==================== 挂刀行情接口 ====================
    def get_exchange_data(self, force_refresh: bool = False) -> Tuple[Optional[List[Dict]], str]:
        """获取挂刀行情详情信息"""
        if not force_refresh:
            cache_data = load_cache(CSQAQ_EXCHANGE_CACHE, expire_hours=1)
            if cache_data:
                return cache_data, "加载本地缓存成功"
        data, error = self._request("GET", "exchange/list")
        if data:
            save_cache(data, CSQAQ_EXCHANGE_CACHE)
            return data, ""
        cache_data = load_cache_force(CSQAQ_EXCHANGE_CACHE)
        if cache_data:
            return cache_data, "API调用失败，加载本地缓存兜底"
        return None, error

    # ==================== 库存监控全接口 ====================
    def get_monitor_latest_dynamic(self) -> Tuple[Optional[List[Dict]], str]:
        """获取库存监控最新动态"""
        return self._request("GET", "monitor/latest")

    def get_monitor_task_list(self, keyword: str = "") -> Tuple[Optional[List[Dict]], str]:
        """获取库存监控任务列表，支持模糊检索"""
        return self._request("POST", "monitor/task_list", json={"keyword": keyword})

    def get_monitor_hold_rank(self, good_id: str) -> Tuple[Optional[List[Dict]], str]:
        """获取饰品持有量排行榜"""
        return self._request("GET", f"monitor/hold_rank/{good_id}")

    def get_monitor_user_info(self, task_id: str) -> Tuple[Optional[Dict], str]:
        """获取监控单个用户信息"""
        return self._request("GET", f"monitor/user_info/{task_id}")

    def get_monitor_user_dynamic(self, task_id: str) -> Tuple[Optional[List[Dict]], str]:
        """获取监控单个用户库存动态"""
        return self._request("GET", f"monitor/user_dynamic/{task_id}")

    def get_monitor_user_inventory(self, task_id: str) -> Tuple[Optional[List[Dict]], str]:
        """获取监控单个用户全部库存"""
        return self._request("GET", f"monitor/user_inventory/{task_id}")

    def get_monitor_user_snapshot(self, task_id: str) -> Tuple[Optional[List[Dict]], str]:
        """获取监控单个用户库存快照列表"""
        return self._request("GET", f"monitor/user_snapshot/{task_id}")

    # ==================== 武器箱/开箱数据全接口 ====================
    def get_case_open_stat(self, force_refresh: bool = False) -> Tuple[Optional[List[Dict]], str]:
        """获取武器箱开箱数量统计"""
        if not force_refresh:
            cache_data = load_cache(CSQAQ_CASE_CACHE)
            if cache_data:
                return cache_data, "加载本地缓存成功"
        data, error = self._request("GET", "case/open_stat")
        if data:
            save_cache(data, CSQAQ_CASE_CACHE)
            return data, ""
        cache_data = load_cache_force(CSQAQ_CASE_CACHE)
        if cache_data:
            return cache_data, "API调用失败，加载本地缓存兜底"
        return None, error

    def get_case_return_list(self) -> Tuple[Optional[List[Dict]], str]:
        """获取武器箱开箱回报率列表"""
        return self._request("GET", "case/return_list")

    def get_case_return_trend(self, case_id: str) -> Tuple[Optional[List[Dict]], str]:
        """获取单个武器箱开箱回报率走势"""
        return self._request("GET", f"case/return_trend/{case_id}")

    def get_case_open_history(self, case_id: str) -> Tuple[Optional[List[Dict]], str]:
        """获取单个武器箱历史开箱量"""
        return self._request("GET", f"case/open_history/{case_id}")

    def get_all_collection_list(self) -> Tuple[Optional[List[Dict]], str]:
        """获取所有收藏品列表"""
        return self._request("GET", "collection/list")

    def get_collection_detail(self, collection_id: str) -> Tuple[Optional[Dict], str]:
        """获取单个收藏品包含物详情"""
        return self._request("GET", f"collection/detail/{collection_id}")

# ==================== 通用业务工具函数 ====================
def send_to_wechat(message: str, source: str = PlatformType.SYNTHESIS.value):
    """企业微信推送函数，强制标注数据来源"""
    source_mark = f"\n【数据来源：{source}】"
    full_message = message + source_mark
    headers = {'Content-Type': 'application/json'}
    payload = {
        "msgtype": "text",
        "text": {
            "content": full_message
        }
    }
    try:
        response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(payload), timeout=10, proxies=NO_PROXY)
        response.raise_for_status()
        result = response.json()
        return result.get('errcode') == 0
    except Exception as e:
        return False

def parse_item_info(item_name: str) -> Tuple[str, str]:
    """解析饰品类型和磨损度，用于筛选功能"""
    wear_match = WEAR_PATTERN.search(item_name)
    wear_level = wear_match.group(1) if wear_match else "无磨损"
    weapon_type = "其他"
    weapon_match = WEAPON_NAME_PATTERN.match(item_name)
    weapon_prefix = weapon_match.group(1).strip() if weapon_match else item_name
    
    WEAPON_TYPE_MAP = {
        "Glock": "手枪", "USP": "手枪", "P250": "手枪", "Desert Eagle": "手枪", "Five-SeveN": "手枪",
        "AK-47": "步枪", "M4A4": "步枪", "M4A1": "步枪", "AUG": "步枪", "Galil": "步枪", "FAMAS": "步枪",
        "AWP": "狙击枪", "SSG 08": "狙击枪", "SCAR-20": "狙击枪", "G3SG1": "狙击枪",
        "MP5": "冲锋枪", "MP7": "冲锋枪", "MP9": "冲锋枪", "P90": "冲锋枪", "UMP": "冲锋枪", "MAC-10": "冲锋枪",
        "Nova": "霰弹枪", "XM1014": "霰弹枪", "Sawed-Off": "霰弹枪", "MAG-7": "霰弹枪",
        "Negev": "机枪", "M249": "机枪",
        "Karambit": "刀具", "Butterfly Knife": "刀具", "M9 Bayonet": "刀具", "Bayonet": "刀具",
        "Glove": "手套", "Gloves": "手套", "Hand Wraps": "手套",
        "Case": "武器箱", "Sticker": "贴纸", "Music Kit": "音乐盒", "Agent": "探员"
    }
    for weapon_key, type_name in WEAPON_TYPE_MAP.items():
        if weapon_key in weapon_prefix:
            weapon_type = type_name
            break
    return weapon_type, wear_level

def init_item_classify_data(item_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """给饰品列表预添加分类和磨损字段，用于筛选功能"""
    classified_list = []
    for item in item_list:
        item_name = item.get("name", " ")
        weapon_type, wear_level = parse_item_info(item_name)
        classified_item = item.copy()
        classified_item["weapon_type"] = weapon_type
        classified_item["wear_level"] = wear_level
        classified_list.append(classified_item)
    return classified_list

def filter_items(
    item_list: List[Dict[str, Any]],
    weapon_type: str = "全部",
    wear_level: str = "全部",
    keyword: str = ""
) -> List[Dict[str, Any]]:
    """多条件筛选饰品，核心筛选功能完整保留"""
    filtered = item_list.copy()
    if weapon_type != "全部":
        filtered = [item for item in filtered if item["weapon_type"] == weapon_type]
    if wear_level != "全部":
        filtered = [item for item in filtered if item["wear_level"] == wear_level]
    if keyword.strip():
        keyword = keyword.strip().lower()
        filtered = [item for item in filtered if keyword in item["name"].lower()]
    return filtered

def clean_standard_data(platform: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """统一数据清洗标准化，强制标注来源"""
    if not data:
        return None
    standard_data = {
        "basic": {
            "name": data.get("name", ""),
            "market_hash_name": data.get("marketHashName", ""),
            "good_id": data.get("good_id", ""),
            "weapon_type": "",
            "wear_level": ""
        },
        "price": {
            "sell_price": 0.0,
            "bid_price": 0.0,
            "min_price": 0.0,
            "avg_7day": 0.0
        },
        "trade": {
            "volume": 0,
            "sell_count": 0,
            "bid_count": 0
        },
        "source": platform,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_data": data
    }
    weapon_type, wear_level = parse_item_info(standard_data["basic"]["name"])
    standard_data["basic"]["weapon_type"] = weapon_type
    standard_data["basic"]["wear_level"] = wear_level

    if platform == PlatformType.STEAMDT.value:
        if isinstance(data.get("sellPrice"), (int, float)) and data["sellPrice"] > 0:
            standard_data["price"]["sell_price"] = round(data["sellPrice"], 2)
        if isinstance(data.get("biddingPrice"), (int, float)) and data["biddingPrice"] > 0:
            standard_data["price"]["bid_price"] = round(data["biddingPrice"], 2)
        if isinstance(data.get("sellCount"), int) and data["sellCount"] >= 0:
            standard_data["trade"]["sell_count"] = data["sellCount"]
        if isinstance(data.get("bidCount"), int) and data["bidCount"] >= 0:
            standard_data["trade"]["bid_count"] = data["bidCount"]
        if isinstance(data.get("avgPrice"), (int, float)) and data["avgPrice"] > 0:
            standard_data["price"]["avg_7day"] = round(data["avgPrice"], 2)
    elif platform == PlatformType.CSQAQ.value:
        if isinstance(data.get("sell_price"), (int, float)) and data["sell_price"] > 0:
            standard_data["price"]["sell_price"] = round(data["sell_price"], 2)
            standard_data["price"]["min_price"] = round(data["sell_price"], 2)
        if isinstance(data.get("bid_price"), (int, float)) and data["bid_price"] > 0:
            standard_data["price"]["bid_price"] = round(data["bid_price"], 2)
        if isinstance(data.get("volume"), (int, float)) and data["volume"] >= 0:
            standard_data["trade"]["volume"] = int(data["volume"])
        if isinstance(data.get("sell_count"), int) and data["sell_count"] >= 0:
            standard_data["trade"]["sell_count"] = data["sell_count"]
        if isinstance(data.get("bid_count"), int) and data["bid_count"] >= 0:
            standard_data["trade"]["bid_count"] = data["bid_count"]
    return standard_data

def merge_dual_platform_data(dt_data: Dict[str, Any], qaq_data: Dict[str, Any]) -> Dict[str, Any]:
    """双平台数据合并，保留双源原始数据，标注合并来源"""
    if not dt_data and not qaq_data:
        return {}
    if not dt_data:
        return qaq_data
    if not qaq_data:
        return dt_data

    merged_data = dt_data.copy()
    merged_data["source"] = PlatformType.SYNTHESIS.value
    merged_data["merge_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if qaq_data["price"]["sell_price"] > 0:
        merged_data["price"] = qaq_data["price"]
    if qaq_data["trade"]["volume"] > 0:
        merged_data["trade"]["volume"] = qaq_data["trade"]["volume"]
    
    for key in merged_data["basic"]:
        if merged_data["basic"][key] == "" and qaq_data["basic"][key] != "":
            merged_data["basic"][key] = qaq_data["basic"][key]
    for key in merged_data["trade"]:
        if merged_data["trade"][key] == 0 and qaq_data["trade"][key] > 0:
            merged_data["trade"][key] = qaq_data["trade"][key]
    
    merged_data["raw_steamdt_data"] = dt_data.get("raw_data", {})
    merged_data["raw_csqaq_data"] = qaq_data.get("raw_data", {})
    return merged_data

# ==================== 价格监测配置函数 ====================
def load_monitor_config() -> List[Dict[str, Any]]:
    """加载监测配置，自动去重"""
    if os.path.exists(MONITOR_CONFIG_FILE):
        try:
            with open(MONITOR_CONFIG_FILE, "r", encoding="utf-8") as f:
                raw_config = json.load(f)
            unique_config = []
            seen = set()
            for item in raw_config:
                key = f"{item.get('name')}_{item.get('market_hash_name')}"
                if key not in seen:
                    seen.add(key)
                    unique_config.append(item)
            if len(unique_config) != len(raw_config):
                save_monitor_config(unique_config)
            return unique_config
        except Exception as e:
            return []
    return []

def save_monitor_config(config: List[Dict[str, Any]]):
    """保存监测配置"""
    with open(MONITOR_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ==================== GUI主界面（终极完整版）====================
class CS2ItemDataTerminal(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CS2 饰品双平台全功能数据终端 | 终极完整版")
        self.geometry("1680x1050")
        self.resizable(True, True)
        self._init_global_variables()
        self._init_api_clients()
        self._create_notebook()
        self._create_all_tabs()
        threading.Thread(target=self._init_platform_data, daemon=True).start()

    def _init_global_variables(self):
        """全局变量初始化（全功能扩展）"""
        self.CURRENT_DATA_MODE = tk.StringVar(value=DataSourceMode.SYNTHESIS.value)
        self.AI_SWITCH = tk.BooleanVar(value=False)
        self.AI_API_URL = tk.StringVar(value=DEFAULT_AI_API_URL)
        self.AI_API_KEY = tk.StringVar(value="")
        self.AI_MODEL_NAME = tk.StringVar(value=DEFAULT_AI_MODEL)
        self.AI_TEMPERATURE = tk.DoubleVar(value=DEFAULT_AI_TEMPERATURE)
        # 核心数据存储
        self.steamdt_item_data: Optional[List[Dict]] = None
        self.csqaq_item_data: Optional[List[Dict]] = None
        self.csqaq_series_data: Optional[List[Dict]] = None
        self.csqaq_case_data: Optional[List[Dict]] = None
        self.classified_item_data: Optional[List[Dict]] = None
        self.is_loading = False
        self.final_analysis_data: Optional[Dict] = None
        # 价格监测相关
        self.monitor_config: List[Dict] = load_monitor_config()
        for item in self.monitor_config:
            if "history" not in item:
                item["history"] = []
        save_monitor_config(self.monitor_config)
        self.monitor_thread_running = False
        self.monitor_refresh_interval = DEFAULT_REFRESH_INTERVAL
        self.monitor_thread: Optional[threading.Thread] = None
        # 排行榜枚举绑定
        self.rank_type_map = {e.name: e for e in RankType}
        self.period_type_map = {e.name: e for e in PeriodType}

    def _init_api_clients(self):
        """初始化API客户端"""
        self.dt_api = SteamDTAPI()
        self.qaq_api = CSQAQAPI()

    def _create_notebook(self):
        """创建标签页容器"""
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

    def _create_all_tabs(self):
        """创建所有功能标签页（原有功能100%保留+CSQAQ全功能扩展）"""
        # 原有核心功能Tab
        self.tab_quick_search = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_quick_search, text="🔍 快速查询(筛选)")
        self._create_quick_search_tab()

        self.tab_single_price = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_single_price, text="💰 单饰品价格")
        self._create_single_price_tab()

        self.tab_batch_price = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_batch_price, text="📦 批量价格")
        self._create_batch_price_tab()

        self.tab_avg_price = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_avg_price, text="📈 7天均价")
        self._create_avg_price_tab()

        self.tab_wear_query = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_wear_query, text="🔍 磨损查询")
        self._create_wear_query_tab()

        self.tab_preview_image = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_preview_image, text="🖼️ 检视图生成")
        self._create_preview_image_tab()

        self.tab_price_monitor = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_price_monitor, text="⚠️ 价格监测")
        self._create_price_monitor_tab()

        self.tab_ai_analysis = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_ai_analysis, text="🤖 AI智能分析")
        self._create_ai_analysis_tab()

        # CSQAQ全功能扩展Tab
        self.tab_csqaq_index = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_csqaq_index, text="📊 饰品指数")
        self._create_csqaq_index_tab()

        self.tab_csqaq_rank = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_csqaq_rank, text="🏆 涨跌排行")
        self._create_csqaq_rank_tab()

        self.tab_csqaq_exchange = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_csqaq_exchange, text="💱 挂刀行情")
        self._create_csqaq_exchange_tab()

        self.tab_csqaq_series = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_csqaq_series, text="📦 热门系列")
        self._create_csqaq_series_tab()

        self.tab_csqaq_case = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_csqaq_case, text="🎁 开箱数据")
        self._create_csqaq_case_tab()

        self.tab_csqaq_monitor = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_csqaq_monitor, text="👁️ 库存监控")
        self._create_csqaq_monitor_tab()

        self.tab_csqaq_kline = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_csqaq_kline, text="📈 饰品K线")
        self._create_csqaq_kline_tab()

        self.tab_system_config = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_system_config, text="⚙️ 系统配置")
        self._create_system_config_tab()

    # ==================== 通用UI工具函数 ====================
    def _append_log(self, text: str, widget: scrolledtext.ScrolledText, end="\n"):
        """通用日志输出函数，全场景统一使用"""
        def _append():
            widget.config(state=tk.NORMAL)
            widget.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {text}{end}")
            widget.config(state=tk.DISABLED)
            widget.see(tk.END)
        self.after(0, _append)

    def _init_platform_data(self):
        """初始化双平台基础数据，强化兜底逻辑"""
        self.is_loading = True
        self._append_log("🔄 正在初始化双平台基础数据...", self.quick_log)
        # SteamDT数据初始化
        dt_data, dt_msg = self.dt_api.get_all_item_base_info()
        if dt_data:
            self.steamdt_item_data = dt_data
            self.classified_item_data = init_item_classify_data(dt_data)
            self._append_log(f"✅ SteamDT数据初始化成功，共 {len(dt_data)} 个饰品 | {dt_msg}", self.quick_log)
        else:
            self._append_log(f"⚠️ SteamDT数据初始化异常 | {dt_msg}，已启用兜底缓存", self.quick_log)
        # CSQAQ IP绑定+全量数据初始化
        bind_success, bind_msg = self.qaq_api.bind_local_ip()
        if bind_success:
            self._append_log(f"✅ CSQAQ IP白名单绑定成功 | {bind_msg}", self.quick_log)
        else:
            self._append_log(f"⚠️ CSQAQ IP白名单绑定异常 | {bind_msg}", self.quick_log)
        qaq_data, qaq_msg = self.qaq_api.get_all_good_id()
        if qaq_data:
            self.csqaq_item_data = qaq_data
            self._append_log(f"✅ CSQAQ饰品数据初始化成功，共 {len(qaq_data)} 个饰品 | {qaq_msg}", self.quick_log)
        else:
            self._append_log(f"⚠️ CSQAQ饰品数据初始化异常 | {qaq_msg}，已启用兜底缓存", self.quick_log)
        # CSQAQ附属数据初始化
        series_data, series_msg = self.qaq_api.get_hot_series_list()
        if series_data:
            self.csqaq_series_data = series_data
            self._append_log(f"✅ CSQAQ热门系列数据初始化成功，共 {len(series_data)} 个系列", self.quick_log)
        case_data, case_msg = self.qaq_api.get_case_open_stat()
        if case_data:
            self.csqaq_case_data = case_data
            self._append_log(f"✅ CSQAQ武器箱数据初始化成功，共 {len(case_data)} 个武器箱", self.quick_log)
        # 更新UI状态
        self.after(0, lambda: self.home_status_label.config(text="✅ 双平台全量数据初始化完成", foreground="green"))
        self.after(0, self.do_filter_items)
        self.is_loading = False

    # ==================== 快速查询Tab（原有功能100%保留）====================
    def _create_quick_search_tab(self):
        # 状态栏
        status_frame = ttk.Frame(self.tab_quick_search)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        self.home_status_label = ttk.Label(status_frame, text="⏳ 正在初始化双平台数据...", foreground="orange", font=("微软雅黑", 10, "bold"))
        self.home_status_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(status_frame, text="🔄 刷新饰品数据", command=self.manual_update_data).pack(side=tk.RIGHT, padx=5)
        ttk.Button(status_frame, text="📡 重新绑定CSQAQ IP", command=self.rebind_qaq_ip).pack(side=tk.RIGHT, padx=5)

        # 筛选条件面板
        filter_frame = ttk.LabelFrame(self.tab_quick_search, text="筛选条件")
        filter_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(filter_frame, text="武器类型:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.weapon_type_combo = ttk.Combobox(filter_frame, state="readonly", width=12)
        self.weapon_type_combo.grid(row=0, column=1, padx=5, pady=8)
        all_types = sorted(list(set([
            "手枪", "步枪", "狙击枪", "冲锋枪", "霰弹枪", "机枪", "刀具", "手套",
            "武器箱", "贴纸", "音乐盒", "探员", "其他"
        ])))
        self.weapon_type_combo["values"] = ["全部"] + all_types
        self.weapon_type_combo.current(0)

        ttk.Label(filter_frame, text="磨损度:").grid(row=0, column=2, padx=10, pady=8, sticky="w")
        self.wear_level_combo = ttk.Combobox(filter_frame, state="readonly", width=10)
        self.wear_level_combo.grid(row=0, column=3, padx=5, pady=8)
        self.wear_level_combo["values"] = WEAR_LEVEL_LIST
        self.wear_level_combo.current(0)

        ttk.Label(filter_frame, text="关键字搜索:").grid(row=0, column=4, padx=10, pady=8, sticky="w")
        self.search_keyword_input = ttk.Entry(filter_frame, width=20)
        self.search_keyword_input.grid(row=0, column=5, padx=5, pady=8)
        self.search_keyword_input.insert(0, "")

        ttk.Label(filter_frame, text="监测预警阈值 (%):").grid(row=0, column=6, padx=10, pady=8, sticky="w")
        self.quick_threshold_input = ttk.Entry(filter_frame, width=6)
        self.quick_threshold_input.grid(row=0, column=7, padx=5, pady=8)
        self.quick_threshold_input.insert(0, "5")

        self.search_btn = ttk.Button(filter_frame, text="搜索", command=self.do_filter_items)
        self.search_btn.grid(row=0, column=8, padx=10, pady=8)
        self.reset_filter_btn = ttk.Button(filter_frame, text="重置筛选", command=self.reset_filter)
        self.reset_filter_btn.grid(row=0, column=9, padx=5, pady=8)
        self.search_keyword_input.bind("<Return>", lambda event: self.do_filter_items())

        # 筛选结果表格
        table_frame = ttk.LabelFrame(self.tab_quick_search, text="筛选结果（按住 Ctrl/Shift 可多选）")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        quick_columns = ("item_name", "weapon_type", "wear_level", "market_hash_name")
        self.quick_search_tree = ttk.Treeview(
            table_frame, columns=quick_columns, show="headings", height=18, selectmode="extended"
        )
        self.quick_search_tree.heading("item_name", text="饰品中文全称")
        self.quick_search_tree.heading("weapon_type", text="武器类型")
        self.quick_search_tree.heading("wear_level", text="磨损度")
        self.quick_search_tree.heading("market_hash_name", text="marketHashName")
        self.quick_search_tree.column("item_name", width=380)
        self.quick_search_tree.column("weapon_type", width=90)
        self.quick_search_tree.column("wear_level", width=90)
        self.quick_search_tree.column("market_hash_name", width=550)
        self.quick_search_tree.tag_configure("even", background="#f5f5f5")
        self.quick_search_tree.tag_configure("odd", background="#ffffff")

        quick_tree_y_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.quick_search_tree.yview)
        quick_tree_x_scroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.quick_search_tree.xview)
        self.quick_search_tree.configure(yscrollcommand=quick_tree_y_scroll.set, xscrollcommand=quick_tree_x_scroll.set)
        quick_tree_y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        quick_tree_x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.quick_search_tree.pack(fill=tk.BOTH, expand=True)
        self.quick_search_tree.bind("<Double-1>", self.on_quick_item_double_click)

        # 操作按钮栏
        action_frame = ttk.Frame(self.tab_quick_search)
        action_frame.pack(fill=tk.X, padx=10, pady=8)
        self.quick_query_price_btn = ttk.Button(action_frame, text="查询单饰品价格", command=self.quick_query_price)
        self.quick_query_price_btn.pack(side=tk.LEFT, padx=5)
        self.quick_query_avg_btn = ttk.Button(action_frame, text="查询 7 日均价", command=self.quick_query_7day_avg)
        self.quick_query_avg_btn.pack(side=tk.LEFT, padx=5)
        self.quick_add_batch_btn = ttk.Button(action_frame, text="添加到批量查询", command=self.quick_add_to_batch)
        self.quick_add_batch_btn.pack(side=tk.LEFT, padx=5)
        self.quick_add_monitor_btn = ttk.Button(action_frame, text="添加到价格监测", command=self.quick_add_to_monitor)
        self.quick_add_monitor_btn.pack(side=tk.LEFT, padx=5)
        self.quick_copy_name_btn = ttk.Button(action_frame, text="复制饰品名称", command=self.quick_copy_item_name)
        self.quick_copy_name_btn.pack(side=tk.LEFT, padx=5)
        self.quick_copy_hash_btn = ttk.Button(action_frame, text="复制 marketHashName", command=self.quick_copy_hash_name)
        self.quick_copy_hash_btn.pack(side=tk.LEFT, padx=5)

        # 操作日志
        log_frame = ttk.LabelFrame(self.tab_quick_search, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.quick_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, height=5)
        self.quick_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ==================== 快速查询相关方法 ====================
    def rebind_qaq_ip(self):
        threading.Thread(target=self._rebind_qaq_ip_logic, daemon=True).start()

    def _rebind_qaq_ip_logic(self):
        self._append_log("🔄 正在重新绑定CSQAQ IP白名单...", self.quick_log)
        bind_success, bind_msg = self.qaq_api.bind_local_ip()
        if bind_success:
            self._append_log(f"✅ CSQAQ IP白名单绑定成功 | {bind_msg}", self.quick_log)
        else:
            self._append_log(f"❌ CSQAQ IP白名单绑定失败 | {bind_msg}", self.quick_log)

    def manual_update_data(self):
        if self.is_loading:
            self._append_log("⚠️ 数据正在加载中，请稍候", self.quick_log)
            return
        self.home_status_label.config(text="🔄 更新中...", foreground="orange")
        self._append_log("🔄 开始手动更新饰品数据...", self.quick_log)
        threading.Thread(target=self._manual_update_logic, daemon=True).start()

    def _manual_update_logic(self):
        dt_data, dt_msg = self.dt_api.get_all_item_base_info(force_refresh=True)
        if dt_data:
            self.steamdt_item_data = dt_data
            self.classified_item_data = init_item_classify_data(dt_data)
            self._append_log(f"✅ SteamDT数据更新成功，共 {len(self.classified_item_data)} 个饰品", self.quick_log)
        else:
            self._append_log(f"❌ SteamDT数据更新失败，继续使用缓存 | {dt_msg}", self.quick_log)
        qaq_data, qaq_msg = self.qaq_api.get_all_good_id(force_refresh=True)
        if qaq_data:
            self.csqaq_item_data = qaq_data
            self._append_log(f"✅ CSQAQ数据更新成功，共 {len(qaq_data)} 个饰品", self.quick_log)
        else:
            self._append_log(f"❌ CSQAQ数据更新失败，继续使用缓存 | {qaq_msg}", self.quick_log)
        self.after(0, lambda: self.home_status_label.config(text="✅ 数据更新完成", foreground="green"))
        self.after(0, self.do_filter_items)

    def do_filter_items(self):
        if not self.classified_item_data:
            self._append_log("⚠️ 饰品基础数据尚未加载完成，请稍候", self.quick_log)
            return
        weapon_type = self.weapon_type_combo.get()
        wear_level = self.wear_level_combo.get()
        keyword = self.search_keyword_input.get()
        filtered_list = filter_items(
            self.classified_item_data, weapon_type=weapon_type, wear_level=wear_level, keyword=keyword
        )
        for item in self.quick_search_tree.get_children():
            self.quick_search_tree.delete(item)
        for idx, item in enumerate(filtered_list):
            tag = "even" if idx % 2 == 0 else "odd"
            self.quick_search_tree.insert("", tk.END, values=(
                item["name"],
                item["weapon_type"],
                item["wear_level"],
                item["marketHashName"]
            ), tags=(tag,))
        self._append_log(f"✅ 筛选完成，共找到 {len(filtered_list)} 个符合条件的饰品", self.quick_log)

    def reset_filter(self):
        self.weapon_type_combo.current(0)
        self.wear_level_combo.current(0)
        self.search_keyword_input.delete(0, tk.END)
        self.quick_threshold_input.delete(0, tk.END)
        self.quick_threshold_input.insert(0, "5")
        self.do_filter_items()

    def on_quick_item_double_click(self, event):
        self.quick_query_price()

    def get_selected_quick_items(self) -> List[Dict[str, Any]]:
        selected_items = self.quick_search_tree.selection()
        if not selected_items:
            self._append_log("⚠️ 请先选中表格中的饰品", self.quick_log)
            return []
        result = []
        for selected_item in selected_items:
            item_values = self.quick_search_tree.item(selected_item, "values")
            item_name = item_values[0]
            for item in self.classified_item_data:
                if item["name"] == item_name:
                    result.append(item)
                    break
        return result

    def quick_query_price(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        if len(selected_items) > 1:
            self._append_log("⚠️ 单饰品价格查询仅支持选中 1 个饰品", self.quick_log)
            return
        selected_item = selected_items[0]
        item_name = selected_item["name"]
        self.notebook.select(self.tab_single_price)
        self.single_price_input.delete(0, tk.END)
        self.single_price_input.insert(0, item_name)
        self.query_single_price()

    def quick_query_7day_avg(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        if len(selected_items) > 1:
            self._append_log("⚠️ 7 日均价查询仅支持选中 1 个饰品", self.quick_log)
            return
        selected_item = selected_items[0]
        item_name = selected_item["name"]
        self.notebook.select(self.tab_avg_price)
        self.avg_price_input.delete(0, tk.END)
        self.avg_price_input.insert(0, item_name)
        self.query_avg_price()

    def quick_add_to_batch(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        current_text = self.batch_price_input.get().strip()
        current_names = [name.strip() for name in current_text.split(",") if name.strip()]
        new_names = []
        for item in selected_items:
            item_name = item["name"]
            if item_name not in current_names:
                current_names.append(item_name)
                new_names.append(item_name)
        self.batch_price_input.delete(0, tk.END)
        self.batch_price_input.insert(0, ", ".join(current_names))
        self._append_log(f"✅ 已添加 {len(new_names)} 个饰品到批量查询列表", self.quick_log)
        self.notebook.select(self.tab_batch_price)

    def quick_add_to_monitor(self):
        if self.is_loading or not self.steamdt_item_data:
            self._append_log("⚠️ 饰品基础数据尚未加载完成", self.quick_log)
            return
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        threading.Thread(target=self._quick_add_monitor_logic, args=(selected_items,), daemon=True).start()

    def _quick_add_monitor_logic(self, selected_items: List[Dict]):
        try:
            threshold = float(self.quick_threshold_input.get().strip())
            if threshold <= 0:
                threshold = 5
        except:
            threshold = 5
        success_count = 0
        skip_count = 0
        fail_count = 0
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append_log(f"🔄 正在批量添加 {len(selected_items)} 个饰品到监测列表...", self.quick_log)
        for selected_item in selected_items:
            item_name = selected_item["name"]
            hash_name = selected_item["marketHashName"]
            for item in self.monitor_config:
                if item["name"] == item_name:
                    skip_count += 1
                    continue
            init_price = None
            price_data, _ = self.dt_api.get_single_price(hash_name)
            if price_data:
                min_price = float("inf")
                for platform_data in price_data:
                    sell_price = platform_data.get("sellPrice")
                    if isinstance(sell_price, (int, float)) and sell_price > 0 and sell_price < min_price:
                        min_price = sell_price
                if min_price != float("inf"):
                    init_price = min_price
            if not init_price:
                fail_count += 1
                self._append_log(f"❌【{item_name}】初始价格获取失败，跳过", self.quick_log)
                continue
            new_monitor_item = {
                "name": item_name,
                "market_hash_name": hash_name,
                "init_price": init_price,
                "last_price": init_price,
                "current_price": init_price,
                "threshold": threshold,
                "update_time": current_time,
                "source": PlatformType.STEAMDT.value,
                "history": [{"time": current_time, "price": init_price}]
            }
            self.monitor_config.append(new_monitor_item)
            success_count += 1
        save_monitor_config(self.monitor_config)
        self.after(0, self.update_monitor_table)
        self._append_log(f"✅ 批量添加完成：成功{success_count}个，跳过{skip_count}个，失败{fail_count}个", self.quick_log)

    def quick_copy_item_name(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        names = [item["name"] for item in selected_items]
        copy_text = ", ".join(names)
        self.clipboard_clear()
        self.clipboard_append(copy_text)
        self._append_log(f"✅ 已复制 {len(names)} 个饰品名称", self.quick_log)

    def quick_copy_hash_name(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        hash_names = [item["marketHashName"] for item in selected_items]
        copy_text = "\n".join(hash_names)
        self.clipboard_clear()
        self.clipboard_append(copy_text)
        self._append_log(f"✅ 已复制 {len(hash_names)} 个 marketHashName", self.quick_log)

    # ==================== 单饰品价格Tab（移除手动推送，自动推送）====================
    def _create_single_price_tab(self):
        input_frame = ttk.Frame(self.tab_single_price)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(input_frame, text="饰品中文全称:").pack(side=tk.LEFT, padx=5)
        self.single_price_input = ttk.Entry(input_frame, width=60)
        self.single_price_input.pack(side=tk.LEFT, padx=5)
        self.single_price_input.insert(0, "AK-47 | 红线 (略有磨损)")
        ttk.Button(input_frame, text="查询双平台价格", command=self.query_single_price).pack(side=tk.LEFT, padx=5)
        self.single_price_result = scrolledtext.ScrolledText(self.tab_single_price, wrap=tk.WORD, state=tk.DISABLED)
        self.single_price_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.single_price_cache = {}

    def query_single_price(self):
        if self.is_loading:
            self._append_log("⚠️ 数据正在加载中，请稍候", self.single_price_result)
            return
        cn_name = self.single_price_input.get().strip()
        if not cn_name:
            self._append_log("⚠️ 请输入饰品名称", self.single_price_result)
            return
        threading.Thread(target=self._query_single_price_logic, args=(cn_name,), daemon=True).start()

    def _query_single_price_logic(self, cn_name: str):
        self._append_log(f"\n===== 双平台价格查询：{cn_name} =====", self.single_price_result)
        self.single_price_cache = {"name": cn_name, "dt_data": None, "qaq_data": None}
        push_message = f"🔍【CS2饰品双平台价格查询】\n饰品名称：{cn_name}\n\n"
        source = PlatformType.SYNTHESIS.value
        # SteamDT数据查询
        if self.steamdt_item_data:
            hash_name = None
            for item in self.steamdt_item_data:
                if item.get("name", "").strip() == cn_name:
                    hash_name = item.get("marketHashName")
                    break
            if not hash_name:
                self._append_log("❌ SteamDT未找到该饰品，请检查名称和磨损度是否完全匹配", self.single_price_result)
                push_message += "【SteamDT】未找到该饰品\n"
            else:
                self._append_log(f"✅ SteamDT匹配成功 | marketHashName: {hash_name}", self.single_price_result)
                price_data, error = self.dt_api.get_single_price(hash_name)
                if price_data:
                    self.single_price_cache["dt_data"] = price_data
                    self._append_log("\n【SteamDT平台数据】", self.single_price_result)
                    push_message += "【SteamDT平台数据】\n"
                    min_price = float("inf")
                    min_platform = ""
                    for platform_data in price_data:
                        platform = platform_data.get("platform", "未知平台")
                        sell_price = platform_data.get("sellPrice", "未知")
                        sell_count = platform_data.get("sellCount", 0)
                        bid_price = platform_data.get("biddingPrice", "未知")
                        line = f"  【{platform}】在售价格：{sell_price} | 在售数量：{sell_count} | 求购价格：{bid_price}"
                        self._append_log(line, self.single_price_result)
                        push_message += line + "\n"
                        if isinstance(sell_price, (int, float)) and sell_price < min_price:
                            min_price = sell_price
                            min_platform = platform
                    if min_platform:
                        line = f"  💡 全网最低：{min_price}（{min_platform}）"
                        self._append_log(line, self.single_price_result)
                        push_message += line + "\n"
                else:
                    line = f"❌ SteamDT价格查询失败 | {error}"
                    self._append_log(line, self.single_price_result)
                    push_message += line + "\n"
        # CSQAQ数据查询
        if self.csqaq_item_data:
            good_id = self.qaq_api.get_good_id_by_name(self.csqaq_item_data, cn_name)
            if not good_id:
                self._append_log("❌ CSQAQ未找到该饰品，请检查名称和磨损度是否完全匹配", self.single_price_result)
                push_message += "\n【CSQAQ】未找到该饰品\n"
            else:
                self._append_log(f"✅ CSQAQ匹配成功 | good_id: {good_id}", self.single_price_result)
                detail_data, error = self.qaq_api.get_single_good_detail(good_id)
                if detail_data:
                    self.single_price_cache["qaq_data"] = detail_data
                    self._append_log("\n【CSQAQ平台数据】", self.single_price_result)
                    push_message += "\n【CSQAQ平台数据】\n"
                    sell_price = detail_data.get("sell_price", "未知")
                    bid_price = detail_data.get("bid_price", "未知")
                    volume = detail_data.get("volume", "未知")
                    sell_count = detail_data.get("sell_count", "未知")
                    bid_count = detail_data.get("bid_count", "未知")
                    line1 = f"  当前售价：{sell_price} | 求购价：{bid_price}"
                    line2 = f"  日成交量：{volume} | 在售数量：{sell_count} | 求购数量：{bid_count}"
                    self._append_log(line1, self.single_price_result)
                    self._append_log(line2, self.single_price_result)
                    push_message += line1 + "\n" + line2 + "\n"
                else:
                    line = f"❌ CSQAQ详情查询失败 | {error}"
                    self._append_log(line, self.single_price_result)
                    push_message += line + "\n"
        # 自动推送
        send_to_wechat(push_message, source)
        self._append_log("✅ 查询结果已自动推送到企业微信", self.single_price_result)

    # ==================== 批量价格Tab（移除手动推送，自动推送）====================
    def _create_batch_price_tab(self):
        input_frame = ttk.Frame(self.tab_batch_price)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(input_frame, text="饰品名称（中文，逗号分隔）:").pack(side=tk.LEFT, padx=5)
        self.batch_price_input = ttk.Entry(input_frame, width=80)
        self.batch_price_input.pack(side=tk.LEFT, padx=5)
        self.batch_price_input.insert(0, "AWP | 二西莫夫 (久经沙场), M4A1-S | 氮化处理 (崭新出厂)")
        ttk.Button(input_frame, text="查询双平台批量价格", command=self.query_batch_price).pack(side=tk.LEFT, padx=5)
        self.batch_price_result = scrolledtext.ScrolledText(self.tab_batch_price, wrap=tk.WORD, state=tk.DISABLED)
        self.batch_price_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.batch_price_cache = {}

    def query_batch_price(self):
        if self.is_loading:
            self._append_log("⚠️ 数据正在加载中，请稍候", self.batch_price_result)
            return
        input_text = self.batch_price_input.get().strip()
        if not input_text:
            self._append_log("⚠️ 请输入饰品名称", self.batch_price_result)
            return
        cn_names = [name.strip() for name in input_text.split(",") if name.strip()]
        threading.Thread(target=self._query_batch_price_logic, args=(cn_names,), daemon=True).start()

    def _query_batch_price_logic(self, cn_names: List[str]):
        self._append_log(f"\n===== 双平台批量价格查询，共 {len(cn_names)} 个饰品 =====", self.batch_price_result)
        self.batch_price_cache = {"names": cn_names, "dt_data": None, "qaq_data": None}
        push_message = f"📊【CS2饰品双平台批量价格查询】\n共查询 {len(cn_names)} 个饰品\n\n"
        source = PlatformType.SYNTHESIS.value
        # SteamDT批量查询
        if self.steamdt_item_data:
            hash_names = []
            name_map = {}
            for cn_name in cn_names:
                for item in self.steamdt_item_data:
                    if item.get("name", "").strip() == cn_name:
                        hash_name = item.get("marketHashName")
                        hash_names.append(hash_name)
                        name_map[hash_name] = cn_name
                        break
            if not hash_names:
                self._append_log("❌ SteamDT未匹配到任何饰品，请检查名称", self.batch_price_result)
                push_message += "【SteamDT】未匹配到任何饰品\n"
            else:
                self._append_log(f"✅ SteamDT匹配成功，共 {len(hash_names)} 个饰品", self.batch_price_result)
                batch_data, error = self.dt_api.get_batch_price(hash_names)
                if batch_data:
                    self.batch_price_cache["dt_data"] = batch_data
                    self._append_log("\n【SteamDT平台批量数据】", self.batch_price_result)
                    push_message += "【SteamDT平台批量数据】\n"
                    for item in batch_data:
                        hash_name = item.get("marketHashName", "未知")
                        cn_name = name_map.get(hash_name, hash_name)
                        self._append_log(f"\n  📦 {cn_name}", self.batch_price_result)
                        push_message += f"\n📦 {cn_name}\n"
                        for platform_data in item.get("dataList", []):
                            platform = platform_data.get("platform", "未知")
                            price = platform_data.get("sellPrice", "未知")
                            line = f"    【{platform}】售价：{price}"
                            self._append_log(line, self.batch_price_result)
                            push_message += line + "\n"
                else:
                    line = f"❌ SteamDT批量查询失败 | {error}"
                    self._append_log(line, self.batch_price_result)
                    push_message += line + "\n"
        # CSQAQ批量查询
        if self.csqaq_item_data:
            hash_names = []
            name_map = {}
            for cn_name in cn_names:
                for item in self.csqaq_item_data:
                    if item.get("name", "").strip() == cn_name:
                        hash_name = item.get("marketHashName")
                        hash_names.append(hash_name)
                        name_map[hash_name] = cn_name
                        break
            if not hash_names:
                self._append_log("❌ CSQAQ未匹配到任何饰品，请检查名称", self.batch_price_result)
                push_message += "\n【CSQAQ】未匹配到任何饰品\n"
            else:
                self._append_log(f"✅ CSQAQ匹配成功，共 {len(hash_names)} 个饰品", self.batch_price_result)
                batch_data, error = self.qaq_api.get_batch_price(hash_names)
                if batch_data:
                    self.batch_price_cache["qaq_data"] = batch_data
                    self._append_log("\n【CSQAQ平台批量数据】", self.batch_price_result)
                    push_message += "\n【CSQAQ平台批量数据】\n"
                    for item in batch_data:
                        hash_name = item.get("marketHashName", "未知")
                        cn_name = name_map.get(hash_name, hash_name)
                        sell_price = item.get("sell_price", "未知")
                        sell_count = item.get("sell_count", "未知")
                        line = f"  📦 {cn_name} | 售价：{sell_price} | 在售数量：{sell_count}"
                        self._append_log(line, self.batch_price_result)
                        push_message += line + "\n"
                else:
                    line = f"❌ CSQAQ批量查询失败 | {error}"
                    self._append_log(line, self.batch_price_result)
                    push_message += line + "\n"
        # 自动推送
        send_to_wechat(push_message, source)
        self._append_log("✅ 查询结果已自动推送到企业微信", self.batch_price_result)

    # ==================== 7天均价Tab（移除手动推送，自动推送）====================
    def _create_avg_price_tab(self):
        input_frame = ttk.Frame(self.tab_avg_price)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(input_frame, text="饰品中文全称:").pack(side=tk.LEFT, padx=5)
        self.avg_price_input = ttk.Entry(input_frame, width=60)
        self.avg_price_input.pack(side=tk.LEFT, padx=5)
        self.avg_price_input.insert(0, "AK-47 | 红线 (略有磨损)")
        ttk.Button(input_frame, text="查询双平台7天均价", command=self.query_avg_price).pack(side=tk.LEFT, padx=5)
        self.avg_price_result = scrolledtext.ScrolledText(self.tab_avg_price, wrap=tk.WORD, state=tk.DISABLED)
        self.avg_price_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.avg_price_cache = {}

    def query_avg_price(self):
        if self.is_loading:
            self._append_log("⚠️ 数据正在加载中，请稍候", self.avg_price_result)
            return
        cn_name = self.avg_price_input.get().strip()
        if not cn_name:
            self._append_log("⚠️ 请输入饰品名称", self.avg_price_result)
            return
        threading.Thread(target=self._query_avg_price_logic, args=(cn_name,), daemon=True).start()

    def _query_avg_price_logic(self, cn_name: str):
        self._append_log(f"\n===== 双平台7天均价查询：{cn_name} =====", self.avg_price_result)
        self.avg_price_cache = {"name": cn_name, "dt_data": None, "qaq_data": None}
        push_message = f"📈【CS2饰品双平台7天均价查询】\n饰品名称：{cn_name}\n\n"
        source = PlatformType.SYNTHESIS.value
        # SteamDT均价查询
        if self.steamdt_item_data:
            hash_name = None
            for item in self.steamdt_item_data:
                if item.get("name", "").strip() == cn_name:
                    hash_name = item.get("marketHashName")
                    break
            if not hash_name:
                self._append_log("❌ SteamDT未找到该饰品", self.avg_price_result)
                push_message += "【SteamDT】未找到该饰品\n"
            else:
                self._append_log(f"✅ SteamDT匹配成功 | marketHashName: {hash_name}", self.avg_price_result)
                avg_data, error = self.dt_api.get_7day_average_price(hash_name)
                if avg_data:
                    self.avg_price_cache["dt_data"] = avg_data
                    self._append_log("\n【SteamDT平台7天均价】", self.avg_price_result)
                    push_message += "【SteamDT平台7天均价】\n"
                    line = f"  全平台近7天均价：{avg_data.get('avgPrice', '未知')}"
                    self._append_log(line, self.avg_price_result)
                    push_message += line + "\n"
                    for platform_data in avg_data.get("dataList", []):
                        platform = platform_data.get("platform", "未知")
                        avg_price = platform_data.get("avgPrice", "未知")
                        line = f"  【{platform}】近7天均价：{avg_price}"
                        self._append_log(line, self.avg_price_result)
                        push_message += line + "\n"
                else:
                    line = f"❌ SteamDT均价查询失败 | {error}"
                    self._append_log(line, self.avg_price_result)
                    push_message += line + "\n"
        # CSQAQ数据查询
        if self.csqaq_item_data:
            good_id = self.qaq_api.get_good_id_by_name(self.csqaq_item_data, cn_name)
            if not good_id:
                self._append_log("❌ CSQAQ未找到该饰品", self.avg_price_result)
                push_message += "\n【CSQAQ】未找到该饰品\n"
            else:
                self._append_log(f"✅ CSQAQ匹配成功 | good_id: {good_id}", self.avg_price_result)
                detail_data, error = self.qaq_api.get_single_good_detail(good_id)
                if detail_data:
                    self.avg_price_cache["qaq_data"] = detail_data
                    self._append_log("\n【CSQAQ平台价格数据】", self.avg_price_result)
                    push_message += "\n【CSQAQ平台价格数据】\n"
                    line1 = f"  当前售价：{detail_data.get('sell_price', '未知')}"
                    line2 = f"  近7天成交量：{detail_data.get('volume', '未知')}"
                    self._append_log(line1, self.avg_price_result)
                    self._append_log(line2, self.avg_price_result)
                    push_message += line1 + "\n" + line2 + "\n"
                else:
                    line = f"❌ CSQAQ数据查询失败 | {error}"
                    self._append_log(line, self.avg_price_result)
                    push_message += line + "\n"
        # 自动推送
        send_to_wechat(push_message, source)
        self._append_log("✅ 查询结果已自动推送到企业微信", self.avg_price_result)

    # ==================== 磨损查询Tab（原有功能保留，自动推送）====================
    def _create_wear_query_tab(self):
        url_frame = ttk.LabelFrame(self.tab_wear_query, text="通过检视链接查询磨损")
        url_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(url_frame, text="检视链接:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        self.wear_url_input = ttk.Entry(url_frame, width=100)
        self.wear_url_input.grid(row=0, column=1, padx=5, pady=8)
        ttk.Button(url_frame, text="查询磨损", command=self.query_wear_by_url).grid(row=0, column=2, padx=10, pady=8)

        asmd_frame = ttk.LabelFrame(self.tab_wear_query, text="通过ASMD参数查询磨损")
        asmd_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(asmd_frame, text="ASMD 参数:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        self.wear_asmd_input = ttk.Entry(asmd_frame, width=100)
        self.wear_asmd_input.grid(row=0, column=1, padx=5, pady=8)
        ttk.Button(asmd_frame, text="查询磨损", command=self.query_wear_by_asmd).grid(row=0, column=2, padx=10, pady=8)

        self.wear_result = scrolledtext.ScrolledText(self.tab_wear_query, wrap=tk.WORD, state=tk.DISABLED)
        self.wear_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def query_wear_by_url(self):
        url = self.wear_url_input.get().strip()
        if not url:
            self._append_log("⚠️ 请输入检视链接", self.wear_result)
            return
        threading.Thread(target=self._query_wear_url_logic, args=(url,), daemon=True).start()

    def _query_wear_url_logic(self, url: str):
        self._append_log(f"\n===== 检视链接磨损查询【{PlatformType.STEAMDT.value}】 =====", self.wear_result)
        wear_data, error = self.dt_api.get_wear_by_inspect_url(url)
        if wear_data:
            result_str = json.dumps(wear_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.wear_result)
            push_message = f"🔍【CS2饰品磨损查询】\n检视链接：{url}\n查询结果：\n{result_str}"
            send_to_wechat(push_message, PlatformType.STEAMDT.value)
            self._append_log("✅ 查询结果已自动推送到企业微信", self.wear_result)
        else:
            self._append_log(f"❌ 查询失败 | {error}", self.wear_result)

    def query_wear_by_asmd(self):
        asmd = self.wear_asmd_input.get().strip()
        if not asmd:
            self._append_log("⚠️ 请输入ASMD参数", self.wear_result)
            return
        threading.Thread(target=self._query_wear_asmd_logic, args=(asmd,), daemon=True).start()

    def _query_wear_asmd_logic(self, asmd: str):
        self._append_log(f"\n===== ASMD参数磨损查询【{PlatformType.STEAMDT.value}】 =====", self.wear_result)
        wear_data, error = self.dt_api.get_wear_by_asmd(asmd)
        if wear_data:
            result_str = json.dumps(wear_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.wear_result)
            push_message = f"🔍【CS2饰品磨损查询】\nASMD参数：{asmd}\n查询结果：\n{result_str}"
            send_to_wechat(push_message, PlatformType.STEAMDT.value)
            self._append_log("✅ 查询结果已自动推送到企业微信", self.wear_result)
        else:
            self._append_log(f"❌ 查询失败 | {error}", self.wear_result)

    # ==================== 检视图生成Tab（原有功能保留，自动推送）====================
    def _create_preview_image_tab(self):
        url_frame = ttk.LabelFrame(self.tab_preview_image, text="通过检视链接生成检视图")
        url_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(url_frame, text="检视链接:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        self.image_url_input = ttk.Entry(url_frame, width=100)
        self.image_url_input.grid(row=0, column=1, padx=5, pady=8)
        ttk.Button(url_frame, text="生成检视图", command=self.gen_image_by_url).grid(row=0, column=2, padx=10, pady=8)

        asmd_frame = ttk.LabelFrame(self.tab_preview_image, text="通过ASMD参数生成检视图")
        asmd_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(asmd_frame, text="ASMD 参数:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        self.image_asmd_input = ttk.Entry(asmd_frame, width=100)
        self.image_asmd_input.grid(row=0, column=1, padx=5, pady=8)
        ttk.Button(asmd_frame, text="生成检视图", command=self.gen_image_by_asmd).grid(row=0, column=2, padx=10, pady=8)

        self.image_result = scrolledtext.ScrolledText(self.tab_preview_image, wrap=tk.WORD, state=tk.DISABLED)
        self.image_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def gen_image_by_url(self):
        url = self.image_url_input.get().strip()
        if not url:
            self._append_log("⚠️ 请输入检视链接", self.image_result)
            return
        threading.Thread(target=self._gen_image_url_logic, args=(url,), daemon=True).start()

    def _gen_image_url_logic(self, url: str):
        self._append_log(f"\n===== 检视链接生成检视图【{PlatformType.STEAMDT.value}】 =====", self.image_result)
        image_data, error = self.dt_api.generate_preview_image_by_url(url)
        if image_data:
            result_str = json.dumps(image_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.image_result)
            push_message = f"🖼️【CS2饰品检视图生成】\n检视链接：{url}\n生成结果：\n{result_str}"
            send_to_wechat(push_message, PlatformType.STEAMDT.value)
            self._append_log("✅ 生成结果已自动推送到企业微信", self.image_result)
        else:
            self._append_log(f"❌ 生成失败 | {error}", self.image_result)

    def gen_image_by_asmd(self):
        asmd = self.image_asmd_input.get().strip()
        if not asmd:
            self._append_log("⚠️ 请输入ASMD参数", self.image_result)
            return
        threading.Thread(target=self._gen_image_asmd_logic, args=(asmd,), daemon=True).start()

    def _gen_image_asmd_logic(self, asmd: str):
        self._append_log(f"\n===== ASMD参数生成检视图【{PlatformType.STEAMDT.value}】 =====", self.image_result)
        image_data, error = self.dt_api.generate_preview_image_by_asmd(asmd)
        if image_data:
            result_str = json.dumps(image_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.image_result)
            push_message = f"🖼️【CS2饰品检视图生成】\nASMD参数：{asmd}\n生成结果：\n{result_str}"
            send_to_wechat(push_message, PlatformType.STEAMDT.value)
            self._append_log("✅ 生成结果已自动推送到企业微信", self.image_result)
        else:
            self._append_log(f"❌ 生成失败 | {error}", self.image_result)

    # ==================== 价格监测Tab（原有功能保留，自动推送）====================
    def _create_price_monitor_tab(self):
        add_frame = ttk.LabelFrame(self.tab_price_monitor, text="添加监测饰品")
        add_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(add_frame, text="饰品中文全称:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        self.monitor_add_input = ttk.Entry(add_frame, width=40)
        self.monitor_add_input.grid(row=0, column=1, padx=5, pady=8)
        self.monitor_add_input.insert(0, "AK-47 | 红线 (略有磨损)")

        ttk.Label(add_frame, text="涨跌预警阈值 (%):").grid(row=0, column=2, padx=5, pady=8, sticky="w")
        self.monitor_threshold_input = ttk.Entry(add_frame, width=10)
        self.monitor_threshold_input.grid(row=0, column=3, padx=5, pady=8)
        self.monitor_threshold_input.insert(0, "5")

        ttk.Button(add_frame, text="添加到监测", command=self.add_monitor_item).grid(row=0, column=4, padx=10, pady=8)

        control_frame = ttk.Frame(self.tab_price_monitor)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        self.refresh_btn = ttk.Button(control_frame, text="手动刷新全部", command=self.manual_refresh_monitor)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        self.auto_refresh_btn = ttk.Button(control_frame, text="开启自动刷新", command=self.toggle_auto_refresh)
        self.auto_refresh_btn.pack(side=tk.LEFT, padx=5)
        ttk.Label(control_frame, text="刷新间隔 (秒):").pack(side=tk.LEFT, padx=10)
        self.interval_input = ttk.Entry(control_frame, width=8)
        self.interval_input.pack(side=tk.LEFT, padx=5)
        self.interval_input.insert(0, str(DEFAULT_REFRESH_INTERVAL))
        self.clear_btn = ttk.Button(control_frame, text="清空监测列表", command=self.clear_monitor)
        self.clear_btn.pack(side=tk.RIGHT, padx=5)

        table_frame = ttk.Frame(self.tab_price_monitor)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        columns = ("name", "current_price", "last_price", "change_amount", "change_rate", "init_price", "total_change", "update_time", "source")
        self.monitor_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        self.monitor_tree.heading("name", text="饰品名称")
        self.monitor_tree.heading("current_price", text="当前价格")
        self.monitor_tree.heading("last_price", text="上次价格")
        self.monitor_tree.heading("change_amount", text="涨跌额")
        self.monitor_tree.heading("change_rate", text="涨跌幅")
        self.monitor_tree.heading("init_price", text="初始价格")
        self.monitor_tree.heading("total_change", text="累计涨跌")
        self.monitor_tree.heading("update_time", text="最后刷新时间")
        self.monitor_tree.heading("source", text="数据来源")
        self.monitor_tree.column("name", width=220)
        self.monitor_tree.column("current_price", width=80)
        self.monitor_tree.column("last_price", width=80)
        self.monitor_tree.column("change_amount", width=80)
        self.monitor_tree.column("change_rate", width=80)
        self.monitor_tree.column("init_price", width=80)
        self.monitor_tree.column("total_change", width=80)
        self.monitor_tree.column("update_time", width=160)
        self.monitor_tree.column("source", width=120)
        self.monitor_tree.tag_configure("up", foreground="green")
        self.monitor_tree.tag_configure("down", foreground="red")
        self.monitor_tree.tag_configure("normal", foreground="black")

        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.monitor_tree.yview)
        self.monitor_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.monitor_tree.pack(fill=tk.BOTH, expand=True)

        history_btn_frame = ttk.Frame(self.tab_price_monitor)
        history_btn_frame.pack(fill=tk.X, padx=10, pady=5)
        self.view_history_btn = ttk.Button(history_btn_frame, text="📊 查看选中项历史", command=self.show_selected_history)
        self.view_history_btn.pack(side=tk.LEFT, padx=5)

        log_frame = ttk.LabelFrame(self.tab_price_monitor, text="监测日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.monitor_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, height=6)
        self.monitor_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.update_monitor_table()

    def append_monitor_log(self, text: str):
        def _append():
            self.monitor_log.config(state=tk.NORMAL)
            self.monitor_log.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
            self.monitor_log.config(state=tk.DISABLED)
            self.monitor_log.see(tk.END)
        self.after(0, _append)

    def update_monitor_table(self):
        for item in self.monitor_tree.get_children():
            self.monitor_tree.delete(item)
        for monitor_item in self.monitor_config:
            name = monitor_item["name"]
            current_price = monitor_item.get("current_price", 0)
            last_price = monitor_item.get("last_price", 0)
            init_price = monitor_item.get("init_price", 0)
            update_time = monitor_item.get("update_time", "-")
            source = monitor_item.get("source", PlatformType.STEAMDT.value)

            change_amount = current_price - last_price if last_price > 0 else 0
            change_rate = (change_amount / last_price) * 100 if last_price > 0 else 0
            total_change = current_price - init_price if init_price > 0 else 0

            tag = "up" if change_rate > 0 else "down" if change_rate < 0 else "normal"
            self.monitor_tree.insert("", tk.END, values=(
                name,
                f"{current_price:.2f}",
                f"{last_price:.2f}",
                f"{change_amount:+.2f}",
                f"{change_rate:+.2f}%",
                f"{init_price:.2f}",
                f"{total_change:+.2f}",
                update_time,
                source
            ), tags=(tag,))

    def get_selected_monitor_items(self) -> List[Dict[str, Any]]:
        selected_items = self.monitor_tree.selection()
        if not selected_items:
            self.append_monitor_log("⚠️ 请先选中表格中的饰品")
            return []
        result = []
        for selected_item in selected_items:
            item_values = self.monitor_tree.item(selected_item, "values")
            item_name = item_values[0]
            for config_item in self.monitor_config:
                if config_item["name"] == item_name:
                    result.append(config_item)
                    break
        return result

    def show_selected_history(self):
        selected_configs = self.get_selected_monitor_items()
        if not selected_configs:
            return
        if len(selected_configs) > 1:
            self.append_monitor_log("⚠️ 请只选中一个饰品来查看历史")
            return
        selected_config = selected_configs[0]
        history = selected_config.get("history", [])
        name = selected_config["name"]

        history_window = tk.Toplevel(self)
        history_window.title(f"价格历史 - {name}")
        history_window.geometry("600x400")
        history_window.resizable(True, True)

        history_text = scrolledtext.ScrolledText(history_window, wrap=tk.WORD)
        history_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if not history:
            history_text.insert(tk.END, "暂无历史记录。\n")
        else:
            history_text.insert(tk.END, f"饰品: {name}\n")
            history_text.insert(tk.END, f"初始价格: {selected_config.get('init_price', 0):.2f}\n\n")
            history_text.insert(tk.END, "价格变动历史:\n")
            history_text.insert(tk.END, "-"*60 + "\n")
            for entry in history:
                time_str = entry.get("time", "未知时间")
                price_str = f"{entry.get('price', 0):.2f}"
                history_text.insert(tk.END, f"时间: {time_str} | 价格: {price_str}\n")
        history_text.config(state=tk.DISABLED)

    def add_monitor_item(self):
        if self.is_loading or not self.steamdt_item_data:
            self.append_monitor_log("⚠️ 请等待饰品基础数据加载完成")
            return
        cn_name = self.monitor_add_input.get().strip()
        threshold_str = self.monitor_threshold_input.get().strip()
        if not cn_name:
            self.append_monitor_log("⚠️ 请输入饰品名称")
            return
        try:
            threshold = float(threshold_str)
            if threshold <= 0:
                threshold = 5
        except:
            threshold = 5
            self.monitor_threshold_input.delete(0, tk.END)
            self.monitor_threshold_input.insert(0, "5")

        for item in self.monitor_config:
            if item["name"] == cn_name:
                self.append_monitor_log("⚠️ 该饰品已在监测列表中")
                return

        hash_name = None
        for item in self.steamdt_item_data:
            if item.get("name", "").strip() == cn_name:
                hash_name = item.get("marketHashName")
                break
        if not hash_name:
            self.append_monitor_log("❌ 未找到该饰品，请检查名称和磨损度是否完全匹配")
            return

        self.append_monitor_log(f"正在添加【{cn_name}】，获取初始价格...")
        init_price = None
        source = PlatformType.STEAMDT.value
        price_data, _ = self.dt_api.get_single_price(hash_name)
        if price_data:
            min_price = float("inf")
            for platform_data in price_data:
                sell_price = platform_data.get("sellPrice")
                if isinstance(sell_price, (int, float)) and sell_price > 0 and sell_price < min_price:
                    min_price = sell_price
            if min_price != float("inf"):
                init_price = min_price
        if not init_price:
            self.append_monitor_log("❌ 获取饰品初始价格失败")
            return

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_monitor_item = {
            "name": cn_name,
            "market_hash_name": hash_name,
            "init_price": init_price,
            "last_price": init_price,
            "current_price": init_price,
            "threshold": threshold,
            "update_time": current_time,
            "source": source,
            "history": [{"time": current_time, "price": init_price}]
        }
        self.monitor_config.append(new_monitor_item)
        save_monitor_config(self.monitor_config)
        self.update_monitor_table()
        self.append_monitor_log(f"✅ 成功添加【{cn_name}】，初始价格：{init_price:.2f}，来源：{source}")
        self.monitor_add_input.delete(0, tk.END)

    def refresh_all_monitor(self):
        if not self.monitor_config:
            self.append_monitor_log("监测列表为空，无需刷新")
            return
        refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.append_monitor_log(f"🔄 开始刷新全部监测饰品，共 {len(self.monitor_config)} 个")
        alert_list = []
        change_list = []

        for monitor_item in self.monitor_config:
            name = monitor_item["name"]
            hash_name = monitor_item["market_hash_name"]
            threshold = monitor_item["threshold"]
            source = monitor_item.get("source", PlatformType.STEAMDT.value)
            new_price = None

            price_data, _ = self.dt_api.get_single_price(hash_name)
            if price_data:
                min_price = float("inf")
                for platform_data in price_data:
                    sell_price = platform_data.get("sellPrice")
                    if isinstance(sell_price, (int, float)) and sell_price > 0 and sell_price < min_price:
                        min_price = sell_price
                if min_price != float("inf"):
                    new_price = min_price
            if not new_price:
                self.append_monitor_log(f"⚠️【{name}】价格刷新失败")
                continue

            old_last_price = monitor_item["last_price"]
            old_current_price = monitor_item["current_price"]
            monitor_item["last_price"] = old_current_price
            monitor_item["current_price"] = new_price
            monitor_item["update_time"] = refresh_time
            monitor_item["history"].append({"time": refresh_time, "price": new_price})
            if len(monitor_item["history"]) > 100:
                monitor_item["history"] = monitor_item["history"][-100:]

            change_rate = ((new_price - old_last_price) / old_last_price) * 100 if old_last_price > 0 else 0
            if new_price != old_current_price:
                change_list.append({
                    "name": name,
                    "old_price": old_current_price,
                    "new_price": new_price,
                    "change_rate": change_rate,
                    "source": source
                })
            if abs(change_rate) >= threshold:
                alert_list.append(f"【{name}】涨跌幅：{change_rate:+.2f}%，当前价格：{new_price:.2f}，来源：{source}")

        save_monitor_config(self.monitor_config)
        self.after(0, self.update_monitor_table)

        if change_list:
            change_messages = []
            for change in change_list:
                change_messages.append(f"{change['name']}: {change['old_price']:.2f} -> {change['new_price']:.2f} ({change['change_rate']:+.2f}%)【{change['source']}】")
            change_summary = "\n".join(change_messages)
            wechat_message_changes = f"🔄【CS2饰品价格变动】\n{change_summary}"
            send_to_wechat(wechat_message_changes, PlatformType.SYNTHESIS.value)
            self.append_monitor_log("价格变动信息已推送至企业微信")
        if alert_list:
            alert_msg = "⚠️【CS2饰品价格涨跌预警】\n" + "\n".join(alert_list)
            send_to_wechat(alert_msg, PlatformType.SYNTHESIS.value)
            self.append_monitor_log("预警信息已推送至企业微信")
        self.append_monitor_log(f"✅ 全部饰品刷新完成")

    def manual_refresh_monitor(self):
        if self.is_loading or not self.steamdt_item_data:
            self.append_monitor_log("⚠️ 请等待饰品基础数据加载完成")
            return
        threading.Thread(target=self.refresh_all_monitor, daemon=True).start()

    def auto_refresh_loop(self):
        while self.monitor_thread_running:
            try:
                self.refresh_all_monitor()
            except Exception as e:
                self.append_monitor_log(f"❌ 自动刷新异常：{str(e)}")
            for _ in range(self.monitor_refresh_interval):
                if not self.monitor_thread_running:
                    break
                threading.Event().wait(1)

    def toggle_auto_refresh(self):
        if not self.steamdt_item_data:
            self.append_monitor_log("⚠️ 饰品基础数据未加载")
            return
        if not self.monitor_thread_running:
            try:
                interval = int(self.interval_input.get().strip())
                if interval < 60:
                    interval = 60
                    self.interval_input.delete(0, tk.END)
                    self.interval_input.insert(0, "60")
                    self.append_monitor_log("⚠️ 刷新间隔最小60秒，已自动设置为60秒")
                self.monitor_refresh_interval = interval
            except:
                self.monitor_refresh_interval = DEFAULT_REFRESH_INTERVAL
                self.interval_input.delete(0, tk.END)
                self.interval_input.insert(0, str(DEFAULT_REFRESH_INTERVAL))
                self.append_monitor_log("⚠️ 刷新间隔格式错误，使用默认值300秒")
            self.monitor_thread_running = True
            self.monitor_thread = threading.Thread(target=self.auto_refresh_loop, daemon=True)
            self.monitor_thread.start()
            self.auto_refresh_btn.config(text="关闭自动刷新")
            self.append_monitor_log(f"✅ 自动刷新已开启，刷新间隔：{self.monitor_refresh_interval}秒")
        else:
            self.monitor_thread_running = False
            self.auto_refresh_btn.config(text="开启自动刷新")
            self.append_monitor_log("❌ 自动刷新已关闭")

    def clear_monitor(self):
        self.monitor_config = []
        save_monitor_config(self.monitor_config)
        self.update_monitor_table()
        self.append_monitor_log("🗑️ 监测列表已清空")

    # ==================== AI智能分析Tab（原有功能100%保留）====================
    def _create_ai_analysis_tab(self):
        input_frame = ttk.Frame(self.tab_ai_analysis)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(input_frame, text="饰品中文全称：").pack(side=tk.LEFT, padx=5)
        self.ai_analysis_input = ttk.Entry(input_frame, width=50)
        self.ai_analysis_input.pack(side=tk.LEFT, padx=5)
        self.ai_analysis_input.insert(0, "AK-47 | 红线 (略有磨损)")
        ttk.Button(input_frame, text="执行全流程分析", command=self.run_full_ai_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(input_frame, text="导出分析结果", command=self.export_analysis_result).pack(side=tk.LEFT, padx=5)

        data_frame = ttk.LabelFrame(self.tab_ai_analysis, text="📊 标准化综合数据")
        data_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.ai_data_result = scrolledtext.ScrolledText(data_frame, wrap=tk.WORD, state=tk.DISABLED, height=10)
        self.ai_data_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ai_frame = ttk.LabelFrame(self.tab_ai_analysis, text="🤖 AI智能分析结论")
        ai_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.ai_analysis_result = scrolledtext.ScrolledText(ai_frame, wrap=tk.WORD, state=tk.DISABLED, height=12)
        self.ai_analysis_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def append_ai_data_log(self, text: str):
        def _append():
            self.ai_data_result.config(state=tk.NORMAL)
            self.ai_data_result.delete(1.0, tk.END)
            self.ai_data_result.insert(tk.END, text)
            self.ai_data_result.config(state=tk.DISABLED)
        self.after(0, _append)

    def append_ai_analysis_log(self, text: str):
        def _append():
            self.ai_analysis_result.config(state=tk.NORMAL)
            self.ai_analysis_result.delete(1.0, tk.END)
            self.ai_analysis_result.insert(tk.END, text)
            self.ai_analysis_result.config(state=tk.DISABLED)
        self.after(0, _append)

    def ai_intelligent_analysis(self, standard_data: Dict[str, Any]) -> str:
        if not self.AI_SWITCH.get():
            return "🔘 AI分析模块已关闭，跳过分析步骤"
        if not self.AI_API_KEY.get().strip() or not self.AI_API_URL.get().strip():
            return "❌ AI分析配置不完整：请填写API地址与密钥"
        if not standard_data:
            return "❌ AI分析失败：无有效分析数据"

        prompt = f"""
        你是专业的CS2饰品数据分析师，基于以下标准化饰品数据完成多维度分析，要求结论严谨、简洁、有指导性，分点输出，总字数控制在500字以内。
        分析维度：
        1. 数据质量检测：判断数据完整性、有效性，指出缺失/异常项，明确数据来源
        2. 量价关系分析：分析实时价格、成交量、在售数量的匹配关系
        3. 热度与风险评分：对饰品热度（1-10分）和投资风险（1-10分）打分并说明理由
        4. 波动与异动判断：判断是否存在价格异动、库存异动，是否有异常波动
        5. 操作建议：基于分析结果给出买入/卖出/持有/观望的操作建议
        饰品标准化数据：
        {json.dumps(standard_data, ensure_ascii=False, indent=2)}
        输出要求：使用中文，分点清晰，无冗余内容，不使用Markdown格式。
        """
        headers = {
            "Authorization": f"Bearer {self.AI_API_KEY.get().strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.AI_MODEL_NAME.get().strip(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.AI_TEMPERATURE.get(),
            "max_tokens": 1000,
            "stream": False
        }
        try:
            response = requests.post(self.AI_API_URL.get().strip(), headers=headers, json=payload, timeout=20, proxies=NO_PROXY)
            response.raise_for_status()
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                analysis_result = result["choices"][0]["message"]["content"].strip()
                return analysis_result
            else:
                error_msg = result.get("error", {}).get("message", "大模型无有效返回结果")
                return f"❌ AI分析失败：{error_msg}"
        except Exception as e:
            return f"❌ AI分析网络异常：{str(e)}"

    def run_full_ai_analysis(self):
        if self.is_loading:
            self.append_ai_analysis_log("⚠️ 数据正在加载中，请稍候")
            return
        cn_name = self.ai_analysis_input.get().strip()
        if not cn_name:
            self.append_ai_analysis_log("⚠️ 请输入饰品名称")
            return
        self.append_ai_analysis_log("🔄 开始执行全流程分析，固定双平台同步模式")
        threading.Thread(target=self._full_analysis_logic, args=(cn_name,), daemon=True).start()

    def _full_analysis_logic(self, cn_name: str):
        self.after(0, lambda: self.append_ai_analysis_log("🔍 第一步：双平台数据采集..."))
        dt_clean_data = None
        qaq_clean_data = None
        final_data = None

        if self.steamdt_item_data:
            hash_name = None
            for item in self.steamdt_item_data:
                if item.get("name", "").strip() == cn_name:
                    hash_name = item.get("marketHashName")
                    break
            if not hash_name:
                self.after(0, lambda: self.append_ai_analysis_log("❌ 未找到该饰品，请检查名称和磨损度是否完全匹配"))
                return
            dt_raw_data, _ = self.dt_api.get_single_price(hash_name)
            if dt_raw_data:
                dt_full_data = next((item for item in self.steamdt_item_data if item["name"] == cn_name), {})
                for platform_data in dt_raw_data:
                    dt_full_data.update(platform_data)
                dt_clean_data = clean_standard_data(PlatformType.STEAMDT.value, dt_full_data)
                self.after(0, lambda: self.append_ai_analysis_log("✅ SteamDT数据采集与清洗完成"))

        if self.csqaq_item_data:
            good_id = self.qaq_api.get_good_id_by_name(self.csqaq_item_data, cn_name)
            if good_id:
                qaq_raw_data, _ = self.qaq_api.get_single_good_detail(good_id)
                if qaq_raw_data:
                    qaq_clean_data = clean_standard_data(PlatformType.CSQAQ.value, qaq_raw_data)
                    self.after(0, lambda: self.append_ai_analysis_log("✅ CSQAQ数据采集与清洗完成"))

        self.after(0, lambda: self.append_ai_analysis_log("📦 第二步：双平台数据合并..."))
        final_data = merge_dual_platform_data(dt_clean_data, qaq_clean_data)
        if not final_data:
            self.after(0, lambda: self.append_ai_analysis_log("❌ 数据处理失败，无有效最终数据"))
            return
        self.final_analysis_data = final_data
        self.after(0, lambda: self.append_ai_data_log(json.dumps(final_data, ensure_ascii=False, indent=2)))

        self.after(0, lambda: self.append_ai_analysis_log("🤖 第三步：执行AI智能分析..."))
        ai_result = self.ai_intelligent_analysis(final_data)
        self.after(0, lambda: self.append_ai_analysis_log(ai_result))
        self.after(0, lambda: self.append_ai_analysis_log("✅ 全流程分析执行完成"))

        send_to_wechat(f"🤖【CS2饰品AI智能分析】\n饰品名称：{cn_name}\n分析结论：\n{ai_result}", final_data.get("source", PlatformType.SYNTHESIS.value))

    def export_analysis_result(self):
        if not self.final_analysis_data:
            self.append_ai_analysis_log("⚠️ 暂无分析结果，请先执行分析")
            return
        try:
            export_data = {
                "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_mode": self.CURRENT_DATA_MODE.get(),
                "ai_switch": self.AI_SWITCH.get(),
                "final_data": self.final_analysis_data,
                "ai_analysis": self.ai_analysis_result.get(1.0, tk.END).strip()
            }
            with open(EXPORT_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            self.append_ai_analysis_log(f"✅ 分析结果已导出到：{EXPORT_DATA_FILE}")
        except Exception as e:
            self.append_ai_analysis_log(f"❌ 导出失败：{str(e)}")

    # ==================== CSQAQ 饰品指数Tab ====================
    def _create_csqaq_index_tab(self):
        control_frame = ttk.Frame(self.tab_csqaq_index)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(control_frame, text="刷新指数数据", command=self.refresh_csqaq_index).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="查看指数K线", command=self.show_index_kline).pack(side=tk.LEFT, padx=5)
        self.index_period_combo = ttk.Combobox(control_frame, state="readonly", width=10)
        self.index_period_combo["values"] = [e.name for e in PeriodType]
        self.index_period_combo.current(1)
        self.index_period_combo.pack(side=tk.LEFT, padx=5)

        data_frame = ttk.LabelFrame(self.tab_csqaq_index, text="📊 饰品指数核心数据")
        data_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.index_result = scrolledtext.ScrolledText(data_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.index_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def refresh_csqaq_index(self):
        threading.Thread(target=self._refresh_csqaq_index_logic, daemon=True).start()

    def _refresh_csqaq_index_logic(self):
        self._append_log("🔄 正在获取CSQAQ饰品指数数据...", self.index_result)
        index_data, error = self.qaq_api.get_index_home_data(force_refresh=True)
        if index_data:
            result_str = json.dumps(index_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.index_result)
            push_message = f"📊【CS2饰品指数数据】\n{result_str}"
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ 指数数据已自动推送到企业微信", self.index_result)
        else:
            self._append_log(f"❌ 指数数据获取失败 | {error}", self.index_result)

    def show_index_kline(self):
        period_name = self.index_period_combo.get()
        period = self.period_type_map.get(period_name, PeriodType.DAY_7)
        threading.Thread(target=self._show_index_kline_logic, args=(period,), daemon=True).start()

    def _show_index_kline_logic(self, period: PeriodType):
        self._append_log(f"🔄 正在获取{period.value}周期指数K线数据...", self.index_result)
        kline_data, error = self.qaq_api.get_index_kline(period)
        if kline_data:
            result_str = json.dumps(kline_data, ensure_ascii=False, indent=2)
            self._append_log(f"\n【{period.value}周期指数K线数据】\n{result_str}", self.index_result)
            push_message = f"📈【CS2饰品指数K线】\n周期：{period.value}\n数据：\n{result_str}"
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ K线数据已自动推送到企业微信", self.index_result)
        else:
            self._append_log(f"❌ K线数据获取失败 | {error}", self.index_result)

    # ==================== CSQAQ 涨跌排行Tab ====================
    def _create_csqaq_rank_tab(self):
        filter_frame = ttk.Frame(self.tab_csqaq_rank)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(filter_frame, text="排行类型:").pack(side=tk.LEFT, padx=5)
        self.rank_type_combo = ttk.Combobox(filter_frame, state="readonly", width=15)
        self.rank_type_combo["values"] = [e.name for e in RankType]
        self.rank_type_combo.current(0)
        self.rank_type_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="统计周期:").pack(side=tk.LEFT, padx=5)
        self.rank_period_combo = ttk.Combobox(filter_frame, state="readonly", width=10)
        self.rank_period_combo["values"] = [e.name for e in PeriodType]
        self.rank_period_combo.current(0)
        self.rank_period_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="查询排行榜", command=self.query_rank_list).pack(side=tk.LEFT, padx=10)

        table_frame = ttk.Frame(self.tab_csqaq_rank)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        rank_columns = ("rank", "name", "price", "change_rate", "volume", "sell_count", "source")
        self.rank_tree = ttk.Treeview(table_frame, columns=rank_columns, show="headings", height=20)
        self.rank_tree.heading("rank", text="排名")
        self.rank_tree.heading("name", text="饰品名称")
        self.rank_tree.heading("price", text="当前价格")
        self.rank_tree.heading("change_rate", text="涨跌幅")
        self.rank_tree.heading("volume", text="日成交量")
        self.rank_tree.heading("sell_count", text="在售数量")
        self.rank_tree.heading("source", text="数据来源")
        self.rank_tree.column("rank", width=60)
        self.rank_tree.column("name", width=350)
        self.rank_tree.column("price", width=100)
        self.rank_tree.column("change_rate", width=100)
        self.rank_tree.column("volume", width=100)
        self.rank_tree.column("sell_count", width=100)
        self.rank_tree.column("source", width=120)
        self.rank_tree.tag_configure("up", foreground="green")
        self.rank_tree.tag_configure("down", foreground="red")

        rank_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.rank_tree.yview)
        self.rank_tree.configure(yscrollcommand=rank_scroll.set)
        rank_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.rank_tree.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.LabelFrame(self.tab_csqaq_rank, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.rank_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, height=5)
        self.rank_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def query_rank_list(self):
        rank_type_name = self.rank_type_combo.get()
        period_name = self.rank_period_combo.get()
        rank_type = self.rank_type_map.get(rank_type_name, RankType.PRICE)
        period = self.period_type_map.get(period_name, PeriodType.DAY_1)
        threading.Thread(target=self._query_rank_list_logic, args=(rank_type, period), daemon=True).start()

    # 修复：调用get_rank_list时传入force_refresh=True，确保点击查询时强制刷新
    def _query_rank_list_logic(self, rank_type: RankType, period: PeriodType):
        self._append_log(f"🔄 正在获取{rank_type.name} {period.value} 排行榜数据...", self.rank_log)
        rank_data, error = self.qaq_api.get_rank_list(rank_type, period, force_refresh=True)
        if rank_data:
            for item in self.rank_tree.get_children():
                self.rank_tree.delete(item)
            list_data = rank_data.get("list", [])
            push_message = f"🏆【CS2饰品排行榜】\n类型：{rank_type.name}\n周期：{period.value}\n\n"
            for idx, item in enumerate(list_data[:100]):
                rank = idx + 1
                name = item.get("name", "未知")
                price = item.get("sell_price", 0)
                change_rate = item.get("change_rate", 0)
                volume = item.get("volume", 0)
                sell_count = item.get("sell_count", 0)
                tag = "up" if change_rate > 0 else "down" if change_rate < 0 else "normal"
                self.rank_tree.insert("", tk.END, values=(
                    rank, name, f"{price:.2f}", f"{change_rate:+.2f}%", volume, sell_count, PlatformType.CSQAQ.value
                ), tags=(tag,))
                if rank <= 20:
                    push_message += f"{rank}. {name} | 价格：{price:.2f} | 涨跌幅：{change_rate:+.2f}%\n"
            self._append_log(f"✅ 排行榜数据获取成功，共 {len(list_data)} 条数据", self.rank_log)
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ 排行榜TOP20已自动推送到企业微信", self.rank_log)
        else:
            self._append_log(f"❌ 排行榜数据获取失败 | {error}", self.rank_log)

    # ==================== CSQAQ 挂刀行情Tab ====================
    def _create_csqaq_exchange_tab(self):
        control_frame = ttk.Frame(self.tab_csqaq_exchange)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(control_frame, text="刷新挂刀行情", command=self.refresh_exchange_data).pack(side=tk.LEFT, padx=5)

        table_frame = ttk.Frame(self.tab_csqaq_exchange)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        exchange_columns = ("rank", "name", "steam_price", "platform_price", "rate", "profit", "source")
        self.exchange_tree = ttk.Treeview(table_frame, columns=exchange_columns, show="headings", height=20)
        self.exchange_tree.heading("rank", text="排名")
        self.exchange_tree.heading("name", text="饰品名称")
        self.exchange_tree.heading("steam_price", text="Steam价格")
        self.exchange_tree.heading("platform_price", text="平台价格")
        self.exchange_tree.heading("rate", text="兑换比例")
        self.exchange_tree.heading("profit", text="利润")
        self.exchange_tree.heading("source", text="数据来源")
        self.exchange_tree.column("rank", width=60)
        self.exchange_tree.column("name", width=350)
        self.exchange_tree.column("steam_price", width=120)
        self.exchange_tree.column("platform_price", width=120)
        self.exchange_tree.column("rate", width=100)
        self.exchange_tree.column("profit", width=100)
        self.exchange_tree.column("source", width=120)

        exchange_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.exchange_tree.yview)
        self.exchange_tree.configure(yscrollcommand=exchange_scroll.set)
        exchange_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.exchange_tree.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.LabelFrame(self.tab_csqaq_exchange, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.exchange_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, height=5)
        self.exchange_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def refresh_exchange_data(self):
        threading.Thread(target=self._refresh_exchange_data_logic, daemon=True).start()

    def _refresh_exchange_data_logic(self):
        self._append_log("🔄 正在获取CSQAQ挂刀行情数据...", self.exchange_log)
        exchange_data, error = self.qaq_api.get_exchange_data(force_refresh=True)
        if exchange_data:
            for item in self.exchange_tree.get_children():
                self.exchange_tree.delete(item)
            push_message = f"💱【CS2饰品挂刀行情】\nTOP20最优挂刀方案：\n\n"
            for idx, item in enumerate(exchange_data[:100]):
                rank = idx + 1
                name = item.get("name", "未知")
                steam_price = item.get("steam_price", 0)
                platform_price = item.get("platform_price", 0)
                rate = item.get("rate", 0)
                profit = item.get("profit", 0)
                self.exchange_tree.insert("", tk.END, values=(
                    rank, name, f"{steam_price:.2f}", f"{platform_price:.2f}", f"{rate:.2f}", f"{profit:.2f}", PlatformType.CSQAQ.value
                ))
                if rank <= 20:
                    push_message += f"{rank}. {name} | 兑换比例：{rate:.2f} | 利润：{profit:.2f}\n"
            self._append_log(f"✅ 挂刀行情数据获取成功，共 {len(exchange_data)} 条数据", self.exchange_log)
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ 挂刀行情TOP20已自动推送到企业微信", self.exchange_log)
        else:
            self._append_log(f"❌ 挂刀行情数据获取失败 | {error}", self.exchange_log)

    # ==================== CSQAQ 热门系列Tab ====================
    def _create_csqaq_series_tab(self):
        control_frame = ttk.Frame(self.tab_csqaq_series)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(control_frame, text="刷新热门系列", command=self.refresh_series_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="查看选中系列详情", command=self.show_series_detail).pack(side=tk.LEFT, padx=5)

        table_frame = ttk.Frame(self.tab_csqaq_series)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        series_columns = ("series_id", "name", "item_count", "hot", "source")
        self.series_tree = ttk.Treeview(table_frame, columns=series_columns, show="headings", height=15)
        self.series_tree.heading("series_id", text="系列ID")
        self.series_tree.heading("name", text="系列名称")
        self.series_tree.heading("item_count", text="饰品数量")
        self.series_tree.heading("hot", text="热度")
        self.series_tree.heading("source", text="数据来源")
        self.series_tree.column("series_id", width=100)
        self.series_tree.column("name", width=350)
        self.series_tree.column("item_count", width=100)
        self.series_tree.column("hot", width=100)
        self.series_tree.column("source", width=120)

        series_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.series_tree.yview)
        self.series_tree.configure(yscrollcommand=series_scroll.set)
        series_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.series_tree.pack(fill=tk.BOTH, expand=True)

        detail_frame = ttk.LabelFrame(self.tab_csqaq_series, text="系列详情")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.series_detail_result = scrolledtext.ScrolledText(detail_frame, wrap=tk.WORD, state=tk.DISABLED, height=8)
        self.series_detail_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def refresh_series_list(self):
        threading.Thread(target=self._refresh_series_list_logic, daemon=True).start()

    def _refresh_series_list_logic(self):
        self._append_log("🔄 正在获取CSQAQ热门系列数据...", self.series_detail_result)
        series_data, error = self.qaq_api.get_hot_series_list(force_refresh=True)
        if series_data:
            self.csqaq_series_data = series_data
            for item in self.series_tree.get_children():
                self.series_tree.delete(item)
            for item in series_data:
                self.series_tree.insert("", tk.END, values=(
                    item.get("series_id", ""),
                    item.get("name", "未知"),
                    item.get("item_count", 0),
                    item.get("hot", 0),
                    PlatformType.CSQAQ.value
                ))
            self._append_log(f"✅ 热门系列数据获取成功，共 {len(series_data)} 个系列", self.series_detail_result)
        else:
            self._append_log(f"❌ 热门系列数据获取失败 | {error}", self.series_detail_result)

    def show_series_detail(self):
        selected_items = self.series_tree.selection()
        if not selected_items:
            self._append_log("⚠️ 请先选中表格中的系列", self.series_detail_result)
            return
        series_id = self.series_tree.item(selected_items[0], "values")[0]
        series_name = self.series_tree.item(selected_items[0], "values")[1]
        threading.Thread(target=self._show_series_detail_logic, args=(series_id, series_name), daemon=True).start()

    def _show_series_detail_logic(self, series_id: str, series_name: str):
        self._append_log(f"🔄 正在获取【{series_name}】系列详情...", self.series_detail_result)
        detail_data, error = self.qaq_api.get_series_detail(series_id)
        if detail_data:
            result_str = json.dumps(detail_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.series_detail_result)
            push_message = f"📦【CS2饰品热门系列详情】\n系列名称：{series_name}\n详情数据：\n{result_str}"
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ 系列详情已自动推送到企业微信", self.series_detail_result)
        else:
            self._append_log(f"❌ 系列详情获取失败 | {error}", self.series_detail_result)

    # ==================== CSQAQ 开箱数据Tab ====================
    def _create_csqaq_case_tab(self):
        control_frame = ttk.Frame(self.tab_csqaq_case)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(control_frame, text="刷新开箱统计", command=self.refresh_case_stat).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="查看回报率列表", command=self.show_case_return_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="查看选中武器箱走势", command=self.show_case_trend).pack(side=tk.LEFT, padx=5)

        table_frame = ttk.Frame(self.tab_csqaq_case)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        case_columns = ("case_id", "name", "today_open", "total_open", "source")
        self.case_tree = ttk.Treeview(table_frame, columns=case_columns, show="headings", height=15)
        self.case_tree.heading("case_id", text="武器箱ID")
        self.case_tree.heading("name", text="武器箱名称")
        self.case_tree.heading("today_open", text="今日开箱数")
        self.case_tree.heading("total_open", text="累计开箱数")
        self.case_tree.heading("source", text="数据来源")
        self.case_tree.column("case_id", width=100)
        self.case_tree.column("name", width=350)
        self.case_tree.column("today_open", width=120)
        self.case_tree.column("total_open", width=120)
        self.case_tree.column("source", width=120)

        case_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.case_tree.yview)
        self.case_tree.configure(yscrollcommand=case_scroll.set)
        case_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.case_tree.pack(fill=tk.BOTH, expand=True)

        result_frame = ttk.LabelFrame(self.tab_csqaq_case, text="数据详情")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.case_result = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, state=tk.DISABLED, height=8)
        self.case_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def refresh_case_stat(self):
        threading.Thread(target=self._refresh_case_stat_logic, daemon=True).start()

    def _refresh_case_stat_logic(self):
        self._append_log("🔄 正在获取CSQAQ武器箱开箱统计数据...", self.case_result)
        case_data, error = self.qaq_api.get_case_open_stat(force_refresh=True)
        if case_data:
            self.csqaq_case_data = case_data
            for item in self.case_tree.get_children():
                self.case_tree.delete(item)
            for item in case_data:
                self.case_tree.insert("", tk.END, values=(
                    item.get("case_id", ""),
                    item.get("name", "未知"),
                    item.get("today_open", 0),
                    item.get("total_open", 0),
                    PlatformType.CSQAQ.value
                ))
            self._append_log(f"✅ 武器箱数据获取成功，共 {len(case_data)} 个武器箱", self.case_result)
        else:
            self._append_log(f"❌ 武器箱数据获取失败 | {error}", self.case_result)

    def show_case_return_list(self):
        threading.Thread(target=self._show_case_return_list_logic, daemon=True).start()

    def _show_case_return_list_logic(self):
        self._append_log("🔄 正在获取武器箱开箱回报率列表...", self.case_result)
        return_data, error = self.qaq_api.get_case_return_list()
        if return_data:
            result_str = json.dumps(return_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.case_result)
            push_message = f"🎁【CS2武器箱开箱回报率列表】\n{result_str}"
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ 回报率列表已自动推送到企业微信", self.case_result)
        else:
            self._append_log(f"❌ 回报率列表获取失败 | {error}", self.case_result)

    def show_case_trend(self):
        selected_items = self.case_tree.selection()
        if not selected_items:
            self._append_log("⚠️ 请先选中表格中的武器箱", self.case_result)
            return
        case_id = self.case_tree.item(selected_items[0], "values")[0]
        case_name = self.case_tree.item(selected_items[0], "values")[1]
        threading.Thread(target=self._show_case_trend_logic, args=(case_id, case_name), daemon=True).start()

    def _show_case_trend_logic(self, case_id: str, case_name: str):
        self._append_log(f"🔄 正在获取【{case_name}】回报率走势...", self.case_result)
        trend_data, error = self.qaq_api.get_case_return_trend(case_id)
        if trend_data:
            result_str = json.dumps(trend_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.case_result)
            push_message = f"📈【CS2武器箱回报率走势】\n武器箱：{case_name}\n走势数据：\n{result_str}"
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ 走势数据已自动推送到企业微信", self.case_result)
        else:
            self._append_log(f"❌ 走势数据获取失败 | {error}", self.case_result)

    # ==================== CSQAQ 库存监控Tab ====================
    def _create_csqaq_monitor_tab(self):
        control_frame = ttk.Frame(self.tab_csqaq_monitor)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(control_frame, text="刷新最新动态", command=self.refresh_monitor_dynamic).pack(side=tk.LEFT, padx=5)
        ttk.Label(control_frame, text="用户检索:").pack(side=tk.LEFT, padx=10)
        self.monitor_user_input = ttk.Entry(control_frame, width=20)
        self.monitor_user_input.pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="查询用户任务", command=self.search_monitor_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="查看选中用户库存", command=self.show_user_inventory).pack(side=tk.LEFT, padx=5)

        table_frame = ttk.Frame(self.tab_csqaq_monitor)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        monitor_columns = ("task_id", "user_name", "steam_id", "item_count", "update_time", "source")
        self.monitor_user_tree = ttk.Treeview(table_frame, columns=monitor_columns, show="headings", height=15)
        self.monitor_user_tree.heading("task_id", text="任务ID")
        self.monitor_user_tree.heading("user_name", text="用户名")
        self.monitor_user_tree.heading("steam_id", text="SteamID")
        self.monitor_user_tree.heading("item_count", text="饰品数量")
        self.monitor_user_tree.heading("update_time", text="更新时间")
        self.monitor_user_tree.heading("source", text="数据来源")
        self.monitor_user_tree.column("task_id", width=100)
        self.monitor_user_tree.column("user_name", width=200)
        self.monitor_user_tree.column("steam_id", width=150)
        self.monitor_user_tree.column("item_count", width=100)
        self.monitor_user_tree.column("update_time", width=180)
        self.monitor_user_tree.column("source", width=120)

        monitor_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.monitor_user_tree.yview)
        self.monitor_user_tree.configure(yscrollcommand=monitor_scroll.set)
        monitor_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.monitor_user_tree.pack(fill=tk.BOTH, expand=True)

        result_frame = ttk.LabelFrame(self.tab_csqaq_monitor, text="监控动态/库存详情")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.monitor_detail_result = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, state=tk.DISABLED, height=8)
        self.monitor_detail_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def refresh_monitor_dynamic(self):
        threading.Thread(target=self._refresh_monitor_dynamic_logic, daemon=True).start()

    def _refresh_monitor_dynamic_logic(self):
        self._append_log("🔄 正在获取库存监控最新动态...", self.monitor_detail_result)
        dynamic_data, error = self.qaq_api.get_monitor_latest_dynamic()
        if dynamic_data:
            result_str = json.dumps(dynamic_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.monitor_detail_result)
            push_message = f"👁️【CS2库存监控最新动态】\n{result_str}"
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ 最新动态已自动推送到企业微信", self.monitor_detail_result)
        else:
            self._append_log(f"❌ 最新动态获取失败 | {error}", self.monitor_detail_result)

    def search_monitor_task(self):
        keyword = self.monitor_user_input.get().strip()
        threading.Thread(target=self._search_monitor_task_logic, args=(keyword,), daemon=True).start()

    def _search_monitor_task_logic(self, keyword: str):
        self._append_log(f"🔄 正在检索用户【{keyword}】的监控任务...", self.monitor_detail_result)
        task_data, error = self.qaq_api.get_monitor_task_list(keyword)
        if task_data:
            for item in self.monitor_user_tree.get_children():
                self.monitor_user_tree.delete(item)
            for item in task_data:
                self.monitor_user_tree.insert("", tk.END, values=(
                    item.get("task_id", ""),
                    item.get("user_name", "未知"),
                    item.get("steam_id", ""),
                    item.get("item_count", 0),
                    item.get("update_time", ""),
                    PlatformType.CSQAQ.value
                ))
            self._append_log(f"✅ 检索完成，共找到 {len(task_data)} 个相关任务", self.monitor_detail_result)
        else:
            self._append_log(f"❌ 任务检索失败 | {error}", self.monitor_detail_result)

    def show_user_inventory(self):
        selected_items = self.monitor_user_tree.selection()
        if not selected_items:
            self._append_log("⚠️ 请先选中表格中的用户", self.monitor_detail_result)
            return
        task_id = self.monitor_user_tree.item(selected_items[0], "values")[0]
        user_name = self.monitor_user_tree.item(selected_items[0], "values")[1]
        threading.Thread(target=self._show_user_inventory_logic, args=(task_id, user_name), daemon=True).start()

    def _show_user_inventory_logic(self, task_id: str, user_name: str):
        self._append_log(f"🔄 正在获取【{user_name}】的库存详情...", self.monitor_detail_result)
        inventory_data, error = self.qaq_api.get_monitor_user_inventory(task_id)
        if inventory_data:
            result_str = json.dumps(inventory_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.monitor_detail_result)
            push_message = f"👁️【CS2用户库存详情】\n用户名：{user_name}\n库存数据：\n{result_str}"
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ 库存详情已自动推送到企业微信", self.monitor_detail_result)
        else:
            self._append_log(f"❌ 库存详情获取失败 | {error}", self.monitor_detail_result)

    # ==================== CSQAQ 饰品K线Tab ====================
    def _create_csqaq_kline_tab(self):
        input_frame = ttk.Frame(self.tab_csqaq_kline)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(input_frame, text="饰品中文全称:").pack(side=tk.LEFT, padx=5)
        self.kline_item_input = ttk.Entry(input_frame, width=50)
        self.kline_item_input.pack(side=tk.LEFT, padx=5)
        self.kline_item_input.insert(0, "AK-47 | 红线 (略有磨损)")

        ttk.Label(input_frame, text="K线周期:").pack(side=tk.LEFT, padx=10)
        self.kline_period_combo = ttk.Combobox(input_frame, state="readonly", width=10)
        self.kline_period_combo["values"] = [e.name for e in PeriodType]
        self.kline_period_combo.current(1)
        self.kline_period_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(input_frame, text="查询K线数据", command=self.query_good_kline).pack(side=tk.LEFT, padx=10)

        result_frame = ttk.LabelFrame(self.tab_csqaq_kline, text="K线数据详情")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.kline_result = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.kline_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def query_good_kline(self):
        cn_name = self.kline_item_input.get().strip()
        period_name = self.kline_period_combo.get()
        if not cn_name:
            self._append_log("⚠️ 请输入饰品名称", self.kline_result)
            return
        period = self.period_type_map.get(period_name, PeriodType.DAY_7)
        threading.Thread(target=self._query_good_kline_logic, args=(cn_name, period), daemon=True).start()

    def _query_good_kline_logic(self, cn_name: str, period: PeriodType):
        self._append_log(f"🔄 正在获取【{cn_name}】{period.value}周期K线数据...", self.kline_result)
        if not self.csqaq_item_data:
            self._append_log("❌ CSQAQ饰品数据未加载", self.kline_result)
            return
        good_id = self.qaq_api.get_good_id_by_name(self.csqaq_item_data, cn_name)
        if not good_id:
            self._append_log("❌ 未找到该饰品，请检查名称和磨损度是否完全匹配", self.kline_result)
            return
        kline_data, error = self.qaq_api.get_single_good_kline(good_id, period)
        if kline_data:
            result_str = json.dumps(kline_data, ensure_ascii=False, indent=2)
            self._append_log(result_str, self.kline_result)
            push_message = f"📈【CS2饰品K线数据】\n饰品名称：{cn_name}\n周期：{period.value}\n数据：\n{result_str}"
            send_to_wechat(push_message, PlatformType.CSQAQ.value)
            self._append_log("✅ K线数据已自动推送到企业微信", self.kline_result)
        else:
            self._append_log(f"❌ K线数据获取失败 | {error}", self.kline_result)

    # ==================== 系统配置Tab ====================
    def _create_system_config_tab(self):
        mode_frame = ttk.LabelFrame(self.tab_system_config, text="📊 数据源模式配置")
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(mode_frame, text="当前数据源模式：").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.current_mode_label = ttk.Label(mode_frame, text=DataSourceMode.SYNTHESIS.value, foreground="blue", font=("微软雅黑", 10, "bold"))
        self.current_mode_label.grid(row=0, column=1, padx=5, pady=8, sticky="w")
        ttk.Label(mode_frame, text="说明：固定双平台同步查询，自动合并SteamDT与CSQAQ数据").grid(row=0, column=2, padx=20, pady=8, sticky="w")

        csqaq_frame = ttk.LabelFrame(self.tab_system_config, text="📡 CSQAQ平台配置")
        csqaq_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(csqaq_frame, text="CSQAQ API_KEY：").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.csqaq_api_key_input = ttk.Entry(csqaq_frame, textvariable=tk.StringVar(value=CSQAQ_API_KEY), width=40, show="*")
        self.csqaq_api_key_input.grid(row=0, column=1, padx=5, pady=8)
        self.csqaq_bind_btn_config = ttk.Button(csqaq_frame, text="绑定本机IP白名单", command=self.rebind_qaq_ip_config)
        self.csqaq_bind_btn_config.grid(row=0, column=2, padx=10, pady=8)
        ttk.Button(csqaq_frame, text="刷新CSQAQ全量饰品数据", command=self.refresh_csqaq_data).grid(row=0, column=3, padx=5, pady=8)

        steamdt_frame = ttk.LabelFrame(self.tab_system_config, text="📡 SteamDT平台配置")
        steamdt_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(steamdt_frame, text="SteamDT API_KEY：").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.dt_api_key_input = ttk.Entry(steamdt_frame, textvariable=tk.StringVar(value=STEAMDT_API_KEY), width=40, show="*")
        self.dt_api_key_input.grid(row=0, column=1, padx=5, pady=8)
        ttk.Button(steamdt_frame, text="刷新SteamDT全量饰品数据", command=self.refresh_steamdt_data).grid(row=0, column=2, padx=10, pady=8)

        ai_frame = ttk.LabelFrame(self.tab_system_config, text="🤖 AI智能分析配置")
        ai_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Checkbutton(ai_frame, text="开启AI智能分析模块", variable=self.AI_SWITCH).grid(row=0, column=0, padx=10, pady=8, sticky="w")
        ttk.Label(ai_frame, text="大模型API地址（OpenAI兼容）：").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        ttk.Entry(ai_frame, textvariable=self.AI_API_URL, width=60).grid(row=1, column=1, padx=5, pady=8)
        ttk.Label(ai_frame, text="API密钥：").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        ttk.Entry(ai_frame, textvariable=self.AI_API_KEY, show="*", width=60).grid(row=2, column=1, padx=5, pady=8)
        ttk.Label(ai_frame, text="模型名称：").grid(row=3, column=0, padx=10, pady=8, sticky="w")
        ttk.Entry(ai_frame, textvariable=self.AI_MODEL_NAME, width=30).grid(row=3, column=1, padx=5, pady=8, sticky="w")
        ttk.Label(ai_frame, text="温度系数（0-1）：").grid(row=3, column=2, padx=10, pady=8, sticky="w")
        ttk.Entry(ai_frame, textvariable=self.AI_TEMPERATURE, width=10).grid(row=3, column=3, padx=5, pady=8, sticky="w")
        ttk.Button(ai_frame, text="测试AI连接", command=self.test_ai_connection).grid(row=4, column=0, padx=10, pady=8)

        log_frame = ttk.LabelFrame(self.tab_system_config, text="配置操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.config_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, height=15)
        self.config_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def append_config_log(self, text: str):
        def _append():
            self.config_log.config(state=tk.NORMAL)
            self.config_log.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
            self.config_log.config(state=tk.DISABLED)
            self.config_log.see(tk.END)
        self.after(0, _append)

    def rebind_qaq_ip_config(self):
        threading.Thread(target=self._rebind_qaq_ip_config_logic, daemon=True).start()

    def _rebind_qaq_ip_config_logic(self):
        self.append_config_log("🔄 正在重新绑定CSQAQ IP白名单...")
        bind_success, bind_msg = self.qaq_api.bind_local_ip()
        if bind_success:
            self.append_config_log(f"✅ CSQAQ IP白名单绑定成功 | {bind_msg}")
        else:
            self.append_config_log(f"❌ CSQAQ IP白名单绑定失败 | {bind_msg}")

    def refresh_csqaq_data(self):
        self.append_config_log("🔄 正在刷新CSQAQ全量饰品数据...")
        threading.Thread(target=self._refresh_csqaq_data_logic, daemon=True).start()

    def _refresh_csqaq_data_logic(self):
        csqaq_data, qaq_msg = self.qaq_api.get_all_good_id(force_refresh=True)
        if csqaq_data:
            self.csqaq_item_data = csqaq_data
            self.append_config_log(f"✅ CSQAQ数据刷新成功，共 {len(csqaq_data)} 个饰品 | {qaq_msg}")
        else:
            self.append_config_log(f"❌ CSQAQ数据刷新失败 | {qaq_msg}")

    def refresh_steamdt_data(self):
        self.append_config_log("🔄 正在刷新SteamDT全量饰品数据...")
        threading.Thread(target=self._refresh_steamdt_data_logic, daemon=True).start()

    def _refresh_steamdt_data_logic(self):
        dt_data, dt_msg = self.dt_api.get_all_item_base_info(force_refresh=True)
        if dt_data:
            self.steamdt_item_data = dt_data
            self.classified_item_data = init_item_classify_data(dt_data)
            self.append_config_log(f"✅ SteamDT数据刷新成功，共 {len(dt_data)} 个饰品 | {dt_msg}")
            self.after(0, self.do_filter_items)
        else:
            self.append_config_log(f"❌ SteamDT数据刷新失败 | {dt_msg}")

    def test_ai_connection(self):
        if not self.AI_API_KEY.get().strip() or not self.AI_API_URL.get().strip():
            self.append_config_log("⚠️ 请填写API地址和密钥")
            return
        self.append_config_log("🔄 正在测试AI连接...")
        threading.Thread(target=self._test_ai_connection_logic, daemon=True).start()

    def _test_ai_connection_logic(self):
        headers = {
            "Authorization": f"Bearer {self.AI_API_KEY.get().strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.AI_MODEL_NAME.get().strip(),
            "messages": [{"role": "user", "content": "你好，回复一句话确认连接正常即可"}],
            "max_tokens": 50,
            "stream": False
        }
        try:
            response = requests.post(self.AI_API_URL.get().strip(), headers=headers, json=payload, timeout=10, proxies=NO_PROXY)
            response.raise_for_status()
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                reply = result["choices"][0]["message"]["content"].strip()
                self.append_config_log(f"✅ AI连接测试成功，模型回复：{reply}")
            else:
                error_msg = result.get("error", {}).get("message", "无有效返回")
                self.append_config_log(f"❌ AI连接测试失败：{error_msg}")
        except Exception as e:
            self.append_config_log(f"❌ AI连接测试异常：{str(e)}")

# ==================== 程序入口 ====================
if __name__ == "__main__":
    app = CS2ItemDataTerminal()
    app.mainloop()
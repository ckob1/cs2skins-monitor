import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import requests
import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import sys

# ==================== 配置区 ====================
API_KEY: str = "73970210142d48bbb8515da1a730487b"
BASE_URL: str = "https://open.steamdt.com/open/cs2/v1"
HEADERS: Dict[str, str] = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# --- 新增：企业微信 Webhook URL ---
WEBHOOK_URL: str = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=a7ae7d4c-b0a2-412d-9fa1-cb537cb745ba"

# ==================== 打包兼容路径函数（关键修改） ====================
def get_resource_path(filename: str) -> str:
    """ 获取资源文件路径（兼容打包后的 exe）
    打包文件读取临时目录，运行时缓存写入 exe 同目录 """
    if getattr(sys, 'frozen', False): # 打包后的 exe 环境
        base_path = os.path.dirname(sys.executable)
        # 打包的数据文件在临时目录
        temp_path = getattr(sys, '_MEIPASS', base_path)
        # 优先返回临时目录的打包文件路径
        packed_file = os.path.join(temp_path, filename)
        if os.path.exists(packed_file):
            return packed_file
        # 否则返回 exe 同目录（运行时缓存）
        return os.path.join(base_path, filename)
    else: # 开发环境 - 使用脚本所在目录
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def get_cache_path(filename: str) -> str:
    """ 获取缓存文件写入路径（始终是 exe 同目录，可写） """
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

# 打包数据文件（只读）
PACKED_CACHE_FILE: str = get_resource_path("steam_items_cache.json")
# 运行时缓存文件（可写）
CACHE_FILE: str = get_cache_path("steam_items_cache.json")
MONITOR_CONFIG_FILE: str = get_cache_path("steam_price_monitor.json")
CACHE_EXPIRE_HOURS: int = 24
DEFAULT_REFRESH_INTERVAL: int = 300

# ==================== 全品类精准分类映射 ====================
WEAPON_TYPE_MAP: Dict[str, str] = {
    # 手枪
    "Glock-18": "手枪", "Glock": "手枪", "格洛克": "手枪",
    "P250": "手枪",
    "USP-S": "手枪", "USP": "手枪",
    "P2000": "手枪",
    "Desert Eagle": "手枪", "沙鹰": "手枪",
    "Five-SeveN": "手枪", "FN57": "手枪", "FN 57": "手枪", "Five Seven": "手枪",
    "Tec-9": "手枪", "Tec9": "手枪",
    "CZ75-Auto": "手枪", "CZ75": "手枪",
    "Dual Berettas": "手枪", "双枪": "手枪", "双贝瑞塔": "手枪",
    "R8 Revolver": "手枪", "R8": "手枪", "左轮": "手枪",

    # 步枪
    "AK-47": "步枪", "AK": "步枪",
    "M4A4": "步枪", "M4": "步枪", "M4A1-S": "步枪", "M4A1": "步枪",
    "SG 553": "步枪", "SG553": "步枪",
    "AUG": "步枪",
    "Galil AR": "步枪", "Galil": "步枪", "加利尔": "步枪", "咖喱": "步枪",
    "FAMAS": "步枪", "法玛斯": "步枪",

    # 狙击枪
    "AWP": "狙击枪", "大狙": "狙击枪",
    "SSG 08": "狙击枪", "SSG08": "狙击枪", "鸟狙": "狙击枪",
    "SCAR-20": "狙击枪", "SCAR20": "狙击枪", "连狙": "狙击枪",
    "G3SG1": "狙击枪", "G3": "狙击枪",

    # 冲锋枪
    "MP5-SD": "冲锋枪", "MP5": "冲锋枪",
    "MP7": "冲锋枪",
    "MP9": "冲锋枪",
    "P90": "冲锋枪",
    "PP-Bizon": "冲锋枪", "PP Bizon": "冲锋枪", "野牛": "冲锋枪",
    "UMP-45": "冲锋枪", "UMP45": "冲锋枪", "UMP": "冲锋枪",
    "MAC-10": "冲锋枪", "MAC10": "冲锋枪", "吹风机": "冲锋枪",
    "Vector": "冲锋枪", "维克托": "冲锋枪",

    # 霰弹枪
    "Nova": "霰弹枪", "新星": "霰弹枪",
    "XM1014": "霰弹枪", "连喷": "霰弹枪",
    "Sawed-Off": "霰弹枪", "短喷": "霰弹枪",
    "MAG-7": "霰弹枪", "MAG7": "霰弹枪", "警喷": "霰弹枪",

    # 机枪
    "Negev": "机枪", "内格夫": "机枪",
    "M249": "机枪",

    # 刀具
    "Karambit": "刀具", "爪子刀": "刀具", "爪刀": "刀具",
    "Butterfly Knife": "刀具", "蝴蝶刀": "刀具",
    "M9 Bayonet": "刀具", "M9 刺刀": "刀具",
    "Bayonet": "刀具", "刺刀": "刀具",
    "Flip Knife": "刀具", "折叠刀": "刀具",
    "Gut Knife": "刀具", "穿肠刀": "刀具",
    "Huntsman Knife": "刀具", "猎杀者匕首": "刀具",
    "Falchion Knife": "刀具", "弯刀": "刀具",
    "Bowie Knife": "刀具", "鲍伊猎刀": "刀具",
    "Stiletto": "刀具", "短剑": "刀具",
    "Navaja": "刀具", "折刀": "刀具",
    "Talon": "刀具", "熊刀": "刀具",
    "Ursus": "刀具", "系绳匕首": "刀具",
    "Skeleton Knife": "刀具", "骷髅匕首": "刀具",
    "Nomad Knife": "刀具", "流浪者匕首": "刀具",
    "Survival Knife": "刀具", "求生匕首": "刀具",
    "Paracord Knife": "刀具", "伞兵绳匕首": "刀具",
    "Classic Knife": "刀具", "古典匕首": "刀具",
    "Kukri Knife": "刀具", "廓尔喀刀": "刀具",

    # 手套
    "Glove": "手套", "Gloves": "手套",
    "Hand Wraps": "手套", "裹手": "手套",
    "Broken Fang Gloves": "手套", "裂网手套": "手套",
    "Driver Gloves": "手套", "驾驶手套": "手套",
    "Moto Gloves": "手套", "摩托手套": "手套",
    "Specialist Gloves": "手套", "专业手套": "手套",
    "Sport Gloves": "手套", "运动手套": "手套",
    "Hydra Gloves": "手套", "九头蛇手套": "手套",

    # 其他品类
    "Music Kit": "音乐盒", "音乐盒": "音乐盒",
    "Sticker": "贴纸", "印花": "贴纸",
    "Graffiti": "涂鸦",
    "Patch": "布章",
    "Pin": "胸章",
    "Agent": "探员", "角色": "探员",
    "Case": "武器箱", "箱子": "武器箱",
    "Key": "钥匙",
    "Operation": "通行证",
    "Souvenir": "纪念品",
    "StatTrak": "暗金",
}

WEAR_LEVEL_LIST: List[str] = ["全部", "崭新出厂", "略有磨损", "久经沙场", "破损不堪", "战痕累累"]
WEAR_PATTERN = re.compile(r"((崭新出厂|略有磨损|久经沙场|破损不堪|战痕累累))$")
WEAPON_NAME_PATTERN = re.compile(r"^(.+?)\s*\|")

# ==================== 企业微信推送函数 ====================
def send_to_wechat(message: str):
    """
    发送消息到企业微信群聊机器人
    """
    headers = {'Content-Type': 'application/json'}
    payload = {
        "msgtype": "text",
        "text": {
            "content": message
        }
    }
    try:
        response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        if result.get('errcode') == 0:
            print("✅ 消息已推送到企业微信")
            return True
        else:
            print(f"❌ 推送失败: {result.get('errmsg')}")
            return False
    except Exception as e:
        print(f"❌ 推送异常: {str(e)}")
        return False


# ==================== 核心函数（支持打包数据 + 更新按钮） ====================
def get_steam_items(force_refresh: bool = False) -> Optional[List[Dict[str, Any]]]:
    """ 获取 Steam CS2 饰品基础信息 优先级：1.运行时缓存 2.打包数据 3.API 请求 """
    cache_data = None
    cache_valid = False

    # 1. 优先读取运行时缓存（exe 同目录，可写）
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            cache_time = datetime.fromisoformat(cache_data["cache_time"])
            if datetime.now() - cache_time < timedelta(hours=CACHE_EXPIRE_HOURS):
                cache_valid = True
                print(f"✅ 使用运行时缓存")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"⚠️ 运行时缓存损坏：{str(e)}")
            cache_data = None

    # 2. 其次读取打包数据（只读，作为默认数据）
    if not cache_valid and os.path.exists(PACKED_CACHE_FILE):
        try:
            with open(PACKED_CACHE_FILE, "r", encoding="utf-8") as f:
                packed_data = json.load(f)
            print(f"✅ 使用打包的默认饰品数据")
            return packed_data.get("data", [])
        except Exception as e:
            print(f"⚠️ 打包数据读取失败：{str(e)}")

    # 3. 最后尝试 API 请求
    if force_refresh or not cache_valid:
        print("🔄 正在请求最新饰品数据...")
        try:
            response = requests.get(f"{BASE_URL}/base", headers=HEADERS, timeout=15)
            response.raise_for_status()
            api_data = response.json()
            if api_data.get("success"):
                # 更新运行时缓存
                new_cache_data = {
                    "cache_time": datetime.now().isoformat(),
                    "data": api_data["data"]
                }
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_cache_data, f, ensure_ascii=False, indent=2)
                print(f"✅ 饰品数据更新成功，共 {len(api_data['data'])} 个饰品")
                return api_data["data"]
            else:
                print(f"❌ API 请求失败：{api_data.get('errorMsg', '未知错误')}")
        except Exception as e:
            print(f"❌ 网络请求失败：{str(e)}")
            # API 失败但有打包数据，使用打包数据
            if os.path.exists(PACKED_CACHE_FILE):
                try:
                    with open(PACKED_CACHE_FILE, "r", encoding="utf-8") as f:
                        packed_data = json.load(f)
                    print("⚠️ 使用打包的默认数据（API 请求失败）")
                    return packed_data.get("data", [])
                except:
                    pass
            return None

    return cache_data.get("data", []) if cache_data else None

# ==================== 分类解析核心函数 ====================
def parse_item_info(item_name: str) -> Tuple[str, str]:
    """解析饰品名称，返回 (武器类型，磨损度)"""
    wear_match = WEAR_PATTERN.search(item_name)
    wear_level = wear_match.group(1) if wear_match else "无磨损"
    weapon_type = "其他"
    weapon_match = WEAPON_NAME_PATTERN.match(item_name)
    if weapon_match:
        weapon_prefix = weapon_match.group(1).strip()
        for weapon_key, type_name in WEAPON_TYPE_MAP.items():
            if weapon_key in weapon_prefix:
                weapon_type = type_name
                break
    else:
        for weapon_key, type_name in WEAPON_TYPE_MAP.items():
            if weapon_key in item_name:
                weapon_type = type_name
                break
    return weapon_type, wear_level

def init_item_classify_data(item_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """给饰品列表预添加分类和磨损字段"""
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
    """多条件筛选饰品"""
    filtered = item_list.copy()
    if weapon_type != "全部":
        filtered = [item for item in filtered if item["weapon_type"] == weapon_type]
    if wear_level != "全部":
        filtered = [item for item in filtered if item["wear_level"] == wear_level]
    if keyword.strip():
        keyword = keyword.strip().lower()
        filtered = [item for item in filtered if keyword in item["name"].lower()]
    return filtered

# ==================== 原有核心函数 ====================
def cn_to_market_hash(items: List[Dict[str, Any]], chinese_name: str) -> Optional[str]:
    """中文饰品名 → 官方 marketHashName"""
    if not items or not chinese_name:
        return None
    for item in items:
        if item.get("name", "").strip() == chinese_name.strip():
            return item.get("marketHashName")
    return None

def get_single_item_price(market_hash_name: str) -> Optional[List[Dict[str, Any]]]:
    """单饰品价格查询"""
    if not market_hash_name:
        return None
    params = {"marketHashName": market_hash_name}
    try:
        response = requests.get(
            f"{BASE_URL}/price/single", headers=HEADERS, params=params, timeout=10
        )
        response.raise_for_status()
        api_data = response.json()
        if api_data.get("success"):
            return api_data["data"]
        else:
            print(f"❌ 价格查询失败：{api_data.get('errorMsg', '未知错误')}")
            return None
    except Exception as e:
        print(f"❌ 网络请求失败：{str(e)}")
        return None

def get_item_min_price(market_hash_name: str) -> Optional[float]:
    """获取饰品全网最低售价"""
    price_list = get_single_item_price(market_hash_name)
    if not price_list:
        return None
    min_price = float("inf")
    for platform_data in price_list:
        sell_price = platform_data.get("sellPrice")
        if isinstance(sell_price, (int, float)) and sell_price > 0 and sell_price < min_price:
            min_price = sell_price
    return min_price if min_price != float("inf") else None

def get_batch_item_price(items: List[Dict[str, Any]], chinese_names: List[str]) -> Optional[List[Dict[str, Any]]]:
    """批量饰品价格查询"""
    hash_names = [cn_to_market_hash(items, name) for name in chinese_names if cn_to_market_hash(items, name)]
    if not hash_names:
        return None
    try:
        response = requests.post(
            f"{BASE_URL}/price/batch", headers=HEADERS, json={"marketHashNames": hash_names}, timeout=15
        )
        response.raise_for_status()
        api_data = response.json()
        if api_data.get("success"):
            return api_data["data"]
        else:
            print(f"❌ 批量查询失败：{api_data.get('errorMsg', '未知错误')}")
            return None
    except Exception as e:
        print(f"❌ 批量请求失败：{str(e)}")
        return None

# ==================== 7 天均价查询函数 ====================
def get_7day_average_price(market_hash_name: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """查询饰品近 7 天全平台均价"""
    if not market_hash_name:
        return None, "marketHashName 为空"
    params = {"marketHashName": market_hash_name}
    try:
        response = requests.get(
            f"{BASE_URL}/price/avg", headers=HEADERS, params=params, timeout=10
        )
        response.raise_for_status()
        api_data = response.json()
    except Exception as e:
        return None, f"GET 请求异常：{str(e)}"

    if api_data.get("success"):
        return api_data["data"], ""
    else:
        error_msg = api_data.get("errorMsg", f"接口返回业务错误")
        return None, error_msg

def get_wear_by_inspect_url(inspect_url: str) -> Optional[Dict[str, Any]]:
    """通过检视链接查询饰品磨损/贴纸数据"""
    if not inspect_url:
        return None
    try:
        response = requests.post(
            f"{BASE_URL}/wear/inspect", headers=HEADERS, json={"inspectUrl": inspect_url}, timeout=15
        )
        response.raise_for_status()
        api_data = response.json()
        if api_data.get("success"):
            return api_data["data"]
        else:
            print(f"❌ 磨损查询失败：{api_data.get('errorMsg', '未知错误')}")
            return None
    except Exception as e:
        print(f"❌ 网络请求失败：{str(e)}")
        return None

def get_wear_by_asmd(asmd_param: str) -> Optional[Dict[str, Any]]:
    """通过 ASMD 参数查询饰品磨损/贴纸数据"""
    if not asmd_param:
        return None
    try:
        response = requests.post(
            f"{BASE_URL}/wear/asm", headers=HEADERS, json={"asm": asmd_param}, timeout=15
        )
        response.raise_for_status()
        api_data = response.json()
        if api_data.get("success"):
            return api_data["data"]
        else:
            print(f"❌ 磨损查询失败：{api_data.get('errorMsg', '未知错误')}")
            return None
    except Exception as e:
        print(f"❌ 网络请求失败：{str(e)}")
        return None

def generate_preview_image_by_url(inspect_url: str) -> Optional[Dict[str, Any]]:
    """通过检视链接生成饰品检视图"""
    if not inspect_url:
        return None
    try:
        response = requests.post(
            f"{BASE_URL}/image/inspect", headers=HEADERS, json={"inspectUrl": inspect_url}, timeout=15
        )
        response.raise_for_status()
        api_data = response.json()
        if api_data.get("success"):
            return api_data["data"]
        else:
            print(f"❌ 检视图生成失败：{api_data.get('errorMsg', '未知错误')}")
            return None
    except Exception as e:
        print(f"❌ 网络请求失败：{str(e)}")
        return None

def generate_preview_image_by_asmd(asmd_param: str) -> Optional[Dict[str, Any]]:
    """通过 ASMD 参数生成饰品检视图"""
    if not asmd_param:
        return None
    try:
        response = requests.post(
            f"{BASE_URL}/image/asm", headers=HEADERS, json={"asm": asmd_param}, timeout=15
        )
        response.raise_for_status()
        api_data = response.json()
        if api_data.get("success"):
            return api_data["data"]
        else:
            print(f"❌ 检视图生成失败：{api_data.get('errorMsg', '未知错误')}")
            return None
    except Exception as e:
        print(f"❌ 网络请求失败：{str(e)}")
        return None

# ==================== 价格监测核心函数 ====================
def load_monitor_config() -> List[Dict[str, Any]]:
    """加载本地监测配置"""
    if os.path.exists(MONITOR_CONFIG_FILE):
        try:
            with open(MONITOR_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_monitor_config(config: List[Dict[str, Any]]):
    """保存监测配置到本地"""
    with open(MONITOR_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ==================== GUI 主界面 ====================
class SteamDTTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SteamDT CS2 饰品全功能工具 | 打包数据版 & 价格历史 & 企业微信推送")
        self.geometry("1280x800")
        self.resizable(True, True)
        self.item_base_data: Optional[List[Dict]] = None
        self.classified_item_data: Optional[List[Dict]] = None
        self.is_loading = False
        self.monitor_config: List[Dict] = load_monitor_config()
        # 初始化历史记录
        for item in self.monitor_config:
            if "history" not in item:
                item["history"] = []
        save_monitor_config(self.monitor_config)
        self.monitor_thread_running = False
        self.monitor_refresh_interval = DEFAULT_REFRESH_INTERVAL
        self.monitor_thread: Optional[threading.Thread] = None

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self.tab_quick_search = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_quick_search, text="🔍 快速查询")
        self.create_quick_search_tab()

        self.tab_single = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_single, text="单饰品价格")
        self.create_single_tab()

        self.tab_batch = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_batch, text="批量价格")
        self.create_batch_tab()

        self.tab_avg = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_avg, text="7 天均价")
        self.create_avg_tab()

        self.tab_wear = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_wear, text="磨损查询")
        self.create_wear_tab()

        self.tab_image = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_image, text="检视图生成")
        self.create_image_tab()

        self.tab_monitor = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_monitor, text="价格监测")
        self.create_monitor_tab()

        threading.Thread(target=self.load_base_data, daemon=True).start()

    # ==================== 快速查询页面创建 ====================
    def create_quick_search_tab(self):
        filter_frame = ttk.LabelFrame(self.tab_quick_search, text="筛选条件")
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="武器类型:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.weapon_type_combo = ttk.Combobox(filter_frame, state="readonly", width=12)
        self.weapon_type_combo.grid(row=0, column=1, padx=5, pady=8)
        all_types = sorted(list(set(WEAPON_TYPE_MAP.values())))
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
        self.search_keyword_input.insert(0, "鹤吻莓")

        ttk.Label(filter_frame, text="监测预警阈值 (%):").grid(row=0, column=6, padx=10, pady=8, sticky="w")
        self.quick_threshold_input = ttk.Entry(filter_frame, width=6)
        self.quick_threshold_input.grid(row=0, column=7, padx=5, pady=8)
        self.quick_threshold_input.insert(0, "5")

        self.search_btn = ttk.Button(filter_frame, text="搜索", command=self.do_filter_items)
        self.search_btn.grid(row=0, column=8, padx=10, pady=8)

        self.reset_filter_btn = ttk.Button(filter_frame, text="重置筛选", command=self.reset_filter)
        self.reset_filter_btn.grid(row=0, column=9, padx=5, pady=8)

        # 缓存状态和更新按钮
        self.cache_status_label = ttk.Label(filter_frame, text="⏳ 加载中...", foreground="orange")
        self.cache_status_label.grid(row=0, column=10, padx=10, pady=8)
        self.update_data_btn = ttk.Button(filter_frame, text="🔄 更新饰品数据", command=self.manual_update_data)
        self.update_data_btn.grid(row=0, column=11, padx=5, pady=8)
        self.update_data_btn.config(state=tk.DISABLED)

        self.search_keyword_input.bind("<Return>", lambda event: self.do_filter_items())

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

        log_frame = ttk.LabelFrame(self.tab_quick_search, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.quick_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, height=5)
        self.quick_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ==================== 快速查询相关方法 ====================
    def append_quick_log(self, text: str):
        def _append():
            self.quick_log.config(state=tk.NORMAL)
            self.quick_log.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
            self.quick_log.config(state=tk.DISABLED)
            self.quick_log.see(tk.END)
        self.after(0, _append)

    def get_selected_quick_items(self) -> List[Dict[str, Any]]:
        selected_items = self.quick_search_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选中表格中的饰品")
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

    def do_filter_items(self):
        if not self.classified_item_data:
            messagebox.showwarning("提示", "饰品基础数据尚未加载完成，请稍候")
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
        self.append_quick_log(f"✅ 筛选完成，共找到 {len(filtered_list)} 个符合条件的饰品")

    def reset_filter(self):
        self.weapon_type_combo.current(0)
        self.wear_level_combo.current(0)
        self.search_keyword_input.delete(0, tk.END)
        self.quick_threshold_input.delete(0, tk.END)
        self.quick_threshold_input.insert(0, "5")
        self.do_filter_items()

    def on_quick_item_double_click(self, event):
        self.quick_query_price()

    # ==================== 手动更新数据功能 ====================
    def manual_update_data(self):
        """手动触发饰品数据更新"""
        if self.is_loading:
            messagebox.showwarning("提示", "数据正在加载中，请稍候")
            return
        if not messagebox.askyesno("确认", "确定要更新饰品数据吗？\n\n注意：\n1. 每日只能成功调用 1 次 API\n2. 更新过程可能需要几秒到几十秒\n3. 更新失败会自动使用旧数据"):
            return

        self.update_data_btn.config(state=tk.DISABLED)
        self.cache_status_label.config(text="🔄 更新中...", foreground="orange")
        self.append_quick_log("🔄 开始手动更新饰品数据...")
        threading.Thread(target=self._manual_update_logic, daemon=True).start()

    def _manual_update_logic(self):
        """后台执行数据更新"""
        raw_data = get_steam_items(force_refresh=True)
        if raw_data:
            self.item_base_data = raw_data
            self.classified_item_data = init_item_classify_data(raw_data)
            self.after(0, lambda: self.append_quick_log(f"✅ 饰品数据更新成功，共 {len(self.classified_item_data)} 个饰品"))
            self.after(0, lambda: self.cache_status_label.config(text="✅ 已更新", foreground="green"))
            self.after(0, self.do_filter_items)
        else:
            self.after(0, lambda: self.append_quick_log("❌ 饰品数据更新失败，继续使用旧数据"))
            self.after(0, lambda: self.cache_status_label.config(text="⚠️ 使用旧数据", foreground="orange"))
            messagebox.showwarning("提示", "数据更新失败，将继续使用旧数据\n\n可能原因：\n1. 网络问题\n2. API 调用次数已达上限\n3. API_KEY 无效")
        self.after(0, lambda: self.update_data_btn.config(state=tk.NORMAL))

    # ==================== 核心操作按钮实现 ====================
    def quick_query_price(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        if len(selected_items) > 1:
            messagebox.showwarning("提示", "单饰品价格查询仅支持选中 1 个饰品")
            return
        selected_item = selected_items[0]
        item_name = selected_item["name"]
        self.notebook.select(self.tab_single)
        self.single_input.delete(0, tk.END)
        self.single_input.insert(0, item_name)
        self.query_single_price()

    def quick_query_7day_avg(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        if len(selected_items) > 1:
            messagebox.showwarning("提示", "7 日均价查询仅支持选中 1 个饰品")
            return
        selected_item = selected_items[0]
        item_name = selected_item["name"]
        self.notebook.select(self.tab_avg)
        self.avg_input.delete(0, tk.END)
        self.avg_input.insert(0, item_name)
        self.query_avg_price()

    def quick_add_to_batch(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        current_text = self.batch_input.get().strip()
        current_names = [name.strip() for name in current_text.split(",") if name.strip()]
        new_names = []
        for item in selected_items:
            item_name = item["name"]
            if item_name not in current_names:
                current_names.append(item_name)
                new_names.append(item_name)
        self.batch_input.delete(0, tk.END)
        self.batch_input.insert(0, ", ".join(current_names))
        self.append_quick_log(f"✅ 已添加 {len(new_names)} 个饰品到批量查询列表")
        self.notebook.select(self.tab_batch)

    def quick_add_to_monitor(self):
        if self.is_loading or not self.item_base_data:
            messagebox.showwarning("提示", "饰品基础数据尚未加载完成")
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
        self.after(0, lambda: self.append_quick_log(f"🔄 正在批量添加 {len(selected_items)} 个饰品到监测列表..."))

        for selected_item in selected_items:
            item_name = selected_item["name"]
            hash_name = selected_item["marketHashName"]

            for item in self.monitor_config:
                if item["name"] == item_name:
                    skip_count += 1
                    continue

            init_price = get_item_min_price(hash_name)
            if not init_price:
                fail_count += 1
                self.after(0, lambda n=item_name: self.append_quick_log(f"❌【{n}】初始价格获取失败，跳过"))
                continue

            new_monitor_item = {
                "name": item_name,
                "market_hash_name": hash_name,
                "init_price": init_price,
                "last_price": init_price,
                "current_price": init_price,
                "threshold": threshold,
                "update_time": current_time,
                "history": [{"time": current_time, "price": init_price}]
            }
            self.monitor_config.append(new_monitor_item)
            success_count += 1

        save_monitor_config(self.monitor_config)
        self.after(0, self.update_monitor_table)
        self.after(0, lambda: self.append_quick_log(f"✅ 批量添加完成：成功{success_count}个，跳过{skip_count}个，失败{fail_count}个"))
        self.after(0, lambda: messagebox.showinfo("完成", f"批量添加监测完成\n成功：{success_count}个\n跳过：{skip_count}个\n失败：{fail_count}个"))

    def quick_copy_item_name(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        names = [item["name"] for item in selected_items]
        copy_text = ", ".join(names)
        self.clipboard_clear()
        self.clipboard_append(copy_text)
        self.append_quick_log(f"✅ 已复制 {len(names)} 个饰品名称")

    def quick_copy_hash_name(self):
        selected_items = self.get_selected_quick_items()
        if not selected_items:
            return
        hash_names = [item["marketHashName"] for item in selected_items]
        copy_text = "\n".join(hash_names)
        self.clipboard_clear()
        self.clipboard_append(copy_text)
        self.append_quick_log(f"✅ 已复制 {len(hash_names)} 个 marketHashName")

    # ==================== 原有页面创建（省略重复代码，保持原有逻辑） ====================
    def create_single_tab(self):
        input_frame = ttk.Frame(self.tab_single)
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(input_frame, text="饰品中文全称:").pack(side=tk.LEFT, padx=5)
        self.single_input = ttk.Entry(input_frame, width=50)
        self.single_input.pack(side=tk.LEFT, padx=5)
        self.single_input.insert(0, "AK-47 | 红线 (略有磨损)")
        ttk.Button(input_frame, text="查询价格", command=self.query_single_price).pack(side=tk.LEFT, padx=5)

        self.single_result = scrolledtext.ScrolledText(self.tab_single, wrap=tk.WORD, state=tk.DISABLED)
        self.single_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def create_batch_tab(self):
        input_frame = ttk.Frame(self.tab_batch)
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(input_frame, text="饰品名称（中文，逗号分隔）:").pack(side=tk.LEFT, padx=5)
        self.batch_input = ttk.Entry(input_frame, width=70)
        self.batch_input.pack(side=tk.LEFT, padx=5)
        self.batch_input.insert(0, "AWP | 二西莫夫 (久经沙场), M4A1-S | 氮化处理 (崭新出厂)")
        ttk.Button(input_frame, text="批量查询", command=self.query_batch_price).pack(side=tk.LEFT, padx=5)

        self.batch_result = scrolledtext.ScrolledText(self.tab_batch, wrap=tk.WORD, state=tk.DISABLED)
        self.batch_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def create_avg_tab(self):
        input_frame = ttk.Frame(self.tab_avg)
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(input_frame, text="饰品中文全称:").pack(side=tk.LEFT, padx=5)
        self.avg_input = ttk.Entry(input_frame, width=50)
        self.avg_input.pack(side=tk.LEFT, padx=5)
        self.avg_input.insert(0, "AK-47 | 红线 (略有磨损)")
        ttk.Button(input_frame, text="查询 7 天均价", command=self.query_avg_price).pack(side=tk.LEFT, padx=5)

        self.avg_result = scrolledtext.ScrolledText(self.tab_avg, wrap=tk.WORD, state=tk.DISABLED)
        self.avg_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def create_wear_tab(self):
        url_frame = ttk.Frame(self.tab_wear)
        url_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(url_frame, text="检视链接:").pack(side=tk.LEFT, padx=5)
        self.wear_url_input = ttk.Entry(url_frame, width=80)
        self.wear_url_input.pack(side=tk.LEFT, padx=5)
        ttk.Button(url_frame, text="查询磨损", command=self.query_wear_by_url).pack(side=tk.LEFT, padx=5)

        asmd_frame = ttk.Frame(self.tab_wear)
        asmd_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(asmd_frame, text="ASMD 参数:").pack(side=tk.LEFT, padx=5)
        self.wear_asmd_input = ttk.Entry(asmd_frame, width=80)
        self.wear_asmd_input.pack(side=tk.LEFT, padx=5)
        ttk.Button(asmd_frame, text="查询磨损", command=self.query_wear_by_asmd).pack(side=tk.LEFT, padx=5)

        self.wear_result = scrolledtext.ScrolledText(self.tab_wear, wrap=tk.WORD, state=tk.DISABLED)
        self.wear_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def create_image_tab(self):
        url_frame = ttk.Frame(self.tab_image)
        url_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(url_frame, text="检视链接:").pack(side=tk.LEFT, padx=5)
        self.image_url_input = ttk.Entry(url_frame, width=80)
        self.image_url_input.pack(side=tk.LEFT, padx=5)
        ttk.Button(url_frame, text="生成检视图", command=self.gen_image_by_url).pack(side=tk.LEFT, padx=5)

        asmd_frame = ttk.Frame(self.tab_image)
        asmd_frame.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(asmd_frame, text="ASMD 参数:").pack(side=tk.LEFT, padx=5)
        self.image_asmd_input = ttk.Entry(asmd_frame, width=80)
        self.image_asmd_input.pack(side=tk.LEFT, padx=5)
        ttk.Button(asmd_frame, text="生成检视图", command=self.gen_image_by_asmd).pack(side=tk.LEFT, padx=5)

        self.image_result = scrolledtext.ScrolledText(self.tab_image, wrap=tk.WORD, state=tk.DISABLED)
        self.image_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def create_monitor_tab(self):
        add_frame = ttk.LabelFrame(self.tab_monitor, text="添加监测饰品")
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

        control_frame = ttk.Frame(self.tab_monitor)
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

        # 表格框架
        table_frame = ttk.Frame(self.tab_monitor)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("name", "current_price", "last_price", "change_amount", "change_rate", "init_price", "total_change", "update_time")
        self.monitor_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        self.monitor_tree.heading("name", text="饰品名称")
        self.monitor_tree.heading("current_price", text="当前价格")
        self.monitor_tree.heading("last_price", text="上次价格")
        self.monitor_tree.heading("change_amount", text="涨跌额")
        self.monitor_tree.heading("change_rate", text="涨跌幅")
        self.monitor_tree.heading("init_price", text="初始价格")
        self.monitor_tree.heading("total_change", text="累计涨跌")
        self.monitor_tree.heading("update_time", text="最后刷新时间")

        self.monitor_tree.column("name", width=220)
        self.monitor_tree.column("current_price", width=80)
        self.monitor_tree.column("last_price", width=80)
        self.monitor_tree.column("change_amount", width=80)
        self.monitor_tree.column("change_rate", width=80)
        self.monitor_tree.column("init_price", width=80)
        self.monitor_tree.column("total_change", width=80)
        self.monitor_tree.column("update_time", width=160)

        self.monitor_tree.tag_configure("up", foreground="green")
        self.monitor_tree.tag_configure("down", foreground="red")
        self.monitor_tree.tag_configure("normal", foreground="black")

        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.monitor_tree.yview)
        self.monitor_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.monitor_tree.pack(fill=tk.BOTH, expand=True)

        # 增加一个按钮来查看历史
        history_btn_frame = ttk.Frame(self.tab_monitor)
        history_btn_frame.pack(fill=tk.X, padx=10, pady=5)

        self.view_history_btn = ttk.Button(history_btn_frame, text="📊 查看选中项历史", command=self.show_selected_history)
        self.view_history_btn.pack(side=tk.LEFT, padx=5)

        log_frame = ttk.LabelFrame(self.tab_monitor, text="监测日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.monitor_log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, height=6)
        self.monitor_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.update_monitor_table()

    # ==================== 原有工具方法 ====================
    def load_base_data(self):
        self.is_loading = True
        self.append_log("正在加载饰品基础数据...", "single")
        self.append_quick_log("🔄 正在加载饰品基础数据...")
        raw_data = get_steam_items(force_refresh=False)
        if raw_data:
            self.item_base_data = raw_data
            self.classified_item_data = init_item_classify_data(raw_data)
            self.append_log(f"✅ 加载完成，共 {len(self.item_base_data)} 个饰品", "single")
            self.append_quick_log(f"✅ 饰品数据加载完成，共 {len(self.classified_item_data)} 个饰品")
            self.after(0, lambda: self.cache_status_label.config(text="✅ 就绪", foreground="green"))
            self.after(0, lambda: self.update_data_btn.config(state=tk.NORMAL))
            self.after(0, self.do_filter_items)
        else:
            self.append_log("❌ 加载失败，请检查 API_KEY 和网络", "single")
            self.append_quick_log("❌ 饰品数据加载失败，请检查 API_KEY 和网络")
            self.after(0, lambda: self.cache_status_label.config(text="❌ 失败", foreground="red"))
            self.after(0, lambda: self.update_data_btn.config(state=tk.NORMAL))
            messagebox.showerror("错误", "饰品基础数据加载失败！\n\n请确保：\n1. 网络连接正常\n2. API_KEY 有效\n3. 本地有缓存文件")
        self.is_loading = False

    def append_log(self, text: str, tab: str, end="\n"):
        def _append():
            text_widget_map = {
                "single": self.single_result,
                "batch": self.batch_result,
                "avg": self.avg_result,
                "wear": self.wear_result,
                "image": self.image_result
            }
            widget = text_widget_map.get(tab)
            if not widget:
                return
            widget.config(state=tk.NORMAL)
            widget.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {text}{end}")
            widget.config(state=tk.DISABLED)
            widget.see(tk.END)
        self.after(0, _append)

    def append_monitor_log(self, text: str):
        def _append():
            self.monitor_log.config(state=tk.NORMAL)
            self.monitor_log.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
            self.monitor_log.config(state=tk.DISABLED)
            self.monitor_log.see(tk.END)
        self.after(0, _append)

    def append_wechat_log(self, text: str): # 新增：用于价格监测页面显示推送日志
        def _append():
            self.monitor_log.config(state=tk.NORMAL)
            self.monitor_log.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] [企业微信] {text}\n")
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
                update_time
            ), tags=(tag,))

    # ==================== 新增：查看历史记录功能 ====================
    def get_selected_monitor_items(self) -> List[Dict[str, Any]]:
        """获取监测表格中选中的项目数据"""
        selected_items = self.monitor_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选中表格中的饰品")
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
        """显示选中项的历史记录"""
        selected_configs = self.get_selected_monitor_items()
        if not selected_configs:
            return
        if len(selected_configs) > 1:
            messagebox.showwarning("提示", "请只选中一个饰品来查看历史")
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

    # ==================== 监测业务逻辑 ====================
    def add_monitor_item(self):
        if self.is_loading or not self.item_base_data:
            messagebox.showwarning("提示", "请等待饰品基础数据加载完成")
            return

        cn_name = self.monitor_add_input.get().strip()
        threshold_str = self.monitor_threshold_input.get().strip()

        if not cn_name:
            messagebox.showwarning("提示", "请输入饰品名称")
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
                messagebox.showwarning("提示", "该饰品已在监测列表中")
                return

        hash_name = cn_to_market_hash(self.item_base_data, cn_name)
        if not hash_name:
            messagebox.showerror("错误", "未找到该饰品，请检查名称和磨损度是否完全匹配")
            return

        self.append_monitor_log(f"正在添加【{cn_name}】，获取初始价格...")
        init_price = get_item_min_price(hash_name)
        if not init_price:
            messagebox.showerror("错误", "获取饰品初始价格失败")
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
            "history": [{"time": current_time, "price": init_price}] # 初始化历史记录
        }

        self.monitor_config.append(new_monitor_item)
        save_monitor_config(self.monitor_config)
        self.update_monitor_table()
        self.append_monitor_log(f"✅ 成功添加【{cn_name}】，初始价格：{init_price:.2f}")
        self.monitor_add_input.delete(0, tk.END)

    def refresh_all_monitor(self):
        if not self.monitor_config:
            self.append_monitor_log("监测列表为空，无需刷新")
            return

        refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.append_monitor_log(f"🔄 开始刷新全部监测饰品，共 {len(self.monitor_config)} 个")

        alert_list = []
        change_list = [] # 记录本次刷新的价格变动

        for monitor_item in self.monitor_config:
            name = monitor_item["name"]
            hash_name = monitor_item["market_hash_name"]
            threshold = monitor_item["threshold"]

            new_price = get_item_min_price(hash_name)
            if not new_price:
                self.append_monitor_log(f"⚠️【{name}】价格刷新失败")
                continue

            old_last_price = monitor_item["last_price"]
            old_current_price = monitor_item["current_price"]

            monitor_item["last_price"] = old_current_price
            monitor_item["current_price"] = new_price
            monitor_item["update_time"] = refresh_time

            # 添加新的价格记录到历史
            monitor_item["history"].append({"time": refresh_time, "price": new_price})
            # 限制历史记录数量，例如保留最近100条
            if len(monitor_item["history"]) > 100:
                monitor_item["history"] = monitor_item["history"][-100:]

            change_rate = ((new_price - old_last_price) / old_last_price) * 100 if old_last_price > 0 else 0

            if new_price != old_current_price: # 有变动才记录
                change_list.append({
                    "name": name,
                    "old_price": old_current_price,
                    "new_price": new_price,
                    "change_rate": change_rate
                })

            if abs(change_rate) >= threshold:
                alert_list.append(f"【{name}】涨跌幅：{change_rate:+.2f}%，当前价格：{new_price:.2f}")

        save_monitor_config(self.monitor_config)
        self.after(0, self.update_monitor_table)

        # --- 企业微信推送逻辑 ---
        if change_list:
            change_messages = []
            for change in change_list:
                change_messages.append(f"{change['name']}: {change['old_price']:.2f} -> {change['new_price']:.2f} ({change['change_rate']:+.2f}%)")
            change_summary = "\n".join(change_messages)
            wechat_message_changes = f"🔄【CS2饰品价格变动】\n{change_summary}"
            if send_to_wechat(wechat_message_changes):
                 self.append_wechat_log("价格变动信息已推送")
            else:
                 self.append_wechat_log("价格变动信息推送失败")

        if alert_list:
            alert_msg = "⚠️【CS2饰品价格涨跌预警】\n" + "\n".join(alert_list)
            if send_to_wechat(alert_msg):
                self.append_wechat_log("预警信息已推送")
            else:
                self.append_wechat_log("预警信息推送失败")

        self.append_monitor_log(f"✅ 全部饰品刷新完成")

    def manual_refresh_monitor(self):
        if self.is_loading or not self.item_base_data:
            messagebox.showwarning("提示", "请等待饰品基础数据加载完成")
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
        if not self.item_base_data:
            messagebox.showwarning("提示", "饰品基础数据未加载")
            return
        if not self.monitor_thread_running:
            try:
                interval = int(self.interval_input.get().strip())
                if interval < 60:
                    messagebox.showwarning("提示", "刷新间隔最小 60 秒，已自动设置为 60 秒")
                    interval = 60
                    self.interval_input.delete(0, tk.END)
                    self.interval_input.insert(0, "60")
                self.monitor_refresh_interval = interval
            except:
                messagebox.showwarning("提示", "刷新间隔格式错误，使用默认值 300 秒")
                self.monitor_refresh_interval = DEFAULT_REFRESH_INTERVAL
                self.interval_input.delete(0, tk.END)
                self.interval_input.insert(0, str(DEFAULT_REFRESH_INTERVAL))

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
        if not messagebox.askyesno("确认", "确定要清空全部监测列表吗？"):
            return
        self.monitor_config = []
        save_monitor_config(self.monitor_config)
        self.update_monitor_table()
        self.append_monitor_log("🗑️ 监测列表已清空")

    # ==================== 原有业务逻辑 ====================
    def query_single_price(self):
        if self.is_loading:
            messagebox.showwarning("提示", "请等待基础数据加载完成")
            return
        if not self.item_base_data:
            messagebox.showerror("错误", "饰品基础数据未加载！")
            return
        cn_name = self.single_input.get().strip()
        if not cn_name:
            messagebox.showwarning("提示", "请输入饰品名称")
            return
        threading.Thread(target=self._query_single_logic, args=(cn_name,), daemon=True).start()

    def _query_single_logic(self, cn_name: str):
        self.append_log(f"\n===== 查询：{cn_name} =====", "single")
        hash_name = cn_to_market_hash(self.item_base_data, cn_name)
        if not hash_name:
            self.append_log("❌ 未找到该饰品，请检查名称和磨损度是否完全匹配", "single")
            return
        self.append_log(f"✅ 匹配 marketHashName: {hash_name}", "single")

        price_list = get_single_item_price(hash_name)
        if not price_list:
            self.append_log("❌ 价格查询失败", "single")
            return
        self.append_log("✅ 查询成功，各平台价格：", "single")

        min_price = float("inf")
        min_platform = ""
        platform_details = []
        for platform_data in price_list:
            platform = platform_data.get("platform", "未知平台")
            sell_price = platform_data.get("sellPrice", "未知")
            sell_count = platform_data.get("sellCount", 0)
            bidding_price = platform_data.get("biddingPrice", "未知")
            platform_details.append(f" 【{platform}】在售价格：{sell_price} | 在售数量：{sell_count} | 求购价格：{bidding_price}")
            self.append_log(platform_details[-1], "single")

            if isinstance(sell_price, (int, float)) and sell_price < min_price:
                min_price = sell_price
                min_platform = platform

        if min_platform:
            min_price_line = f"💡 全网最低：{min_price}（{min_platform}）"
            self.append_log(min_price_line, "single")

        # --- 企业微信推送 ---
        wechat_message = f"🔍【CS2饰品价格查询】\n饰品: {cn_name}\n{min_price_line}\n详情:\n" + "\n".join(platform_details)
        if send_to_wechat(wechat_message):
             self.append_quick_log("单饰品查询结果已推送至企业微信")
        else:
             self.append_quick_log("单饰品查询结果推送至企业微信失败")

    def query_batch_price(self):
        if self.is_loading:
            messagebox.showwarning("提示", "请等待基础数据加载完成")
            return
        if not self.item_base_data:
            messagebox.showerror("错误", "饰品基础数据未加载！")
            return
        input_text = self.batch_input.get().strip()
        if not input_text:
            messagebox.showwarning("提示", "请输入饰品名称")
            return
        cn_names = [name.strip() for name in input_text.split(",") if name.strip()]
        threading.Thread(target=self._query_batch_logic, args=(cn_names,), daemon=True).start()

    def _query_batch_logic(self, cn_names: List[str]):
        self.append_log(f"\n===== 批量查询：{len(cn_names)} 个饰品 =====", "batch")
        batch_data = get_batch_item_price(self.item_base_data, cn_names)
        if not batch_data:
            self.append_log("❌ 批量查询失败", "batch")
            return

        results_lines = []
        for item in batch_data:
            hash_name = item.get("marketHashName", "未知")
            platform_list = item.get("dataList", [])
            result_line = f"\n📦 饰品：{hash_name}"
            self.append_log(result_line, "batch")
            results_lines.append(result_line)

            for platform_data in platform_list:
                platform = platform_data.get("platform", "未知")
                price = platform_data.get("sellPrice", "未知")
                detail_line = f" 【{platform}】{price}"
                self.append_log(detail_line, "batch")
                results_lines.append(detail_line)

        # --- 企业微信推送 ---
        wechat_message = f"📊【CS2饰品批量价格查询】\n查询了 {len(cn_names)} 个饰品\n详情:\n" + "".join(results_lines)
        if send_to_wechat(wechat_message):
             self.append_quick_log("批量查询结果已推送至企业微信")
        else:
             self.append_quick_log("批量查询结果推送至企业微信失败")

    def query_avg_price(self):
        if self.is_loading:
            messagebox.showwarning("提示", "请等待基础数据加载完成")
            return
        if not self.item_base_data:
            messagebox.showerror("错误", "饰品基础数据未加载！")
            return
        cn_name = self.avg_input.get().strip()
        if not cn_name:
            messagebox.showwarning("提示", "请输入饰品名称")
            return
        threading.Thread(target=self._query_avg_logic, args=(cn_name,), daemon=True).start()

    def _query_avg_logic(self, cn_name: str):
        self.append_log(f"\n===== 7 天均价查询：{cn_name} =====", "avg")
        hash_name = cn_to_market_hash(self.item_base_data, cn_name)
        if not hash_name:
            self.append_log("❌ 未找到该饰品，请检查名称和磨损度是否完全匹配", "avg")
            return
        self.append_log(f"✅ 匹配 marketHashName: {hash_name}", "avg")

        avg_data, error_msg = get_7day_average_price(hash_name)
        if not avg_data:
            self.append_log(f"❌ 均价查询失败，原因：{error_msg}", "avg")
            return
        self.append_log(f"✅ 查询成功，全平台近 7 天均价：{avg_data.get('avgPrice', '未知')}", "avg")
        self.append_log("📊 各平台近 7 天均价：", "avg")

        details_lines = []
        for platform_data in avg_data.get("dataList", []):
            platform = platform_data.get("platform", "未知平台")
            avg_price = platform_data.get("avgPrice", "未知")
            detail_line = f" 【{platform}】近 7 天均价：{avg_price}"
            self.append_log(detail_line, "avg")
            details_lines.append(detail_line)

        # --- 企业微信推送 ---
        wechat_message = f"📈【CS2饰品7天均价查询】\n饰品: {cn_name}\n全平台均价: {avg_data.get('avgPrice', '未知')}\n详情:\n" + "\n".join(details_lines)
        if send_to_wechat(wechat_message):
             self.append_quick_log("7天均价查询结果已推送至企业微信")
        else:
             self.append_quick_log("7天均价查询结果推送至企业微信失败")

    def query_wear_by_url(self):
        url = self.wear_url_input.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入检视链接")
            return
        threading.Thread(target=self._wear_url_logic, args=(url,), daemon=True).start()

    def _wear_url_logic(self, url: str):
        self.append_log(f"\n===== 检视链接磨损查询 =====", "wear")
        wear_data = get_wear_by_inspect_url(url)
        if not wear_data:
            self.append_log("❌ 查询失败", "wear")
            return
        self.append_log(json.dumps(wear_data, ensure_ascii=False, indent=2), "wear")

    def query_wear_by_asmd(self):
        asmd = self.wear_asmd_input.get().strip()
        if not asmd:
            messagebox.showwarning("提示", "请输入 ASMD 参数")
            return
        threading.Thread(target=self._wear_asmd_logic, args=(asmd,), daemon=True).start()

    def _wear_asmd_logic(self, asmd: str):
        self.append_log(f"\n===== ASMD 磨损查询 =====", "wear")
        wear_data = get_wear_by_asmd(asmd)
        if not wear_data:
            self.append_log("❌ 查询失败", "wear")
            return
        self.append_log(json.dumps(wear_data, ensure_ascii=False, indent=2), "wear")

    def gen_image_by_url(self):
        url = self.image_url_input.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入检视链接")
            return
        threading.Thread(target=self._image_url_logic, args=(url,), daemon=True).start()

    def _image_url_logic(self, url: str):
        self.append_log(f"\n===== 检视链接生成检视图 =====", "image")
        image_data = generate_preview_image_by_url(url)
        if not image_data:
            self.append_log("❌ 生成失败", "image")
            return
        self.append_log(json.dumps(image_data, ensure_ascii=False, indent=2), "image")

    def gen_image_by_asmd(self):
        asmd = self.image_asmd_input.get().strip()
        if not asmd:
            messagebox.showwarning("提示", "请输入 ASMD 参数")
            return
        threading.Thread(target=self._image_asmd_logic, args=(asmd,), daemon=True).start()

    def _image_asmd_logic(self, asmd: str):
        self.append_log(f"\n===== ASMD 生成检视图 =====", "image")
        image_data = generate_preview_image_by_asmd(asmd)
        if not image_data:
            self.append_log("❌ 生成失败", "image")
            return
        self.append_log(json.dumps(image_data, ensure_ascii=False, indent=2), "image")


# ==================== 程序入口 ====================
if __name__ == "__main__":
    app = SteamDTTool()
    app.mainloop()
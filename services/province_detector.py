import re
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class ProvinceMatch:
    province: str
    matched_by: str


_PROVINCES = [
    "北京市",
    "天津市",
    "河北省",
    "山西省",
    "内蒙古自治区",
    "辽宁省",
    "吉林省",
    "黑龙江省",
    "上海市",
    "江苏省",
    "浙江省",
    "安徽省",
    "福建省",
    "江西省",
    "山东省",
    "河南省",
    "湖北省",
    "湖南省",
    "广东省",
    "广西壮族自治区",
    "海南省",
    "重庆市",
    "四川省",
    "贵州省",
    "云南省",
    "西藏自治区",
    "陕西省",
    "甘肃省",
    "青海省",
    "宁夏回族自治区",
    "新疆维吾尔自治区",
]


_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("北京市", "北京", re.compile(r"(北京|beijing|(?<![a-z])bj(?![a-z]))", re.I)),
    ("上海市", "上海", re.compile(r"(上海|shanghai|(?<![a-z])sh(?![a-z]))", re.I)),
    ("天津市", "天津", re.compile(r"(天津|tianjin|(?<![a-z])tj(?![a-z]))", re.I)),
    ("重庆市", "重庆", re.compile(r"(重庆|chongqing|(?<![a-z])cq(?![a-z]))", re.I)),
    ("河北省", "河北", re.compile(r"(河北|石家庄|保定|唐山|邯郸|张家口|hebei)", re.I)),
    ("山西省", "山西", re.compile(r"(山西|太原|大同|晋中|shanxi)", re.I)),
    ("内蒙古自治区", "内蒙古", re.compile(r"(内蒙古|呼和浩特|包头|鄂尔多斯|neimenggu|inner\s*mongolia)", re.I)),
    ("辽宁省", "辽宁", re.compile(r"(辽宁|沈阳|大连|鞍山|liaoning)", re.I)),
    ("吉林省", "吉林", re.compile(r"(吉林省|长春|吉林市|jilin)", re.I)),
    ("黑龙江省", "黑龙江", re.compile(r"(黑龙江|哈尔滨|齐齐哈尔|heilongjiang)", re.I)),
    ("江苏省", "江苏", re.compile(r"(江苏|南京|苏州|无锡|扬州|jiangsu)", re.I)),
    ("浙江省", "浙江", re.compile(r"(浙江|杭州|宁波|温州|绍兴|嘉兴|zhejiang)", re.I)),
    ("安徽省", "安徽", re.compile(r"(安徽|合肥|黄山|芜湖|anhui)", re.I)),
    ("福建省", "福建", re.compile(r"(福建|福州|厦门|泉州|fujian)", re.I)),
    ("江西省", "江西", re.compile(r"(江西|南昌|景德镇|赣州|jiangxi)", re.I)),
    ("山东省", "山东", re.compile(r"(山东|济南|青岛|泰安|yantai|shandong)", re.I)),
    ("河南省", "河南", re.compile(r"(河南|郑州|洛阳|开封|henan)", re.I)),
    ("湖北省", "湖北", re.compile(r"(湖北|武汉|宜昌|襄阳|hubei)", re.I)),
    ("湖南省", "湖南", re.compile(r"(湖南|长沙|张家界|湘潭|hunan)", re.I)),
    ("广东省", "广东", re.compile(r"(广东|广州|深圳|shenzhen|珠海|佛山|dongguan|guangdong)", re.I)),
    ("广西壮族自治区", "广西", re.compile(r"(广西|南宁|桂林|柳州|guangxi)", re.I)),
    ("海南省", "海南", re.compile(r"(海南|海口|三亚|hainan)", re.I)),
    ("四川省", "四川", re.compile(r"(四川|成都|乐山|九寨沟|sichuan)", re.I)),
    ("贵州省", "贵州", re.compile(r"(贵州|贵阳|遵义|guiyang|guizhou)", re.I)),
    ("云南省", "云南", re.compile(r"(云南|昆明|大理|丽江|yunnan)", re.I)),
    ("西藏自治区", "西藏", re.compile(r"(西藏|拉萨|tibet|xizang)", re.I)),
    ("陕西省", "陕西", re.compile(r"(陕西|西安|咸阳|兵马俑|shaanxi)", re.I)),
    ("甘肃省", "甘肃", re.compile(r"(甘肃|兰州|敦煌|gansu)", re.I)),
    ("青海省", "青海", re.compile(r"(青海|西宁|qinghai)", re.I)),
    ("宁夏回族自治区", "宁夏", re.compile(r"(宁夏|银川|ningxia)", re.I)),
    ("新疆维吾尔自治区", "新疆", re.compile(r"(新疆|乌鲁木齐|喀什|xinjiang|urumqi|kashgar)", re.I)),
]


def all_provinces() -> list[str]:
    return list(_PROVINCES)


def detect_province(text: str) -> Optional[ProvinceMatch]:
    if not text:
        return None
    normalized = str(text)
    for province, matched_by, pat in _PATTERNS:
        if pat.search(normalized):
            return ProvinceMatch(province=province, matched_by=matched_by)
    return None


def normalize_province_input(raw: str) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s in _PROVINCES:
        return s
    match = detect_province(s)
    return match.province if match else None


def best_province_from_candidates(values: Iterable[str]) -> Optional[ProvinceMatch]:
    for v in values:
        m = detect_province(v)
        if m:
            return m
    return None

# -*- coding: utf-8 -*-
import json, os

OUT = r'E:\Hackthon\Map\picture\json'
os.makedirs(OUT, exist_ok=True)

# ============ 大铭-杭州 ============
daming = {
    "city": "杭州",
    "blogger": "大铭",
    "platform": "抖音",
    "video_title": "杭州两日游攻略 避开人流不走回头路！",
    "video_duration": "约10分钟",
    "video_link": "https://v.douyin.com/UxqAfWLU-w8/",
    "spots": [
        {"name": "断桥残雪", "lng": 120.15193, "lat": 30.25959,
         "speech": "白娘子与许仙相遇地，因断桥不断的传说得名。步行至白堤，坐湖边长椅感受人在画中游。",
         "environment": "西湖湖畔，断桥横卧，桃柳夹道，游人如织",
         "signs": ["断桥残雪", "白堤入口"],
         "recommendation": "西湖十景之一，白娘子传说发源地。清晨8点前到，人少景美，步行白堤桃柳相间如入画中。",
         "visit_duration": "40分钟", "best_time": "清晨/春季桃花期", "ticket": "免费",
         "tag": "城市", "mood": "浪漫",
         "images": ["hangzhou/大铭/断桥-1.webp", "hangzhou/大铭/断桥-2.webp", "hangzhou/大铭/断桥-3.webp"]},
        {"name": "平湖秋月", "lng": 120.14460, "lat": 30.25635,
         "speech": "西湖顶流出片地，沿途歪脖子树极具清透感。途经西泠印社，可了解篆刻艺术。",
         "environment": "湖面开阔，长廊临水，歪脖子树倒影入水",
         "signs": ["平湖秋月", "西泠印社", "孤山路"],
         "recommendation": "湖边歪脖子树是热门出片点，傍晚月色最动人。顺路打卡西泠印社，感受篆刻文化。",
         "visit_duration": "40分钟", "best_time": "傍晚/秋天月圆夜", "ticket": "免费",
         "tag": "海", "mood": "清透",
         "images": ["hangzhou/大铭/平湖秋月-1.webp", "hangzhou/大铭/平湖秋月-2.jpeg"]},
        {"name": "曲院风荷", "lng": 120.13450, "lat": 30.25350,
         "speech": "夏季赏荷胜地，非花期时环境清幽，适合散步。有免费梦核金鱼打卡点。",
         "environment": "荷塘碧绿，风吹荷香，有梦核金鱼打卡点",
         "signs": ["曲院风荷", "梦核金鱼"],
         "recommendation": "7-8月荷花盛开，全园免费。梦核金鱼打卡点独特，非花期也适合休憩散步。",
         "visit_duration": "45分钟", "best_time": "6-8月荷花季", "ticket": "免费",
         "tag": "海", "mood": "清雅",
         "images": ["hangzhou/大铭/曲院风荷-1.webp", "hangzhou/大铭/曲院风荷-2.png"]},
        {"name": "水上巴士1号线", "lng": 120.13650, "lat": 30.24200,
         "speech": "中美友谊井码头乘坐，沿途可看三潭映月、雷峰塔。建议提前排队，电子屏显示剩余座位。",
         "environment": "湖面乘船，水天一色，雷峰塔遥遥在望",
         "signs": ["中美友谊井码头", "水上巴士1号线"],
         "recommendation": "仅6元湖上体验！沿途经三潭映月、雷峰塔，湖上视角独特。建议16点前去排队。",
         "visit_duration": "30分钟", "best_time": "全年，晴天最佳", "ticket": "6元",
         "tag": "海", "mood": "惬意", "images": []},
        {"name": "花港观鱼", "lng": 120.15890, "lat": 30.24430,
         "speech": "下船即达，从蒋庄进入可打卡西湖字墙。",
         "environment": "园林水系，花木繁盛，锦鲤成群",
         "signs": ["花港观鱼", "蒋庄入口", "西湖字墙"],
         "recommendation": "水上巴士就到，蒋庄入口可打卡西湖字墙，锦鲤成群，适合慢慢逛。",
         "visit_duration": "45分钟", "best_time": "3-5月", "ticket": "免费",
         "tag": "海", "mood": "惬意",
         "images": ["hangzhou/大铭/花港观鱼-1.webp", "hangzhou/大铭/花港观鱼-2.jpeg"]},
        {"name": "柳浪闻莺", "lng": 120.15470, "lat": 30.24010,
         "speech": "天气好时可看日落，感受柳浪闻莺的诗意。",
         "environment": "柳丝飘摇，湖风轻拂，日落西山",
         "signs": ["柳浪闻莺"],
         "recommendation": "傍晚柳枝随风，日落西湖美不胜收，Day1收尾绝佳地点。",
         "visit_duration": "30分钟", "best_time": "傍晚日落", "ticket": "免费",
         "tag": "海", "mood": "诗意",
         "images": ["hangzhou/大铭/柳浪闻莺-1.webp"]},
        {"name": "法喜寺", "lng": 120.10860, "lat": 30.26210,
         "speech": "103路公交直达。门票10元，现场购买。免费领三炷清香，摸经文墙沾好运。",
         "environment": "山间古寺，清幽寂静，香烟袅袅",
         "signs": ["法喜寺", "103路公交站"],
         "recommendation": "门票仅10元，免费领三炷清香，摸经文墙沾好运。人比灵隐寺少很多，体验更好。",
         "visit_duration": "40分钟", "best_time": "上午", "ticket": "10元",
         "tag": "山", "mood": "禅意", "images": []},
        {"name": "灵隐寺", "lng": 120.10270, "lat": 30.26540,
         "speech": "中午灵隐寺，10元观光车直达。需提前在小程序预约，刷身份证入园。必看飞来峰石窟造像，大雄宝殿前香炉不可触摸。",
         "environment": "古刹深山，飞来峰石窟造像震撼，参天古木",
         "signs": ["灵隐寺", "飞来峰石窟"],
         "recommendation": "需提前小程序预约，10元观光车直达。飞来峰石窟造像必看！建议上午到。",
         "visit_duration": "1.5小时", "best_time": "上午", "ticket": "预约免费进寺",
         "tag": "山", "mood": "禅意",
         "images": ["hangzhou/大铭/灵隐寺-1.webp", "hangzhou/大铭/灵隐寺-2.webp", "hangzhou/大铭/灵隐寺-3.webp"]},
        {"name": "杭州植物园", "lng": 120.11750, "lat": 30.25320,
         "speech": "下午植物园，南门进直奔韩美林艺术馆。馆内有震撼大佛头雕塑，二楼有泡泡玛特联名展。",
         "environment": "绿意盎然，艺术馆静谧，雕塑与自然共存",
         "signs": ["杭州植物园南门", "韩美林艺术馆"],
         "recommendation": "门票10元，韩美林艺术馆是隐藏宝藏，大佛头雕塑震撼，泡泡玛特联名展很出片。",
         "visit_duration": "1.5小时", "best_time": "下午", "ticket": "10元",
         "tag": "山", "mood": "艺术",
         "images": ["hangzhou/大铭/植物园-1.webp", "hangzhou/大铭/植物园-2.jpeg"]}
    ],
    "food": [
        {"name": "新白鹿餐厅", "location": "银泰IN77(庆春路)", "price": "人均50元", "desc": "性价比高，糖醋排骨、蛋黄鸡翅必点", "rating": "⭐⭐⭐⭐"},
        {"name": "西湖醋鱼", "location": "西湖周边", "price": "约88元/道", "desc": "杭州经典名菜，草鱼酸甜鲜嫩", "rating": "⭐⭐⭐⭐"},
        {"name": "龙井虾仁", "location": "知味观等杭帮菜", "price": "约68元/道", "desc": "龙井清香配鲜嫩虾仁", "rating": "⭐⭐⭐⭐"},
        {"name": "定胜糕", "location": "西湖周边小店", "price": "5-10元", "desc": "杭州传统小吃，软糯香甜", "rating": "⭐⭐⭐"}
    ],
    "transport": [
        {"from": "断桥残雪", "to": "平湖秋月", "mode": "步行", "duration": "15分钟", "desc": "沿白堤步行，桃柳相间", "cost": "免费"},
        {"from": "平湖秋月", "to": "曲院风荷", "mode": "步行", "duration": "30分钟", "desc": "沿苏堤走到曲院风荷", "cost": "免费"},
        {"from": "曲院风荷", "to": "水上巴士码头", "mode": "步行", "duration": "10分钟", "desc": "导航中美友谊井", "cost": "免费"},
        {"from": "水上巴士码头", "to": "花港观鱼", "mode": "水上巴士", "duration": "约20分钟", "desc": "6元水上巴士", "cost": "6元"},
        {"from": "花港观鱼", "to": "柳浪闻莺", "mode": "步行", "duration": "25分钟", "desc": "沿南山路步行", "cost": "免费"},
        {"from": "住宿", "to": "法喜寺", "mode": "公交", "duration": "约30分钟", "desc": "103路公交直达", "cost": "2元"},
        {"from": "法喜寺", "to": "灵隐寺", "mode": "观光车", "duration": "10分钟", "desc": "10元观光车", "cost": "10元"},
        {"from": "灵隐寺", "to": "植物园南门", "mode": "步行", "duration": "约15分钟", "desc": "沿灵隐路向东", "cost": "免费"}
    ],
    "tips": [
        "灵隐寺需提前微信公众号预约，节假日名额紧，建议提前2-3天",
        "水上巴士每班约30人，建议16点前到码头排队，查电子屏剩余座位",
        "法喜寺门票仅10元现场购，人流比灵隐寺少很多，体验更佳",
        "植物园韩美林艺术馆是隐藏宝藏，门票含在植物园内",
        "雨天路滑穿防滑鞋；西湖湖边风大注意保暖",
        "支付宝可租公共自行车，1小时内免费，适合环湖骑行"
    ]
}

# ============ 圆子芝士-杭州 ============
yuanzi = {
    "city": "杭州",
    "blogger": "圆子芝士",
    "platform": "抖音",
    "video_title": "杭州一日游就看这里！灵隐寺+太子湾赏花+吃漂亮饭 太松弛啦",
    "video_duration": "约8分钟",
    "video_link": "https://v.douyin.com/H6hHl3H196s/",
    "spots": [
        {"name": "灵隐寺", "lng": 120.10270, "lat": 30.26540,
         "speech": "灵隐寺是杭州最古老的佛教寺院之一，始建于东晋，香火旺盛，可免费领取三柱清香祈福。无需门票，需在公众号提前预约。",
         "environment": "古刹深山，晨雾缭绕，参天古木，香烟袅袅",
         "signs": ["灵隐寺", "灵隐寺停车场"],
         "recommendation": "免费入内但需提前预约。可免费领三柱清香，拍门头大殿在入口处，非常出片！",
         "visit_duration": "1小时", "best_time": "上午7点开门即到", "ticket": "免费入寺（提前预约）",
         "tag": "山", "mood": "禅意",
         "images": ["hangzhou/圆子芝士/灵隐寺-1.webp", "hangzhou/圆子芝士/灵隐寺-2.webp", "hangzhou/圆子芝士/灵隐寺-3.webp"]},
        {"name": "太子湾公园", "lng": 120.14690, "lat": 30.23380,
         "speech": "太子湾公园以郁金香花海闻名，40多万株郁金香汇成春日壁纸，大风车、小教堂、溪流边是热门机位。",
         "environment": "花海如毯，郁金香铺满草地，大风车小教堂童话感十足",
         "signs": ["太子湾公园", "郁金香花海", "大风车", "小教堂"],
         "recommendation": "春季郁金香花期（3-4月）最佳！坐太子湾专线船来，还能看雷峰塔和三潭印月。",
         "visit_duration": "1小时", "best_time": "3-4月郁金香花期", "ticket": "免费（花期可能收费）",
         "tag": "海", "mood": "浪漫",
         "images": ["hangzhou/圆子芝士/太子湾-1.jpeg"]},
        {"name": "曲院风荷", "lng": 120.13450, "lat": 30.25350,
         "speech": "人少景美，有免费梦核金鱼打卡点，适合休息观景。曲院风荷是西湖十景之一。",
         "environment": "荷塘清幽，梦核金鱼池如梦似幻，傍晚光线柔和",
         "signs": ["曲院风荷", "梦核金鱼"],
         "recommendation": "傍晚来人不多，有网红梦核金鱼打卡点，荷花季香气阵阵，其他时节也适合散步。",
         "visit_duration": "40分钟", "best_time": "傍晚，6-8月荷花季", "ticket": "免费",
         "tag": "海", "mood": "治愈",
         "images": ["hangzhou/圆子芝士/曲院风荷-1.webp", "hangzhou/圆子芝士/曲院风荷-2.jpeg"]},
        {"name": "来福士52楼高空餐厅", "lng": 120.20160, "lat": 30.20780,
         "speech": "需提前预约，建议选窗边位置，可俯瞰杭州大金球、CBD及钱塘江一线江景。餐厅有驻唱歌手。",
         "environment": "52楼高空，钱塘江一线江景，灯光璀璨，驻唱歌手",
         "signs": ["来福士广场", "HOMELESS餐厅"],
         "recommendation": "杭州最美夜景打卡！俯瞰钱塘江和CBD大金球。鱼子酱甜虾塔、澳洲和牛眼肉釜饭强烈推荐。",
         "visit_duration": "2小时", "best_time": "晚上19:00-21:00", "ticket": "餐厅消费（人均约300元）",
         "tag": "城市", "mood": "精致", "images": []}
    ],
    "food": [
        {"name": "米其林煎饺馄饨", "location": "灵隐寺附近", "price": "约50元/人", "desc": "午餐首选，煎饺皮脆馅鲜，馄饨汤头清澈", "rating": "⭐⭐⭐⭐⭐"},
        {"name": "鱼子酱甜虾塔", "location": "来福士52楼HOMELESS", "price": "约80元/道", "desc": "精致摆盘，鱼子酱配甜虾，仪式感满满", "rating": "⭐⭐⭐⭐⭐"},
        {"name": "澳洲和牛眼肉釜饭", "location": "来福士52楼HOMELESS", "price": "约180元/道", "desc": "釜饭形式，和牛鲜嫩，饭粒晶莹", "rating": "⭐⭐⭐⭐⭐"}
    ],
    "transport": [
        {"from": "住宿", "to": "灵隐寺", "mode": "公交/打车", "duration": "约50分钟", "desc": "建议定位灵隐寺停车场", "cost": "约5-30元"},
        {"from": "灵隐寺", "to": "太子湾公园", "mode": "游船", "duration": "约20分钟", "desc": "乘太子湾专线，从钱王祠码头到花港观鱼码头，步行300米", "cost": "外地人15元"},
        {"from": "太子湾公园", "to": "曲院风荷", "mode": "步行", "duration": "约15分钟", "desc": "沿苏堤步行", "cost": "免费"},
        {"from": "曲院风荷", "to": "来福士广场", "mode": "打车", "duration": "约30分钟", "desc": "打车或公交前往钱塘新区", "cost": "约15元"}
    ],
    "tips": [
        "灵隐寺节假日名额紧，建议提前3-5天公众号预约",
        "太子湾郁金香花期约3月底-4月中旬，花期较短需提前查询",
        "来福士52楼HOMELESS必须提前预约，建议选18:30场看日落+夜景",
        "全天行程以松弛感为主，不要赶太多景点"
    ]
}

# ============ 柚在吃什么-成都 ============
youzi = {
    "city": "成都",
    "blogger": "柚在吃什么！",
    "platform": "抖音",
    "video_title": "四天三晚成都特种兵之旅！熊猫基地+九寨沟+都江堰+宽窄巷子+三星堆",
    "video_duration": "约10分钟",
    "video_link": "https://v.douyin.com/Ylxe4qsQkXw/",
    "spots": [
        {"name": "熊猫基地", "lng": 104.08660, "lat": 30.73630,
         "speech": "上午去熊猫基地，南门进，可选打车或直通车。工作日排队约2小时，可选西门减少人流量。",
         "environment": "竹林掩映，熊猫宝宝懒洋洋吃竹子，游客争相拍照",
         "signs": ["成都大熊猫繁育研究基地", "南门入口"],
         "recommendation": "必打卡！建议7:30开门即进，看熊猫吃早餐最活泼。工作日人少，西门等候时间短，提前预约门票。",
         "visit_duration": "2-3小时", "best_time": "上午7:30-10:00", "ticket": "55元（需提前预约）",
         "tag": "山", "mood": "治愈",
         "images": ["chengdu/柚在吃什么！/熊猫基地-1.webp", "chengdu/柚在吃什么！/熊猫基地-2.webp", "chengdu/柚在吃什么！/熊猫基地-3.webp"]},
        {"name": "九寨沟", "lng": 103.91700, "lat": 33.26000,
         "speech": "九寨沟是世界自然遗产，以翠海、叠瀑、彩林、雪峰和藏情五绝闻名。右线景点较多，建议先玩右线再回诺瑞朗中心转左线。",
         "environment": "高原彩池湛蓝如玉，叠瀑飞流，藏寨木屋，雪山为幕",
         "signs": ["九寨沟景区", "树正寨", "五花海", "诺瑞朗瀑布"],
         "recommendation": "世界自然遗产！五花海颜色超绝。先走右线再转左线，不走回头路。海拔2000-3000米，注意高原反应。",
         "visit_duration": "一整天", "best_time": "9-11月秋季", "ticket": "含观光车约220元",
         "tag": "山", "mood": "壮丽",
         "images": ["chengdu/柚在吃什么！/九寨沟-1.webp", "chengdu/柚在吃什么！/九寨沟-2.webp", "chengdu/柚在吃什么！/九寨沟-3.webp"]},
        {"name": "都江堰", "lng": 103.61700, "lat": 30.99700,
         "speech": "上午都江堰景区外逛。建议提前购票，景区较大，可选观光车或步行。都江堰是世界文化遗产，两千多年来一直发挥着防洪灌溉的作用。",
         "environment": "古堰雄伟，岷江水声轰鸣，两千年水利工程奇迹",
         "signs": ["都江堰景区", "鱼嘴分水堤"],
         "recommendation": "世界文化遗产，两千年古代水利奇迹。建议乘观光车游览。",
         "visit_duration": "2小时", "best_time": "全年", "ticket": "80元",
         "tag": "山", "mood": "震撼",
         "images": ["chengdu/柚在吃什么！/都江堰-1.jpeg"]},
        {"name": "宽窄巷子", "lng": 104.05373, "lat": 30.67193,
         "speech": "下午宽窄巷子自由行，打卡美食。可尝试甜皮鸭、肥肠粉等特色美食。清朝古街道，成都遗留较成规模的历史街区。",
         "environment": "青砖灰瓦，老街市井，古色古香与现代小店交织",
         "signs": ["宽巷子", "窄巷子", "井巷子"],
         "recommendation": "成都最具代表性历史街区！甜皮鸭、肥肠粉、糖油果子必吃！上午来人少更出片。",
         "visit_duration": "1.5小时", "best_time": "上午（人少）", "ticket": "免费",
         "tag": "城市", "mood": "悠闲",
         "images": ["chengdu/柚在吃什么！/宽窄巷子-1.jpeg"]},
        {"name": "春熙路太古里", "lng": 104.08290, "lat": 30.65670,
         "speech": "晚上春熙路太古里逛街。成都最繁华商业街，太古里是成都的时尚地标，融合了传统与现代的建筑风格。",
         "environment": "开放式街区，现代与古建融合，霓虹灯光",
         "signs": ["春熙路", "太古里", "大慈寺"],
         "recommendation": "傍晚最舒服，太古里随手一拍大片！大慈寺藏在太古里里面很出片，夜景超漂亮。",
         "visit_duration": "1.5小时", "best_time": "傍晚/夜晚", "ticket": "免费",
         "tag": "城市", "mood": "精致",
         "images": ["chengdu/柚在吃什么！/春熙路太古里-1.jpeg"]},
        {"name": "三星堆博物馆", "lng": 104.18870, "lat": 31.13040,
         "speech": "上午三星堆博物馆，门票需提前购买，周末可能售罄；建议从春熙路乘坐直通车前往。古蜀文明的重要遗址。",
         "environment": "博物馆内宏大展厅，青铜神树、纵目面具震撼陈列",
         "signs": ["三星堆博物馆", "新馆"],
         "recommendation": "震撼！青铜纵目面具和神树必看。周末门票需提前1周抢，从春熙路乘直通车约1小时。",
         "visit_duration": "3小时", "best_time": "上午开馆", "ticket": "62元（需提前预约）",
         "tag": "城市", "mood": "震撼",
         "images": ["chengdu/柚在吃什么！/三星堆-1.webp", "chengdu/柚在吃什么！/三星堆-2.webp", "chengdu/柚在吃什么！/三星堆-3.webp"]}
    ],
    "food": [
        {"name": "老妈蹄花", "location": "成都市区", "price": "约50元/人", "desc": "清淡口味，蹄花软烂，汤头清澈", "rating": "⭐⭐⭐⭐"},
        {"name": "牦牛汤锅", "location": "九寨沟景区附近", "price": "约80元/人", "desc": "菌汤锅底，牦牛肉鲜嫩，高原特色必吃", "rating": "⭐⭐⭐⭐⭐"},
        {"name": "甜皮鸭", "location": "宽窄巷子", "price": "约35元/半只", "desc": "纯甜口味，皮脆肉嫩，成都特色小吃", "rating": "⭐⭐⭐⭐"},
        {"name": "肥肠粉", "location": "成都街边", "price": "约15元", "desc": "成都街头小吃之王，红薯粉+肥肠+辣椒，香辣过瘾", "rating": "⭐⭐⭐⭐⭐"},
        {"name": "地道老火锅", "location": "成都市区", "price": "约200元/人", "desc": "麻辣鲜香，推荐香油油碟蘸料", "rating": "⭐⭐⭐⭐⭐"}
    ],
    "transport": [
        {"from": "市区", "to": "熊猫基地", "mode": "打车/直通车", "duration": "约30分钟", "desc": "建议打车或专线直通车到南门", "cost": "约30元打车"},
        {"from": "成都东站", "to": "九寨沟", "mode": "高铁+大巴", "duration": "约4小时", "desc": "高铁到松潘约2小时，再转大巴约2小时", "cost": "约150元"},
        {"from": "都江堰", "to": "宽窄巷子", "mode": "地铁", "duration": "约50分钟", "desc": "成都地铁4号线", "cost": "约5元"},
        {"from": "宽窄巷子", "to": "春熙路太古里", "mode": "地铁", "duration": "约20分钟", "desc": "地铁2号线或3号线", "cost": "约3元"},
        {"from": "春熙路", "to": "三星堆", "mode": "直通车", "duration": "约1小时", "desc": "从春熙路乘三星堆直通车", "cost": "约30-50元"}
    ],
    "tips": [
        "九寨沟海拔2000-3000米，建议备好红景天，避免剧烈运动",
        "熊猫基地工作日去人少；7:30开馆即进，看熊猫吃早餐最活泼",
        "三星堆周末容易售罄，建议提前1周在官方App购票",
        "成都火锅人均约200元，推荐香油油碟蘸料可解辣",
        "特种兵行程体力消耗大，建议每天晚上泡脚放松",
        "盖碗茶是成都特色伴手礼，返程前在宽窄巷子购买"
    ]
}

# 写入单独文件
for data, name in [(daming, 'hangzhou_daming.json'), (yuanzi, 'hangzhou_yuanzi.json'), (youzi, 'chengdu_youzi.json')]:
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'Written: {name}')

# 整合知识库
kb = {
    "_meta": {
        "description": "灵动地图 Demo 知识库 - 由真实博主视频解析生成",
        "sources": [
            "大铭-杭州两日游（断桥+平湖秋月+曲院风荷+水上巴士+花港观鱼+柳浪闻莺+法喜寺+灵隐寺+植物园）",
            "圆子芝士-杭州一日游（灵隐寺+太子湾+曲院风荷+来福士52楼）",
            "柚在吃什么！-成都四天三晚（熊猫基地+九寨沟+都江堰+宽窄巷子+太古里+三星堆）"
        ],
        "generated": "2026-04-18",
        "image_base_path": "E:/Hackthon/Map/picture/visual"
    },
    "杭州": {
        daming["blogger"]: {k: v for k, v in daming.items() if k not in ("city", "blogger")},
        yuanzi["blogger"]: {k: v for k, v in yuanzi.items() if k not in ("city", "blogger")}
    },
    "成都": {
        youzi["blogger"]: {k: v for k, v in youzi.items() if k not in ("city", "blogger")}
    }
}
with open(os.path.join(OUT, 'knowledge_base_demo.json'), 'w', encoding='utf-8') as f:
    json.dump(kb, f, ensure_ascii=False, indent=2)
print('Written: knowledge_base_demo.json')
print('All done!')

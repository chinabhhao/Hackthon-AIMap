import unittest

from services.province_detector import detect_province, normalize_province_input


class TestProvinceDetector(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(detect_province(""))
        self.assertIsNone(detect_province(None))  # type: ignore[arg-type]

    def test_beijing(self):
        self.assertEqual(detect_province("北京vlog").province, "北京市")
        self.assertEqual(detect_province("beijing_trip.mp4").province, "北京市")
        self.assertEqual(detect_province("bj_001").province, "北京市")

    def test_shanghai(self):
        self.assertEqual(detect_province("上海 CityWalk").province, "上海市")
        self.assertEqual(detect_province("shanghai").province, "上海市")

    def test_tianjin(self):
        self.assertEqual(detect_province("天津相声").province, "天津市")
        self.assertEqual(detect_province("tianjin").province, "天津市")

    def test_chongqing(self):
        self.assertEqual(detect_province("重庆洪崖洞").province, "重庆市")
        self.assertEqual(detect_province("cq_hotpot").province, "重庆市")

    def test_hebei(self):
        self.assertEqual(detect_province("石家庄").province, "河北省")
        self.assertEqual(detect_province("河北唐山").province, "河北省")

    def test_shanxi(self):
        self.assertEqual(detect_province("太原一日").province, "山西省")
        self.assertEqual(detect_province("shanxi").province, "山西省")

    def test_neimenggu(self):
        self.assertEqual(detect_province("呼和浩特").province, "内蒙古自治区")
        self.assertEqual(detect_province("inner mongolia").province, "内蒙古自治区")

    def test_liaoning(self):
        self.assertEqual(detect_province("大连海边").province, "辽宁省")
        self.assertEqual(detect_province("liaoning").province, "辽宁省")

    def test_jilin(self):
        self.assertEqual(detect_province("长春").province, "吉林省")
        self.assertEqual(detect_province("吉林省").province, "吉林省")

    def test_heilongjiang(self):
        self.assertEqual(detect_province("哈尔滨中央大街").province, "黑龙江省")
        self.assertEqual(detect_province("heilongjiang").province, "黑龙江省")

    def test_jiangsu(self):
        self.assertEqual(detect_province("南京").province, "江苏省")
        self.assertEqual(detect_province("苏州园林").province, "江苏省")
        self.assertEqual(detect_province("jiangsu").province, "江苏省")

    def test_zhejiang(self):
        self.assertEqual(detect_province("杭州西湖").province, "浙江省")
        self.assertEqual(detect_province("zhejiang").province, "浙江省")
        self.assertEqual(detect_province("宁波").province, "浙江省")

    def test_anhui(self):
        self.assertEqual(detect_province("黄山日出").province, "安徽省")
        self.assertEqual(detect_province("anhui").province, "安徽省")

    def test_fujian(self):
        self.assertEqual(detect_province("厦门鼓浪屿").province, "福建省")
        self.assertEqual(detect_province("fujian").province, "福建省")

    def test_jiangxi(self):
        self.assertEqual(detect_province("南昌").province, "江西省")
        self.assertEqual(detect_province("jiangxi").province, "江西省")

    def test_shandong(self):
        self.assertEqual(detect_province("青岛").province, "山东省")
        self.assertEqual(detect_province("yantai").province, "山东省")

    def test_henan(self):
        self.assertEqual(detect_province("洛阳").province, "河南省")
        self.assertEqual(detect_province("henan").province, "河南省")

    def test_hubei(self):
        self.assertEqual(detect_province("武汉").province, "湖北省")
        self.assertEqual(detect_province("hubei").province, "湖北省")

    def test_hunan(self):
        self.assertEqual(detect_province("长沙").province, "湖南省")
        self.assertEqual(detect_province("张家界").province, "湖南省")

    def test_guangdong(self):
        self.assertEqual(detect_province("广州").province, "广东省")
        self.assertEqual(detect_province("shenzhen").province, "广东省")

    def test_guangxi(self):
        self.assertEqual(detect_province("桂林山水").province, "广西壮族自治区")
        self.assertEqual(detect_province("guangxi").province, "广西壮族自治区")

    def test_hainan(self):
        self.assertEqual(detect_province("三亚").province, "海南省")
        self.assertEqual(detect_province("hainan").province, "海南省")

    def test_sichuan(self):
        self.assertEqual(detect_province("成都").province, "四川省")
        self.assertEqual(detect_province("九寨沟").province, "四川省")

    def test_guizhou(self):
        self.assertEqual(detect_province("贵阳").province, "贵州省")
        self.assertEqual(detect_province("guizhou").province, "贵州省")

    def test_yunnan(self):
        self.assertEqual(detect_province("大理").province, "云南省")
        self.assertEqual(detect_province("yunnan").province, "云南省")

    def test_tibet(self):
        self.assertEqual(detect_province("拉萨").province, "西藏自治区")
        self.assertEqual(detect_province("tibet").province, "西藏自治区")

    def test_shaanxi(self):
        self.assertEqual(detect_province("西安").province, "陕西省")
        self.assertEqual(detect_province("兵马俑").province, "陕西省")

    def test_gansu(self):
        self.assertEqual(detect_province("敦煌").province, "甘肃省")
        self.assertEqual(detect_province("gansu").province, "甘肃省")

    def test_qinghai(self):
        self.assertEqual(detect_province("西宁").province, "青海省")
        self.assertEqual(detect_province("qinghai").province, "青海省")

    def test_ningxia(self):
        self.assertEqual(detect_province("银川").province, "宁夏回族自治区")
        self.assertEqual(detect_province("ningxia").province, "宁夏回族自治区")

    def test_xinjiang(self):
        self.assertEqual(detect_province("乌鲁木齐").province, "新疆维吾尔自治区")
        self.assertEqual(detect_province("kashgar").province, "新疆维吾尔自治区")

    def test_normalize(self):
        self.assertEqual(normalize_province_input("浙江省"), "浙江省")
        self.assertEqual(normalize_province_input("杭州"), "浙江省")
        self.assertIsNone(normalize_province_input("不存在的省份"))


if __name__ == "__main__":
    unittest.main()


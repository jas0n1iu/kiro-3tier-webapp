"""A/S request report logic. Pure functions, no I/O, no third-party imports (Python 3.9 compatible).

All rules below (warranty months, response times, repair steps) are SAMPLE rules for a demo.
Replace them with the real service-center policy before any production use.
"""
import calendar
import datetime as dt

PRODUCTS = ["TV", "冰箱", "洗衣机", "空调", "智能手机"]
FAULTS = ["电源故障", "噪声", "制冷故障", "显示故障", "物理损坏"]
URGENCIES = ["高", "中", "低"]

MAX_SYMPTOM_LEN = 500
EARLIEST_PURCHASE = dt.date(2000, 1, 1)

# Sample warranty period in months, per product category.
WARRANTY_MONTHS = {"TV": 24, "冰箱": 24, "洗衣机": 24, "空调": 36, "智能手机": 12}

# Sample response targets per urgency.
PRIORITY = {
    "高": {
        "level": "P1 紧急",
        "contact": "受理后 4 小时内联系客户",
        "service": "24 小时内安排检测或上门",
        "guidance": [
            "立即指派资深工程师，优先于普通工单处理。",
            "联系客户确认是否存在安全风险（冒烟、异味、漏电、漏水）；有风险时先指导客户断电停用。",
            "备件缺货时启动加急调货，并每日向客户同步进度。",
        ],
    },
    "中": {
        "level": "P2 一般",
        "contact": "受理后 1 个工作日内联系客户",
        "service": "3 个工作日内安排检测或上门",
        "guidance": [
            "按常规派工队列处理。",
            "联系客户确认故障现象与方便的上门时间。",
            "维修超过 3 个工作日时主动告知客户原因。",
        ],
    },
    "低": {
        "level": "P3 低",
        "contact": "受理后 3 个工作日内联系客户",
        "service": "7 个工作日内安排检测或上门",
        "guidance": [
            "可与同区域其他工单合并安排。",
            "先提供自助排查建议，客户仍需服务时再派工。",
        ],
    },
}

COMMON_INTAKE = ["核对产品型号、序列号与购买凭证。", "向客户确认故障现象，并留存照片或视频。"]
COMMON_CLOSE = ["维修后功能验证并清理现场。", "填写维修记录，回访客户确认问题已解决。"]

# Product-specific steps for each (product, fault). Kept short and generic on purpose.
REPAIR_STEPS = {
    "TV": {
        "电源故障": ["检查电源线、插座与遥控器电池。", "检测电源板与待机指示灯状态。", "必要时更换电源板。"],
        "噪声": ["区分声音来源（扬声器、风扇、电源板啸叫）。", "检查外壳固定与散热通风。", "更换故障扬声器或风扇。"],
        "制冷故障": ["电视无制冷功能，向客户确认故障描述是否准确。", "检查机身过热、散热口堵塞情况。", "必要时检测主板与电源板温度保护。"],
        "显示故障": ["切换信号源并外接设备，排除线材与信号问题。", "进入自检画面，判断是面板还是主板故障。", "更换主板、逻辑板或面板（视检测结果）。"],
        "物理损坏": ["检查外观与屏幕损伤，拍照留证。", "判断损坏是否属于人为因素并告知客户保修影响。", "出具维修报价，客户确认后更换部件。"],
    },
    "冰箱": {
        "电源故障": ["检查电源线、插座与断路器。", "测量压缩机启动继电器与保护器。", "更换电源板或启动元件。"],
        "噪声": ["区分噪声来源（压缩机、风扇、管路共振）。", "检查摆放是否水平，管路是否接触箱体。", "更换风扇电机或加固管路。"],
        "制冷故障": ["检查温度设定、门封条与结霜情况。", "检测压缩机、风扇与化霜系统工作状态。", "检漏并补充制冷剂，或更换故障部件。"],
        "显示故障": ["检查控制面板与排线连接。", "重启后观察显示是否恢复。", "更换显示板或主控板。"],
        "物理损坏": ["检查箱体、门体与门封损伤并拍照留证。", "判断是否影响制冷与安全。", "出具维修报价，客户确认后更换部件。"],
    },
    "洗衣机": {
        "电源故障": ["检查电源线、插座与门锁状态。", "检测电源板与门锁开关。", "更换电源板或门锁组件。"],
        "噪声": ["检查是否放平、运输螺栓是否已拆除。", "检查减震器、轴承与排水泵。", "更换轴承、减震器或排水泵。"],
        "制冷故障": ["洗衣机无制冷功能，向客户确认是否指烘干或加热异常。", "检测加热管与温度传感器。", "更换加热管或传感器。"],
        "显示故障": ["检查显示面板与排线连接。", "重启并尝试进入自检模式。", "更换显示板或主控板。"],
        "物理损坏": ["检查外壳、门玻璃与门封损伤并拍照留证。", "判断是否存在漏水风险。", "出具维修报价，客户确认后更换部件。"],
    },
    "空调": {
        "电源故障": ["检查电源开关、断路器与遥控器。", "检测室内外机主板与保险管。", "更换主板或保险组件。"],
        "噪声": ["区分室内机或室外机噪声来源。", "检查风扇叶、固定支架与管路共振。", "更换风扇电机或加固支架。"],
        "制冷故障": ["检查滤网、设定温度与室外机散热。", "检测制冷剂压力与压缩机运行状态。", "检漏补充制冷剂，或更换压缩机、传感器。"],
        "显示故障": ["检查显示板与接收头。", "重启并核对遥控器指令响应。", "更换显示板或主板。"],
        "物理损坏": ["检查室内外机外壳、管路与支架损伤并拍照留证。", "判断是否存在漏冷媒或坠落风险。", "出具维修报价，客户确认后更换部件。"],
    },
    "智能手机": {
        "电源故障": ["尝试更换充电线与充电器，检查充电口。", "检测电池健康度与开机状态。", "更换电池或主板（视检测结果）。"],
        "噪声": ["区分噪声来源（听筒、扬声器、麦克风）。", "清理扬声器网孔，排除软件问题。", "更换扬声器或麦克风组件。"],
        "制冷故障": ["手机无制冷功能，向客户确认是否指过热问题。", "检查充电与后台耗电情况。", "检测电池与主板温度，必要时更换电池。"],
        "显示故障": ["重启并进入安全模式，排除软件问题。", "检查屏幕触控、亮线与花屏情况。", "更换屏幕总成。"],
        "物理损坏": ["检查机身、屏幕与进水指示标记并拍照留证。", "判断是否属人为损坏并告知客户保修影响。", "出具维修报价，客户确认后更换部件。"],
    },
}


class ValidationError(ValueError):
    pass


def add_months(d, months):
    """Calendar-month addition; clamps the day to the target month's last day."""
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def parse_input(data, today):
    """Validate untrusted input. Returns a clean dict or raises ValidationError."""
    if not isinstance(data, dict):
        raise ValidationError("请求格式不正确")
    product = data.get("product")
    fault = data.get("fault")
    urgency = data.get("urgency")
    if product not in PRODUCTS:
        raise ValidationError("产品类别无效")
    if fault not in FAULTS:
        raise ValidationError("故障类型无效")
    if urgency not in URGENCIES:
        raise ValidationError("紧急程度无效")
    raw_date = data.get("purchase_date")
    if not isinstance(raw_date, str):
        raise ValidationError("购买日期无效")
    try:
        purchase = dt.date.fromisoformat(raw_date)
    except ValueError:
        raise ValidationError("购买日期格式应为 YYYY-MM-DD")
    if purchase > today:
        raise ValidationError("购买日期不能晚于今天")
    if purchase < EARLIEST_PURCHASE:
        raise ValidationError("购买日期过早")
    symptom = data.get("symptom")
    if not isinstance(symptom, str):
        raise ValidationError("故障症状描述无效")
    symptom = symptom.strip()
    if not symptom:
        raise ValidationError("请填写故障症状描述")
    if len(symptom) > MAX_SYMPTOM_LEN:
        raise ValidationError("故障症状描述不能超过 %d 个字符" % MAX_SYMPTOM_LEN)
    return {
        "product": product, "fault": fault, "urgency": urgency,
        "purchase_date": purchase, "symptom": symptom,
    }


def warranty(product, fault, purchase, today):
    end = add_months(purchase, WARRANTY_MONTHS[product])
    in_warranty = today <= end
    if in_warranty:
        note = "保修期内（截止 %s）。" % end.isoformat()
        if fault == "物理损坏":
            note += "物理损坏通常属人为因素，不在免费保修范围，需检测后确认。"
    else:
        note = "保修期外（已于 %s 到期），维修需按标准收费。" % end.isoformat()
    return {
        "status": "保修期内" if in_warranty else "保修期外",
        "months": WARRANTY_MONTHS[product],
        "end_date": end.isoformat(),
        "note": note,
    }


def build_report(clean, today, ticket_no):
    """Build the structured report plus the formal plain-text draft."""
    w = warranty(clean["product"], clean["fault"], clean["purchase_date"], today)
    p = PRIORITY[clean["urgency"]]
    steps = COMMON_INTAKE + REPAIR_STEPS[clean["product"]][clean["fault"]] + COMMON_CLOSE
    if w["status"] == "保修期外":
        steps = steps[:-2] + ["向客户出具维修报价并取得确认后再施工。"] + steps[-2:]

    lines = [
        "A/S 受理报告（草稿）",
        "=" * 28,
        "受理编号：%s" % ticket_no,
        "受理日期：%s" % today.isoformat(),
        "",
        "一、产品与故障信息",
        "产品类别：%s" % clean["product"],
        "故障类型：%s" % clean["fault"],
        "购买日期：%s" % clean["purchase_date"].isoformat(),
        "紧急程度：%s" % clean["urgency"],
        "故障症状描述：%s" % clean["symptom"],
        "",
        "二、保修判定",
        "保修状态：%s" % w["status"],
        "保修期限：%d 个月（截止 %s）" % (w["months"], w["end_date"]),
        "说明：%s" % w["note"],
        "",
        "三、处理优先级",
        "优先级：%s" % p["level"],
        "联系时限：%s" % p["contact"],
        "服务时限：%s" % p["service"],
        "处理指导：",
    ]
    lines += ["  - %s" % g for g in p["guidance"]]
    lines += ["", "四、预计维修步骤"]
    lines += ["  %d. %s" % (i, s) for i, s in enumerate(steps, 1)]
    lines += [
        "",
        "备注：本报告由系统自动生成，仅为草稿。保修期限、处理时限与维修步骤为示例规则，",
        "以服务中心正式政策与工程师现场检测结果为准。",
    ]
    return {
        "ticket_no": ticket_no,
        "warranty": w,
        "priority": {"level": p["level"], "contact": p["contact"], "service": p["service"], "guidance": p["guidance"]},
        "steps": steps,
        "report_text": "\n".join(lines),
    }


def ticket_number(today, row_id=None):
    if row_id is None:
        return "AS%s-DRAFT" % today.strftime("%Y%m%d")
    return "AS%s-%05d" % (today.strftime("%Y%m%d"), row_id)

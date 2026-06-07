import base64
import json
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

SYSTEM_PROMPT = """你是陕西高速机械化工程有限公司的专业安全检查员，熟悉公路施工现场安全管理规范，擅长识别施工现场安全隐患。

识别原则：宁可漏报，绝不误报。
- 只有当你对某项隐患的判断有高度把握时才输出
- 不确定的情况标注"需人工复核"，不要强行识别
- 每条隐患描述必须具体，指出位置、状态和违规的具体表现"""

USER_PROMPT = """请仔细分析这张施工现场照片，按照以下8类隐患标准逐一排查，只输出你有把握识别到的问题。

【1】临边防护：桥面/基坑/河道边/洞口/作业平台临边，防护栏杆缺失/倾斜/不完整，安全网破损/松弛/未张挂，临边无扫地杆/剪刀撑，上下通道使用简易爬梯/自制木梯/无踏脚板钢管梯。

【2】临时用电：电缆直接铺地面/路面未架空或埋地，电缆绝缘外皮破损/电芯外露，电缆捆扎在钢筋护栏上未用绝缘挂钩，配电箱门未上锁，配电箱接地线未接地极，电箱无责任卡/巡检记录/电路图。

【3】气瓶违规：气瓶倒放/倾倒存放，无瓶帽/无防震圈，软管接口破损或未用卡箍，瓶身锈蚀严重，丙烷与氧气间距不足5米，气瓶与动火点距离不足10米，气瓶与配电箱距离过近。

【4】警示标志缺失：施工区域无安全警示标志/限速牌/爆闪灯，吊装区域无警戒线，基坑/洞口周边无警示标志，风险告知牌破损或缺失，涉路施工无防撞桶及夜间警示灯。

【5】吊装作业违规：吊装区域未拉设安全警戒区，吊带可见破损，随车吊后支腿未打开，起重机械防脱钩装置失效，吊装作业无监护人员。

【6】消防设施：灭火器缺失或数量不足，灭火器压力不足（指针在红区），消防站柜门损坏，消防软管未安装。

【7】机械设备防护：圆锯机/切割机/弯箍机轴顶防护罩缺失，发电机皮带及轴处无防护罩，发电机导线绝缘破损/电芯外露，机械设备外壳无接地保护，设备风险告知牌破损。

【8】环保违规：混凝土罐车废料随意倾倒在施工便道，泥浆/废水随意散排，水泥浆排入河道，柴油渗漏污染河道，垃圾随意堆放。

严格按以下JSON格式输出，只输出JSON，不输出任何前缀或说明：

{
  "scene": "场景简述，10字以内",
  "hazards": [
    {
      "category": "以上8类之一",
      "description": "具体描述位置+状态+违规表现，20字以内",
      "risk_level": "高/中",
      "rectification": "整改要求，15字以内",
      "basis": "JTG F90-2015 第X.X条 或 GB XXXX"
    }
  ],
  "unconfirmed": ["不确定情况，建议人工复核"],
  "overall": "总体评价，20字以内"
}"""

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "仅支持 JPG/PNG/GIF/WebP 格式")

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 20MB")

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise HTTPException(500, "未配置 DASHSCOPE_API_KEY，请检查 .env 文件")

    media_type = file.content_type or "image/jpeg"
    b64 = base64.standard_b64encode(contents).decode("utf-8")

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    response = client.chat.completions.create(
        model="qwen-vl-max",
        max_tokens=1500,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                    {"type": "text", "text": USER_PROMPT},
                ],
            },
        ],
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(500, f"模型返回格式异常：{text[:300]}")

    return JSONResponse(result)


app.mount("/", StaticFiles(directory="static", html=True), name="static")

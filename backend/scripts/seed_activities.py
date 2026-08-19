"""用初始示例活动填充 activities 表（仅当表为空时插入，避免重复）。

用法： python -m scripts.seed_activities          # 表为空时插入示例
       python -m scripts.seed_activities --force  # 即使已有数据也追加示例

封面图用 academy 资源相对路径，公开接口会自动转成 /api/v1/assets/academy/... 。
"""
import sys

from sqlalchemy import create_engine, text

from app.core.config import settings

PAINT = "组织画家绘制了十大书院事件图"
PHOTOS = "组织拍摄了江西遗存书院/江西四大书院"

SEED = [
    {
        "category": "书院公告", "title": "豫章书院数智化项目正式启动",
        "summary": "引入知识检索、AI 导览与数字档案系统，开放在线「问书院」。",
        "body": "豫章书院数智化项目正式上线，依托知识库检索、智能问答与历史名人互动等技术，将馆藏典籍、碑刻题咏与书院史事系统数字化，向公众开放「问书院」在线服务。",
        "event_date": "2026-04-01", "period": "长期开放", "place": "线上 · 豫章书院数智平台",
        "audience": "面向社会公众", "status": "ongoing",
        "highlights": ["在线问书院，回答尽附出处", "AI 数字导览先生随时答疑", "历史名人隔空对谈"],
        "image": f"{PAINT}/省会豫章书院的设立.jpg", "sort_order": 100,
    },
    {
        "category": "讲会论道", "title": "传统文化讲座系列 · 江右理学专题",
        "summary": "邀学者分享儒学经典、书院礼仪与江右文化传承。",
        "body": "本季讲座聚焦江右理学源流，邀请高校学者与书院研究者，围绕白鹿洞之规、象山心学、阳明良知等主题展开，兼及古籍解读、书院礼仪与当代创新。",
        "event_date": "2026-03-28", "period": "每周六 14:30", "place": "豫章书院 · 明伦堂",
        "audience": "高校师生 / 文化爱好者", "status": "open",
        "highlights": ["名家主讲 + 现场会讲问难", "每场赠书院文化读本", "可线上同步直播回看"],
        "image": f"{PAINT}/朱熹亲订《白鹿洞书院揭示》.jpg", "sort_order": 90,
    },
    {
        "category": "研学体验", "title": "春季研学营 · 走读江右四大书院",
        "summary": "书院探访、古籍阅读、礼仪体验与主题讨论。",
        "body": "春季研学营带领营员实地走读白鹿洞、白鹭洲、鹅湖、豫章等江右名院，安排古籍诵读、拓片体验、束脩开笔礼与分组主题研讨。",
        "event_date": "2026-03-25", "period": "4 月 · 两日一晚", "place": "南昌 / 庐山 / 吉安 / 铅山",
        "audience": "中小学及社会公众", "status": "open",
        "highlights": ["四大书院实地走读", "开笔礼 · 拓片 · 古籍诵读", "结业颁发研学证书"],
        "image": f"{PHOTOS}/白鹿洞书院/白鹿洞书院正学之门前古牌坊.JPG", "sort_order": 80,
    },
    {
        "category": "书院公告", "title": "书院入选省级文化遗产保护单位",
        "summary": "成为江右文化与儒学传承的重要标志。",
        "body": "豫章书院正式入选省级文化遗产保护单位，其建筑遗存、碑刻匾额与讲学传统获得系统性保护。",
        "event_date": "2026-03-20", "period": "已公布", "place": "江西 · 南昌",
        "audience": "—", "status": "closed",
        "highlights": ["建筑遗存系统性修缮", "碑刻题咏数字建档", "挂牌省级保护单位"],
        "image": f"{PHOTOS}/白鹭洲书院/白鹭洲书院云章阁.JPG", "sort_order": 70,
    },
    {
        "category": "文化交流", "title": "鹅湖之会 · 朱陆论道复现雅集",
        "summary": "重现「尊德性」与「道问学」的千古论辩。",
        "body": "于鹅湖书院旧址举办文化雅集，以情景再现与学术对谈相结合的方式，重现朱熹、陆九渊「鹅湖之会」的为学异同。",
        "event_date": "2026-03-12", "period": "半日", "place": "铅山 · 鹅湖书院",
        "audience": "学界 / 文化机构", "status": "closed",
        "highlights": ["情景再现朱陆论道", "古琴 · 茶礼 · 诗文唱和", "两岸学人会讲"],
        "image": f"{PAINT}/“尊德性”与“道问学”的鹅湖之会.jpg", "sort_order": 60,
    },
    {
        "category": "文化交流", "title": "白鹭洲「文章节义」主题展",
        "summary": "以江万里与文天祥为线，讲述书院气节教育。",
        "body": "展览以白鹭洲书院「文章节义」之教为主线，串联江万里创院、培育文天祥等忠义之士的史事，结合书院画作、文献与多媒体装置。",
        "event_date": "2026-02-28", "period": "展期一个月", "place": "吉安 · 白鹭洲书院",
        "audience": "面向社会公众", "status": "closed",
        "highlights": ["十大书院事件画作展出", "文天祥与白鹭洲专题", "沉浸式多媒体导览"],
        "image": f"{PAINT}/白鹭洲书院的“文章节义”.jpg", "sort_order": 50,
    },
]


def main() -> None:
    force = "--force" in sys.argv
    engine = create_engine(settings.alembic_database_uri)
    import json

    with engine.begin() as conn:
        existing = conn.execute(text("SELECT COUNT(*) FROM activities")).scalar() or 0
        if existing and not force:
            print(f"activities already has {existing} rows; skip (use --force to append)")
            return
        for s in SEED:
            conn.execute(
                text(
                    "INSERT INTO activities "
                    "(category,title,summary,body,event_date,period,place,audience,status,highlights,image,is_published,sort_order) "
                    "VALUES (:category,:title,:summary,:body,:event_date,:period,:place,:audience,:status,:highlights,:image,1,:sort_order)"
                ),
                {**s, "highlights": json.dumps(s["highlights"], ensure_ascii=False)},
            )
        print(f"inserted {len(SEED)} activities")


if __name__ == "__main__":
    main()

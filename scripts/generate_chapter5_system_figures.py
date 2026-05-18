from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


OUTPUT_DIR = Path(r"F:/sleep/outputs")
FONT_PATHS = [
    Path(r"C:/Windows/Fonts/msyh.ttc"),
    Path(r"C:/Windows/Fonts/simhei.ttf"),
    Path(r"C:/Windows/Fonts/simsun.ttc"),
]


def get_font(size: int, bold: bool = False) -> FontProperties | None:
    for path in FONT_PATHS:
        if path.exists():
            return FontProperties(fname=str(path), size=size, weight="bold" if bold else "normal")
    return None


FONT = get_font(10)
FONT_SMALL = get_font(8)
FONT_BOLD = get_font(11, bold=True)
FONT_TITLE = get_font(13, bold=True)


def setup_canvas(width: float, height: float):
    fig, ax = plt.subplots(figsize=(width, height), dpi=220)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def save_figure(fig, name: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(path)


def add_text(ax, x, y, text, size=10, bold=False, ha="center", va="center", color="#111111"):
    ax.text(
        x,
        y,
        text,
        ha=ha,
        va=va,
        fontproperties=get_font(size, bold=bold),
        color=color,
        wrap=True,
    )


def add_rect(ax, x, y, w, h, text, fc="white", ec="#222222", lw=1.2, fontsize=10):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec, linewidth=lw))
    add_text(ax, x + w / 2, y + h / 2, text, size=fontsize)


def add_round_rect(ax, x, y, w, h, text, fc="white", ec="#222222", lw=1.2, fontsize=10, radius=0.08):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle=f"round,pad=0.02,rounding_size={radius * min(w, h)}",
            facecolor=fc,
            edgecolor=ec,
            linewidth=lw,
        )
    )
    add_text(ax, x + w / 2, y + h / 2, text, size=fontsize)


def add_container(ax, x, y, w, h, title, fc, ec="#666666", title_fc="#333333"):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec, linewidth=1.3))
    add_text(ax, x + 2, y + h - 2.5, title, size=9, bold=True, ha="left", va="top", color=title_fc)


def add_diamond(ax, cx, cy, w, h, text, fc="white", ec="#222222", lw=1.2, fontsize=9):
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=fc, edgecolor=ec, linewidth=lw))
    add_text(ax, cx, cy, text, size=fontsize)


def add_arrow(ax, start, end, text="", color="#222222", lw=1.1, ms=12, rad=0.0, fontsize=8, text_offset=(0, 0)):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=ms,
        linewidth=lw,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
    )
    ax.add_patch(arrow)
    if text:
        mx = (start[0] + end[0]) / 2 + text_offset[0]
        my = (start[1] + end[1]) / 2 + text_offset[1]
        add_text(ax, mx, my, text, size=fontsize, color=color)


def add_line(ax, start, end, text="", lw=1.1, fontsize=8, text_offset=(0, 0)):
    ax.plot([start[0], end[0]], [start[1], end[1]], color="#222222", linewidth=lw)
    if text:
        mx = (start[0] + end[0]) / 2 + text_offset[0]
        my = (start[1] + end[1]) / 2 + text_offset[1]
        add_text(ax, mx, my, text, size=fontsize)


def add_start_end(ax, cx, cy, r=1.6):
    ax.add_patch(Circle((cx, cy), r, facecolor="white", edgecolor="#222222", linewidth=1.1))


def add_merge_circle(ax, cx, cy, r=1.4):
    ax.add_patch(Circle((cx, cy), r, facecolor="white", edgecolor="#222222", linewidth=1.1))


def add_database_group(ax, x, y, w, h, title):
    ax.add_patch(Rectangle((x, y), w, h, facecolor="#f6d9d9", edgecolor="#555555", linewidth=1.1))
    add_text(ax, x + 1.5, y + h - 2, title, size=8, bold=True, ha="left", va="top")
    inner_x, inner_y, inner_w, inner_h = x + 5, y + 8, w - 10, h - 14
    ax.add_patch(Rectangle((inner_x, inner_y), inner_w, inner_h, facecolor="#f8f8f8", edgecolor="#666666", linewidth=1.0))
    add_round_rect(ax, inner_x + 4, inner_y + inner_h - 12, inner_w - 8, 7, "SQLite数据库", fc="#ffffff", ec="#666666", lw=1.0, fontsize=8.3, radius=0.18)
    return inner_x, inner_y, inner_w, inner_h


def draw_architecture():
    fig, ax = setup_canvas(13.5, 7.2)
    add_text(ax, 50, 96, "系统架构图", size=13, bold=True)

    add_container(ax, 3, 18, 26, 72, "前端展示层", fc="#cfe3f6")
    add_container(ax, 35, 18, 27, 56, "后端服务层", fc="#d8efda")
    add_container(ax, 66, 18, 30, 38, "数据存储层", fc="#f6d9d9")

    add_round_rect(ax, 12, 76, 9, 7, "Vue.js框架", fc="white", fontsize=8.5, radius=0.04)
    add_round_rect(ax, 10, 56, 13, 8, "页面路由与状态管理", fc="white", fontsize=8.2, radius=0.04)
    add_rect(ax, 6, 24, 6.5, 8, "首页概览页", fc="white", fontsize=8)
    add_rect(ax, 13.8, 24, 6.5, 8, "诊断分析页", fc="white", fontsize=8)
    add_rect(ax, 21.6, 24, 6.5, 8, "历史与规则页", fc="white", fontsize=8)
    add_line(ax, (16.5, 76), (16.5, 64))
    add_line(ax, (16.5, 56), (9.2, 32))
    add_line(ax, (16.5, 56), (17.0, 32))
    add_line(ax, (16.5, 56), (24.8, 32))

    add_round_rect(ax, 44, 67, 10, 7, "FastAPI框架", fc="white", fontsize=8.5, radius=0.04)
    add_round_rect(ax, 42, 53, 14, 7.5, "路由控制层（Controller）", fc="white", fontsize=8.0, radius=0.04)
    add_round_rect(ax, 37, 38, 9, 7, "诊断任务服务", fc="white", fontsize=8, radius=0.04)
    add_round_rect(ax, 44.5, 38, 8, 7, "患者模型服务", fc="white", fontsize=8, radius=0.04)
    add_round_rect(ax, 53, 38, 8, 7, "规则历史服务", fc="white", fontsize=8, radius=0.04)
    add_rect(ax, 38, 25, 8, 6.5, "推理调度", fc="white", fontsize=8)
    add_rect(ax, 51.5, 25, 8, 6.5, "文字结果生成", fc="white", fontsize=8)
    add_line(ax, (49, 67), (49, 60.5))
    add_line(ax, (49, 53), (41.5, 45))
    add_line(ax, (49, 53), (48.5, 45))
    add_line(ax, (49, 53), (57, 45))
    add_line(ax, (41.5, 38), (42, 31.5))
    add_line(ax, (57, 38), (55.5, 31.5))

    inner_x, inner_y, inner_w, inner_h = add_database_group(ax, 69, 23, 24, 26, "结构化数据层")
    add_rect(ax, inner_x + 1.6, inner_y + 8.5, 5.2, 4.8, "患者信息", fontsize=7.1)
    add_rect(ax, inner_x + 8.0, inner_y + 8.5, 5.2, 4.8, "模型信息", fontsize=7.1)
    add_rect(ax, inner_x + 14.4, inner_y + 8.5, 5.2, 4.8, "诊断任务", fontsize=7.1)
    add_rect(ax, inner_x + 1.6, inner_y + 2.2, 5.2, 4.8, "规则信息", fontsize=7.1)
    add_rect(ax, inner_x + 8.0, inner_y + 2.2, 5.2, 4.8, "阶段统计", fontsize=7.1)
    add_rect(ax, inner_x + 14.4, inner_y + 2.2, 5.2, 4.8, "预测结果", fontsize=7.1)

    add_round_rect(ax, 78, 63, 18, 10, "模型文件目录\n上传记录目录\n结果产物目录", fc="white", fontsize=8.2, radius=0.03)

    add_arrow(ax, (29, 69), (35, 69), "RESTful API", text_offset=(0, 3), fontsize=8)
    add_arrow(ax, (62, 60), (78, 68), "任务调度 / 结果回写", text_offset=(0, 3), fontsize=8)
    add_arrow(ax, (62, 52), (69, 42), "JDBC / SQLite", text_offset=(2, 3), fontsize=8, rad=-0.1)
    add_arrow(ax, (25, 82), (35, 77), "前端页面根据任务状态显示不同界面", text_offset=(5, 5), fontsize=7.5, rad=-0.12)
    add_arrow(ax, (62, 74), (69, 68), "后端负责结果组织、异常处理与日志记录", text_offset=(7, 4), fontsize=7.2, rad=0.1)

    save_figure(fig, "图5-1_轻量化辅助诊断系统总体架构图.png")


def draw_function_modules():
    fig, ax = setup_canvas(16, 7.2)
    add_text(ax, 50, 95, "系统功能模块图", size=13, bold=True)

    add_rect(ax, 42, 83, 16, 6.5, "多源数据睡眠障碍病症轻量化辅助诊断系统", fontsize=8.8)
    add_line(ax, (50, 83), (50, 75))

    top_modules = [
        (8, "首页概览"),
        (21, "患者管理"),
        (34, "模型管理"),
        (47, "诊断分析"),
        (60, "规则中心"),
        (73, "历史回看"),
        (86, "结果导出"),
    ]
    for x, label in top_modules:
        add_rect(ax, x - 5.2, 69, 10.4, 6.2, label, fontsize=8.3)
        add_line(ax, (x, 75), (x, 69))
    add_line(ax, (8, 75), (86, 75))

    submodules = {
        8: ["任务统计", "趋势展示", "近期任务"],
        21: ["患者建档", "信息维护", "患者历史"],
        34: ["模型注册", "状态维护", "模型详情"],
        47: ["记录上传", "任务提交", "结果展示"],
        60: ["规则检索", "类别筛选", "规则详情"],
        73: ["历史详情", "波形预览", "结果复核"],
        86: ["CSV导出", "结果下载", "文件留存"],
    }

    for x, labels in submodules.items():
        branch_x = [x - 4.2, x, x + 4.2]
        add_line(ax, (x, 69), (x, 62))
        add_line(ax, (branch_x[0], 62), (branch_x[2], 62))
        for bx, label in zip(branch_x, labels):
            add_line(ax, (bx, 62), (bx, 57))
            add_rect(ax, bx - 1.8, 46, 3.6, 11, label, fontsize=7.2)

    save_figure(fig, "图5-2_系统功能模块图.png")


def draw_workflow():
    fig, ax = setup_canvas(6.2, 14.2)
    add_text(ax, 50, 97, "系统诊断业务流程图", size=13, bold=True)

    add_start_end(ax, 50, 93)
    add_round_rect(ax, 32, 86, 36, 5.5, "选择患者与诊断模型", fontsize=8.5, radius=0.18)
    add_round_rect(ax, 32, 78, 36, 5.5, "上传多导睡眠图记录文件", fontsize=8.5, radius=0.18)
    add_diamond(ax, 50, 69.5, 24, 9, "输入是否完整且合法", fontsize=8.2)
    add_round_rect(ax, 6, 58, 22, 5.5, "返回错误提示", fontsize=8.2, radius=0.18)
    add_round_rect(ax, 32, 58, 36, 5.5, "创建诊断任务并写入队列", fontsize=8.4, radius=0.18)
    add_round_rect(ax, 32, 50, 36, 5.5, "后台线程执行特征提取与模型推理", fontsize=8.1, radius=0.18)
    add_round_rect(ax, 32, 42, 36, 5.5, "生成阶段统计、规则结果与文字结论", fontsize=8.0, radius=0.18)
    add_round_rect(ax, 32, 34, 36, 5.5, "结果写入数据库并生成导出文件", fontsize=8.1, radius=0.18)
    add_round_rect(ax, 32, 26, 36, 5.5, "前端轮询状态并读取诊断详情", fontsize=8.2, radius=0.18)
    add_round_rect(ax, 32, 18, 36, 5.5, "页面展示结果并支持历史回看", fontsize=8.2, radius=0.18)
    add_start_end(ax, 17, 50)
    add_start_end(ax, 50, 12.3)

    for y1, y2 in [(91.4, 91), (86, 83.5), (78, 74)]:
        add_arrow(ax, (50, y1), (50, y2))
    add_arrow(ax, (38, 69.5), (17, 63.5), "否", text_offset=(-1, 2))
    add_arrow(ax, (17, 58), (17, 51.8))
    add_arrow(ax, (50, 65), (50, 63.5), "是", text_offset=(6, 1))
    add_arrow(ax, (50, 58), (50, 55.5))
    add_arrow(ax, (50, 50), (50, 47.5))
    add_arrow(ax, (50, 42), (50, 39.5))
    add_arrow(ax, (50, 34), (50, 31.5))
    add_arrow(ax, (50, 26), (50, 23.5))
    add_arrow(ax, (50, 18), (50, 13.9))

    save_figure(fig, "图5-3_系统诊断业务流程图.png")
    save_figure(fig, "图5-2_系统诊断业务流程图.png")


def draw_text_flow():
    fig, ax = setup_canvas(6.2, 14.8)
    add_text(ax, 50, 97, "后端文字诊断结果生成流程图", size=13, bold=True)

    add_start_end(ax, 50, 93)
    add_round_rect(ax, 28, 86, 44, 5.5, "读取逐 epoch 预测结果与类别概率", fontsize=8.4, radius=0.18)
    add_round_rect(ax, 28, 78, 44, 5.5, "统计五类睡眠阶段占比", fontsize=8.5, radius=0.18)
    add_round_rect(ax, 28, 70, 44, 5.5, "构造睡眠结构向量 s", fontsize=8.5, radius=0.18)
    add_diamond(ax, 50, 60.5, 24, 9, "是否满足高风险阈值", fontsize=8.0)
    add_round_rect(ax, 34, 52, 32, 5.5, "标记为高风险", fontsize=8.4, radius=0.18)
    add_diamond(ax, 50, 42.5, 24, 9, "是否满足中风险阈值", fontsize=8.0)
    add_round_rect(ax, 34, 34, 32, 5.5, "标记为中风险", fontsize=8.4, radius=0.18)
    add_round_rect(ax, 34, 26, 32, 5.5, "标记为低风险", fontsize=8.4, radius=0.18)
    add_round_rect(ax, 22, 17, 56, 5.5, "提取主导阶段、次主导阶段与重点关注阶段", fontsize=8.1, radius=0.18)
    add_round_rect(ax, 22, 9, 56, 5.5, "生成摘要、结论与建议并写入诊断任务表", fontsize=8.1, radius=0.18)
    add_start_end(ax, 50, 3.8)

    add_arrow(ax, (50, 91.4), (50, 91))
    add_arrow(ax, (50, 86), (50, 83.5))
    add_arrow(ax, (50, 78), (50, 75.5))
    add_arrow(ax, (50, 70), (50, 65.0))
    add_arrow(ax, (50, 56), (50, 54.7), "是", text_offset=(6, 0))
    add_arrow(ax, (62, 60.5), (78, 60.5), "否", text_offset=(0, 2))
    add_line(ax, (78, 60.5), (78, 42.5))
    add_arrow(ax, (78, 42.5), (62, 42.5))
    add_line(ax, (50, 52), (50, 47.1))
    add_arrow(ax, (50, 38.0), (50, 36.7), "是", text_offset=(6, 0))
    add_arrow(ax, (62, 42.5), (78, 42.5), "否", text_offset=(0, 2))
    add_line(ax, (78, 42.5), (78, 28.0))
    add_arrow(ax, (78, 28.0), (66, 28.0))
    add_line(ax, (50, 34), (50, 31.5))
    add_line(ax, (50, 26), (50, 22.5))
    add_arrow(ax, (50, 17), (50, 14.5))
    add_arrow(ax, (50, 9), (50, 5.4))

    save_figure(fig, "图5-4_后端文字诊断结果生成流程图.png")


def draw_er():
    fig, ax = setup_canvas(13.5, 8.2)
    add_text(ax, 50, 96, "核心数据ER图", size=13, bold=True)

    add_rect(ax, 8, 62, 12, 7, "患者", fontsize=9.5)
    add_rect(ax, 7, 22, 14, 7, "数据模态", fontsize=9.5)
    add_rect(ax, 36, 46, 16, 8, "诊断任务", fontsize=9.5)
    add_rect(ax, 35, 77, 14, 7, "模型", fontsize=9.5)
    add_rect(ax, 66, 63, 14, 7, "规则", fontsize=9.5)
    add_rect(ax, 84, 77, 12, 7, "规则条件", fontsize=9.0)
    add_rect(ax, 31, 14, 14, 7, "阶段统计", fontsize=9.5)
    add_rect(ax, 49, 14, 16, 7, "逐周期预测", fontsize=9.5)
    add_rect(ax, 70, 14, 14, 7, "结果文件", fontsize=9.5)
    add_rect(ax, 79, 40, 14, 7, "规则激活", fontsize=9.5)

    add_diamond(ax, 28, 52, 10, 7, "发起", fontsize=8.3)
    add_diamond(ax, 14, 45, 10, 7, "包含", fontsize=8.3)
    add_diamond(ax, 43, 66, 10, 7, "使用", fontsize=8.3)
    add_diamond(ax, 59, 66, 10, 7, "拥有", fontsize=8.3)
    add_diamond(ax, 82, 66, 10, 7, "包含", fontsize=8.3)
    add_diamond(ax, 36, 30, 10, 7, "产生", fontsize=8.3)
    add_diamond(ax, 52, 30, 10, 7, "产生", fontsize=8.3)
    add_diamond(ax, 70, 30, 10, 7, "产生", fontsize=8.3)
    add_diamond(ax, 68, 45, 10, 7, "激活", fontsize=8.3)
    add_diamond(ax, 86, 54, 10, 7, "对应", fontsize=8.3)

    add_line(ax, (20, 65.5), (23, 58.0), text="1", text_offset=(-1, 2))
    add_line(ax, (33, 52), (36, 50), text="n", text_offset=(0, 3))

    add_line(ax, (14, 62), (14, 48.5), text="1", text_offset=(3, 0))
    add_line(ax, (14, 41.5), (14, 29), text="n", text_offset=(3, 0))

    add_line(ax, (42, 54), (42, 62.5), text="n", text_offset=(-3, 0))
    add_line(ax, (42, 69.5), (42, 77), text="1", text_offset=(-3, 0))

    add_line(ax, (52, 50), (60, 50))
    add_line(ax, (60, 50), (60, 63), text="n", text_offset=(-2, 3))
    add_line(ax, (60, 69), (49, 80.5), text="1", text_offset=(0, 3))

    add_line(ax, (80, 66), (84, 66), text="1", text_offset=(0, 3))
    add_line(ax, (87, 73), (90, 77), text="n", text_offset=(0, 3))

    add_line(ax, (40, 46), (36, 33.5), text="1", text_offset=(-3, 0))
    add_line(ax, (38, 26.5), (38, 21), text="n", text_offset=(-3, 0))

    add_line(ax, (44, 46), (52, 33.5), text="1", text_offset=(2, 0))
    add_line(ax, (57, 26.5), (57, 21), text="n", text_offset=(3, 0))

    add_line(ax, (49, 46), (70, 33.5), text="1", text_offset=(0, -2))
    add_line(ax, (77, 26.5), (77, 21), text="n", text_offset=(3, 0))

    add_line(ax, (52, 47), (63, 45), text="1", text_offset=(0, 3))
    add_line(ax, (73, 45), (79, 43.5), text="n", text_offset=(0, 3))

    add_line(ax, (82, 47), (86, 50.5), text="n", text_offset=(0, 3))
    add_line(ax, (86, 57.5), (73, 63), text="1", text_offset=(0, 3))

    save_figure(fig, "图5-5_核心数据ER图.png")
    save_figure(fig, "图5-5_核心数据实体关系图.png")


def main():
    draw_architecture()
    draw_function_modules()
    draw_workflow()
    draw_text_flow()
    draw_er()


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "_pipeline_doc_assets"
OUTPUT = DOCS / "Assignment_2_NeRF_Pipeline_Documentation.docx"

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

GOOD = [
    ("盆栽", "plant_360", "object_00184cc3"),
    ("草棚推车", "cart_360", "object_001cfadf"),
    ("风车", "windmill_360", "object_0046f208"),
    ("烤鸡", "roast_chicken_360", "object_004fb4d7"),
    ("红色车辆", "red_vehicle_360", "object_00c7005a"),
    ("鸭子", "duck_360", "object_00f980c0"),
    ("市场摊位", "market_stall_360", "object_05437330"),
    ("酒桶架", "barrel_rack_360", "object_0269ed15"),
    ("城堡", "castle_large_360", "object_04794e1a"),
    ("木屋", "cottage_360_retry", "object_06b9953a"),
]

TRAIN_FAILED = [
    ("椅子", "object_002aec05"),
    ("篮子", "object_0051724d"),
]

BAD = [
    ("手表", "object_000f88bb"),
    ("甜品店", "object_00790c70"),
    ("底盘", "object_016ca0f9"),
    ("双翼飞机", "object_02522f3c"),
    ("花园", "object_0427b05e"),
    ("屋顶桁架", "object_05e9d934"),
]

NAME_BY_DATASET = {dataset: name for name, _, dataset in GOOD}
NAME_BY_DATASET.update({dataset: name for name, dataset in TRAIN_FAILED})
NAME_BY_DATASET.update({dataset: name for name, dataset in BAD})


def font(size: int, bold: bool = False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size=size)


def rgba_on_background(path: Path, size: tuple[int, int], background=(246, 247, 249)) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    canvas = Image.new("RGBA", size, background + (255,))
    scale = min((size[0] - 24) / image.width, (size[1] - 24) / image.height)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    x = (size[0] - resized.width) // 2
    y = (size[1] - resized.height) // 2
    canvas.alpha_composite(resized, (x, y))
    return canvas.convert("RGB")


def add_centered_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fnt, fill=(20, 25, 32)):
    x0, y0, x1, y1 = box
    bounds = draw.textbbox((0, 0), text, font=fnt)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(((x0 + x1 - width) / 2, (y0 + y1 - height) / 2 - bounds[1]), text, font=fnt, fill=fill)


def make_object_gallery() -> Path:
    cell_w, cell_h = 330, 310
    canvas = Image.new("RGB", (cell_w * 5, cell_h * 2), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (name, _, dataset) in enumerate(GOOD):
        row, col = divmod(index, 5)
        x, y = col * cell_w, row * cell_h
        image_path = ROOT / "data" / "nerf_synthetic" / dataset / "test" / "r_000.png"
        tile = rgba_on_background(image_path, (cell_w - 20, cell_h - 58))
        canvas.paste(tile, (x + 10, y + 8))
        draw.rectangle((x + 10, y + 8, x + cell_w - 10, y + cell_h - 50), outline=(216, 220, 225), width=2)
        add_centered_text(draw, (x, y + cell_h - 48, x + cell_w, y + cell_h), f"{index + 1}  {name}", font(26, True))
    output = ASSETS / "qualified_objects_gallery.png"
    canvas.save(output, quality=95)
    return output


def make_match_gallery() -> Path:
    selected = [GOOD[i] for i in (0, 3, 5, 6, 8, 9)]
    cell_w, cell_h = 760, 330
    canvas = Image.new("RGB", (cell_w * 2, cell_h * 3), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (name, _, dataset) in enumerate(selected):
        match_files = sorted((ROOT / "outputs" / "sfm" / dataset / "matches").glob("*.png"))
        image = Image.open(match_files[0]).convert("RGB")
        target_w, target_h = cell_w - 24, cell_h - 62
        scale = min(target_w / image.width, target_h / image.height)
        resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
        row, col = divmod(index, 2)
        x, y = col * cell_w, row * cell_h
        canvas.paste(resized, (x + (cell_w - resized.width) // 2, y + 8))
        add_centered_text(draw, (x, y + cell_h - 48, x + cell_w, y + cell_h), f"{name}  SIFT几何内点匹配", font(24, True))
    output = ASSETS / "match_gallery.png"
    canvas.save(output, quality=95)
    return output


def make_failure_gallery(stats: dict) -> Path:
    cell_w, cell_h = 500, 360
    canvas = Image.new("RGB", (cell_w * 3, cell_h * 2), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (name, dataset) in enumerate(BAD):
        row, col = divmod(index, 3)
        x, y = col * cell_w, row * cell_h
        image_path = ROOT / "data" / "nerf_synthetic" / dataset / "test" / "r_000.png"
        tile = rgba_on_background(image_path, (cell_w - 24, cell_h - 86))
        canvas.paste(tile, (x + 12, y + 8))
        registered = stats[dataset]["registered_images"]
        add_centered_text(draw, (x, y + cell_h - 75, x + cell_w, y + cell_h - 38), name, font(25, True))
        add_centered_text(draw, (x, y + cell_h - 42, x + cell_w, y + cell_h), f"SfM注册 {registered}/144", font(21), fill=(172, 50, 45))
    output = ASSETS / "rejected_objects_gallery.png"
    canvas.save(output, quality=95)
    return output


def make_exposure_gallery() -> Path:
    selected = [GOOD[i] for i in (0, 1, 2, 8)]
    exposures = {"盆栽": "0.65", "草棚推车": "0.65", "风车": "0.65", "城堡": "0.50"}
    asset_keys = {"盆栽": "plant", "草棚推车": "cart", "风车": "windmill", "城堡": "castle"}
    width, height = 1600, 850
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((55, 20), "曝光修正前后的同视角对比", font=font(34, True), fill=(20, 25, 32))
    draw.text((35, 225), "修正前", font=font(25, True), fill=(172, 50, 45))
    draw.text((35, 585), "修正后", font=font(25, True), fill=(53, 88, 120))
    for index, (name, _, dataset) in enumerate(selected):
        x = 185 + index * 350
        key = asset_keys[name]
        add_centered_text(draw, (x, 62, x + 320, 105), name, font(24, True))
        before_path = ASSETS / f"exposure_before_{key}.png"
        after_path = ASSETS / f"exposure_after_{key}.png"
        before_tile = rgba_on_background(before_path, (320, 320), background=(245, 246, 248))
        after_tile = rgba_on_background(after_path, (320, 320), background=(245, 246, 248))
        canvas.paste(before_tile, (x, 110))
        canvas.paste(after_tile, (x, 470))
        draw.rectangle((x, 110, x + 320, 430), outline=(210, 214, 219), width=2)
        draw.rectangle((x, 470, x + 320, 790), outline=(210, 214, 219), width=2)
        add_centered_text(draw, (x, 430, x + 320, 465), "曝光 0.90", font(19), fill=(172, 50, 45))
        add_centered_text(draw, (x, 790, x + 320, 825), f"曝光 {exposures[name]}", font(19), fill=(53, 88, 120))
    output = ASSETS / "exposure_before_after_gallery.png"
    canvas.save(output, quality=95)
    return output


def make_white_failure_gallery() -> Path:
    rows = [
        (
            "椅子",
            ROOT / "data" / "nerf_synthetic" / "object_002aec05" / "train" / "r_000.png",
            ROOT / "logs" / "chair_360-空白" / "testset_200000" / "000.png",
            "前景平均占比 7.2%  输出像素均值 1.000",
        ),
        (
            "篮子",
            ROOT / "data" / "nerf_synthetic" / "object_0051724d" / "train" / "r_000.png",
            ROOT / "logs" / "basket_360-空白" / "testset_200000" / "000.png",
            "前景平均占比 12.2%  输出像素均值 0.998",
        ),
    ]
    width, height = 1600, 840
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((60, 25), "前景稀疏对象的输入图像与二十万步NeRF输出", font=font(34, True), fill=(20, 25, 32))
    draw.text((385, 82), "输入训练图像", font=font(23, True), fill=(53, 88, 120))
    draw.text((1085, 82), "二十万步输出", font=font(23, True), fill=(172, 50, 45))
    for index, (name, input_path, output_path, detail) in enumerate(rows):
        y = 125 + index * 345
        draw.text((55, y + 115), name, font=font(28, True), fill=(30, 35, 42))
        input_tile = rgba_on_background(input_path, (600, 280), background=(235, 237, 240))
        if output_path.exists():
            output_tile = rgba_on_background(output_path, (600, 280), background=(235, 237, 240))
        else:
            output_tile = Image.new("RGB", (600, 280), "white")
        canvas.paste(input_tile, (180, y))
        canvas.paste(output_tile, (890, y))
        draw.rectangle((180, y, 780, y + 280), outline=(190, 195, 201), width=3)
        draw.rectangle((890, y, 1490, y + 280), outline=(190, 195, 201), width=3)
        draw.text((180, y + 292), detail, font=font(20), fill=(72, 78, 86))
    output = ASSETS / "white_collapse_gallery.png"
    canvas.save(output, quality=95)
    return output


def make_pipeline_diagram() -> Path:
    width, height = 1700, 720
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    title_font = font(36, True)
    box_font = font(27, True)
    small_font = font(20)
    draw.text((60, 30), "从GLB模型到NeRF渲染结果的完整流程", font=title_font, fill=(20, 25, 32))
    stages = [
        ("GLB模型", "统一坐标与尺度"),
        ("360多视角渲染", "144训练 24验证 40测试"),
        ("数据清洗", "曝光 RGBA 掩膜"),
        ("特征提取与匹配", "SIFT RANSAC"),
        ("增量式SfM", "三角化与Bundle Adjustment"),
        ("位姿适配", "导出transforms_sfm_train"),
        ("经典NeRF训练", "粗细网络与体渲染"),
        ("结果输出", "360视频与GIF"),
    ]
    boxes = []
    box_w, box_h = 350, 190
    xs = [70, 470, 870, 1270]
    ys = [130, 450]
    for i, (stage, detail) in enumerate(stages):
        row = 0 if i < 4 else 1
        col = i if i < 4 else 7 - i
        x, y = xs[col], ys[row]
        boxes.append((x, y, x + box_w, y + box_h))
        draw.rounded_rectangle(boxes[-1], radius=18, fill=(238, 244, 249), outline=(77, 113, 145), width=4)
        add_centered_text(draw, (x + 12, y + 30, x + box_w - 12, y + 92), stage, box_font)
        add_centered_text(draw, (x + 12, y + 100, x + box_w - 12, y + 155), detail, small_font, fill=(72, 78, 86))
    arrow_color = (56, 92, 125)
    for i in range(3):
        start = (boxes[i][2] + 8, (boxes[i][1] + boxes[i][3]) // 2)
        end = (boxes[i + 1][0] - 8, (boxes[i + 1][1] + boxes[i + 1][3]) // 2)
        draw.line((start, end), fill=arrow_color, width=6)
        draw.polygon([(end[0], end[1]), (end[0] - 18, end[1] - 11), (end[0] - 18, end[1] + 11)], fill=arrow_color)
    draw.line(((boxes[3][0] + boxes[3][2]) // 2, boxes[3][3] + 8, (boxes[4][0] + boxes[4][2]) // 2, boxes[4][1] - 8), fill=arrow_color, width=6)
    draw.polygon([((boxes[4][0] + boxes[4][2]) // 2, boxes[4][1]), ((boxes[4][0] + boxes[4][2]) // 2 - 11, boxes[4][1] - 18), ((boxes[4][0] + boxes[4][2]) // 2 + 11, boxes[4][1] - 18)], fill=arrow_color)
    for i in range(4, 7):
        start = (boxes[i][0] - 8, (boxes[i][1] + boxes[i][3]) // 2)
        end = (boxes[i + 1][2] + 8, (boxes[i + 1][1] + boxes[i + 1][3]) // 2)
        draw.line((start, end), fill=arrow_color, width=6)
        draw.polygon([(end[0], end[1]), (end[0] + 18, end[1] - 11), (end[0] + 18, end[1] + 11)], fill=arrow_color)
    output = ASSETS / "pipeline_overview.png"
    canvas.save(output, quality=95)
    return output


def make_registration_chart(stats: dict) -> Path:
    ordered = (
        [(name, dataset, "final") for name, _, dataset in GOOD]
        + [(name, dataset, "nerf_failed") for name, dataset in TRAIN_FAILED]
        + [(name, dataset, "rejected") for name, dataset in BAD]
    )
    width, height = 1500, 1220
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 25), "18个候选对象的SfM图像注册率", font=font(35, True), fill=(20, 25, 32))
    legend = [((60, 137, 106), "最终10个"), ((205, 145, 55), "NeRF全白失败"), ((191, 75, 67), "数据或SfM淘汰")]
    legend_x = 720
    for color, label in legend:
        draw.rounded_rectangle((legend_x, 38, legend_x + 38, 62), radius=5, fill=color)
        draw.text((legend_x + 48, 34), label, font=font(18, True), fill=(60, 65, 72))
        legend_x += 220
    left, right, top = 240, 1410, 140
    row_h = 56
    for tick in (0, 25, 50, 75, 90, 100):
        x = left + int((right - left) * tick / 100)
        draw.line((x, top, x, top + row_h * len(ordered)), fill=(225, 228, 232), width=2)
        draw.text((x - 18, top - 34), str(tick), font=font(18), fill=(90, 95, 102))
    threshold_x = left + int((right - left) * 0.9)
    draw.line((threshold_x, top, threshold_x, top + row_h * len(ordered)), fill=(190, 120, 35), width=4)
    draw.text((threshold_x - 95, top - 62), "90%参考线", font=font(19, True), fill=(166, 96, 24))
    for index, (name, dataset, status) in enumerate(ordered):
        y = top + index * row_h + 8
        registered = stats[dataset]["registered_images"]
        rate = registered / 144 * 100
        draw.text((70, y + 5), name, font=font(21, status == "final"), fill=(30, 35, 42))
        bar_end = left + int((right - left) * rate / 100)
        color = {"final": (60, 137, 106), "nerf_failed": (205, 145, 55), "rejected": (191, 75, 67)}[status]
        draw.rounded_rectangle((left, y, max(left + 3, bar_end), y + 32), radius=7, fill=color)
        if rate >= 90:
            draw.text((bar_end - 90, y + 3), f"{registered}/144", font=font(18, True), fill="white")
        else:
            draw.text((min(bar_end + 10, right - 90), y + 3), f"{registered}/144", font=font(18, True), fill=color)
    output = ASSETS / "registration_chart.png"
    canvas.save(output, quality=95)
    return output


def make_pairing_improvement_chart() -> Path:
    rows = [
        ("酒桶架", 91.54, 0.63),
        ("木屋", 87.15, 0.175),
        ("风车", 4.64, 1.118),
    ]
    width, height = 1500, 660
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((70, 35), "重复纹理对象采用邻域匹配前后的平均旋转误差", font=font(34, True), fill=(20, 25, 32))
    left, right, top = 260, 1380, 140
    max_value = 100.0
    for tick in range(0, 101, 20):
        x = left + int((right - left) * tick / max_value)
        draw.line((x, top, x, 575), fill=(228, 231, 234), width=2)
        draw.text((x - 14, 590), str(tick), font=font(18), fill=(80, 85, 92))
    for index, (name, before, after) in enumerate(rows):
        y = top + index * 140
        draw.text((75, y + 40), name, font=font(25, True), fill=(30, 35, 42))
        before_end = left + int((right - left) * before / max_value)
        after_end = left + max(5, int((right - left) * after / max_value))
        draw.rounded_rectangle((left, y + 10, before_end, y + 48), radius=8, fill=(203, 111, 68))
        draw.rounded_rectangle((left, y + 65, after_end, y + 103), radius=8, fill=(63, 121, 158))
        draw.text((min(before_end + 10, right - 140), y + 12), f"全连接匹配 {before:.3f}°", font=font(19, True), fill=(164, 77, 42))
        draw.text((after_end + 10, y + 67), f"邻域匹配 {after:.3f}°", font=font(19, True), fill=(43, 93, 128))
    output = ASSETS / "pairing_improvement.png"
    canvas.save(output, quality=95)
    return output


def make_render_result_gallery() -> Path:
    width, height = 1950, 1530
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((55, 20), "二十万步NeRF最终测试视角渲染结果", font=font(34, True), fill=(20, 25, 32))
    frame_indices = (0, 10, 20)
    tile_size = 245
    block_x = (50, 1000)
    tile_offsets = (0, 260, 520)
    for row in range(5):
        y = 82 + row * 286
        for column in range(2):
            index = row * 2 + column
            name, experiment, _ = GOOD[index]
            x0 = block_x[column]
            draw.text((x0, y + 92), f"对象 {index + 1}", font=font(18), fill=(90, 96, 103))
            draw.text((x0, y + 122), name, font=font(23, True), fill=(30, 35, 42))
            for offset, frame_index in zip(tile_offsets, frame_indices):
                x = x0 + 100 + offset
                add_centered_text(draw, (x, y, x + tile_size, y + 24), f"{frame_index:03d}", font(16, True), fill=(53, 88, 120))
                image_path = ROOT / "logs" / experiment / "testset_200000" / f"{frame_index:03d}.png"
                if not image_path.exists():
                    raise FileNotFoundError(f"Missing final NeRF result: {image_path}")
                tile = rgba_on_background(image_path, (tile_size, tile_size), background=(250, 250, 250))
                canvas.paste(tile, (x, y + 26))
                draw.rectangle((x, y + 26, x + tile_size, y + 26 + tile_size), outline=(208, 213, 218), width=2)
    output = ASSETS / "render_results_1_10.png"
    canvas.save(output, quality=95)
    return output


def set_cell_shading(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=110, bottom=100, end=110):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table, color="D9D9D9", size="8"):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), color)


def repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_repeat_table_widths(table, widths_cm):
    for row in table.rows:
        for cell, width in zip(row.cells, widths_cm):
            cell.width = Cm(width)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)


def style_table(table, header_fill="2F4F67", widths_cm=None, small=False):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    repeat_table_header(table.rows[0])
    for row_index, row in enumerate(table.rows):
        for cell in row.cells:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)
            if row_index == 0:
                set_cell_shading(cell, header_fill)
            elif row_index % 2 == 0:
                set_cell_shading(cell, "F3F6F8")
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.space_before = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.12
                for run in paragraph.runs:
                    set_run_font(run, "Microsoft YaHei", 8.3 if small else 9.2, bold=(row_index == 0))
                    run.font.color.rgb = RGBColor(255, 255, 255) if row_index == 0 else RGBColor(25, 29, 34)
    if widths_cm:
        set_repeat_table_widths(table, widths_cm)


def set_run_font(run, name="Microsoft YaHei", size=10.5, bold=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_char1, instr_text, fld_char2])
    set_run_font(run, size=9)


def keep_paragraph(paragraph, with_next=False):
    paragraph.paragraph_format.keep_together = True
    paragraph.paragraph_format.keep_with_next = with_next


def add_figure(doc, path: Path, caption: str, width_cm=16.0):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(5)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run()
    run.add_picture(str(path), width=Cm(width_cm))
    cap = doc.add_paragraph(caption, style="Caption")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(8)
    keep_paragraph(cap)


def add_code(doc, text: str):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.left_indent = Cm(0.65)
    paragraph.paragraph_format.right_indent = Cm(0.35)
    paragraph.paragraph_format.space_before = Pt(3)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.08
    run = paragraph.add_run(text)
    set_run_font(run, "Consolas", 8.7)
    return paragraph


def add_bullet(doc, text: str, level=0):
    paragraph = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    paragraph.add_run(text)
    return paragraph


def add_number(doc, text: str):
    paragraph = doc.add_paragraph(style="List Number")
    paragraph.add_run(text)
    return paragraph


def add_body(doc, text: str, bold_lead: str | None = None):
    paragraph = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        lead = paragraph.add_run(bold_lead)
        lead.bold = True
        paragraph.add_run(text[len(bold_lead):])
    else:
        paragraph.add_run(text)
    return paragraph


def configure_styles(doc: Document):
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(25, 29, 34)
    normal.paragraph_format.line_spacing = 1.38
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    title = styles["Title"]
    title.font.name = "Microsoft YaHei"
    title._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    title.font.size = Pt(24)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)
    title.paragraph_format.space_after = Pt(16)
    title_ppr = title._element.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)

    for style_name, size, before, after in (("Heading 1", 17, 18, 8), ("Heading 2", 13.5, 13, 6), ("Heading 3", 11.5, 9, 4)):
        style = styles[style_name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    caption = styles["Caption"]
    caption.font.name = "Microsoft YaHei"
    caption._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    caption.font.size = Pt(9)
    caption.font.italic = False
    caption.font.color.rgb = RGBColor(65, 70, 76)
    caption.paragraph_format.line_spacing = 1.12

    for list_name in ("List Bullet", "List Bullet 2", "List Number"):
        style = styles[list_name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(10.3)
        style.paragraph_format.space_after = Pt(3)


def configure_document(doc: Document):
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.25)
    section.right_margin = Cm(2.25)
    section.header_distance = Cm(1.0)
    section.footer_distance = Cm(0.9)
    header = section.header.paragraphs[0]
    header.text = "三维视觉课程作业二  NeRF重建与渲染流水线"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for run in header.runs:
        set_run_font(run, size=8.5)
        run.font.color.rgb = RGBColor(105, 110, 116)
    add_page_number(section.footer.paragraphs[0])


def add_cover(doc: Document):
    for _ in range(4):
        doc.add_paragraph()
    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("基于Python SfM与经典NeRF的\n多物体三维重建与渲染流水线")
    title_ppr = title._p.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)
    subtitle = doc.add_paragraph("三维视觉课程作业二  Pipeline Documentation")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(34)
    for run in subtitle.runs:
        set_run_font(run, size=13)
        run.font.color.rgb = RGBColor(73, 79, 86)
    info = [
        ("组号", "[请填写组号]"),
        ("组员", "[请填写成员姓名]"),
        ("课程", "三维视觉"),
        ("代码仓库", "https://github.com/your-group/nerf-3d-reconstruction"),
        ("日期", "2026年11月"),
    ]
    table = doc.add_table(rows=len(info), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table, color="FFFFFF", size="0")
    for row, (label, value) in zip(table.rows, info):
        row.cells[0].width = Cm(3.4)
        row.cells[1].width = Cm(10.5)
        row.cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
        left = row.cells[0].paragraphs[0].add_run(label + "  ")
        left.bold = True
        right = row.cells[1].paragraphs[0].add_run(value)
        for run in (left, right):
            set_run_font(run, size=11)
    doc.add_page_break()


def add_contents(doc: Document):
    doc.add_heading("目录", level=1)
    items = [
        "摘要",
        "1 作业目标与总体方案",
        "2 数据生成与清洗",
        "3 Python SfM相机位姿估计",
        "4 经典NeRF训练与渲染",
        "5 十个对象的实验结果",
        "6 主要问题与解决方法",
        "7 影响最终重建质量的因素",
        "8 项目结构与复现方法",
        "9 结论",
        "附录 A 小组成员与贡献",
        "参考文献",
    ]
    for item in items:
        p = doc.add_paragraph(item)
        p.paragraph_format.left_indent = Cm(0.4 if item[0].isdigit() else 0.0)
        p.paragraph_format.space_after = Pt(5)
    doc.add_page_break()


def build_document():
    DOCS.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    summary = json.loads((ROOT / "outputs" / "sfm" / "summary.json").read_text(encoding="utf-8"))
    stats = {dataset: summary[dataset] for dataset in summary}
    nerf_metrics = json.loads((ASSETS / "nerf_metrics.json").read_text(encoding="utf-8"))
    metrics_by_dataset = {item["dataset"]: item for item in nerf_metrics["objects"]}

    gallery = make_object_gallery()
    match_gallery = make_match_gallery()
    failures = make_failure_gallery(stats)
    exposures = make_exposure_gallery()
    white_failures = make_white_failure_gallery()
    pipeline_diagram = make_pipeline_diagram()
    registration_chart = make_registration_chart(stats)
    pairing_chart = make_pairing_improvement_chart()
    render_results = make_render_result_gallery()

    doc = Document()
    configure_styles(doc)
    configure_document(doc)
    add_cover(doc)
    add_contents(doc)

    doc.add_heading("摘要", level=1)
    add_body(doc, "本项目实现了从GLB三维模型、多视角图像生成、数据清洗、相机位姿估计到经典NeRF训练与360度新视角渲染的完整流水线。与直接使用渲染器提供的真实相机矩阵不同，我们在训练前通过Python接口完成SIFT特征提取、几何验证、增量式SfM、三角化和全局Bundle Adjustment，并将估计位姿转换为NeRF可读取的transforms_sfm_train.json。该设计使相机位姿估计成为可复现、可分析的独立步骤，满足从图像到三维重建的课程要求。")
    add_body(doc, "我们累计制作18个对象数据集，每个对象包含144张训练图像、24张验证图像和40张测试图像，共生成3744张多视角图像。6个对象因数据质量或SfM结果不合格被淘汰；椅子和篮子虽然位姿估计可用，但经典NeRF训练在白色背景和前景占比较低的共同作用下收敛到全白输出，因此也被替换。最终10个对象为盆栽、草棚推车、风车、烤鸡、红色车辆、鸭子、市场摊位、酒桶架、重制城堡和木屋。")
    add_body(doc, "针对过曝、弱纹理、重复纹理、扁平结构、前景占比不足和视角覆盖不完整等问题，我们分别采用曝光校正、透明背景掩膜、相邻转台视角匹配、相机距离调整、重新投影和数据替换策略。烤鸡与鸭子作为新数据完成了图像生成和SfM；城堡在原始NeRF结果全白后，将相机半径由4.0缩小到3.5，使训练图像的平均前景占比由13.3%提高到17.7%，并使用新的实验名重新训练，避免载入旧检查点。")
    add_body(doc, "主要结论是：最终重建质量不只取决于NeRF网络本身。数据曝光、可匹配纹理、视角之间的重叠、匹配拓扑、相机位姿精度以及训练采样参数会连续地影响后续结果。其中，重复纹理对象即使达到144/144的图像注册率，也可能产生错误的相机轨迹，因此必须同时检查位姿误差和匹配结构，不能只看注册数量。")
    add_figure(doc, pipeline_diagram, "图 1  本项目从GLB模型到NeRF视频和GIF的完整流水线", 16.2)

    doc.add_heading("1 作业目标与总体方案", level=1)
    doc.add_heading("1.1 作业要求", level=2)
    add_body(doc, "作业要求使用Assignment 1清洗后的数据，建立从图像到三维重建与渲染的完整NeRF或3D Gaussian Splatting流水线，分析流水线各步骤对最终结果的影响，并在10个不同对象上运行。每个对象需要生成一个GIF动画。提交内容包括Pipeline Documentation与GitHub代码仓库，仓库中需要包含完整代码、全部提示词、10个对象的点匹配结果和NeRF或3DGS渲染GIF，同时在文档中注明组号、成员姓名和个人贡献。")
    doc.add_heading("1.2 技术路线选择", level=2)
    add_body(doc, "重建方法选择经典NeRF的PyTorch实现。相机位姿估计没有调用独立的COLMAP可执行程序，而是使用pycolmap的Python接口完成相同的核心SfM计算，因此整套流程可以由Python脚本驱动。数据来自GLB模型的360度离屏渲染，这使我们能够在SfM完成后使用渲染器真实位姿进行误差评估，但真实位姿不会作为SfM输入。")
    add_bullet(doc, "输入：每个对象一个GLB文件。")
    add_bullet(doc, "图像：512×512 RGBA，多高度环绕视角。")
    add_bullet(doc, "位姿：SIFT + RANSAC几何验证 + 增量式SfM + Bundle Adjustment。")
    add_bullet(doc, "重建：经典NeRF粗网络与细网络，使用视角方向编码。")
    add_bullet(doc, "输出：测试视角图像、360度渲染视频、GIF动画、匹配图与统计文件。")
    doc.add_heading("1.3 实现环境", level=2)
    env_table = doc.add_table(rows=1, cols=3)
    env_table.rows[0].cells[0].text = "模块"
    env_table.rows[0].cells[1].text = "实现"
    env_table.rows[0].cells[2].text = "用途"
    for row in [
        ("数据渲染", "Three.js 0.181.1 + Playwright", "加载GLB并离屏生成RGBA多视角图像"),
        ("SfM", "pycolmap 4.2.1", "特征、匹配、几何验证、增量重建与BA"),
        ("辅助处理", "OpenCV 5.1、Pillow、NumPy", "掩膜、可视化、误差统计"),
        ("NeRF", "经典nerf-pytorch源码", "体渲染场训练与新视角合成"),
        ("训练环境", "Self-P2IR-cu124", "CUDA 12.4服务器环境"),
    ]:
        cells = env_table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = value
    style_table(env_table, widths_cm=[3.2, 5.4, 7.5])

    doc.add_heading("2 数据生成与清洗", level=1)
    doc.add_heading("2.1 GLB归一化与场景设置", level=2)
    add_body(doc, "渲染脚本首先读取GLB的包围盒，将模型中心移动到世界坐标原点，并按最大轴长度将模型缩放到统一尺度。相机采用50度水平视场角并始终朝向原点。透明背景用于分离前景模型与环境，后续可直接从Alpha通道生成SfM特征提取掩膜。模型尺寸和形状差异较大时，使用可配置camera radius调整画面占比。新增烤鸡使用3.3，鸭子和重制城堡使用3.5；城堡所有图像均保留至少21像素边距，没有发生塔尖或侧塔裁切。")
    doc.add_heading("2.2 视角采样", level=2)
    sampling = doc.add_table(rows=1, cols=4)
    for cell, value in zip(sampling.rows[0].cells, ["数据划分", "数量", "方位角", "俯仰角"]):
        cell.text = value
    for row in [
        ("Train", "144", "每15度一张，共24个方位", "-35、-20、-5、10、25、40度"),
        ("Validation", "24", "相对训练视角偏移7.5度", "在5个中间高度间交替"),
        ("Test", "40", "每9度一张并偏移4.5度", "固定30度"),
    ]:
        cells = sampling.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = value
    style_table(sampling, widths_cm=[2.7, 2.0, 5.6, 5.8])
    add_body(doc, "训练视角形成6个完整的环形轨道。与只在单一高度采样相比，多高度采样为物体顶部、底部和遮挡区域提供更多可见性，也提高了跨视角特征轨迹的长度。验证集与测试集使用与训练集错开的方位角，避免直接复用训练视角。")
    doc.add_heading("2.3 曝光与图像质量控制", level=2)
    add_body(doc, "初始渲染使用较高曝光时，风车、草棚推车和盆栽的亮部纹理出现压平，导致局部SIFT梯度减少，同时影响NeRF对颜色的拟合。我们将多数对象的曝光降低至0.65，红色车辆使用0.55，浅色城堡使用0.50；新增烤鸡和鸭子在预览后进一步降低到0.45和0.35。曝光选择以高光区域仍能看见材质细节、暗部结构不消失为准，而不是仅追求画面明亮。图2采用相同相机视角进行对比：第一行为曝光0.90的修正前图像，第二行为最终曝光参数下的图像。")
    add_figure(doc, exposures, "图 2  盆栽 草棚推车 风车与城堡的曝光修正前后对比", 16.2)
    doc.add_heading("2.4 最终10个对象", level=2)
    add_figure(doc, gallery, "图 3  最终进入SfM与NeRF训练的10个对象参考视图", 16.3)
    object_table = doc.add_table(rows=1, cols=6)
    for cell, value in zip(object_table.rows[0].cells, ["对象", "数据集", "训练配置", "曝光", "半径", "匹配方式"]):
        cell.text = value
    for name, config, dataset in GOOD:
        item = stats[dataset]
        dataset_info = json.loads((ROOT / "data" / "nerf_synthetic" / dataset / "dataset_info.json").read_text(encoding="utf-8"))
        cells = object_table.add_row().cells
        values = [
            name,
            dataset,
            f"{config}.txt",
            f'{dataset_info["exposure"]:.2f}',
            f'{dataset_info["camera_radius"]:.1f}',
            "转台邻域" if item.get("pairing") == "turntable" else "穷举",
        ]
        for cell, value in zip(cells, values):
            cell.text = value
    style_table(object_table, widths_cm=[2.1, 3.5, 3.7, 1.7, 1.5, 3.2], small=True)
    doc.add_heading("2.5 数据筛选与替换", level=2)
    add_body(doc, "18个对象均完成了统一的208张图像生成。第一轮筛选淘汰手表、甜品店、底盘、双翼飞机、花园和屋顶桁架；其原因包括注册率低、视角链断裂、结构退化或材质异常。第二轮以实际NeRF输出为依据，发现椅子和篮子从50000步到200000步始终接近纯白，因此用纹理更明显、前景占比更高的烤鸡和鸭子替换。城堡保留对象身份，但重新调整相机距离、覆盖生成数据并重新估算位姿。")

    doc.add_heading("3 Python SfM相机位姿估计", level=1)
    doc.add_heading("3.1 为什么仍然需要SfM", level=2)
    add_body(doc, "GLB渲染器可以直接输出精确相机矩阵，但若训练直接读取这些矩阵，就跳过了从图像估计相机位姿的关键环节，也无法分析特征质量和匹配策略对重建的影响。因此，真实位姿只用于SfM完成后的相似变换对齐和误差评估；特征提取、匹配、初始化和增量注册过程中不使用真实位姿。")
    doc.add_heading("3.2 Alpha掩膜与SIFT特征", level=2)
    add_body(doc, "每张训练图像的Alpha通道经过阈值化与一次3×3腐蚀，生成COLMAP格式掩膜。掩膜可以避免透明背景边界和背景区域产生无意义特征。SIFT最大特征数设为8192，peak threshold设为0.003，以增强弱纹理物体上的特征数量。相机模型设为共享内参的PINHOLE模型，初始焦距因子为1.1，内参在Bundle Adjustment中继续优化。")
    doc.add_heading("3.3 特征匹配与几何验证", level=2)
    add_body(doc, "普通对象首先采用穷举匹配。描述子匹配使用0.85的比率阈值并启用guided matching；两视图几何通过RANSAC验证，最少内点数为15，最大重投影误差为3像素。数据库同时保存原始匹配、几何内点和两视图关系，随后从内点数量较高的图像对中输出可视化结果。")
    add_body(doc, "需要特别说明的是，matches目录只导出少量高内点图像对作为人工检查示例，并不是每一张图像的位姿文件。以盆栽object_00184cc3为例，目录中虽然只有6张匹配可视化图，但SfM实际验证了10296个图像对、累计354580个几何内点，并注册了全部144张训练图像。每张图像的NeRF格式位姿保存在outputs/sfm/object_00184cc3/transforms_sfm_train.json；原始COLMAP外参可在sparse/best/text/images.txt中查看，完整匹配关系保存在database.db中。")
    add_figure(doc, match_gallery, "图 4  六个合格对象的代表性SIFT几何内点匹配结果", 16.2)
    doc.add_heading("3.4 增量式重建与Bundle Adjustment", level=2)
    add_body(doc, "增量式SfM从具有足够内点和视差的图像对初始化，逐步注册新图像、三角化三维点，并定期执行局部和全局Bundle Adjustment。初始化最少内点数设为50，最小三角化角为8度；绝对位姿估计最少内点数为20，最低内点比例为0.15。最终输出二进制与文本稀疏模型、PLY点云、相机参数和每张已注册图像的外参。")
    doc.add_heading("3.5 位姿坐标转换与误差评估", level=2)
    add_body(doc, "pycolmap输出world-to-camera变换，NeRF Blender格式需要camera-to-world矩阵，因此先求逆，再应用COLMAP与Blender相机轴方向转换。SfM只确定到一个相似变换尺度，我们使用Umeyama方法将估计相机中心对齐到渲染器真实相机中心。该对齐仅用于解决尺度、旋转和平移规范并计算误差，不参与SfM求解。导出的transforms_sfm_train.json包含已注册训练图像、估计焦距和对齐后的camera-to-world矩阵。")
    add_bullet(doc, "注册率：成功估计位姿的训练图像数除以144。")
    add_bullet(doc, "平均重投影误差：三维点投影到观测图像后的像素误差。")
    add_bullet(doc, "相机中心RMSE：相似变换对齐后估计中心与真实中心的均方根距离。")
    add_bullet(doc, "旋转误差：估计相机朝向与真实朝向之间的平均角度差。")

    doc.add_heading("4 经典NeRF训练与渲染", level=1)
    doc.add_heading("4.1 网络与体渲染", level=2)
    add_body(doc, "训练采用经典nerf-pytorch源码。NeRF使用多层感知机表示连续辐射场：空间位置经过位置编码后预测体密度与中间特征，观察方向经过方向编码后与中间特征共同预测RGB颜色。沿每条相机射线进行分层采样，通过体渲染积分得到像素颜色，并以渲染颜色与真实图像之间的均方误差优化网络。粗网络首先提供概率分布，细网络根据权重进行重要性采样，以较少采样点集中描述表面附近区域。")
    add_figure(doc, ROOT / "imgs" / "pipeline.jpg", "图 5  经典NeRF的5D输入  辐射场预测  体渲染与监督损失  图源为原始NeRF项目", 16.3)
    doc.add_heading("4.2 训练配置", level=2)
    config_table = doc.add_table(rows=1, cols=3)
    for cell, value in zip(config_table.rows[0].cells, ["参数", "取值", "说明"]):
        cell.text = value
    for row in [
        ("dataset_type", "blender", "读取RGBA图像和transforms JSON"),
        ("use_viewdirs", "True", "启用观察方向建模"),
        ("white_bkgd", "True", "透明像素与白色背景合成"),
        ("N_samples", "64", "每条射线的粗采样数"),
        ("N_importance", "128", "细网络重要性采样数"),
        ("N_rand", "1024", "每次迭代随机射线数"),
        ("precrop_iters", "500", "前500步使用中心裁剪稳定训练"),
        ("precrop_frac", "0.5", "中心裁剪比例"),
        ("lrate_decay", "500", "学习率指数衰减周期"),
        ("N_iters", "200000", "经典源码中的总训练迭代数"),
    ]:
        cells = config_table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = value
    style_table(config_table, widths_cm=[4.0, 3.0, 9.1])
    doc.add_heading("4.3 使用SfM位姿的代码修改", level=2)
    add_body(doc, "原始load_blender.py固定读取transforms_train.json。为了确保训练使用估计位姿，我们增加use_sfm_poses参数，并在run_nerf.py中增加--use_sfm_poses命令行开关。启用后训练集读取transforms_sfm_train.json，焦距使用SfM估计值，360度渲染轨道半径则由训练相机中心的中位数自动计算。验证集和测试集保留真实位姿，用于独立评价新视角渲染。")
    add_code(doc, "python run_nerf.py --config configs/plant_360.txt --use_sfm_poses")
    add_body(doc, "若不添加--use_sfm_poses，程序仍兼容原始行为并读取transforms_train.json。这一显式开关可以避免实验中混淆真实位姿与SfM位姿。")
    doc.add_heading("4.4 360度渲染与GIF", level=2)
    add_body(doc, "训练完成后使用render_only模式加载最新检查点，并沿完整环绕轨道生成40帧新视角图像和视频。当前10个对象的二十万步检查点、测试集渲染图与360度RGB视频均已同步到logs目录；文档从每个对象的最终测试集中选取三个固定视角进行对比展示。提交仓库时再将RGB视频转换为循环GIF。")
    add_code(doc, "python run_nerf.py --config configs/plant_360.txt --use_sfm_poses --render_only\nffmpeg -i <输入视频> -vf \"fps=12,scale=512:-1:flags=lanczos\" -loop 0 <输出GIF>")

    doc.add_heading("5 十个对象的实验结果", level=1)
    doc.add_heading("5.1 SfM定量结果", level=2)
    result_table = doc.add_table(rows=1, cols=8)
    headers = ["对象", "数据集", "匹配", "注册", "稀疏点", "重投影 px", "中心 RMSE", "旋转误差"]
    for cell, value in zip(result_table.rows[0].cells, headers):
        cell.text = value
    for name, _, dataset in GOOD:
        item = stats[dataset]
        pose = item["pose_metrics_after_similarity_alignment"]
        cells = result_table.add_row().cells
        values = [
            name,
            dataset.replace("object_", ""),
            "邻域" if item.get("pairing") == "turntable" else "穷举",
            f'{item["registered_images"]}/144',
            str(item["sparse_points"]),
            f'{item["mean_reprojection_error"]:.3f}',
            f'{pose["camera_center_rmse"]:.3f}',
            f'{pose["rotation_mean_error_degrees"]:.3f}°',
        ]
        for cell, value in zip(cells, values):
            cell.text = value
    style_table(result_table, widths_cm=[2.2, 2.0, 1.6, 1.7, 1.8, 2.0, 2.0, 2.0], small=True)
    add_body(doc, "最终10个对象中有8个注册了全部144张训练图像。红色车辆和鸭子分别注册140张，但缺失视角没有破坏完整环绕覆盖，平均旋转误差分别为1.395度和0.248度，因此保留。所有最终对象的平均重投影误差均低于0.9像素。木屋和新增烤鸡分别恢复12763和12110个稀疏点，说明其表面纹理提供了丰富且稳定的跨视角特征。重制城堡注册144张，平均旋转误差0.434度，相机中心RMSE为0.022。")
    doc.add_heading("5.2 NeRF定量评价指标", level=2)
    add_body(doc, "10个对象均已训练至200000步，并同步了最终40帧测试视角图像与360度渲染视频。PSNR由40帧全部像素的总体均方误差计算，SSIM为40帧RGB结构相似度的平均值；真值RGBA图像统一合成到白色背景后再与预测结果比较。PSNR越高表示像素级重建误差越小，SSIM越接近1表示结构相似度越高。LPIPS需要预训练感知网络，当前本地评估环境未包含对应模型，因此保留为待计算，后续在服务器训练环境中补充。")
    metric_table = doc.add_table(rows=1, cols=8)
    metric_headers = ["对象", "数据集", "最终迭代", "测试帧", "PSNR dB", "SSIM", "LPIPS", "结果目录"]
    for cell, value in zip(metric_table.rows[0].cells, metric_headers):
        cell.text = value
    for name, config, dataset in GOOD:
        metric = metrics_by_dataset[dataset]
        cells = metric_table.add_row().cells
        values = [
            name,
            dataset.replace("object_", ""),
            str(metric["checkpoint"]),
            str(metric["test_frames"]),
            f'{metric["psnr_db"]:.3f}',
            f'{metric["ssim"]:.4f}',
            f'{metric["lpips"]:.4f}' if metric["lpips"] is not None else "待计算",
            f"logs/{config}",
        ]
        for cell, value in zip(cells, values):
            cell.text = value
    cells = metric_table.add_row().cells
    for cell, value in zip(cells, [
        "10个对象平均",
        "—",
        "—",
        "—",
        f'{nerf_metrics["mean"]["psnr_db"]:.3f}',
        f'{nerf_metrics["mean"]["ssim"]:.4f}',
        "待计算",
        "",
    ]):
        cell.text = value
    style_table(metric_table, widths_cm=[2.3, 1.9, 1.8, 1.5, 1.8, 1.4, 1.4, 4.0], small=True)
    add_body(doc, "10个对象的平均PSNR为27.831 dB，平均SSIM为0.9309。鸭子的PSNR最高，为34.410 dB；木屋重训后的PSNR为31.605 dB、SSIM为0.9602，进一步证明其首次全白属于训练塌缩而不是数据或位姿失效。酒桶架的PSNR最低，为22.646 dB，与其重复纹理、细小桶体和侧视角投影面积较小等困难一致。")

    doc.add_heading("5.3 十个对象结果文件索引", level=2)
    add_body(doc, "表中路径均为GitHub仓库根目录下的相对路径。SfM目录包含匹配图、数据库、稀疏重建、相机位姿和statistics.json；测试图像、最终RGB视频与GIF均对应二十万步训练结果。")
    render_table = doc.add_table(rows=1, cols=5)
    for cell, value in zip(render_table.rows[0].cells, ["对象", "SfM与匹配结果", "最终测试图像", "360度RGB视频", "GIF"]):
        cell.text = value
    for name, config, dataset in GOOD:
        cells = render_table.add_row().cells
        values = [
            name,
            f"outputs/sfm/{dataset}",
            f"logs/{config}/testset_200000",
            f"logs/{config}/{config}_spiral_200000_rgb.mp4",
            f"results/gifs/{config}.gif",
        ]
        for cell, value in zip(cells, values):
            cell.text = value
    style_table(render_table, widths_cm=[1.7, 3.6, 3.4, 4.6, 2.8], small=True)
    add_body(doc, "定性检查重点包括轮廓是否稳定、细杆和叶片是否连续、镜头绕到背面时是否出现漂浮结构、颜色是否随视角异常变化，以及360度首尾帧能否平滑衔接。复杂纹理对象通常更容易恢复局部细节；细杆、薄片和透明边缘仍然是经典NeRF较困难的区域。图6从每个对象最终测试集选取第0、10和20帧，每行并列展示两个对象，共六张图像，以一致视角间隔展示二十万步后的重建结果；完整动画保存在对应实验目录的spiral RGB视频中。")
    doc.add_heading("5.4 结果图与GIF整理规范", level=2)
    add_bullet(doc, "每个对象统一选取最终测试集的第0、10和20帧，覆盖三个间隔视角，避免只展示单个有利视角。")
    add_bullet(doc, "所有结果图使用512乘512分辨率、白色背景和一致显示尺寸，便于横向比较。")
    add_bullet(doc, "最终报告保留三个固定测试视角，同时在GitHub仓库的results/gifs目录中提供由最终360度RGB视频转换得到的GIF。")
    add_bullet(doc, "除单帧清晰度外，还应检查完整动画中的首尾衔接、背面稳定性、薄结构连续性和视角相关颜色变化。")
    add_figure(doc, render_results, "图 6  十个对象在二十万步的NeRF测试视角渲染结果  每行展示两个对象", 15.7)

    doc.add_heading("6 主要问题与解决方法", level=1)
    doc.add_heading("6.1 过曝导致纹理损失", level=2)
    add_body(doc, "问题表现：最初部分物体采用较高曝光，浅色表面接近纯白，风车、草棚推车和盆栽的细节被压平。由于SIFT依赖局部梯度，过曝不仅影响视觉质量，也会减少稳定匹配点；NeRF则会把大面积饱和颜色作为监督信号，导致渲染结果缺少材质层次。")
    add_body(doc, "解决方法：在正式生成208张图像之前先渲染单张预览并检查亮部细节。多数对象使用0.65，红色车辆使用0.55，浅色城堡使用0.50，烤鸡和鸭子分别使用0.45和0.35。重新渲染后，材质纹理和边界梯度明显恢复。")
    add_body(doc, "曝光修正前后的同视角对比见图2。该对比集中放在数据生成部分展示，本节不再重复插图。")
    doc.add_heading("6.2 白色背景与前景稀疏导致训练塌缩", level=2)
    add_body(doc, "问题表现：椅子和篮子的SfM位姿分别注册144张和133张，位姿本身并不足以解释全白输出。然而，两者在50000、100000、150000和200000步的NeRF结果几乎没有变化。椅子输出像素均值为1.000且标准差为0；篮子输出均值约0.998。椅子平均只有7.2%的像素属于前景，篮子约为12.2%，而篮子主体又包含大面积浅色底面。")
    add_body(doc, "原因分析：当前经典NeRF代码在整张图像中均匀随机抽取1024条射线，并通过white_bkgd将透明像素合成为白色。大多数训练射线因此只监督白色背景。网络在训练初期将体密度压到接近零后，可以依靠白色背景获得较低损失，并可能因密度分支的ReLU进入难以恢复的空场景解。继续增加训练步数没有改善这一结果。")
    add_body(doc, "处理结果：椅子和篮子从最终10个对象中移除，用前景平均占比约21.0%的烤鸡和18.6%的鸭子替换。城堡原始训练也出现全白，因此将相机半径由4.0缩小到3.5，使平均前景占比由13.3%提高到17.7%，重新生成全部图像和SfM位姿，并改用castle_large_360实验名，避免加载旧的白色检查点。木屋首次训练同样得到全白结果，但其平均前景占比约21.4%，SfM注册率为144/144，旋转误差仅0.175度，说明数据和位姿并非主要原因。随后使用新的cottage_360_retry实验目录、禁止载入旧检查点、将raw_noise_std设为1.0并把中心裁剪训练延长至2000步，重新训练后正常收敛。这表明随机初始化、早期密度梯度和错误检查点复用也可能触发或固化空场景解。若后续必须保留稀疏前景对象，应进一步将采样器改为前景、轮廓和背景分层采样，而不能只增加迭代次数。")
    add_figure(doc, white_failures, "图 7  椅子和篮子的输入图像与二十万步全白NeRF输出", 16.0)
    doc.add_heading("6.3 注册率低与视角链断裂", level=2)
    add_body(doc, "手表、花园和底盘分别只注册52、31和85张图像，说明局部视角之间缺少足够稳定的特征链。双翼飞机在拉近相机并提高曝光后从43张提高到120张，但其机翼薄、结构重复且大量侧视角投影面积小，仍未达到最终标准。屋顶桁架只有3张图像成功注册，主要原因是结构近似平面、材质显示异常且不同方位下稳定特征不足。")
    add_figure(doc, failures, "图 8  六个因数据质量或SfM结果被淘汰的对象", 16.1)
    add_figure(doc, registration_chart, "图 9  18个候选对象的注册率与最终处理结果  注册率并非唯一筛选指标", 16.0)
    doc.add_heading("6.4 重复纹理造成错误的完整重建", level=2)
    add_body(doc, "更隐蔽的问题出现在酒桶架、木屋和风车。穷举匹配时，酒桶、屋瓦和叶片之间存在大量相似描述子，导致相隔很远甚至近似相反的视角被错误连接。酒桶架和木屋虽然都显示144/144注册成功，但平均旋转误差分别达到91.54度和87.15度，说明注册数量看似完美，实际相机轨迹已经错误。")
    add_body(doc, "解决方法：利用图像的转台采集顺序，只在同一高度环与相邻高度环的局部方位范围内建立候选图像对。该策略不使用真实相机位姿，只使用采集顺序先验，因此仍属于图像匹配流程。局部匹配避免了跨越半圈的错误闭环，同时保留足够的邻接视图重叠。酒桶架误差降至0.630度，木屋降至0.175度，风车从4.64度降至1.118度。")
    add_figure(doc, pairing_chart, "图 10  邻域匹配显著降低重复纹理对象的旋转误差", 16.0)
    doc.add_heading("6.5 数据筛选原则", level=2)
    add_body(doc, "候选数据不以数量凑满为目标。判断标准同时包含：图像覆盖是否完整、注册率是否接近完整轨道、重投影误差是否合理、相机中心是否形成连续环形、旋转误差是否较低、匹配图是否符合真实几何、前景面积是否足够，以及实际NeRF输出是否避免空场景塌缩。不合格GLB被移动到data/rejected_glb，但其图像、SfM结果和失败训练记录保留，用于分析流水线各阶段对最终结果的影响。")

    doc.add_heading("7 影响最终重建质量的因素", level=1)
    factors = [
        ("图像曝光与动态范围", "过曝会抹除局部梯度并造成颜色监督饱和；过暗则增加低对比区域。", "先做预览，按材质调节曝光，保留高光和暗部纹理。"),
        ("纹理丰富度与唯一性", "弱纹理导致特征不足，重复纹理可能产生高内点但错误的远距离匹配。", "综合检查内点空间分布、轨迹连续性和位姿误差。"),
        ("视角密度与重叠", "间隔过大会降低匹配成功率；仅单高度会遗漏顶部和遮挡区域。", "使用24方位×6高度的训练采样，并让验证测试视角错开。"),
        ("前景掩膜", "透明边缘或背景特征会形成错误三维点，并使相机估计偏向背景。", "从Alpha通道生成腐蚀后的二值掩膜。"),
        ("匹配拓扑", "穷举匹配覆盖广，但在周期性纹理上容易错误闭环。", "普通对象使用穷举；转台重复纹理对象使用局部邻域匹配。"),
        ("相机内参与BA", "焦距偏差会改变相机轨迹尺度和三角化几何。", "共享PINHOLE内参，并在全局BA中联合优化。"),
        ("位姿覆盖与误差", "缺失连续视角会使NeRF在未观测区域产生模糊或漂浮伪影。", "筛除视角链断裂对象，并使用注册率、中心RMSE和旋转误差联合验收。"),
        ("前景占比与射线抽样", "均匀抽样在前景很小时会产生大量白色背景射线，可能使密度网络收敛到空场景。", "通过缩小相机半径提高前景占比；必要时采用前景、轮廓和背景分层抽样。"),
        ("射线和层次采样", "N_samples过少会漏掉薄结构；过多会增加计算与显存。", "使用64个粗采样和128个重要性采样。"),
        ("训练分辨率与批量", "分辨率越高越能保留细节，但训练成本和显存占用上升。", "保持512×512，N_rand为1024；显存不足时优先降低N_rand或使用half_res。"),
        ("背景合成", "RGBA处理不一致会产生轮廓黑边；白色背景与稀疏前景组合还会鼓励全白解。", "统一检查Alpha边缘，同时联合控制前景占比和射线采样。"),
    ]
    factor_table = doc.add_table(rows=1, cols=3)
    for cell, value in zip(factor_table.rows[0].cells, ["因素", "影响机制", "本项目控制方法"]):
        cell.text = value
    for row in factors:
        cells = factor_table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = value
    style_table(factor_table, widths_cm=[3.2, 6.4, 6.5], small=True)
    doc.add_heading("7.1 对结果的整体理解", level=2)
    add_body(doc, "流水线中的误差会逐步传播。曝光和纹理决定可检测特征，特征匹配决定两视图几何，匹配图决定SfM相机轨迹，位姿和焦距决定NeRF射线位置，最后网络容量与采样参数决定连续辐射场能否拟合这些观测。因此，后端训练迭代更多并不能修复前端错误位姿；相反，错误位姿可能被网络吸收为模糊、重影和漂浮密度。")
    add_body(doc, "我们的实验还表明，单一指标容易误导。高注册率不能排除错误闭环，低重投影误差也可能来自内部一致但全局错误的重建。可靠验收需要同时查看匹配图、稀疏点、相机轨迹、对齐后的中心误差与旋转误差，并在最终360视频中检查几何连续性。")

    doc.add_heading("8 项目结构与复现方法", level=1)
    doc.add_heading("8.1 GitHub仓库", level=2)
    add_body(doc, "仓库链接：https://github.com/your-group/nerf-3d-reconstruction")
    add_body(doc, "提交前将占位链接替换为实际GitHub地址，并确认仓库可以访问。建议保留以下目录结构：")
    add_code(doc, "configs/                    # 10个NeRF配置\ndata/nerf_synthetic/        # 图像与transforms_sfm_train.json\noutputs/sfm/                # 匹配图、稀疏点云、位姿和statistics.json\nresults/gifs/               # 10个最终GIF\nprompts/                    # 本项目全部提示词记录\ntools/glb_dataset/          # GLB多视角渲染器\ntools/sfm_pipeline.py       # Python SfM主流程\ntools/run_sfm_all.py        # 批量SfM\nrun_nerf.py                 # 经典NeRF训练入口\nload_blender.py             # SfM位姿读取适配")
    doc.add_heading("8.2 十个训练配置", level=2)
    for _, config, _ in GOOD:
        add_bullet(doc, f"configs/{config}.txt")
    doc.add_heading("8.3 单对象复现顺序", level=2)
    add_number(doc, "将GLB放入data目录，先运行预览并确认曝光和构图。")
    add_number(doc, "生成train、val、test图像以及对应transforms JSON。")
    add_number(doc, "运行sfm_pipeline.py，检查statistics.json和matches目录。")
    add_number(doc, "确认transforms_sfm_train.json已复制到对象数据目录。")
    add_number(doc, "使用--use_sfm_poses启动经典NeRF训练。")
    add_number(doc, "训练完成后使用render_only输出视频并转换为GIF。")

    doc.add_heading("9 结论", level=1)
    add_body(doc, "本项目累计制作18个对象数据集，并从中确定10个最终对象：盆栽、草棚推车、风车、烤鸡、红色车辆、鸭子、市场摊位、酒桶架、重制城堡和木屋。相机位姿文件通过显式命令行开关进入NeRF训练，从而避免使用渲染器真实位姿。椅子和篮子的SfM虽然可用，但其NeRF输出全白，因此没有继续作为最终对象。")
    add_body(doc, "最重要的实验发现是：流水线验收不能停止在SfM阶段。数据质量与匹配策略会影响相机位姿，而前景占比、背景合成、射线采样、随机初始化与检查点载入状态还会在位姿正确时决定NeRF是否学到有效密度。过曝问题通过逐对象曝光校正解决；弱纹理和退化结构对象被淘汰；重复纹理对象通过转台邻域匹配避免错误闭环；全白训练失败则通过放大主体、重新生成数据、替换对象或在独立实验目录中重新初始化训练处理。木屋的成功重训进一步说明，首次全白不能直接等同于数据不合格。该流程同时保留成功结果和失败证据，可用于复现实验并分析各环节对最终结果的影响。")

    doc.add_heading("附录 A 小组成员与贡献", level=1)
    contribution = doc.add_table(rows=1, cols=3)
    for cell, value in zip(contribution.rows[0].cells, ["成员", "学号", "主要贡献"]):
        cell.text = value
    for row in [
        ("[成员1姓名]", "[学号]", "[例如 数据清洗与多视角渲染]"),
        ("[成员2姓名]", "[学号]", "[例如 SfM实现与位姿评估]"),
        ("[成员3姓名]", "[学号]", "[例如 NeRF训练 GIF生成与文档]"),
        ("[成员4姓名]", "[学号]", "[例如 实验评估、指标汇总与失败案例分析]"),
    ]:
        cells = contribution.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = value
    style_table(contribution, widths_cm=[4.2, 3.4, 8.7])
    add_body(doc, "组号：[请填写组号]")
    add_body(doc, "请在提交前用真实成员信息替换以上占位内容，并确保贡献描述与仓库提交记录一致。")

    doc.add_heading("参考文献", level=1)
    references = [
        "[1] Mildenhall B, Srinivasan P P, Tancik M, et al. NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis. ECCV, 2020.",
        "[2] Schönberger J L, Frahm J M. Structure-from-Motion Revisited. CVPR, 2016.",
        "[3] Schönberger J L, Zheng E, Pollefeys M, Frahm J M. Pixelwise View Selection for Unstructured Multi-View Stereo. ECCV, 2016.",
        "[4] Yen-Chen Lin. nerf-pytorch: A PyTorch implementation of NeRF. GitHub repository.",
        "[5] pycolmap. Python bindings for COLMAP. Official project documentation.",
        "[6] Three.js. JavaScript 3D rendering library and GLTFLoader documentation.",
    ]
    for reference in references:
        p = doc.add_paragraph(reference)
        p.paragraph_format.left_indent = Cm(0.55)
        p.paragraph_format.first_line_indent = Cm(-0.55)
        p.paragraph_format.space_after = Pt(4)

    # Normalize direct font formatting for all body runs and keep headings black.
    for paragraph in doc.paragraphs:
        for run in paragraph.runs:
            if run.font.name is None:
                set_run_font(run)
    doc.core_properties.title = "基于Python SfM与经典NeRF的多物体三维重建与渲染流水线"
    doc.core_properties.subject = "三维视觉课程作业二 Pipeline Documentation"
    doc.core_properties.author = "[请填写小组成员]"
    doc.core_properties.keywords = "NeRF, SfM, pycolmap, 3D reconstruction, novel view synthesis"
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build_document()

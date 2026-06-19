from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz
from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "workspace"
UPLOAD_DIR = WORKSPACE_DIR / "uploads"
EXPORT_DIR = WORKSPACE_DIR / "exports"
ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

for directory in (UPLOAD_DIR, EXPORT_DIR):
    directory.mkdir(parents=True, exist_ok=True)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024


@dataclass
class PageItem:
    id: str
    source_path: Path
    source_kind: str
    source_page: int | None
    label: str
    width: float
    height: float
    rotation: int = 0


@dataclass
class ProjectState:
    id: str
    name: str = "空白项目"
    pages: list[PageItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_export_name: str | None = None
    last_export_path: Path | None = None
    uniform_page_size: bool = False
    uniform_width: float | None = None
    uniform_height: float | None = None


PROJECTS: dict[str, ProjectState] = {}


def get_project(project_id: str | None = None) -> ProjectState:
    if project_id and project_id in PROJECTS:
        return PROJECTS[project_id]
    project = ProjectState(id=uuid.uuid4().hex)
    PROJECTS[project.id] = project
    return project


def touch_project(project: ProjectState) -> None:
    project.updated_at = datetime.now()


def safe_output_name(raw_name: str) -> str:
    name = (raw_name or "edited.pdf").strip()
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", Path(name).stem).strip(" .")
    return f"{stem or 'edited'}.pdf"


def safe_folder_name(raw_name: str) -> str:
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", Path(raw_name or "converted").stem).strip(" .")
    return stem or "converted"


def export_path_for_name(filename: str) -> Path:
    return (EXPORT_DIR / safe_output_name(filename)).resolve()


def path_is_in_exports(path: Path) -> bool:
    try:
        path.resolve().relative_to(EXPORT_DIR.resolve())
    except ValueError:
        return False
    return True


def image_for_pdf(path: Path) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(path))
    if image.mode == "RGB":
        return image

    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGB", image.size, "white")
        background.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
        image.close()
        return background

    converted = image.convert("RGB")
    image.close()
    return converted


def serialize_page(page: PageItem) -> dict[str, Any]:
    return {
        "id": page.id,
        "label": page.label,
        "sourceKind": page.source_kind,
        "width": round(page.width, 2),
        "height": round(page.height, 2),
        "rotation": page.rotation,
        "thumbnailUrl": f"/api/page/{page.id}/thumbnail",
    }


def visual_page_size(page: PageItem) -> tuple[float, float]:
    if page.rotation % 180:
        return page.height, page.width
    return page.width, page.height


def common_visual_page_size(pages: list[PageItem]) -> tuple[float, float] | None:
    if not pages:
        return None
    sizes = Counter((round(width, 2), round(height, 2)) for width, height in map(visual_page_size, pages))
    return sizes.most_common(1)[0][0]


def serialize_project(project: ProjectState) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "pageCount": len(project.pages),
        "updatedAt": project.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "lastExportName": project.last_export_name,
        "lastExportPath": str(project.last_export_path) if project.last_export_path else None,
        "uniformPageSize": project.uniform_page_size,
        "uniformWidth": round(project.uniform_width, 2) if project.uniform_width else None,
        "uniformHeight": round(project.uniform_height, 2) if project.uniform_height else None,
    }


def add_pdf_pages(project: ProjectState, path: Path, original_name: str) -> None:
    doc = fitz.open(path)
    for page_index in range(doc.page_count):
        page = doc[page_index]
        project.pages.append(
            PageItem(
                id=uuid.uuid4().hex,
                source_path=path,
                source_kind="pdf",
                source_page=page_index,
                label=f"{original_name} - 第 {page_index + 1} 页",
                width=page.rect.width,
                height=page.rect.height,
                rotation=0,
            )
        )
    doc.close()


def add_image_page(project: ProjectState, path: Path, original_name: str) -> None:
    with Image.open(path) as image:
        width, height = image.size
    project.pages.append(
        PageItem(
            id=uuid.uuid4().hex,
            source_path=path,
            source_kind="image",
            source_page=None,
            label=original_name,
            width=float(width),
            height=float(height),
            rotation=0,
        )
    )


def find_page(page_id: str) -> PageItem | None:
    for project in PROJECTS.values():
        for page in project.pages:
            if page.id == page_id:
                return page
    return None


def find_page_context(page_id: str) -> tuple[ProjectState, PageItem] | None:
    for project in PROJECTS.values():
        for page in project.pages:
            if page.id == page_id:
                return project, page
    return None


def render_page_to_pixmap(page_item: PageItem, zoom: float = 0.2) -> fitz.Pixmap:
    matrix = fitz.Matrix(zoom, zoom).prerotate(page_item.rotation)
    if page_item.source_kind == "pdf":
        doc = fitz.open(page_item.source_path)
        page = doc[page_item.source_page or 0]
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        doc.close()
        return pixmap

    image_doc = fitz.open(page_item.source_path)
    page = image_doc[0]
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image_doc.close()
    return pixmap


def render_uniform_page_to_pixmap(page_item: PageItem, width: float, height: float, zoom: float = 0.2) -> fitz.Pixmap:
    preview = fitz.open()
    insert_page_on_uniform_canvas(preview, page_item, width, height)
    pixmap = preview[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    preview.close()
    return pixmap


def insert_page(output: fitz.Document, page_item: PageItem) -> None:
    if page_item.source_kind == "pdf":
        src = fitz.open(page_item.source_path)
        page_number = page_item.source_page or 0
        output.insert_pdf(src, from_page=page_number, to_page=page_number)
        src.close()
    else:
        page = output.new_page(width=page_item.width, height=page_item.height)
        page.insert_image(page.rect, filename=page_item.source_path)

    if page_item.rotation:
        output[-1].set_rotation(page_item.rotation)


def insert_page_on_uniform_canvas(output: fitz.Document, page_item: PageItem, width: float, height: float) -> None:
    target_page = output.new_page(width=width, height=height)
    if page_item.source_kind == "pdf":
        src = fitz.open(page_item.source_path)
        target_page.show_pdf_page(
            target_page.rect,
            src,
            page_item.source_page or 0,
            keep_proportion=True,
            rotate=page_item.rotation,
        )
        src.close()
        return

    target_page.insert_image(
        target_page.rect,
        filename=page_item.source_path,
        keep_proportion=True,
        rotate=page_item.rotation,
    )


def normalize_toc_levels(entries: list[list[Any]]) -> list[list[Any]]:
    if not entries:
        return []

    base_level = entries[0][0] - 1
    normalized = []
    previous_level = 0
    for level, title, page_number in entries:
        next_level = max(1, level - base_level)
        if previous_level and next_level > previous_level + 1:
            next_level = previous_level + 1
        normalized.append([next_level, title, page_number])
        previous_level = next_level
    return normalized


def build_bookmarks(project: ProjectState) -> list[list[Any]]:
    page_map: dict[str, dict[int, int]] = {}
    source_order: list[Path] = []
    seen_sources: set[str] = set()

    for output_index, page_item in enumerate(project.pages, start=1):
        if page_item.source_kind != "pdf" or page_item.source_page is None:
            continue

        source_key = str(page_item.source_path.resolve())
        page_map.setdefault(source_key, {})
        page_map[source_key].setdefault(page_item.source_page, output_index)
        if source_key not in seen_sources:
            source_order.append(page_item.source_path)
            seen_sources.add(source_key)

    bookmarks: list[list[Any]] = []
    for source_path in source_order:
        source_key = str(source_path.resolve())
        included_pages = page_map.get(source_key, {})
        if not included_pages:
            continue

        source = fitz.open(source_path)
        source_toc = source.get_toc(simple=True)
        source.close()

        source_entries = []
        for level, title, source_page_number in source_toc:
            source_page_index = int(source_page_number) - 1
            output_page_number = included_pages.get(source_page_index)
            if output_page_number:
                source_entries.append([level, title, output_page_number])
        bookmarks.extend(normalize_toc_levels(source_entries))

    return bookmarks


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/project")
def create_project():
    project = get_project()
    return jsonify({"projectId": project.id, "pages": []})


@app.get("/api/projects")
def list_projects():
    projects = sorted(PROJECTS.values(), key=lambda item: item.updated_at, reverse=True)
    return jsonify({"projects": [serialize_project(project) for project in projects]})


@app.get("/api/project/<project_id>")
def load_project(project_id: str):
    project = get_project(project_id)
    touch_project(project)
    return jsonify(
        {
            "projectId": project.id,
            "project": serialize_project(project),
            "pages": [serialize_page(page) for page in project.pages],
        }
    )


@app.post("/api/upload")
def upload_files():
    project = get_project(request.form.get("projectId"))
    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        return jsonify({"error": "请选择 PDF 或图片文件。"}), 400

    for file_storage in uploaded_files:
        original_name = file_storage.filename or "file"
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            return jsonify({"error": f"不支持的文件类型：{original_name}"}), 400

        stored_name = f"{uuid.uuid4().hex}_{secure_filename(original_name) or 'file'}"
        stored_path = UPLOAD_DIR / stored_name
        file_storage.save(stored_path)

        if suffix == ".pdf":
            add_pdf_pages(project, stored_path, original_name)
        else:
            add_image_page(project, stored_path, original_name)

    if uploaded_files:
        project.name = uploaded_files[0].filename or project.name
    touch_project(project)
    return jsonify({"projectId": project.id, "pages": [serialize_page(page) for page in project.pages]})


@app.post("/api/reorder")
def reorder_pages():
    payload = request.get_json(force=True)
    project = get_project(payload.get("projectId"))
    ordered_ids = payload.get("pageIds", [])
    by_id = {page.id: page for page in project.pages}
    if set(ordered_ids) != set(by_id):
        return jsonify({"error": "页面顺序数据不完整，请刷新后重试。"}), 400
    project.pages = [by_id[page_id] for page_id in ordered_ids]
    touch_project(project)
    return jsonify({"pages": [serialize_page(page) for page in project.pages]})


@app.post("/api/page/<page_id>/delete")
def delete_page(page_id: str):
    payload = request.get_json(silent=True) or {}
    project = get_project(payload.get("projectId"))
    project.pages = [page for page in project.pages if page.id != page_id]
    touch_project(project)
    return jsonify({"pages": [serialize_page(page) for page in project.pages]})


@app.post("/api/page/<page_id>/rotate")
def rotate_page(page_id: str):
    payload = request.get_json(force=True)
    project = get_project(payload.get("projectId"))
    degrees = int(payload.get("degrees", 90))
    for page in project.pages:
        if page.id == page_id:
            page.rotation = (page.rotation + degrees) % 360
            break
    touch_project(project)
    return jsonify({"pages": [serialize_page(page) for page in project.pages]})


@app.post("/api/pages/rotate")
def rotate_all_pages():
    payload = request.get_json(force=True)
    project = get_project(payload.get("projectId"))
    degrees = int(payload.get("degrees", 90))
    for page in project.pages:
        page.rotation = (page.rotation + degrees) % 360
    touch_project(project)
    return jsonify({"project": serialize_project(project), "pages": [serialize_page(page) for page in project.pages]})


@app.post("/api/pages/orient")
def orient_pages():
    payload = request.get_json(force=True)
    project = get_project(payload.get("projectId"))
    orientation = payload.get("orientation")
    if orientation not in {"portrait", "landscape"}:
        return jsonify({"error": "orientation must be portrait or landscape"}), 400

    for page in project.pages:
        width, height = visual_page_size(page)
        should_rotate = (orientation == "portrait" and width > height) or (
            orientation == "landscape" and height > width
        )
        if should_rotate:
            page.rotation = (page.rotation + 90) % 360

    touch_project(project)
    return jsonify({"project": serialize_project(project), "pages": [serialize_page(page) for page in project.pages]})


@app.post("/api/pages/unify-size")
def unify_page_size():
    payload = request.get_json(force=True)
    project = get_project(payload.get("projectId"))
    target_size = common_visual_page_size(project.pages)
    if not target_size:
        return jsonify({"error": "当前没有可统一尺寸的页面。"}), 400

    project.uniform_page_size = True
    project.uniform_width, project.uniform_height = target_size
    touch_project(project)
    return jsonify({"project": serialize_project(project), "pages": [serialize_page(page) for page in project.pages]})


@app.get("/api/page/<page_id>/thumbnail")
def page_thumbnail(page_id: str):
    context = find_page_context(page_id)
    if not context:
        return jsonify({"error": "页面不存在。"}), 404
    project, page = context
    if project.uniform_page_size and project.uniform_width and project.uniform_height:
        pixmap = render_uniform_page_to_pixmap(page, project.uniform_width, project.uniform_height)
    else:
        pixmap = render_page_to_pixmap(page)
    temp_path = WORKSPACE_DIR / f"{page_id}.png"
    pixmap.save(temp_path)
    return send_file(temp_path, mimetype="image/png")


@app.post("/api/export")
def export_pdf():
    payload = request.get_json(force=True)
    project = get_project(payload.get("projectId"))
    if not project.pages:
        return jsonify({"error": "当前没有可导出的页面。"}), 400

    output_name = safe_output_name(payload.get("filename", "edited.pdf"))
    output_path = export_path_for_name(output_name)
    temp_path = EXPORT_DIR / f".{uuid.uuid4().hex}_{output_name}"

    output = fitz.open()
    uniform_width = project.uniform_width
    uniform_height = project.uniform_height
    for page in project.pages:
        if project.uniform_page_size and uniform_width and uniform_height:
            insert_page_on_uniform_canvas(output, page, uniform_width, uniform_height)
        else:
            insert_page(output, page)
    bookmarks = build_bookmarks(project)
    if bookmarks:
        output.set_toc(bookmarks)
    output.save(temp_path, garbage=4, deflate=True)
    output.close()
    shutil.move(temp_path, output_path)

    project.name = output_name
    project.last_export_name = output_name
    project.last_export_path = output_path
    touch_project(project)
    return jsonify({"downloadUrl": f"/download/{output_name}", "outputName": output_name, "path": str(output_path)})


@app.post("/api/convert-pdf-to-images")
def convert_pdf_to_images():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "请选择一个 PDF 文件。"}), 400
    if Path(uploaded_file.filename).suffix.lower() != ".pdf":
        return jsonify({"error": "只能转换 PDF 文件。"}), 400

    stored_name = f"{uuid.uuid4().hex}_{secure_filename(uploaded_file.filename) or 'source.pdf'}"
    stored_path = UPLOAD_DIR / stored_name
    uploaded_file.save(stored_path)

    folder_name = f"{safe_folder_name(uploaded_file.filename)}_images_{uuid.uuid4().hex[:8]}"
    output_folder = (EXPORT_DIR / folder_name).resolve()
    output_folder.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(stored_path)
    zoom = 200 / 72
    saved_files = []
    for page_index, page in enumerate(doc, start=1):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image_name = f"page_{page_index:03}.png"
        image_path = output_folder / image_name
        pixmap.save(image_path)
        saved_files.append(str(image_path))
    doc.close()

    return jsonify(
        {
            "count": len(saved_files),
            "folderName": folder_name,
            "folderPath": str(output_folder),
            "files": saved_files,
        }
    )


@app.post("/api/merge-images-to-pdf")
def merge_images_to_pdf():
    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        return jsonify({"error": "请选择至少一张图片。"}), 400

    output_name = safe_output_name(request.form.get("filename", "images.pdf"))
    output_path = export_path_for_name(output_name)
    temp_path = EXPORT_DIR / f".{uuid.uuid4().hex}_{output_name}"
    pdf_images: list[Image.Image] = []

    try:
        for file_storage in uploaded_files:
            if not file_storage or not file_storage.filename:
                continue
            suffix = Path(file_storage.filename).suffix.lower()
            if suffix not in ALLOWED_SUFFIXES or suffix == ".pdf":
                return jsonify({"error": "只能合并图片文件。"}), 400

            stored_name = f"{uuid.uuid4().hex}_{secure_filename(file_storage.filename) or 'image'}"
            stored_path = UPLOAD_DIR / stored_name
            file_storage.save(stored_path)
            pdf_images.append(image_for_pdf(stored_path))

        if not pdf_images:
            return jsonify({"error": "请选择至少一张图片。"}), 400

        first_image, *extra_images = pdf_images
        first_image.save(temp_path, "PDF", save_all=True, append_images=extra_images)
        shutil.move(temp_path, output_path)
    finally:
        for image in pdf_images:
            image.close()
        if temp_path.exists():
            temp_path.unlink()

    return jsonify(
        {
            "count": len(pdf_images),
            "downloadUrl": f"/download/{output_name}",
            "outputName": output_name,
            "path": str(output_path),
        }
    )


@app.get("/download/<path:filename>")
def download_file(filename: str):
    output_path = export_path_for_name(filename)
    if not output_path.exists():
        return jsonify({"error": "文件不存在。"}), 404
    return send_file(output_path, as_attachment=True, download_name=output_path.name)


@app.post("/api/open-folder")
def open_export_folder():
    payload = request.get_json(force=True)
    requested_path = payload.get("path")
    output_path = Path(requested_path).resolve() if requested_path else export_path_for_name(payload.get("filename", ""))
    if not output_path.exists():
        return jsonify({"error": "文件不存在。"}), 404
    if not output_path.is_file():
        return jsonify({"error": "只能定位到导出的 PDF 文件。"}), 400
    if not path_is_in_exports(output_path):
        return jsonify({"error": "只能打开导出目录中的文件。"}), 400

    subprocess.Popen(f'explorer.exe /n,/select,"{output_path}"')
    return jsonify({"opened": True, "path": str(output_path), "selected": True})


@app.post("/api/open-converted-folder")
def open_converted_folder():
    payload = request.get_json(force=True)
    folder_path = (EXPORT_DIR / safe_folder_name(payload.get("folderName", ""))).resolve()
    if not folder_path.exists() or not folder_path.is_dir():
        return jsonify({"error": "文件夹不存在。"}), 404
    if not path_is_in_exports(folder_path):
        return jsonify({"error": "只能打开导出目录中的文件夹。"}), 400

    subprocess.Popen(["explorer", str(folder_path)])
    return jsonify({"opened": True, "path": str(folder_path)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7865, debug=False)

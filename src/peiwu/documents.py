import csv
import io
import json
from pathlib import Path

from peiwu.workspace import WorkspaceError


MAX_UPLOAD = 4 * 1024 * 1024
MAX_TEXT = 150_000
# The CSV module's default field cap is lower than our document text cap.
# Raise it once, without temporarily changing shared state during uploads.
csv.field_size_limit(max(csv.field_size_limit(), MAX_TEXT))


def parse_document(filename: str, raw: bytes, transcript: str = ""):
    extension = Path(filename).suffix.lower()
    if not raw or len(raw) > MAX_UPLOAD:
        raise WorkspaceError("文件为空或大于 4 MiB")
    if extension in (".png", ".jpg", ".jpeg"):
        valid = raw.startswith(b"\x89PNG\r\n\x1a\n") if extension == ".png" else raw.startswith(b"\xff\xd8\xff")
        if not valid:
            raise WorkspaceError("图片格式与文件内容不符")
        media = "image/png" if extension == ".png" else "image/jpeg"
        chunks = [{"locator": "人工摘录（未核验）", "text": transcript[:MAX_TEXT]}] if transcript.strip() else []
        return media, chunks
    if extension == ".pdf":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted or len(reader.pages) > 40:
                raise WorkspaceError("PDF 需要未加密且不超过 40 页")
            chunks = []
            count = 0
            for page_number, page in enumerate(reader.pages, 1):
                content = page.extract_text() or ""
                count += len(content)
                if count > MAX_TEXT:
                    raise WorkspaceError("解析文本超过 150000 字符，请拆分文件")
                if content.strip():
                    chunks.append({"locator": f"P{page_number}", "text": content})
            return "application/pdf", chunks
        except WorkspaceError:
            raise
        except Exception as error:
            raise WorkspaceError("无法解析 PDF，请检查文件；扫描件需另提供摘录") from error
    if extension not in (".txt", ".md", ".csv", ".json", ".yaml", ".yml"):
        raise WorkspaceError("支持 TXT、Markdown、CSV、JSON、YAML、PDF、PNG 和 JPEG")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise WorkspaceError("文本文件需要 UTF-8 编码") from error
    if len(content) > MAX_TEXT:
        raise WorkspaceError("文本超过 150000 字符，请拆分文件")
    if extension == ".csv":
        try:
            rows = list(csv.reader(io.StringIO(content, newline=""), strict=True))
        except csv.Error as error:
            raise WorkspaceError("CSV 格式无效，请检查引号和记录边界") from error
        return "text/csv", [{"locator": f"R{index}", "text": json.dumps(row, ensure_ascii=False)}
                            for index, row in enumerate(rows, 1)]
    if extension == ".json":
        try:
            json.loads(content, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (ValueError, json.JSONDecodeError) as error:
            raise WorkspaceError("JSON 格式无效") from error
    return "text/plain", [{"locator": f"L{index}", "text": line}
                          for index, line in enumerate(content.splitlines(), 1) if line.strip()]

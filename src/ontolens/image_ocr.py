"""Local OCR for image evidence. Extracted text remains unreviewed."""

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock

from ontolens.documents import MAX_TEXT
from ontolens.workspace import WorkspaceError


_INFERENCE_LOCK = Lock()
MAX_PIXELS = 12_000_000


@lru_cache(maxsize=1)
def _engine():
    from rapidocr import RapidOCR
    import rapidocr

    models = Path(rapidocr.__file__).parent / "models"
    paths = {
        "Det.model_path": models / "PP-OCRv6_det_small.onnx",
        "Cls.model_path": models / "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        "Rec.model_path": models / "PP-OCRv6_rec_small.onnx",
    }
    if not all(path.is_file() for path in paths.values()):
        raise WorkspaceError("缺少 OCR 本地模型，请重新安装项目的 ocr 依赖")
    return RapidOCR(params={
        **{name: str(path) for name, path in paths.items()},
        "Global.log_level": "warning",
        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    })


def extract_image_text(raw: bytes) -> list[dict[str, str]]:
    try:
        from PIL import Image
    except ImportError as error:
        raise WorkspaceError("本机 OCR 未安装，可填写人工摘录或安装项目的 ocr 依赖") from error

    try:
        with Image.open(BytesIO(raw), formats=["PNG", "JPEG"]) as image:
            width, height = image.size
            if width * height > MAX_PIXELS:
                raise WorkspaceError("OCR 图片不能超过 1200 万像素")
            image.verify()
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise WorkspaceError("OCR 无法读取图片内容") from error

    try:
        with _INFERENCE_LOCK:
            result = _engine()(raw)
    except ImportError as error:
        raise WorkspaceError("本机 OCR 未安装，可填写人工摘录或安装项目的 ocr 依赖") from error
    except WorkspaceError:
        raise
    except Exception as error:
        raise WorkspaceError("本机 OCR 识别失败，请检查安装或改用人工摘录") from error

    if not result.txts:
        return []
    chunks = []
    total = 0
    for box, text in zip(result.boxes, result.txts, strict=True):
        text = text.strip()
        if not text:
            continue
        total += len(text)
        if total > MAX_TEXT:
            raise WorkspaceError("OCR 文本超过 150000 字符，请拆分图片")
        xs, ys = zip(*box, strict=True)
        x1, x2 = max(0, round(min(xs))), min(width, round(max(xs)))
        y1, y2 = max(0, round(min(ys))), min(height, round(max(ys)))
        locator = f"OCR{len(chunks) + 1} [{x1},{y1}–{x2},{y2}]（未核验）"
        chunks.append({"locator": locator, "text": text})
    return chunks

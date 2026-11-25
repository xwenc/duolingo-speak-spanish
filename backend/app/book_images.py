"""Portable image attachments for book JSON backups."""
import base64
import binascii
import re
from fastapi import HTTPException
from .covers import upload_directory, store_cover, MAX_BYTES

MAX_IMPORT_BYTES = 100 * 1024 * 1024
LOCAL_IMAGE = re.compile(r'/api/covers/[0-9a-f]{32}\.webp\Z')


def export_images(urls):
    images = {}
    for url in set(urls):
        if not url or not LOCAL_IMAGE.fullmatch(url):
            continue
        try:
            data = (upload_directory() / url.rsplit('/', 1)[1]).read_bytes()
        except OSError:
            raise HTTPException(409, '图片文件缺失，无法完整导出，请重新上传图片后重试')
        if len(data) > MAX_BYTES:
            raise HTTPException(413, '单张图片不能超过 5 MB')
        images[url] = base64.b64encode(data).decode('ascii')
    return images


def import_images(images, references):
    """Validate all attachments before writing; remove new files on failure."""
    decoded = {}
    for url, encoded in images.items():
        if not LOCAL_IMAGE.fullmatch(url) or url not in references:
            raise HTTPException(422, '图片附件引用无效')
        if len(encoded) > ((MAX_BYTES + 2) // 3) * 4:
            raise HTTPException(413, '单张图片不能超过 5 MB')
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(422, '图片附件不是有效的 Base64 数据')
        if len(data) > MAX_BYTES:
            raise HTTPException(413, '单张图片不能超过 5 MB')
        decoded[url] = data
    stored = {}
    try:
        for url, data in decoded.items():
            stored[url] = store_cover(data)['url']
    except Exception:
        cleanup_images(stored)
        raise
    return stored


def cleanup_images(stored):
    for url in stored.values():
        (upload_directory() / url.rsplit('/', 1)[1]).unlink(missing_ok=True)

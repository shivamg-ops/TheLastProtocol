import os
import mimetypes
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {
    'image': ['.jpg', '.jpeg', '.png', '.webp'],
    'video': ['.mp4', '.mov', '.avi'],
    'audio': ['.mp3', '.wav', '.ogg', '.m4a'],
    'document': ['.pdf', '.txt', '.doc', '.docx']
}

# Explicitly banned dangerous and executable file extensions
BANNED_EXTENSIONS = {
    '.exe', '.sh', '.bat', '.cmd', '.py', '.php', '.phtml', '.js', '.vbs',
    '.ps1', '.jar', '.apk', '.scr', '.bin', '.msi', '.cgi', '.pl'
}

ALLOWED_MIME_PREFIXES = {
    'image': ['image/jpeg', 'image/png', 'image/webp'],
    'video': ['video/mp4', 'video/quicktime', 'video/x-msvideo'],
    'audio': ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4', 'audio/x-m4a'],
    'document': ['application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
}

MAX_FILE_SIZE = 25 * 1024 * 1024 # 25 MB

def get_file_type_from_file(file) -> str:
    """
    Infers file category ('image', 'video', 'audio', 'document') based on file extension and MIME type.
    """
    ext = os.path.splitext(file.name)[1].lower() if file.name else ""
    for category, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return category
    
    # Fallback to content_type if available
    content_type = getattr(file, 'content_type', '') or mimetypes.guess_type(file.name or '')[0] or ''
    for category, prefixes in ALLOWED_MIME_PREFIXES.items():
        if any(content_type.startswith(p) for p in prefixes):
            return category

    return 'document'

def validate_evidence_file(file):
    """
    Production-grade evidence validation:
    1. Size enforcement (<= 25 MB).
    2. Banned extension prevention.
    3. Whitelist format check.
    4. Image binary / magic byte validation via Pillow (prevents polyglot/malicious payloads).
    """
    # 1. Size Validation
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(f"File size exceeds maximum permitted limit of 25 MB (provided: {round(file.size / (1024*1024), 2)} MB).")

    # 2. Extension Validation
    ext = os.path.splitext(file.name)[1].lower() if file.name else ""
    if ext in BANNED_EXTENSIONS:
        raise ValidationError(f"Unsupported file format '{ext}'. Executable or dangerous script uploads are strictly prohibited.")

    all_allowed = [item for sublist in ALLOWED_EXTENSIONS.values() for item in sublist]
    if ext not in all_allowed:
        raise ValidationError(f"Unsupported file format '{ext}'. Allowed extensions: {', '.join(all_allowed)}")

    # 3. MIME type consistency validation
    content_type = getattr(file, 'content_type', '')
    if content_type:
        inferred_category = get_file_type_from_file(file)
        expected_prefixes = ALLOWED_MIME_PREFIXES.get(inferred_category, [])
        if expected_prefixes and not any(content_type.startswith(p) for p in expected_prefixes) and content_type != 'application/octet-stream':
            raise ValidationError(f"File content type '{content_type}' does not match expected format for extension '{ext}'.")

    # 4. Deep Image Binary Header Verification
    inferred_category = get_file_type_from_file(file)
    if inferred_category == 'image':
        try:
            from PIL import Image
            # Ensure file pointer is at beginning
            if hasattr(file, 'seek') and callable(file.seek):
                file.seek(0)
            img = Image.open(file)
            img.verify()
            if hasattr(file, 'seek') and callable(file.seek):
                file.seek(0)
        except Exception:
            raise ValidationError("The uploaded image file is corrupted, unreadable, or contains invalid binary data.")



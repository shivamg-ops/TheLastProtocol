import os
import mimetypes
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {
    'image': ['.jpg', '.jpeg', '.png', '.webp'],
    'video': ['.mp4', '.mov', '.avi'],
    'audio': ['.mp3', '.wav', '.ogg', '.m4a'],
    'document': ['.pdf', '.txt', '.doc', '.docx']
}

ALLOWED_MIME_PREFIXES = {
    'image': ['image/'],
    'video': ['video/'],
    'audio': ['audio/'],
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
    # 1. Size Validation
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(f"File size exceeds maximum permitted limit of 25 MB (provided: {round(file.size / (1024*1024), 2)} MB).")

    # 2. Extension Validation
    ext = os.path.splitext(file.name)[1].lower() if file.name else ""
    all_allowed = [item for sublist in ALLOWED_EXTENSIONS.values() for item in sublist]
    if ext not in all_allowed:
        raise ValidationError(f"Unsupported file format '{ext}'. Allowed extensions: {', '.join(all_allowed)}")

    # 3. MIME type consistency validation
    content_type = getattr(file, 'content_type', '')
    if content_type:
        inferred_category = get_file_type_from_file(file)
        expected_prefixes = ALLOWED_MIME_PREFIXES.get(inferred_category, [])
        # If content_type is provided and doesn't match the general family, flag warning/error
        if expected_prefixes and not any(content_type.startswith(p) for p in expected_prefixes) and content_type != 'application/octet-stream':
            raise ValidationError(f"File content type '{content_type}' does not match expected format for extension '{ext}'.")



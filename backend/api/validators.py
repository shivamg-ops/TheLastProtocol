import os
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {
    'image': ['.jpg', '.jpeg', '.png', '.webp'],
    'video': ['.mp4', '.mov', '.avi'],
    'audio': ['.mp3', '.wav', '.ogg', '.m4a'],
    'document': ['.pdf', '.txt', '.doc', '.docx']
}

MAX_FILE_SIZE = 25 * 1024 * 1024 # 25 MB

def validate_evidence_file(file):
    # 1. Size Validation
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(f"File size exceeds maximum permitted limit of 25 MB (provided: {round(file.size / (1024*1024), 2)} MB).")

    # 2. Extension Validation
    ext = os.path.splitext(file.name)[1].lower()
    all_allowed = [item for sublist in ALLOWED_EXTENSIONS.values() for item in sublist]
    if ext not in all_allowed:
        raise ValidationError(f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(all_allowed)}")


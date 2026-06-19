import cloudinary
import cloudinary.uploader

def upload_image(image_bytes: bytes, job_id: str, label: str) -> str:
    """Upload to Cloudinary, return public URL."""
    result = cloudinary.uploader.upload(
        image_bytes,
        folder=f"karigar/{job_id}",
        public_id=label
    )
    return result['secure_url']
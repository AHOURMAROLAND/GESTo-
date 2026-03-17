from PIL import Image
import os


def compresser_image(image_field, max_width=800, qualite=85):
    """
    Compresse une image uploadée.
    A appeler dans le save() des modèles avec ImageField.
    """
    if not image_field:
        return

    try:
        img = Image.open(image_field.path)

        # Convertir en RGB si nécessaire (PNG avec transparence)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Redimensionner si trop grand
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize(
                (max_width, new_height),
                Image.LANCZOS
            )

        # Sauvegarder compressé
        img.save(image_field.path, optimize=True, quality=qualite)

    except Exception as e:
        print(f"[COMPRESS] Erreur compression image : {e}")


def compresser_image_upload(image_file, max_width=800, qualite=85):
    """
    Compresse une image avant sauvegarde (dans une vue).
    Retourne l'image compressée.
    """
    import io
    from django.core.files.uploadedfile import InMemoryUploadedFile
    import sys

    try:
        img = Image.open(image_file)

        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize(
                (max_width, new_height),
                Image.LANCZOS
            )

        output = io.BytesIO()
        img.save(output, format='JPEG', optimize=True, quality=qualite)
        output.seek(0)

        return InMemoryUploadedFile(
            output,
            'ImageField',
            f"{image_file.name.split('.')[0]}.jpg",
            'image/jpeg',
            sys.getsizeof(output),
            None
        )
    except Exception:
        return image_file

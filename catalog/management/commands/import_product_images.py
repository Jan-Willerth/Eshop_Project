import os
from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = "Bulk assigns existing images to products by their slug."

    def add_arguments(self, parser):
        parser.add_argument(
            'images_dir',
            type=str,
            help='Path to the image folder'
        )

    def handle(self, *args, **options):
        images_dir = options['images_dir']

        if not os.path.exists(images_dir):
            self.stdout.write(self.style.ERROR(f"Folder '{images_dir}' not exists."))
            return

        valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
        count_success = 0
        count_not_found = 0

        for filename in os.listdir(images_dir):
            if not filename.lower().endswith(valid_extensions):
                continue

            slug, _ = os.path.splitext(filename)

            try:
                product = Product.objects.get(slug=slug)

                product.image = f"products/{filename}"
                product.save()

                self.stdout.write(self.style.SUCCESS(f"Image assigned to product: {slug}"))
                count_success += 1

            except Product.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Product with slug '{slug}' not found."))
                count_not_found += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in {filename}: {e}"))

        self.stdout.write("---")
        self.stdout.write(self.style.SUCCESS(f"Done! Assigned: {count_success}, Found: {count_not_found}"))
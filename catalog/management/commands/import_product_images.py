import os
from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = "Hromadně přiřadí existující obrázky k produktům podle jejich slugu."

    def add_arguments(self, parser):
        parser.add_argument(
            'images_dir',
            type=str,
            help='Cesta ke složce s obrázky'
        )

    def handle(self, *args, **options):
        images_dir = options['images_dir']

        if not os.path.exists(images_dir):
            self.stdout.write(self.style.ERROR(f"Složka '{images_dir}' neexistuje."))
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

                self.stdout.write(self.style.SUCCESS(f"Přiřazen obrázek k produktu: {slug}"))
                count_success += 1

            except Product.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Produkt se slugem '{slug}' nebyl nalezen."))
                count_not_found += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Chyba u {filename}: {e}"))

        self.stdout.write("---")
        self.stdout.write(self.style.SUCCESS(f"Hotovo! Přiřazeno: {count_success}, Nenalezeno: {count_not_found}"))
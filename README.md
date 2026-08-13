3D Print E-shop 🛒

A fully functional e-shop focused on selling 3D printing filaments and accessories, created
as part of web development studies. The project is built on the Django framework and tailored for local development
using MySQL and production deployment on PythonAnywhere (SQLite).


🚀 Key Features

  • Product Catalog: Clear display of products divided into categories (PLA, PETG, ABS, etc.)
    with detailed information and prices with/without VAT.
  • Shopping Cart: Dynamic management of items in the cart with a quantity counter.
  • User System: Registration, login, profile management, and order history.
  • Responsive Design: Optimized layout for both desktop computers and mobile devices.
  • Smart Database Management: Automatic switching between local MySQL and server-side SQLite
    depending on the environment.
  • Test Fixtures: Included JSON data files for quick database seeding (category.json, product.json,
    paymentmethod.json, shippingmethod.json, vatrate.json).
  • Custom Management Commands: Includes a specialized script (import_product_images.py) to automate product image
    imports and linking.


🛠️ Technologies Used

  • Backend: Python, Django
  • Database: MySQL (locally), SQLite (PythonAnywhere)
  • Frontend: HTML5, CSS3 (flexbox, grid, media queries)
  • Hosting / Deploy: PythonAnywhere, GitHub (Git version control)


⚙️ Installation and Setup (Local Development)

If you want to run the project locally on your computer, follow these steps:

1. Clone the repository:
   git clone https://github.com/Jan-Willerth/Eshop_Project.git
   cd Eshop_Project

2. Create and activate a virtual environment:
   python -m venv .venv
# On Windows:
    .venv\Scripts\activate
# On macOS/Linux:
    source .venv/bin/activate

3. Install dependencies:
   pip install -r requirements.txt

4. Configure the database:
   - Make sure you have a local MySQL database running (e.g., in XAMPP or Laragon) and a database created with the name eshop_db.
   - In the settings.py file, the login credentials are set to default local values (root without a password).

5. Run migrations, load test data, and start the local server:
   python manage.py makemigrations
   python manage.py migrate
   python manage.py loaddata catalog/fixtures/*.json
   python manage.py runserver

6. Open your browser and go to http://127.0.0.1:8000/.


🌐 Live Demo

The project is deployed and running on PythonAnywhere:
janwillerth.pythonanywhere.com

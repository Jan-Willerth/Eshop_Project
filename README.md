# 3D Print E-shop 🛒

A fully functional e-shop focused on selling 3D printing filaments and accessories, created as part of web development studies. The project is built on the Django framework and tailored for local development using MySQL and production deployment on PythonAnywhere (SQLite).

## 🚀 Key Features

- **Product Catalog:** Clear display of products divided into categories (PLA, PETG, ABS, etc.) with detailed information and prices with/without VAT.
- **Shopping Cart:** Dynamic management of items in the cart with a quantity counter.
- **User System:** Registration, login, profile management, and order history.
- **Responsive Design:** Optimized layout for both desktop computers and mobile devices.
- **Smart Database Management:** Automatic switching between local MySQL and server-side SQLite depending on the environment.
- **Test Fixtures:** Included JSON data files for quick database seeding (`category.json`, `product.json`, `paymentmethod.json`, `shippingmethod.json`, `vatrate.json`).
- **Custom Management Commands:** Includes a specialized script (`import_product_images.py`) to automate product image imports and linking.
- **Automated Tests:** 75 tests covering the cart, checkout, accounts and staff product management.
- **Docker Support:** The app can be built and run in a container.

## 📊 Database ER Diagram

The following entity-relationship diagram illustrates the database architecture, including models for products, categories, orders, items, users, and shipping/payment methods:

![ER Diagram](./assets/er_diagram.png)

## 🛠️ Technologies Used

- **Backend:** Python, Django
- **Database:** MySQL (locally), SQLite (PythonAnywhere)
- **Frontend:** HTML5, CSS3 (flexbox, grid, media queries), JavaScript
- **Containerization:** Docker, Docker Compose
- **Hosting / Deploy:** PythonAnywhere, GitHub (Git version control)

## ⚙️ Installation and Setup (Local Development)

1. Clone the repository:

   ```bash
   git clone https://github.com/Jan-Willerth/Eshop_Project.git
   cd Eshop_Project
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure the environment:
   - Copy `.env.example` to `.env` and fill in your values.
   - Make sure a local MySQL database named `eshop_db` is running (e.g. in XAMPP or Laragon).

5. Run migrations, load test data and start the server:

   ```bash
   python manage.py migrate
   python manage.py loaddata catalog/fixtures/*.json
   python manage.py runserver
   ```

6. Open http://127.0.0.1:8000/ in your browser.

## 🧪 Running Tests

```bash
python manage.py test catalog
```

## 🐳 Running with Docker

The app can run in a container. The container connects to the MySQL database running on your host machine.

1. Copy `.env.example` to `.env.prod` and fill in your values. Set `DB_HOST=host.docker.internal` so the container can reach MySQL on your computer.
2. If your `SECRET_KEY` contains a `$` character, write it as `$$` in `.env.prod`, otherwise Docker Compose treats it as a variable.
3. Build and start the container:

   ```bash
   docker compose up --build
   ```

4. Open http://127.0.0.1:8000/ in your browser.

`.env`, `.env.prod` and the local database are excluded from the image via `.dockerignore`.

## 🌐 Live Demo

The project is deployed and running on PythonAnywhere:
[janwillerth.pythonanywhere.com](https://janwillerth.pythonanywhere.com)

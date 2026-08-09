### Inventory Management System

### A Python-based inventory management application with a Flask web interface, CLI, and PostgreSQL database.

### Features:
View all products
Search products
Add new products
Update existing products
Delete products
View brands
Product and brand pagination
Product selection by brand
PostgreSQL database integration
CLI and Flask web interface

### Technologies:
Python 3
Flask
PostgreSQL
psycopg
Jinja2
python-dotenv

### Installation

### Clone the repository:
git clone https://github.com/wladimirkarpicki/inventory-management-system.git
cd inventory-management-system

### Install dependencies:
pip install -r requirements.txt

### Configure the PostgreSQL database in .env:
DATABASE_HOST=localhost
DATABASE_NAME=your_database
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password

### Run

### CLI:
python main.py

### Web application:
python app.py

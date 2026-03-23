# Intelligent Test Data Generator

An intelligent Python tool that connects to your database, analyzes its schema and data distribution, and generates realistic test data that respects foreign key relationships and mimics your actual data patterns.

## Features

- **Database Connection**: Supports PostgreSQL, MySQL, and SQL Server databases
- **Schema Discovery**: Automatically analyzes table structures, columns, and relationships
- **Relationship Analysis**: Identifies primary keys and foreign key dependencies
- **Statistics Collection**: Gathers data distribution information including:
  - Cardinality estimates (distinct value counts)
  - NULL value ratios
  - Min/Max/Average values for numeric columns
  - Sample values from existing data
- **Intelligent Data Generation**: Creates test data that:
  - Respects parent/child relationships (foreign keys)
  - Follows proper insertion order (topological sort)
  - Mimics actual data distribution patterns
  - Maintains referential integrity
- **Multiple Export Formats**: Export as SQL INSERT statements or JSON

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Test-Data-Generator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

For PostgreSQL:
```bash
pip install psycopg2-binary
```

For MySQL:
```bash
pip install mysql-connector-python
```

For SQL Server:
```bash
pip install pyodbc
```

Note: SQL Server also requires the [ODBC Driver 17 for SQL Server](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) to be installed on your system.

## Usage

### Basic Usage

**PostgreSQL:**
```bash
python test_data_generator.py \
  --db-type postgresql \
  --connection "postgresql://user:password@localhost:5432/mydb" \
  --num-rows 100 \
  --output-sql test_data.sql
```

**MySQL:**
```bash
python test_data_generator.py \
  --db-type mysql \
  --connection "mysql://user:password@localhost:3306/mydb" \
  --num-rows 50 \
  --output-json test_data.json
```

**SQL Server:**
```bash
python test_data_generator.py \
  --db-type sqlserver \
  --connection "mssql://user:password@localhost:1433/mydb" \
  --num-rows 100 \
  --output-sql test_data.sql
```

Alternatively, you can use a full ODBC connection string for SQL Server:
```bash
python test_data_generator.py \
  --db-type sqlserver \
  --connection "Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=mydb;UID=user;PWD=password" \
  --num-rows 100 \
  --output-sql test_data.sql
```

### Command Line Arguments

- `--db-type`: Database type (`postgresql`, `postgres`, `mysql`, `sqlserver`, or `mssql`) - **Required**
- `--connection`: Database connection string - **Required**
- `--num-rows`: Number of rows to generate per table (default: 100)
- `--output-sql`: Path to output SQL file
- `--output-json`: Path to output JSON file
- `--schema-only`: Only analyze and display schema without generating data

### Examples

**1. Analyze schema only (no data generation):**
```bash
python test_data_generator.py \
  --db-type postgresql \
  --connection "postgresql://user:pass@localhost/mydb" \
  --schema-only
```

**2. Generate data with both SQL and JSON output:**
```bash
python test_data_generator.py \
  --db-type postgresql \
  --connection "postgresql://user:pass@localhost/mydb" \
  --num-rows 200 \
  --output-sql output/inserts.sql \
  --output-json output/data.json
```

**3. Generate large dataset:**
```bash
python test_data_generator.py \
  --db-type postgresql \
  --connection "postgresql://user:pass@localhost/mydb" \
  --num-rows 10000 \
  --output-sql large_dataset.sql
```

## How It Works

### 1. Database Connection
The tool connects to your target database using the provided connection string. It supports PostgreSQL natively, with extensible architecture for other databases.

### 2. Schema Analysis
- Queries `information_schema` tables to discover all tables, columns, and data types
- Identifies primary keys and foreign key relationships
- Builds a dependency graph of table relationships

### 3. Statistics Collection
For each column, the tool collects:
- **Distinct Count**: Number of unique values
- **NULL Ratio**: Percentage of NULL values
- **Value Ranges**: Min/Max for numeric and date columns
- **Sample Values**: Most common values in the column
- **Row Count**: Total number of rows per table

### 4. Dependency Ordering
Uses topological sort to determine the correct insertion order:
- Tables with no foreign keys are populated first (e.g., lookup tables)
- Child tables are populated after their parent tables
- Detects and reports circular dependencies

### 5. Data Generation
For each table (in dependency order):
- **Primary Keys**: Auto-incremented integers or UUIDs
- **Foreign Keys**: Randomly selected from parent table's generated primary keys
- **Regular Columns**: Generated based on:
  - Data type (integer, string, date, boolean, etc.)
  - Statistics (respecting min/max ranges, NULL ratios)
  - Sample values (reusing actual patterns when available)

### 6. Export
Generated data can be exported as:
- **SQL**: INSERT statements ready to execute
- **JSON**: Structured data for programmatic use

## Architecture

The tool is organized into several key classes:

- **DatabaseConnector**: Abstract base class for database connections
  - `PostgreSQLConnector`: PostgreSQL implementation
  - `MySQLConnector`: MySQL implementation (extensible)
  - `SQLServerConnector`: SQL Server implementation
- **SchemaAnalyzer**: Analyzes database schema and relationships
- **TestDataGenerator**: Generates test data based on schema and statistics

## Configuration

You can create a `config.json` file based on `config.example.json`:

```json
{
  "database": {
    "type": "postgresql",
    "connection_string": "postgresql://user:pass@localhost:5432/dbname"
  },
  "generation": {
    "num_rows_per_table": 100
  },
  "output": {
    "sql_file": "output/test_data.sql",
    "json_file": "output/test_data.json"
  }
}
```

## Example Output

### Schema Analysis:
```
=== Analyzing Database Schema ===
Found 5 tables
Analyzing table: users
Analyzing table: orders
Analyzing table: products
Analyzing table: order_items
Analyzing table: categories

Table dependency order: categories -> products -> users -> orders -> order_items

=== Database Schema Summary ===

Table: categories
  Rows: 1500
  Primary Keys: id
  Columns: 3
    - id (integer) NOT NULL
    - name (character varying) NOT NULL
    - description (text) NULL

Table: products
  Rows: 5000
  Primary Keys: id
  Foreign Keys:
    - category_id -> categories.id
  Columns: 5
    - id (integer) NOT NULL
    - name (character varying) NOT NULL
    - price (numeric) NOT NULL
    - category_id (integer) NOT NULL
    - created_at (timestamp) NOT NULL
```

### Generated SQL:
```sql
-- Generated Test Data
-- Generated at: 2026-03-23 10:30:45

-- Table: categories
INSERT INTO categories (id, name, description) VALUES (1, 'Electronics', 'Electronic devices');
INSERT INTO categories (id, name, description) VALUES (2, 'Books', 'Books and magazines');

-- Table: products
INSERT INTO products (id, name, price, category_id, created_at) VALUES (1, 'Laptop', 999.99, 1, '2024-05-15 10:30:00');
INSERT INTO products (id, name, price, category_id, created_at) VALUES (2, 'Mouse', 29.99, 1, '2024-06-20 14:45:00');
```

## Extending the Tool

### Adding a New Database Connector

Create a new class that inherits from `DatabaseConnector`:

```python
class MyDBConnector(DatabaseConnector):
    def connect(self):
        # Implementation
        pass
    
    def get_tables(self) -> List[str]:
        # Implementation
        pass
    
    def get_table_schema(self, table_name: str) -> TableInfo:
        # Implementation
        pass
    
    def get_table_statistics(self, table_name: str) -> TableStats:
        # Implementation
        pass
```

Then register it in the `create_connector` factory function.

## Limitations

- Composite primary keys are partially supported (uses first key for FK references)
- Circular foreign key dependencies are not fully supported
- Some complex data types may fall back to generic generation
- MySQL support is currently limited (schema discovery needs completion)

## Contributing

Contributions are welcome! Areas for improvement:
- Complete MySQL connector implementation
- Add support for more databases (SQLite, Oracle)
- Enhanced data generation patterns
- Support for complex constraints (CHECK, UNIQUE)
- Performance optimizations for large schemas

## License

MIT License - see LICENSE file for details

## Troubleshooting

**Connection errors:**
- Verify your connection string format
- Ensure the database server is running and accessible
- Check firewall and network settings

**Missing dependencies:**
- Install the appropriate database driver: `psycopg2-binary`, `mysql-connector-python`, or `pyodbc`

**Memory issues with large datasets:**
- Reduce `--num-rows` parameter
- Generate data in batches for very large tables

## Support

For issues, questions, or contributions, please open an issue on the GitHub repository.


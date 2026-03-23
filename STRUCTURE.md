# Intelligent Test Data Generator - Project Structure

## Project Files

```
Test-Data-Generator/
├── test_data_generator.py   # Main script with all functionality
├── example_usage.py          # Examples of programmatic usage
├── requirements.txt          # Python dependencies
├── config.example.json       # Example configuration file
├── README.md                 # Complete documentation
└── output/                   # Generated output files (created at runtime)
    ├── test_data.sql        # SQL INSERT statements
    └── test_data.json       # JSON formatted data
```

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run with PostgreSQL:
   ```bash
   python test_data_generator.py \
     --db-type postgresql \
     --connection "postgresql://user:pass@localhost:5432/db" \
     --num-rows 100 \
     --output-sql output/data.sql
   ```

3. Check the README.md for detailed documentation

## Core Components

### 1. DatabaseConnector (Abstract Base Class)
- Defines interface for database operations
- Implementations: PostgreSQLConnector, MySQLConnector

### 2. SchemaAnalyzer
- Discovers tables, columns, and relationships
- Calculates dependency order (topological sort)
- Collects statistical information

### 3. TestDataGenerator
- Generates test data based on schema and statistics
- Respects foreign key relationships
- Exports to SQL and JSON formats

## Key Features Implemented

✅ Connect to PostgreSQL databases
✅ Analyze database schema automatically
✅ Discover table relationships (FK/PK)
✅ Collect data statistics (cardinality, distribution)
✅ Generate test data respecting relationships
✅ Maintain referential integrity
✅ Export to SQL INSERT statements
✅ Export to JSON format
✅ Command-line interface
✅ Extensible architecture for new databases

## Usage Patterns

### Pattern 1: CLI Usage
Best for quick data generation tasks:
```bash
python test_data_generator.py --db-type postgresql --connection "..." --num-rows 100 --output-sql data.sql
```

### Pattern 2: Programmatic Usage
Best for integration with other tools (see example_usage.py):
```python
from test_data_generator import create_connector, SchemaAnalyzer, TestDataGenerator

connector = create_connector('postgresql', connection_string)
connector.connect()
analyzer = SchemaAnalyzer(connector)
analyzer.analyze()
generator = TestDataGenerator(analyzer)
generator.generate(num_rows_per_table=100)
generator.export_to_sql("output.sql")
```

### Pattern 3: Schema Analysis Only
Best for understanding database structure:
```bash
python test_data_generator.py --db-type postgresql --connection "..." --schema-only
```

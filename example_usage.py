#!/usr/bin/env python3
"""
Example usage of the Test Data Generator as a library
"""

from test_data_generator import (
    create_connector,
    SchemaAnalyzer,
    TestDataGenerator
)


def example_postgresql():
    """Example: Generate test data from PostgreSQL database"""
    
    # 1. Create database connector
    connection_string = "postgresql://user:password@localhost:5432/mydb"
    connector = create_connector('postgresql', connection_string)
    
    try:
        # 2. Connect to database
        connector.connect()
        print("Connected to database")
        
        # 3. Analyze schema
        analyzer = SchemaAnalyzer(connector)
        analyzer.analyze()
        
        # 4. Print schema summary
        analyzer.print_schema_summary()
        
        # 5. Generate test data
        generator = TestDataGenerator(analyzer)
        generator.generate(num_rows_per_table=100)
        
        # 6. Export to files
        generator.export_to_sql("output/test_data.sql")
        generator.export_to_json("output/test_data.json")
        
        print("\nTest data generation complete!")
        
        # 7. Access generated data programmatically
        for table_name, rows in generator.generated_data.items():
            print(f"\n{table_name}: {len(rows)} rows generated")
            if rows:
                print(f"  Sample row: {rows[0]}")
        
    finally:
        # 8. Cleanup
        connector.disconnect()


def example_sqlserver():
    """Example: Generate test data from SQL Server database"""
    
    # 1. Create database connector
    # Option 1: Simple connection string
    connection_string = "mssql://user:password@localhost:1433/mydb"
    
    # Option 2: Full ODBC connection string (more flexible)
    # connection_string = "Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=mydb;UID=user;PWD=password"
    
    connector = create_connector('sqlserver', connection_string)
    
    try:
        # 2. Connect to database
        connector.connect()
        print("Connected to SQL Server database")
        
        # 3. Analyze schema
        analyzer = SchemaAnalyzer(connector)
        analyzer.analyze()
        
        # 4. Print schema summary
        analyzer.print_schema_summary()
        
        # 5. Generate test data
        generator = TestDataGenerator(analyzer)
        generator.generate(num_rows_per_table=100)
        
        # 6. Export to files
        generator.export_to_sql("output/sqlserver_test_data.sql")
        generator.export_to_json("output/sqlserver_test_data.json")
        
        print("\nTest data generation complete!")
        
        # 7. Access generated data programmatically
        for table_name, rows in generator.generated_data.items():
            print(f"\n{table_name}: {len(rows)} rows generated")
            if rows:
                print(f"  Sample row: {rows[0]}")
        
    finally:
        # 8. Cleanup
        connector.disconnect()


def example_schema_only():
    """Example: Only analyze schema without generating data"""
    
    connection_string = "postgresql://user:password@localhost:5432/mydb"
    connector = create_connector('postgresql', connection_string)
    
    try:
        connector.connect()
        
        # Analyze schema only
        analyzer = SchemaAnalyzer(connector)
        analyzer.analyze()
        analyzer.print_schema_summary()
        
        # Access schema information programmatically
        for table_name, table_info in analyzer.tables.items():
            print(f"\nTable: {table_name}")
            print(f"  Primary Keys: {table_info.primary_keys}")
            print(f"  Foreign Keys: {len(table_info.foreign_keys)}")
            print(f"  Row Count: {table_info.stats.row_count if table_info.stats else 'N/A'}")
            
            # Access column statistics
            if table_info.stats:
                for col_name, col_stats in table_info.stats.column_stats.items():
                    distinct = col_stats.get('distinct_count', 0)
                    print(f"    {col_name}: {distinct} distinct values")
        
    finally:
        connector.disconnect()


def example_custom_generation():
    """Example: Generate data with custom logic"""
    
    connection_string = "postgresql://user:password@localhost:5432/mydb"
    connector = create_connector('postgresql', connection_string)
    
    try:
        connector.connect()
        
        analyzer = SchemaAnalyzer(connector)
        analyzer.analyze()
        
        generator = TestDataGenerator(analyzer)
        
        # Generate different amounts of data per table based on relationships
        # Parent tables get more rows than child tables
        for table_name in analyzer.dependency_order:
            table_info = analyzer.tables[table_name]
            
            # Generate more rows for tables without foreign keys (parent tables)
            if not table_info.foreign_keys:
                num_rows = 1000  # Parent tables
            else:
                num_rows = 100   # Child tables
            
            print(f"Generating {num_rows} rows for {table_name}")
            # Generate for this specific table
            # Note: This is a simplified example - actual implementation would need
            # to call internal methods properly
        
        generator.export_to_sql("output/custom_data.sql")
        
    finally:
        connector.disconnect()


def example_save_and_load_schema():
    """Example: Save schema analysis and reuse for multiple data generation runs"""
    
    # Step 1: Analyze database once and save schema
    print("=== Step 1: Analyzing and Saving Schema ===")
    connection_string = "postgresql://user:password@localhost:5432/mydb"
    connector = create_connector('postgresql', connection_string)
    
    try:
        connector.connect()
        
        analyzer = SchemaAnalyzer(connector)
        analyzer.analyze()
        analyzer.print_schema_summary()
        
        # Save the schema to a file
        analyzer.save_to_file("schema_cache.json")
        
        connector.disconnect()
    except Exception as e:
        print(f"Error during schema analysis: {e}")
        return
    
    # Step 2: Load schema from file and generate data (can be run multiple times)
    print("\n=== Step 2: Loading Schema and Generating Data ===")
    
    # Create analyzer without database connection
    analyzer = SchemaAnalyzer()
    analyzer.load_from_file("schema_cache.json")
    
    # Generate test data using the loaded schema
    generator = TestDataGenerator(analyzer)
    generator.generate(num_rows_per_table=500)
    
    # Export to different formats
    generator.export_to_sql("output/test_data_run1.sql")
    generator.export_to_json("output/test_data_run1.json")
    
    print("\n=== Benefits ===")
    print("- No need to reconnect to database")
    print("- Faster data generation for multiple runs")
    print("- Can generate data offline")
    print("- Can share schema files across team")


if __name__ == '__main__':
    print("Test Data Generator - Library Usage Examples\n")
    print("=" * 60)
    
    # Uncomment the example you want to run:
    
    # Example 1: Full data generation (PostgreSQL)
    # example_postgresql()
    
    # Example 2: Full data generation (SQL Server)
    # example_sqlserver()
    
    # Example 3: Schema analysis only
    # example_schema_only()
    
    # Example 4: Custom generation logic
    # example_custom_generation()
    
    # Example 5: Save schema and reuse for data generation
    # example_save_and_load_schema()
    
    print("\nNote: Update connection strings before running examples")

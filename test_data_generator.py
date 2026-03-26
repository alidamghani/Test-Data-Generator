#!/usr/bin/env python3
"""
Intelligent Test Data Generator

This script connects to a database, analyzes its schema and statistics,
and generates test data that respects foreign key relationships and
mimics the data distribution of the source database.
"""

import sys
import argparse
import json
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import random
from datetime import datetime, timedelta, date


@dataclass
class ColumnInfo:
    """Information about a database column"""
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_table: Optional[str] = None
    foreign_key_column: Optional[str] = None
    max_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None


@dataclass
class TableStats:
    """Statistical information about a table"""
    table_name: str
    row_count: int
    column_stats: Dict[str, Dict[str, Any]]


@dataclass
class TableInfo:
    """Complete information about a table"""
    name: str
    columns: List[ColumnInfo]
    primary_keys: List[str]
    foreign_keys: List[Dict[str, str]]
    stats: Optional[TableStats] = None


class DatabaseConnector:
    """Base class for database connections"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None
        
    def connect(self):
        """Establish database connection"""
        raise NotImplementedError("Subclasses must implement connect()")
    
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """Execute a query and return results"""
        raise NotImplementedError("Subclasses must implement execute_query()")
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        raise NotImplementedError("Subclasses must implement get_tables()")
    
    def get_table_schema(self, table_name: str) -> TableInfo:
        """Get schema information for a specific table"""
        raise NotImplementedError("Subclasses must implement get_table_schema()")
    
    def get_table_statistics(self, table_name: str) -> TableStats:
        """Get statistical information about a table"""
        raise NotImplementedError("Subclasses must implement get_table_statistics()")


class PostgreSQLConnector(DatabaseConnector):
    """PostgreSQL-specific database connector"""
    
    def connect(self):
        """Establish PostgreSQL connection"""
        try:
            import psycopg2
            self.connection = psycopg2.connect(self.connection_string)
            print(f"Connected to PostgreSQL database")
        except ImportError:
            raise ImportError("psycopg2 is required for PostgreSQL connections. Install with: pip install psycopg2-binary")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {e}")
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """Execute a query and return results"""
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        return results
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        results = self.execute_query(query)
        return [row[0] for row in results]
    
    def get_table_schema(self, table_name: str) -> TableInfo:
        """Get schema information for a specific table"""
        # Get column information
        column_query = """
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key,
                CASE WHEN fk.column_name IS NOT NULL THEN true ELSE false END as is_foreign_key,
                fk.foreign_table_name,
                fk.foreign_column_name
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku 
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_name = %s
            ) pk ON c.column_name = pk.column_name
            LEFT JOIN (
                SELECT 
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_name = %s
            ) fk ON c.column_name = fk.column_name
            WHERE c.table_name = %s
            ORDER BY c.ordinal_position
        """
        
        results = self.execute_query(column_query, (table_name, table_name, table_name))
        
        columns = []
        primary_keys = []
        foreign_keys = []
        
        for row in results:
            col_info = ColumnInfo(
                name=row[0],
                data_type=row[1],
                is_nullable=(row[2] == 'YES'),
                max_length=row[3],
                numeric_precision=row[4],
                numeric_scale=row[5],
                is_primary_key=row[6],
                is_foreign_key=row[7],
                foreign_key_table=row[8],
                foreign_key_column=row[9]
            )
            columns.append(col_info)
            
            if col_info.is_primary_key:
                primary_keys.append(col_info.name)
            
            if col_info.is_foreign_key:
                foreign_keys.append({
                    'column': col_info.name,
                    'references_table': col_info.foreign_key_table,
                    'references_column': col_info.foreign_key_column
                })
        
        return TableInfo(
            name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys
        )
    
    def _get_indexed_columns(self, table_name: str) -> set:
        """Get list of columns that are part of any index"""
        query = """
            SELECT DISTINCT a.attname as column_name
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            JOIN pg_class t ON t.oid = i.indrelid
            WHERE t.relname = %s
            AND t.relkind = 'r'
        """
        results = self.execute_query(query, (table_name,))
        return {row[0] for row in results}
    
    def get_table_statistics(self, table_name: str) -> TableStats:
        """Get statistical information about a table (only for indexed columns)"""
        # Get row count
        count_query = f'SELECT COUNT(*) FROM "{table_name}"'
        row_count = self.execute_query(count_query)[0][0]
        
        # Get indexed columns
        indexed_columns = self._get_indexed_columns(table_name)
        print(f"  Collecting statistics for {len(indexed_columns)} indexed columns")
        
        # Get column statistics
        table_info = self.get_table_schema(table_name)
        column_stats = {}
        
        for column in table_info.columns:
            # Only collect statistics for indexed columns
            if column.name not in indexed_columns:
                continue
            
            stats = {
                'distinct_count': 0,
                'null_count': 0,
                'min_value': None,
                'max_value': None,
                'avg_value': None,
                'sample_values': []
            }
            
            try:
                # Get distinct count and null count
                stats_query = f"""
                    SELECT 
                        COUNT(DISTINCT "{column.name}") as distinct_count,
                        COUNT(*) - COUNT("{column.name}") as null_count
                    FROM "{table_name}"
                """
                result = self.execute_query(stats_query)[0]
                stats['distinct_count'] = result[0]
                stats['null_count'] = result[1]
                
                # Get min/max/avg for numeric and date types
                if column.data_type in ['integer', 'bigint', 'smallint', 'numeric', 'real', 'double precision', 'decimal']:
                    minmax_query = f"""
                        SELECT MIN("{column.name}"), MAX("{column.name}"), AVG("{column.name}")
                        FROM "{table_name}"
                        WHERE "{column.name}" IS NOT NULL
                    """
                    result = self.execute_query(minmax_query)[0]
                    stats['min_value'] = float(result[0]) if result[0] is not None else None
                    stats['max_value'] = float(result[1]) if result[1] is not None else None
                    stats['avg_value'] = float(result[2]) if result[2] is not None else None
                
                elif column.data_type in ['date', 'timestamp', 'timestamp without time zone', 'timestamp with time zone']:
                    minmax_query = f"""
                        SELECT MIN("{column.name}"), MAX("{column.name}")
                        FROM "{table_name}"
                        WHERE "{column.name}" IS NOT NULL
                    """
                    result = self.execute_query(minmax_query)[0]
                    stats['min_value'] = str(result[0]) if result[0] is not None else None
                    stats['max_value'] = str(result[1]) if result[1] is not None else None
                
                # Get sample values (top 10 most common)
                sample_query = f"""
                    SELECT "{column.name}", COUNT(*) as cnt
                    FROM "{table_name}"
                    WHERE "{column.name}" IS NOT NULL
                    GROUP BY "{column.name}"
                    ORDER BY cnt DESC
                    LIMIT 10
                """
                results = self.execute_query(sample_query)
                stats['sample_values'] = [str(row[0]) for row in results]
                
            except Exception as e:
                print(f"Warning: Could not get statistics for column {column.name}: {e}")
            
            column_stats[column.name] = stats
        
        return TableStats(
            table_name=table_name,
            row_count=row_count,
            column_stats=column_stats
        )


class MySQLConnector(DatabaseConnector):
    """MySQL-specific database connector"""
    
    def connect(self):
        """Establish MySQL connection"""
        try:
            import mysql.connector
            # Parse connection string (format: mysql://user:password@host:port/database)
            parts = self.connection_string.replace('mysql://', '').split('@')
            user_pass = parts[0].split(':')
            host_db = parts[1].split('/')
            host_port = host_db[0].split(':')
            
            self.connection = mysql.connector.connect(
                host=host_port[0],
                port=int(host_port[1]) if len(host_port) > 1 else 3306,
                user=user_pass[0],
                password=user_pass[1] if len(user_pass) > 1 else '',
                database=host_db[1] if len(host_db) > 1 else ''
            )
            print(f"Connected to MySQL database")
        except ImportError:
            raise ImportError("mysql-connector-python is required for MySQL connections. Install with: pip install mysql-connector-python")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MySQL: {e}")
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """Execute a query and return results"""
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        return results
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        query = "SHOW TABLES"
        results = self.execute_query(query)
        return [row[0] for row in results]
    
    def get_table_schema(self, table_name: str) -> TableInfo:
        """Get schema information for a specific table"""
        # This is a simplified implementation
        # Full implementation would query INFORMATION_SCHEMA
        raise NotImplementedError("MySQL schema discovery not yet fully implemented")
    
    def get_table_statistics(self, table_name: str) -> TableStats:
        """Get statistical information about a table"""
        raise NotImplementedError("MySQL statistics collection not yet fully implemented")


class SQLServerConnector(DatabaseConnector):
    """SQL Server-specific database connector"""
    
    def connect(self):
        """Establish SQL Server connection"""
        try:
            import pyodbc
            # Parse connection string (format: mssql://user:password@host:port/database or full connection string)
            if 'Driver=' in self.connection_string or 'DRIVER=' in self.connection_string:
                # print out the connection details
                print(f"Connecting to SQL Server with connection string: {self.connection_string}")
                # Full ODBC connection string
                self.connection = pyodbc.connect(self.connection_string)
            else:
                # Parse simplified connection string (format: mssql://user:password@host:port/database)
                parts = self.connection_string.replace('mssql://', '').replace('sqlserver://', '').split('@')
                user_pass = parts[0].split(':')
                host_db = parts[1].split('/')
                host_port = host_db[0].split(':')
                
                conn_str = (
                    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                    f"SERVER={host_port[0]}"
                    f"{','+host_port[1] if len(host_port) > 1 else ''};"
                    f"DATABASE={host_db[1] if len(host_db) > 1 else ''};"
                    f"UID={user_pass[0]};"
                    f"PWD={user_pass[1] if len(user_pass) > 1 else ''}"
                )
                # print out the connection details
                print(f"Connecting to SQL Server with connection string: {conn_str}")
                self.connection = pyodbc.connect(conn_str)
            print(f"Connected to SQL Server database")
        except ImportError:
            raise ImportError("pyodbc is required for SQL Server connections. Install with: pip install pyodbc")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to SQL Server: {e}")
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """Execute a query and return results"""
        cursor = self.connection.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        return results
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        query = """
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            AND TABLE_SCHEMA = 'dbo'
            ORDER BY TABLE_NAME
        """
        results = self.execute_query(query)
        return [row[0] for row in results]
    
    def get_table_schema(self, table_name: str) -> TableInfo:
        """Get schema information for a specific table"""
        # Get column information
        column_query = """
            SELECT 
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.IS_NULLABLE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.NUMERIC_PRECISION,
                c.NUMERIC_SCALE,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as IS_PRIMARY_KEY,
                CASE WHEN fk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as IS_FOREIGN_KEY,
                fk.REFERENCED_TABLE_NAME,
                fk.REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku 
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                    AND tc.TABLE_NAME = ?
            ) pk ON c.COLUMN_NAME = pk.COLUMN_NAME
            LEFT JOIN (
                SELECT 
                    kcu.COLUMN_NAME,
                    OBJECT_NAME(fk.referenced_object_id) AS REFERENCED_TABLE_NAME,
                    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS REFERENCED_COLUMN_NAME
                FROM sys.foreign_keys fk
                JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu 
                    ON fk.name = kcu.CONSTRAINT_NAME 
                    AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = kcu.COLUMN_NAME
                WHERE OBJECT_NAME(fk.parent_object_id) = ?
            ) fk ON c.COLUMN_NAME = fk.COLUMN_NAME
            WHERE c.TABLE_NAME = ?
            ORDER BY c.ORDINAL_POSITION
        """
        
        results = self.execute_query(column_query, (table_name, table_name, table_name))
        
        columns = []
        primary_keys = []
        foreign_keys = []
        
        for row in results:
            col_info = ColumnInfo(
                name=row[0],
                data_type=row[1],
                is_nullable=(row[2] == 'YES'),
                max_length=row[3],
                numeric_precision=row[4],
                numeric_scale=row[5],
                is_primary_key=bool(row[6]),
                is_foreign_key=bool(row[7]),
                foreign_key_table=row[8],
                foreign_key_column=row[9]
            )
            columns.append(col_info)
            
            if col_info.is_primary_key:
                primary_keys.append(col_info.name)
            
            if col_info.is_foreign_key:
                foreign_keys.append({
                    'column': col_info.name,
                    'references_table': col_info.foreign_key_table,
                    'references_column': col_info.foreign_key_column
                })
        
        return TableInfo(
            name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys
        )
    
    def _get_indexed_columns(self, table_name: str) -> set:
        """Get list of columns that are part of any index"""
        query = """
            SELECT DISTINCT c.name as column_name
            FROM sys.indexes i
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            JOIN sys.tables t ON i.object_id = t.object_id
            WHERE t.name = ?
        """
        results = self.execute_query(query, (table_name,))
        return {row[0] for row in results}
    
    def get_table_statistics(self, table_name: str) -> TableStats:
        """Get statistical information about a table (only for indexed columns)"""
        # Get row count
        count_query = f"SELECT COUNT(*) FROM [{table_name}]"
        row_count = self.execute_query(count_query)[0][0]
        
        # Get indexed columns
        indexed_columns = self._get_indexed_columns(table_name)
        print(f"  Collecting statistics for {len(indexed_columns)} indexed columns")
        
        # Get column statistics
        table_info = self.get_table_schema(table_name)
        column_stats = {}
        
        for column in table_info.columns:
            # Only collect statistics for indexed columns
            if column.name not in indexed_columns:
                continue
            
            stats = {
                'distinct_count': 0,
                'null_count': 0,
                'min_value': None,
                'max_value': None,
                'avg_value': None,
                'sample_values': []
            }
            
            try:
                # Get distinct count and null count
                stats_query = f"""
                    SELECT 
                        COUNT(DISTINCT [{column.name}]) as distinct_count,
                        COUNT(*) - COUNT([{column.name}]) as null_count
                    FROM [{table_name}]
                """
                result = self.execute_query(stats_query)[0]
                stats['distinct_count'] = result[0]
                stats['null_count'] = result[1]
                
                # Get min/max/avg for numeric and date types
                if column.data_type in ['int', 'bigint', 'smallint', 'tinyint', 'numeric', 'decimal', 'float', 'real', 'money', 'smallmoney']:
                    minmax_query = f"""
                        SELECT MIN([{column.name}]), MAX([{column.name}]), AVG(CAST([{column.name}] AS FLOAT))
                        FROM [{table_name}]
                        WHERE [{column.name}] IS NOT NULL
                    """
                    result = self.execute_query(minmax_query)[0]
                    stats['min_value'] = float(result[0]) if result[0] is not None else None
                    stats['max_value'] = float(result[1]) if result[1] is not None else None
                    stats['avg_value'] = float(result[2]) if result[2] is not None else None
                
                elif column.data_type in ['date', 'datetime', 'datetime2', 'smalldatetime', 'datetimeoffset']:
                    minmax_query = f"""
                        SELECT MIN([{column.name}]), MAX([{column.name}])
                        FROM [{table_name}]
                        WHERE [{column.name}] IS NOT NULL
                    """
                    result = self.execute_query(minmax_query)[0]
                    stats['min_value'] = str(result[0]) if result[0] is not None else None
                    stats['max_value'] = str(result[1]) if result[1] is not None else None
                
                # Get sample values (top 10 most common)
                sample_query = f"""
                    SELECT TOP 10 [{column.name}], COUNT(*) as cnt
                    FROM [{table_name}]
                    WHERE [{column.name}] IS NOT NULL
                    GROUP BY [{column.name}]
                    ORDER BY cnt DESC
                """
                results = self.execute_query(sample_query)
                stats['sample_values'] = [str(row[0]) for row in results]
                
            except Exception as e:
                print(f"Warning: Could not get statistics for column {column.name}: {e}")
            
            column_stats[column.name] = stats
        
        return TableStats(
            table_name=table_name,
            row_count=row_count,
            column_stats=column_stats
        )


class SchemaAnalyzer:
    """Analyzes database schema and relationships"""
    
    def __init__(self, connector: Optional[DatabaseConnector] = None):
        self.connector = connector
        self.tables: Dict[str, TableInfo] = {}
        self.dependency_order: List[str] = []
    
    def analyze(self):
        """Analyze the entire database schema"""
        print("\n=== Analyzing Database Schema ===")
        
        # Get all tables
        table_names = self.connector.get_tables()
        print(f"Found {len(table_names)} tables")
        
        # Get schema for each table
        for table_name in table_names:
            print(f"Analyzing table: {table_name}")
            table_info = self.connector.get_table_schema(table_name)
            table_info.stats = self.connector.get_table_statistics(table_name)
            self.tables[table_name] = table_info
        
        # Determine dependency order (tables with no foreign keys first)
        self.dependency_order = self._calculate_dependency_order()
        print(f"\nTable dependency order: {' -> '.join(self.dependency_order)}")
    
    def _calculate_dependency_order(self) -> List[str]:
        """Calculate the order in which tables should be populated based on foreign key dependencies"""
        # Build dependency graph
        dependencies = defaultdict(set)
        for table_name, table_info in self.tables.items():
            for fk in table_info.foreign_keys:
                dependencies[table_name].add(fk['references_table'])
        
        # Topological sort
        order = []
        visited = set()
        temp_visited = set()
        
        def visit(table: str):
            if table in temp_visited:
                raise ValueError(f"Circular dependency detected involving table: {table}")
            if table in visited:
                return
            
            temp_visited.add(table)
            for dependency in dependencies.get(table, set()):
                visit(dependency)
            temp_visited.remove(table)
            visited.add(table)
            order.append(table)
        
        for table in self.tables.keys():
            if table not in visited:
                visit(table)
        
        return order
    
    def print_schema_summary(self):
        """Print a summary of the database schema"""
        print("\n=== Database Schema Summary ===")
        for table_name in self.dependency_order:
            table = self.tables[table_name]
            print(f"\nTable: {table.name}")
            print(f"  Rows: {table.stats.row_count if table.stats else 'N/A'}")
            print(f"  Primary Keys: {', '.join(table.primary_keys)}")
            if table.foreign_keys:
                print(f"  Foreign Keys:")
                for fk in table.foreign_keys:
                    print(f"    - {fk['column']} -> {fk['references_table']}.{fk['references_column']}")
            print(f"  Columns: {len(table.columns)}")
            for col in table.columns:
                nullable = "NULL" if col.is_nullable else "NOT NULL"
                print(f"    - {col.name} ({col.data_type}) {nullable}")
    
    def save_to_file(self, output_file: str):
        """Save schema and statistics to a JSON file"""
        print(f"\n=== Saving Schema to: {output_file} ===")
        
        schema_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_tables': len(self.tables)
            },
            'dependency_order': self.dependency_order,
            'tables': {}
        }
        
        # Convert tables to dictionary format
        for table_name, table_info in self.tables.items():
            table_dict = {
                'name': table_info.name,
                'primary_keys': table_info.primary_keys,
                'foreign_keys': table_info.foreign_keys,
                'columns': [],
                'stats': None
            }
            
            # Convert columns
            for col in table_info.columns:
                col_dict = asdict(col)
                table_dict['columns'].append(col_dict)
            
            # Convert stats
            if table_info.stats:
                table_dict['stats'] = {
                    'table_name': table_info.stats.table_name,
                    'row_count': table_info.stats.row_count,
                    'column_stats': table_info.stats.column_stats
                }
            
            schema_data['tables'][table_name] = table_dict
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(schema_data, f, indent=2)
        
        print(f"Schema saved successfully: {output_file}")
    
    def load_from_file(self, input_file: str):
        """Load schema and statistics from a JSON file"""
        print(f"\n=== Loading Schema from: {input_file} ===")
        
        with open(input_file, 'r') as f:
            schema_data = json.load(f)
        
        # Load dependency order
        self.dependency_order = schema_data['dependency_order']
        
        # Load tables
        self.tables = {}
        for table_name, table_dict in schema_data['tables'].items():
            # Reconstruct columns
            columns = []
            for col_dict in table_dict['columns']:
                col = ColumnInfo(**col_dict)
                columns.append(col)
            
            # Reconstruct stats
            stats = None
            if table_dict['stats']:
                stats = TableStats(
                    table_name=table_dict['stats']['table_name'],
                    row_count=table_dict['stats']['row_count'],
                    column_stats=table_dict['stats']['column_stats']
                )
            
            # Create TableInfo
            table_info = TableInfo(
                name=table_dict['name'],
                columns=columns,
                primary_keys=table_dict['primary_keys'],
                foreign_keys=table_dict['foreign_keys'],
                stats=stats
            )
            
            self.tables[table_name] = table_info
        
        print(f"Loaded {len(self.tables)} tables from {input_file}")
        print(f"Table dependency order: {' -> '.join(self.dependency_order)}")


class TestDataGenerator:
    """Generates test data based on schema and statistics"""
    
    def __init__(self, schema_analyzer: SchemaAnalyzer):
        self.schema_analyzer = schema_analyzer
        self.generated_data: Dict[str, List[Dict[str, Any]]] = {}
        self.primary_key_values: Dict[str, List[Any]] = {}
    
    def generate(self, num_rows_per_table: int = 100):
        """Generate test data for all tables"""
        print(f"\n=== Generating Test Data ({num_rows_per_table} rows per table) ===")
        
        for table_name in self.schema_analyzer.dependency_order:
            print(f"Generating data for table: {table_name}")
            table_info = self.schema_analyzer.tables[table_name]
            
            rows = []
            for i in range(num_rows_per_table):
                row = self._generate_row(table_info, i)
                rows.append(row)
            
            self.generated_data[table_name] = rows
            
            # Store primary key values for foreign key references
            if table_info.primary_keys:
                pk = table_info.primary_keys[0]  # Use first PK if composite
                self.primary_key_values[table_name] = [row[pk] for row in rows]
            
            print(f"  Generated {len(rows)} rows")
    
    def _generate_row(self, table_info: TableInfo, row_index: int) -> Dict[str, Any]:
        """Generate a single row of test data"""
        row = {}
        
        for column in table_info.columns:
            # Handle foreign keys
            if column.is_foreign_key:
                row[column.name] = self._generate_foreign_key_value(column)
            # Handle primary keys
            elif column.is_primary_key:
                row[column.name] = self._generate_primary_key_value(column, row_index)
            # Handle regular columns
            else:
                row[column.name] = self._generate_column_value(column, table_info.stats)
        
        return row
    
    def _generate_primary_key_value(self, column: ColumnInfo, row_index: int) -> Any:
        """Generate a primary key value"""
        if column.data_type in ['integer', 'bigint', 'smallint', 'int', 'serial', 'bigserial']:
            return row_index + 1
        elif column.data_type in ['uuid']:
            import uuid
            return str(uuid.uuid4())
        else:
            return f"pk_{row_index + 1}"
    
    def _generate_foreign_key_value(self, column: ColumnInfo) -> Any:
        """Generate a foreign key value that references an existing primary key"""
        ref_table = column.foreign_key_table
        
        if ref_table in self.primary_key_values and self.primary_key_values[ref_table]:
            # Randomly select from available primary keys
            return random.choice(self.primary_key_values[ref_table])
        else:
            # If no values available yet, use NULL if allowed
            if column.is_nullable:
                return None
            else:
                return 1  # Default fallback
    
    def _generate_column_value(self, column: ColumnInfo, stats: Optional[TableStats]) -> Any:
        """Generate a value for a regular column based on statistics"""
        # Handle NULL values based on statistics
        if column.is_nullable and stats:
            col_stats = stats.column_stats.get(column.name, {})
            null_ratio = col_stats.get('null_count', 0) / max(stats.row_count, 1)
            if random.random() < null_ratio:
                return None
        
        # Get column statistics if available
        col_stats = stats.column_stats.get(column.name, {}) if stats else {}
        
        # Use sample values if available
        if col_stats.get('sample_values'):
            return random.choice(col_stats['sample_values'])
        
        # Generate based on data type
        return self._generate_value_by_type(column, col_stats)
    
    def _generate_value_by_type(self, column: ColumnInfo, col_stats: Dict[str, Any]) -> Any:
        """Generate a value based on column data type"""
        data_type = column.data_type.lower()
        
        # Integer types (PostgreSQL, MySQL, SQL Server)
        if data_type in ['integer', 'int', 'smallint', 'bigint', 'tinyint', 'serial', 'bigserial']:
            # Get min/max from stats or use type-specific defaults
            min_val = col_stats.get('min_value')
            max_val = col_stats.get('max_value')
            
            # Set type-specific limits if stats are not available
            if data_type == 'tinyint':
                # SQL Server tinyint: 0 to 255
                default_min, default_max = 0, 255
            elif data_type == 'smallint':
                # SQL Server smallint: -32768 to 32767
                default_min, default_max = -32768, 32767
            elif data_type == 'bigint':
                # Large range for bigint
                default_min, default_max = 1, 1000000
            else:
                # Default for int/integer
                default_min, default_max = 1, 1000
            
            # Use stats if available, otherwise use defaults
            min_val = int(min_val) if min_val is not None else default_min
            max_val = int(max_val) if max_val is not None else default_max
            
            # Ensure min/max are within type limits
            if data_type == 'tinyint':
                min_val = max(0, min(min_val, 255))
                max_val = max(0, min(max_val, 255))
            elif data_type == 'smallint':
                min_val = max(-32768, min(min_val, 32767))
                max_val = max(-32768, min(max_val, 32767))
            
            # Ensure min <= max
            if min_val > max_val:
                min_val, max_val = max_val, min_val
            
            return random.randint(min_val, max_val)
        
        # Floating point types (PostgreSQL, MySQL, SQL Server)
        elif data_type in ['numeric', 'decimal', 'real', 'double precision', 'float', 'double', 'money', 'smallmoney']:
            min_val = float(col_stats.get('min_value') or 0.0)
            max_val = float(col_stats.get('max_value') or 1000.0)
            value = random.uniform(min_val, max_val)
            if column.numeric_scale:
                return round(value, column.numeric_scale)
            return value
        
        # String types (PostgreSQL, MySQL, SQL Server)
        elif data_type in ['character varying', 'varchar', 'character', 'char', 'text', 'nvarchar', 'nchar', 'ntext']:
            # Handle SQL Server varchar(max) which has max_length = -1
            max_length = column.max_length
            if max_length is None or max_length <= 0:
                max_length = 50
            length = min(max_length, 50)
            return self._generate_random_string(length)
        
        # Boolean (PostgreSQL, MySQL, SQL Server)
        elif data_type in ['boolean', 'bool', 'bit']:
            return random.choice([True, False])
        
        # Date types (PostgreSQL, MySQL, SQL Server)
        elif data_type in ['date']:
            min_date = datetime.now() - timedelta(days=365*5)
            max_date = datetime.now()
            random_date = min_date + timedelta(days=random.randint(0, 365*5))
            return random_date.date()
        
        # Timestamp/DateTime types (PostgreSQL, MySQL, SQL Server)
        elif data_type in ['timestamp', 'timestamp without time zone', 'timestamp with time zone', 'datetime', 'datetime2', 'smalldatetime', 'datetimeoffset']:
            min_date = datetime.now() - timedelta(days=365*5)
            max_date = datetime.now()
            random_timestamp = min_date + timedelta(seconds=random.randint(0, int((max_date - min_date).total_seconds())))
            return random_timestamp
        
        # GUID/UUID types (PostgreSQL, SQL Server)
        elif data_type in ['uuid', 'uniqueidentifier']:
            import uuid
            return str(uuid.uuid4())
        
        # Default fallback
        else:
            return f"test_value_{random.randint(1, 1000)}"
    
    def _generate_random_string(self, length: int) -> str:
        """Generate a random string"""
        import string
        words = ['test', 'data', 'sample', 'value', 'example', 'demo', 'item', 'record']
        result = random.choice(words)
        
        # Add random alphanumeric if needed
        if length > len(result):
            chars = string.ascii_letters + string.digits
            result += ''.join(random.choices(chars, k=min(length - len(result), 10)))
        
        return result[:length]
    
    def export_to_sql(self, output_file: str):
        """Export generated data as SQL INSERT statements"""
        print(f"\n=== Exporting to SQL: {output_file} ===")
        
        with open(output_file, 'w') as f:
            f.write("-- Generated Test Data\n")
            f.write(f"-- Generated at: {datetime.now()}\n\n")
            
            for table_name in self.schema_analyzer.dependency_order:
                rows = self.generated_data[table_name]
                if not rows:
                    continue
                
                f.write(f"\n-- Table: {table_name}\n")
                
                for row in rows:
                    columns = list(row.keys())
                    values = []
                    
                    for col in columns:
                        val = row[col]
                        if val is None:
                            values.append('NULL')
                        elif isinstance(val, str):
                            escaped_val = val.replace("'", "''")
                            values.append(f"'{escaped_val}'")
                        elif isinstance(val, bool):
                            values.append('TRUE' if val else 'FALSE')
                        elif isinstance(val, datetime):
                            # Format datetime with milliseconds (3 digits) instead of microseconds (6 digits)
                            # This is compatible with SQL Server datetime2(3)
                            dt_str = val.strftime('%Y-%m-%dT%H:%M:%S')
                            # Add milliseconds (3 digits)
                            milliseconds = val.microsecond // 1000
                            dt_str += f'.{milliseconds:03d}'
                            values.append(f"'{dt_str}'")
                        elif isinstance(val, date):
                            # Handle date without time component
                            values.append(f"'{val.isoformat()}'")
                        else:
                            values.append(str(val))
                    
                    # Quote table and column names for SQL compatibility
                    quoted_columns = [f'"{col}"' for col in columns]
                    f.write(f'INSERT INTO "{table_name}" ({", ".join(quoted_columns)}) VALUES ({", ".join(values)});\n')
        
        print(f"SQL export completed: {output_file}")
    
    def export_to_json(self, output_file: str):
        """Export generated data as JSON"""
        print(f"\n=== Exporting to JSON: {output_file} ===")
        
        # Convert datetime objects to strings for JSON serialization
        json_data = {}
        for table_name, rows in self.generated_data.items():
            json_rows = []
            for row in rows:
                json_row = {}
                for key, value in row.items():
                    if isinstance(value, (datetime,)):
                        json_row[key] = value.isoformat()
                    else:
                        json_row[key] = value
                json_rows.append(json_row)
            json_data[table_name] = json_rows
        
        with open(output_file, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        print(f"JSON export completed: {output_file}")


def create_connector(db_type: str, connection_string: str) -> DatabaseConnector:
    """Factory function to create the appropriate database connector"""
    connectors = {
        'postgresql': PostgreSQLConnector,
        'postgres': PostgreSQLConnector,
        'mysql': MySQLConnector,
        'sqlserver': SQLServerConnector,
        'mssql': SQLServerConnector,
    }
    
    connector_class = connectors.get(db_type.lower())
    if not connector_class:
        raise ValueError(f"Unsupported database type: {db_type}. Supported types: {list(connectors.keys())}")
    
    return connector_class(connection_string)


def main():
    parser = argparse.ArgumentParser(
        description='Intelligent Test Data Generator - Generate test data based on database schema and statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze database and save schema
  python test_data_generator.py --db-type postgresql \\
    --connection "postgresql://user:password@localhost:5432/mydb" \\
    --save-schema schema.json

  # Generate data from saved schema
  python test_data_generator.py --load-schema schema.json \\
    --num-rows 100 --output-sql test_data.sql

  # Single-step: analyze and generate
  python test_data_generator.py --db-type postgresql \\
    --connection "postgresql://user:password@localhost:5432/mydb" \\
    --num-rows 100 --output-sql test_data.sql

  # MySQL
  python test_data_generator.py --db-type mysql \\
    --connection "mysql://user:password@localhost:3306/mydb" \\
    --num-rows 50 --output-json test_data.json

  # SQL Server
  python test_data_generator.py --db-type sqlserver \\
    --connection "mssql://user:password@localhost:1433/mydb" \\
    --num-rows 100 --output-sql test_data.sql
        """
    )
    
    parser.add_argument('--db-type',
                       choices=['postgresql', 'postgres', 'mysql', 'sqlserver', 'mssql'],
                       help='Database type (required if --load-schema is not used)')
    parser.add_argument('--connection',
                       help='Database connection string (required if --load-schema is not used)')
    parser.add_argument('--num-rows', type=int, default=100,
                       help='Number of rows to generate per table (default: 100)')
    parser.add_argument('--output-sql', 
                       help='Output SQL file path')
    parser.add_argument('--output-json',
                       help='Output JSON file path')
    parser.add_argument('--schema-only', action='store_true',
                       help='Only analyze and display schema without generating data')
    parser.add_argument('--save-schema',
                       help='Save analyzed schema and statistics to a JSON file')
    parser.add_argument('--load-schema',
                       help='Load schema and statistics from a previously saved JSON file')
    
    args = parser.parse_args()
    
    try:
        analyzer = None
        
        # Mode 1: Load schema from file
        if args.load_schema:
            print(f"Loading schema from file: {args.load_schema}")
            analyzer = SchemaAnalyzer()
            analyzer.load_from_file(args.load_schema)
            analyzer.print_schema_summary()
        
        # Mode 2: Connect to database and analyze
        else:
            if not args.db_type or not args.connection:
                parser.error("--db-type and --connection are required when not using --load-schema")
            
            # Create database connector
            print(f"Database Type: {args.db_type}")
            connector = create_connector(args.db_type, args.connection)
            connector.connect()
            
            # Analyze schema
            analyzer = SchemaAnalyzer(connector)
            analyzer.analyze()
            analyzer.print_schema_summary()
            
            # Save schema if requested
            if args.save_schema:
                analyzer.save_to_file(args.save_schema)
            
            # Disconnect
            connector.disconnect()
            
            # If only saving schema, exit here
            if args.schema_only:
                print("\n=== Schema analysis complete (--schema-only mode) ===")
                return 0
        
        # Generate test data if not in schema-only mode
        if not args.schema_only:
            generator = TestDataGenerator(analyzer)
            generator.generate(num_rows_per_table=args.num_rows)
            
            # Export data
            if args.output_sql:
                generator.export_to_sql(args.output_sql)
            
            if args.output_json:
                generator.export_to_json(args.output_json)
            
            if not args.output_sql and not args.output_json:
                print("\nWarning: No output format specified. Use --output-sql or --output-json to export data.")
        
        print("\n=== Complete ===")
        return 0
        
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

import sqlite3
from sqlite3 import Error
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect('plagiarism.db')
        conn.execute("PRAGMA foreign_keys = ON")
        logger.info("Database connection established")
        return conn
    except Error as e:
        logger.error(f"Error connecting to database: {e}")
    return conn

def create_table(conn):
    """Create the keywords table if it doesn't exist."""
    try:
        sql_create_keywords_table = """CREATE TABLE IF NOT EXISTS keywords (
                                    id integer PRIMARY KEY AUTOINCREMENT,
                                    keyword text NOT NULL UNIQUE,
                                    weight real DEFAULT 1.0,
                                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                );"""
        
        sql_create_trigger = """CREATE TRIGGER IF NOT EXISTS update_keyword_timestamp
                            AFTER UPDATE ON keywords
                            BEGIN
                                UPDATE keywords SET updated_at = CURRENT_TIMESTAMP 
                                WHERE id = old.id;
                            END;"""
        
        c = conn.cursor()
        c.execute(sql_create_keywords_table)
        c.execute(sql_create_trigger)
        conn.commit()
        logger.info("Keywords table created or verified")
    except Error as e:
        logger.error(f"Error creating table: {e}")
        raise

def initialize_database():
    """Initialize the database with default keywords if empty."""
    default_keywords = [
        ("research", 1.5),
        ("study", 1.3),
        ("method", 1.4),
        ("analysis", 1.6),
        ("result", 1.5),
        ("conclusion", 1.4),
        ("data", 1.3),
        ("experiment", 1.6),
        ("hypothesis", 1.7),
        ("theory", 1.4),
        ("plagiarism", 2.0),
        ("citation", 1.8),
        ("reference", 1.7),
        ("quote", 1.6),
        ("source", 1.5)
    ]
    
    try:
        conn = create_connection()
        if conn is not None:
            create_table(conn)
            
            # Check if table is empty
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM keywords")
            count = cur.fetchone()[0]
            
            if count == 0:
                logger.info("Adding default keywords to database")
                for keyword, weight in default_keywords:
                    add_keyword(conn, keyword, weight)
                logger.info(f"Added {len(default_keywords)} default keywords")
            else:
                logger.info(f"Database already contains {count} keywords")
                
            conn.close()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def add_keyword(conn, keyword, weight=1.0):
    """Add a new keyword to the keywords table."""
    if not keyword.strip():
        raise ValueError("Keyword cannot be empty")
    
    try:
        sql = '''INSERT OR REPLACE INTO keywords(keyword, weight)
                 VALUES(?,?)'''
        cur = conn.cursor()
        cur.execute(sql, (keyword.lower().strip(), float(weight)))
        conn.commit()
        logger.info(f"Keyword added/updated: {keyword} (weight: {weight})")
        return cur.lastrowid
    except Error as e:
        logger.error(f"Error adding keyword '{keyword}': {e}")
        raise
    except ValueError as e:
        logger.error(f"Invalid weight value for keyword '{keyword}': {e}")
        raise

def get_all_keywords(conn, sort_by='keyword', order='ASC'):
    """Query all keywords from the database with sorting options."""
    valid_sort_columns = ['keyword', 'weight', 'created_at', 'updated_at']
    valid_orders = ['ASC', 'DESC']
    
    sort_by = sort_by if sort_by in valid_sort_columns else 'keyword'
    order = order if order in valid_orders else 'ASC'
    
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT keyword, weight FROM keywords ORDER BY {sort_by} {order}")
        return cur.fetchall()
    except Error as e:
        logger.error(f"Error fetching keywords: {e}")
        raise

def search_keywords(conn, text, min_weight=0.5):
    """Search for keywords in the given text and return matches with weights."""
    if not text.strip():
        return []
    
    try:
        keywords = get_all_keywords(conn)
        found = []
        text_lower = text.lower()
        
        for keyword, weight in keywords:
            if weight >= min_weight and keyword.lower() in text_lower:
                found.append((keyword, weight))
        
        logger.debug(f"Found {len(found)} keywords in text")
        return found
    except Error as e:
        logger.error(f"Error searching keywords: {e}")
        raise

def delete_keyword(conn, keyword):
    """Delete a keyword from the database."""
    try:
        sql = "DELETE FROM keywords WHERE keyword = ?"
        cur = conn.cursor()
        cur.execute(sql, (keyword.lower(),))
        conn.commit()
        affected_rows = cur.rowcount
        if affected_rows > 0:
            logger.info(f"Deleted keyword: {keyword}")
        return affected_rows
    except Error as e:
        logger.error(f"Error deleting keyword '{keyword}': {e}")
        raise

def update_keyword_weight(conn, keyword, new_weight):
    """Update the weight of an existing keyword."""
    try:
        sql = "UPDATE keywords SET weight = ? WHERE keyword = ?"
        cur = conn.cursor()
        cur.execute(sql, (float(new_weight), keyword.lower()))
        conn.commit()
        affected_rows = cur.rowcount
        if affected_rows > 0:
            logger.info(f"Updated weight for '{keyword}' to {new_weight}")
        return affected_rows
    except Error as e:
        logger.error(f"Error updating keyword '{keyword}': {e}")
        raise
    except ValueError as e:
        logger.error(f"Invalid weight value for keyword '{keyword}': {e}")
        raise

# Initialize the database when this module is imported
if __name__ != "__main__":
    initialize_database()
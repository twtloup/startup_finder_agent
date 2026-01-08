"""
Database Manager for Venture Funding Monitor
Handles all SQLite database operations including schema creation,
article storage, and funding announcement tracking.
"""

import sqlite3
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from src import config

# Set up logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database operations for tracking RSS articles
    and funding announcements.

    Why SQLite?
    - No separate server needed (database is just a file)
    - Built into Python (no extra installation)
    - Perfect for single-user applications
    - ACID compliant (won't lose data even if process crashes)
    - You already know SQL from your BI work!
    """

    def __init__(self, db_path: str = None):
        """
        Initialize database connection and create schema if needed.

        Args:
            db_path: Path to SQLite database file. Defaults to config.DATABASE_PATH
        """
        self.db_path = db_path or config.DATABASE_PATH

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize database
        self.conn = None
        self._connect()
        self._create_schema()

    def _connect(self):
        """
        Connect to SQLite database with optimizations.
        Uses WAL (Write-Ahead Logging) mode for better performance.
        """
        try:
            self.conn = sqlite3.connect(self.db_path, timeout=30)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries

            # Enable WAL mode for better concurrency
            self.conn.execute("PRAGMA journal_mode=WAL")

            logger.info(f"Connected to database: {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def _create_schema(self):
        """
        Create database tables if they don't exist.

        Schema design:
        1. articles table: Tracks ALL processed RSS articles (prevents duplicates)
        2. funding_announcements table: Stores extracted funding details
        3. Foreign key relationship: Each announcement links to an article
        """
        try:
            cursor = self.conn.cursor()

            # Table 1: Articles
            # Purpose: Track all processed RSS articles to avoid re-processing
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    published_date TEXT NOT NULL,
                    processed_date TEXT NOT NULL,
                    is_funding_related BOOLEAN NOT NULL,
                    relevance_score INTEGER DEFAULT 0,
                    CONSTRAINT unique_url UNIQUE (url)
                )
            ''')

            # Table 2: Funding Announcements
            # Purpose: Store extracted funding details for digest generation
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS funding_announcements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    company_name TEXT,
                    funding_stage TEXT,
                    funding_amount TEXT,
                    location TEXT,
                    industry TEXT,
                    description TEXT,
                    included_in_digest BOOLEAN DEFAULT 0,
                    extracted_date TEXT NOT NULL,
                    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
                )
            ''')

            # Create indexes for faster lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_articles_url
                ON articles(url)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_articles_published
                ON articles(published_date)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_funding_digest
                ON funding_announcements(included_in_digest)
            ''')

            self.conn.commit()
            logger.info("Database schema created successfully")

        except sqlite3.Error as e:
            logger.error(f"Schema creation error: {e}")
            raise

    def is_article_processed(self, url: str) -> bool:
        """
        Check if an article has already been processed.

        Args:
            url: Article URL to check

        Returns:
            True if article exists in database, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT 1 FROM articles WHERE url = ?', (url,))
            return cursor.fetchone() is not None

        except sqlite3.Error as e:
            logger.error(f"Error checking article: {e}")
            return False

    def store_article(
        self,
        url: str,
        title: str,
        source: str,
        published_date: str,
        is_funding_related: bool,
        relevance_score: int = 0
    ) -> Optional[int]:
        """
        Store a new article in the database.

        Args:
            url: Article URL (must be unique)
            title: Article title
            source: RSS feed source name
            published_date: When article was published (ISO format)
            is_funding_related: Whether article matched funding patterns
            relevance_score: Relevance score (0-100)

        Returns:
            Article ID if successful, None otherwise
        """
        try:
            cursor = self.conn.cursor()
            processed_date = datetime.now().isoformat()

            cursor.execute('''
                INSERT INTO articles
                (url, title, source, published_date, processed_date, is_funding_related, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (url, title, source, published_date, processed_date, is_funding_related, relevance_score))

            self.conn.commit()
            article_id = cursor.lastrowid

            logger.debug(f"Stored article: {title} (ID: {article_id})")
            return article_id

        except sqlite3.IntegrityError:
            logger.warning(f"Duplicate article URL: {url}")
            return None

        except sqlite3.Error as e:
            logger.error(f"Error storing article: {e}")
            return None

    def store_funding_announcement(
        self,
        article_id: int,
        company_name: str,
        funding_stage: str,
        funding_amount: str,
        location: str,
        industry: str,
        description: str
    ) -> Optional[int]:
        """
        Store funding announcement details linked to an article.

        Args:
            article_id: Foreign key to articles table
            company_name: Extracted company name
            funding_stage: Seed, Series A, B, or C
            funding_amount: Raw extracted amount string
            location: Geographic location
            industry: Industry/sector
            description: Article description/summary

        Returns:
            Announcement ID if successful, None otherwise
        """
        try:
            cursor = self.conn.cursor()
            extracted_date = datetime.now().isoformat()

            cursor.execute('''
                INSERT INTO funding_announcements
                (article_id, company_name, funding_stage, funding_amount,
                 location, industry, description, extracted_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (article_id, company_name, funding_stage, funding_amount,
                  location, industry, description, extracted_date))

            self.conn.commit()
            announcement_id = cursor.lastrowid

            logger.info(f"Stored funding announcement: {company_name} - {funding_stage} (ID: {announcement_id})")
            return announcement_id

        except sqlite3.Error as e:
            logger.error(f"Error storing funding announcement: {e}")
            return None

    def get_pending_announcements(self, days: int = 1) -> List[Dict]:
        """
        Retrieve funding announcements not yet included in a digest.

        Args:
            days: Number of days to look back (1 for daily, 7 for weekly)

        Returns:
            List of announcement dictionaries with article details
        """
        try:
            cursor = self.conn.cursor()

            # Calculate cutoff date
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            # Join funding_announcements with articles to get full details
            cursor.execute('''
                SELECT
                    fa.id,
                    fa.company_name,
                    fa.funding_stage,
                    fa.funding_amount,
                    fa.location,
                    fa.industry,
                    fa.description,
                    a.url,
                    a.title,
                    a.source,
                    a.published_date,
                    a.relevance_score
                FROM funding_announcements fa
                JOIN articles a ON fa.article_id = a.id
                WHERE fa.included_in_digest = 0
                  AND a.published_date >= ?
                ORDER BY a.published_date DESC
            ''', (cutoff_date,))

            # Convert rows to dictionaries
            announcements = []
            for row in cursor.fetchall():
                announcements.append({
                    'id': row['id'],
                    'company_name': row['company_name'],
                    'funding_stage': row['funding_stage'],
                    'funding_amount': row['funding_amount'],
                    'location': row['location'],
                    'industry': row['industry'],
                    'description': row['description'],
                    'url': row['url'],
                    'title': row['title'],
                    'source': row['source'],
                    'published_date': row['published_date'],
                    'relevance_score': row['relevance_score']
                })

            logger.info(f"Retrieved {len(announcements)} pending announcements")
            return announcements

        except sqlite3.Error as e:
            logger.error(f"Error retrieving announcements: {e}")
            return []

    def mark_as_digested(self, announcement_ids: List[int]):
        """
        Mark funding announcements as included in a digest.
        Prevents duplicates in future digests.

        Args:
            announcement_ids: List of announcement IDs to mark
        """
        if not announcement_ids:
            return

        try:
            cursor = self.conn.cursor()

            # Create placeholders for SQL IN clause
            placeholders = ','.join('?' * len(announcement_ids))

            cursor.execute(f'''
                UPDATE funding_announcements
                SET included_in_digest = 1
                WHERE id IN ({placeholders})
            ''', announcement_ids)

            self.conn.commit()
            logger.info(f"Marked {len(announcement_ids)} announcements as digested")

        except sqlite3.Error as e:
            logger.error(f"Error marking announcements as digested: {e}")

    def cleanup_old_entries(self, days: int = None):
        """
        Delete old articles and announcements to keep database small.

        Args:
            days: Delete entries older than this many days (default: config.DATABASE_CLEANUP_DAYS)
        """
        days = days or config.DATABASE_CLEANUP_DAYS

        try:
            cursor = self.conn.cursor()
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            # Delete old articles (funding_announcements cascade delete automatically)
            cursor.execute('''
                DELETE FROM articles
                WHERE processed_date < ?
            ''', (cutoff_date,))

            deleted_count = cursor.rowcount
            self.conn.commit()

            logger.info(f"Cleaned up {deleted_count} articles older than {days} days")

        except sqlite3.Error as e:
            logger.error(f"Error cleaning up old entries: {e}")

    def get_stats(self) -> Dict:
        """
        Get database statistics for logging/monitoring.

        Returns:
            Dictionary with article and announcement counts
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM articles')
            total_articles = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM articles WHERE is_funding_related = 1')
            funding_articles = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM funding_announcements')
            total_announcements = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM funding_announcements WHERE included_in_digest = 1')
            digested_announcements = cursor.fetchone()[0]

            return {
                'total_articles': total_articles,
                'funding_articles': funding_articles,
                'total_announcements': total_announcements,
                'digested_announcements': digested_announcements,
                'pending_announcements': total_announcements - digested_announcements
            }

        except sqlite3.Error as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.close()


# Example usage:
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(level=logging.INFO)

    # Test database operations
    with DatabaseManager() as db:
        print("Database initialized successfully!")

        # Get stats
        stats = db.get_stats()
        print(f"Database stats: {stats}")

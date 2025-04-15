import sqlite3
import uuid
from datetime import datetime


class RequestQueue:
    def __init__(self, db_path="db/queue.db"):
        self.db_path = db_path
        self.init_db()
        
    def init_db(self):
        """Initialize SQLite database for persistent queue storage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create requests table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            prompt TEXT,
            submitted_at TEXT,
            estimated_power REAL,
            estimated_completion TEXT,
            status TEXT,
            response TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
        
    def enqueue(self, conversation_id, prompt, estimated_power, estimated_completion):
        """Add a request to the queue"""
        request_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request_id,
            conversation_id,
            prompt,
            datetime.now().isoformat(),
            estimated_power,
            estimated_completion.isoformat(),
            "queued",
            None
        ))
        
        conn.commit()
        conn.close()
        
        return request_id
        
    def get_next_processable_request(self, available_power):
        """Find first request that can be processed with available power"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM requests 
        WHERE status = 'queued' AND estimated_power <= ? 
        ORDER BY submitted_at ASC 
        LIMIT 1
        ''', (available_power,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_request_status(self, request_id, status, response=None):
        """Update the status of a request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if response:
            cursor.execute('''
            UPDATE requests SET status = ?, response = ? WHERE id = ?
            ''', (status, response, request_id))
        else:
            cursor.execute('''
            UPDATE requests SET status = ? WHERE id = ?
            ''', (status, request_id))
        
        conn.commit()
        conn.close()
    
    def get_request(self, request_id):
        """Get a request by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM requests WHERE id = ?', (request_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_conversation_requests(self, conversation_id):
        """Get all requests for a conversation"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM requests WHERE conversation_id = ? ORDER BY submitted_at ASC
        ''', (conversation_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_queue_length(self):
        """Get the number of queued requests"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM requests WHERE status = "queued"')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def get_queue_position(self, request_id):
        """Get position of request in the queue"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT position FROM (
            SELECT id as request_id, ROW_NUMBER() OVER (ORDER BY submitted_at ASC) as position 
            FROM requests 
            WHERE status = 'queued'
        ) WHERE request_id = ?
        ''', (request_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0]
        return None
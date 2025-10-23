#!/usr/bin/env python3
import sqlite3
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Database:
    def __init__(self, db_path='chat.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                joined_date TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        ''')
        
        # Таблица приватных чатов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS private_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1 TEXT NOT NULL,
                user2 TEXT NOT NULL,
                created_date TEXT NOT NULL,
                UNIQUE(user1, user2)
            )
        ''')
        
        # Таблица сообщений приватных чатов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS private_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                message_text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES private_chats (id)
            )
        ''')
        
        # Таблица групп
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                admin TEXT NOT NULL,
                created_date TEXT NOT NULL
            )
        ''')
        
        # Таблица участников групп
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                joined_date TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups (id),
                UNIQUE(group_id, username)
            )
        ''')
        
        # Таблица сообщений групп
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                message_text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ==================== USER METHODS ====================
    
    def add_user(self, username, password):
        """Добавление пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO users (username, password_hash, joined_date, last_seen)
                VALUES (?, ?, ?, ?)
            ''', (
                username,
                generate_password_hash(password),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_user(self, username):
        """Получение пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'id': user[0],
                'username': user[1],
                'password_hash': user[2],
                'joined_date': user[3],
                'last_seen': user[4]
            }
        return None
    
    def verify_user(self, username, password):
        """Проверка пользователя"""
        user = self.get_user(username)
        if user and check_password_hash(user['password_hash'], password):
            self.update_last_seen(username)
            return True
        return False
    
    def update_last_seen(self, username):
        """Обновление времени последнего посещения"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET last_seen = ? WHERE username = ?
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), username))
        
        conn.commit()
        conn.close()
    
    def get_all_users(self):
        """Получение всех пользователей"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT username, last_seen FROM users')
        users = cursor.fetchall()
        conn.close()
        
        return [{'username': user[0], 'last_seen': user[1]} for user in users]
    
    # ==================== PRIVATE CHAT METHODS ====================
    
    def find_or_create_private_chat(self, user1, user2):
        """Находит или создает приватный чат"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Ищем существующий чат
        cursor.execute('''
            SELECT id FROM private_chats 
            WHERE (user1 = ? AND user2 = ?) OR (user1 = ? AND user2 = ?)
        ''', (user1, user2, user2, user1))
        
        chat = cursor.fetchone()
        
        if chat:
            chat_id = chat[0]
        else:
            # Создаем новый чат
            cursor.execute('''
                INSERT INTO private_chats (user1, user2, created_date)
                VALUES (?, ?, ?)
            ''', (user1, user2, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            chat_id = cursor.lastrowid
            conn.commit()
        
        conn.close()
        return chat_id
    
    def add_private_message(self, chat_id, username, message_text):
        """Добавление сообщения в приватный чат"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO private_messages (chat_id, username, message_text, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (chat_id, username, message_text, datetime.now().strftime('%H:%M:%S')))
        
        conn.commit()
        conn.close()
    
    def get_private_chat_history(self, chat_id, limit=50):
        """Получение истории приватного чата"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, message_text, timestamp 
            FROM private_messages 
            WHERE chat_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (chat_id, limit))
        
        messages = cursor.fetchall()
        conn.close()
        
        return [{
            'username': msg[0],
            'text': msg[1],
            'timestamp': msg[2]
        } for msg in reversed(messages)]
    
    def get_user_private_chats(self, username):
        """Получение приватных чатов пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT pc.id, 
                   CASE WHEN pc.user1 = ? THEN pc.user2 ELSE pc.user1 END as other_user,
                   (SELECT message_text FROM private_messages 
                    WHERE chat_id = pc.id 
                    ORDER BY timestamp DESC LIMIT 1) as last_message
            FROM private_chats pc
            WHERE pc.user1 = ? OR pc.user2 = ?
        ''', (username, username, username))
        
        chats = cursor.fetchall()
        conn.close()
        
        return [{
            'chat_id': chat[0],
            'other_user': chat[1],
            'last_message': chat[2] or 'Нет сообщений'
        } for chat in chats]
    
    # ==================== GROUP METHODS ====================
    
    def create_group(self, name, admin, members):
        """Создание группы"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Создаем группу
            cursor.execute('''
                INSERT INTO groups (name, admin, created_date)
                VALUES (?, ?, ?)
            ''', (name, admin, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            group_id = cursor.lastrowid
            
            # Добавляем участников
            all_members = [admin] + members
            for member in all_members:
                cursor.execute('''
                    INSERT INTO group_members (group_id, username, joined_date)
                    VALUES (?, ?, ?)
                ''', (group_id, member, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            return group_id
        except Exception as e:
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def add_group_message(self, group_id, username, message_text):
        """Добавление сообщения в группу"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO group_messages (group_id, username, message_text, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (group_id, username, message_text, datetime.now().strftime('%H:%M:%S')))
        
        conn.commit()
        conn.close()
    
    def get_group_history(self, group_id, limit=50):
        """Получение истории группы"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, message_text, timestamp 
            FROM group_messages 
            WHERE group_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (group_id, limit))
        
        messages = cursor.fetchall()
        conn.close()
        
        return [{
            'username': msg[0],
            'text': msg[1],
            'timestamp': msg[2]
        } for msg in reversed(messages)]
    
    def get_user_groups(self, username):
        """Получение групп пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT g.id, g.name, g.admin, 
                   (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count
            FROM groups g
            JOIN group_members gm ON g.id = gm.group_id
            WHERE gm.username = ?
        ''', (username,))
        
        groups = cursor.fetchall()
        conn.close()
        
        return [{
            'group_id': group[0],
            'name': group[1],
            'admin': group[2],
            'member_count': group[3]
        } for group in groups]

# Создаем глобальный экземпляр базы данных
db = Database()
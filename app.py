#!/usr/bin/env python3
import os
import json
import uuid
import socket
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room, leave_room

from database import db  # Импортируем нашу базу данных

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-chat-key-2024'
app.config['DEBUG'] = True

socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальные переменные для онлайн статуса
active_users = {}  # {socket_id: username}
user_sessions = {}  # {username: socket_id}

# ==================== ROUTES ====================

@app.route('/')
def index():
    if 'username' not in session:
        return redirect('/login')
    return redirect('/chat')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect('/chat')
    
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        if not username or not password:
            flash('Заполните все поля', 'error')
            return render_template('login.html')
        
        if db.verify_user(username, password):
            session['username'] = username
            session['user_id'] = str(uuid.uuid4())
            flash('Успешный вход!', 'success')
            return redirect('/chat')
        else:
            flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect('/chat')
    
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if not username or not password:
            flash('Заполните все поля', 'error')
            return render_template('register.html')
        
        if len(username) < 3:
            flash('Имя пользователя должно быть не менее 3 символов', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Пароль должен быть не менее 6 символов', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return render_template('register.html')
        
        if db.add_user(username, password):
            flash('Регистрация успешна! Теперь войдите в систему.', 'success')
            return redirect('/login')
        else:
            flash('Имя пользователя уже занято', 'error')
    
    return render_template('register.html')

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect('/login')
    
    username = session['username']
    
    # Получаем данные из базы
    all_users_data = db.get_all_users()
    all_users = [user['username'] for user in all_users_data]
    online_users = list(active_users.values())
    
    # Получаем приватные чаты и группы
    user_private_chats = db.get_user_private_chats(username)
    user_groups = db.get_user_groups(username)
    
    return render_template('chat.html',
                         username=username,
                         all_users=all_users,
                         online_users=online_users,
                         private_chats=user_private_chats,
                         groups=user_groups,
                         active_users_count=len(active_users))

@app.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if 'username' not in session:
        return redirect('/login')
    
    if request.method == 'POST':
        group_name = request.form['group_name'].strip()
        members = request.form.getlist('members')
        
        if not group_name:
            flash('Введите название группы', 'error')
            return redirect('/create_group')
        
        group_id = db.create_group(group_name, session['username'], members)
        if group_id:
            flash(f'Группа "{group_name}" создана!', 'success')
            return redirect('/chat')
        else:
            flash('Ошибка при создании группы', 'error')
    
    # Получаем всех пользователей кроме текущего
    all_users = [user['username'] for user in db.get_all_users()]
    other_users = [user for user in all_users if user != session['username']]
    
    return render_template('create_group.html', other_users=other_users)

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect('/login')
    
    username = session['username']
    user_data = db.get_user(username)
    
    if not user_data:
        flash('Пользователь не найден', 'error')
        return redirect('/chat')
    
    user_private_chats = db.get_user_private_chats(username)
    user_groups = db.get_user_groups(username)
    
    profile_info = {
        'username': username,
        'joined_date': user_data.get('joined_date', 'Неизвестно'),
        'last_seen': user_data.get('last_seen', 'Неизвестно'),
        'private_chats_count': len(user_private_chats),
        'groups_count': len(user_groups),
        'contacts_count': len(set([chat['other_user'] for chat in user_private_chats]))
    }
    
    return render_template('profile.html', profile=profile_info)

@app.route('/logout')
def logout():
    username = session.pop('username', None)
    if username and username in user_sessions:
        # Удаляем из активных пользователей
        for sid, user in list(active_users.items()):
            if user == username:
                del active_users[sid]
                break
        del user_sessions[username]
    
    flash('Вы вышли из системы', 'info')
    return redirect('/login')

# ==================== SOCKET IO HANDLERS ====================

@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        username = session['username']
        active_users[request.sid] = username
        user_sessions[username] = request.sid
        
        # Обновляем время последнего посещения
        db.update_last_seen(username)
        
        # Уведомляем всех о новом пользователе онлайн
        emit('user_online', {'username': username}, broadcast=True)
        emit('online_users_update', {'users': list(active_users.values())}, broadcast=True)
        print(f"✅ {username} подключился. Онлайн: {len(active_users)}")

@socketio.on('disconnect')
def handle_disconnect():
    username = active_users.pop(request.sid, None)
    if username and username in user_sessions:
        del user_sessions[username]
    
    if username:
        emit('user_offline', {'username': username}, broadcast=True)
        emit('online_users_update', {'users': list(active_users.values())}, broadcast=True)
        print(f"❌ {username} отключился. Онлайн: {len(active_users)}")

@socketio.on('start_private_chat')
def handle_start_private_chat(data):
    username = session['username']
    other_user = data['other_user']
    
    # Создаем или находим приватный чат
    chat_id = db.find_or_create_private_chat(username, other_user)
    
    # Присоединяем к комнате приватного чата
    join_room(str(chat_id))
    
    # Отправляем историю чата
    chat_history = db.get_private_chat_history(chat_id)
    emit('private_chat_history', {
        'chat_id': chat_id,
        'other_user': other_user,
        'messages': chat_history
    })
    print(f"💬 {username} начал чат с {other_user}")

@socketio.on('join_group')
def handle_join_group(data):
    group_id = data['group_id']
    username = session['username']
    
    # Проверяем что пользователь в группе
    user_groups = db.get_user_groups(username)
    group_ids = [str(g['group_id']) for g in user_groups]
    
    if str(group_id) in group_ids:
        join_room(str(group_id))
        
        # Отправляем историю группы
        group_history = db.get_group_history(group_id)
        group_info = next((g for g in user_groups if str(g['group_id']) == str(group_id)), None)
        
        if group_info:
            emit('group_chat_history', {
                'group_id': group_id,
                'group_name': group_info['name'],
                'messages': group_history
            })
            print(f"👥 {username} присоединился к группе {group_info['name']}")

@socketio.on('private_message')
def handle_private_message(data):
    username = session['username']
    chat_id = data['chat_id']
    message_text = data['text'].strip()
    
    if message_text:
        # Сохраняем сообщение в базу
        db.add_private_message(chat_id, username, message_text)
        
        message_data = {
            'username': username,
            'text': message_text,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        
        # Отправляем сообщение в комнату приватного чата
        emit('new_private_message', {
            'chat_id': chat_id,
            'message': message_data
        }, room=str(chat_id))
        
        print(f"📨 {username} -> Чат {chat_id}: {message_text}")

@socketio.on('group_message')
def handle_group_message(data):
    username = session['username']
    group_id = data['group_id']
    message_text = data['text'].strip()
    
    if message_text:
        # Сохраняем сообщение в базу
        db.add_group_message(group_id, username, message_text)
        
        message_data = {
            'username': username,
            'text': message_text,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        
        # Отправляем сообщение в комнату группы
        emit('new_group_message', {
            'group_id': group_id,
            'message': message_data
        }, room=str(group_id))
        
        print(f"👥 {username} -> Группа {group_id}: {message_text}")

@socketio.on('typing_start')
def handle_typing_start(data):
    username = session['username']
    chat_type = data['chat_type']
    chat_id = data['chat_id']
    
    emit('user_typing', {
        'username': username,
        'chat_type': chat_type,
        'chat_id': chat_id
    }, room=str(chat_id), include_self=False)

@socketio.on('typing_stop')
def handle_typing_stop(data):
    chat_id = data['chat_id']
    emit('user_stop_typing', {'chat_id': chat_id}, room=str(chat_id))

# ==================== MAIN ====================

if __name__ == '__main__':
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    local_ip = get_local_ip()
    
    print("🚀 ChatTM Server с БАЗОЙ ДАННЫХ запущен!")
    print("=" * 50)
    print("📍 Локальный доступ:")
    print("   http://localhost:5000")
    print("   http://127.0.0.1:5000")
    print("")
    print("📍 Сетевой доступ:")
    print(f"   http://{local_ip}:5000")
    print("")
    print("📱 Для подключения с телефона:")
    print(f"   Открой браузер и введи: http://{local_ip}:5000")
    print("")
    print("💾 База данных: chat.db")
    print("⏹️  Для остановки: Ctrl+C")
    print("=" * 50)
    
    # Запускаем на всех интерфейсах
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
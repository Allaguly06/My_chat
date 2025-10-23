import os
import json
import platform
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

# Инициализация приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = 'kali_linux_chat_secret_2024'
app.config['DEBUG'] = True

socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальные переменные
active_users = {}
user_profiles = {}
chat_rooms = {
    'general': {'users': [], 'messages': [], 'description': 'Основная комната'},
    'python': {'users': [], 'messages': [], 'description': 'Обсуждение Python'},
    'help': {'users': [], 'messages': [], 'description': 'Помощь и поддержка'},
    'random': {'users': [], 'messages': [], 'description': 'Свободное общение'},
    'hacking': {'users': [], 'messages': [], 'description': 'Этичный хакинг'}
}

#  ROUTES 

@app.route('/')
def index():
    """Главная страница чата"""
    if 'username' not in session:
        return redirect('/login')
    
    user_agent = request.headers.get('User-Agent', '').lower()
    is_mobile = 'mobile' in user_agent or 'android' in user_agent
    
    return render_template('index.html',
                         username=session['username'],
                         rooms=chat_rooms,
                         active_users=active_users,
                         is_mobile=is_mobile,
                         total_users=len(active_users))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        
        if not username or len(username) < 2:
            return render_template('login.html', error='Имя должно быть от 2 символов')
        
        if username in active_users.values():
            return render_template('login.html', error='Это имя уже используется')
        
        session['username'] = username
        session['login_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        session['user_agent'] = request.headers.get('User-Agent', 'Unknown')
        
        # Создаем профиль пользователя
        user_profiles[username] = {
            'join_time': session['login_time'],
            'message_count': 0,
            'rooms_joined': []
        }
        
        return redirect('/')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Выход из системы"""
    username = session.pop('username', None)
    
    if username:
        # Удаляем из активных пользователей
        for sid, user in list(active_users.items()):
            if user == username:
                del active_users[sid]
                break
        
        # Сохраняем историю
        save_chat_history()
    
    return redirect('/login')

@app.route('/profile')
def profile():
    """Страница профиля"""
    if 'username' not in session:
        return redirect('/login')
    
    username = session['username']
    profile_data = user_profiles.get(username, {})
    
    # Считаем статистику
    user_messages = 0
    user_rooms = []
    
    for room_name, room_data in chat_rooms.items():
        room_msg_count = sum(1 for msg in room_data['messages'] if msg.get('username') == username)
        if room_msg_count > 0:
            user_messages += room_msg_count
            user_rooms.append(room_name)
    
    stats = {
        'username': username,
        'join_time': profile_data.get('join_time', 'Неизвестно'),
        'total_messages': user_messages,
        'rooms_joined': user_rooms,
        'active_rooms': len([r for r in user_rooms if username in chat_rooms[r]['users']]),
        'user_agent': session.get('user_agent', 'Unknown')
    }
    
    return render_template('profile.html', stats=stats)

@app.route('/stats')
def stats():
    """Статистика чата"""
    if 'username' not in session:
        return redirect('/login')
    
    # Статистика по комнатам
    room_stats = []
    for room_name, room_data in chat_rooms.items():
        room_stats.append({
            'name': room_name,
            'description': room_data['description'],
            'online_users': len(room_data['users']),
            'total_messages': len(room_data['messages']),
            'last_activity': room_data['messages'][-1]['timestamp'] if room_data['messages'] else 'Нет активности'
        })
    
    # Общая статистика
    total_messages = sum(len(room['messages']) for room in chat_rooms.values())
    most_active_room = max(chat_rooms.items(), key=lambda x: len(x[1]['messages']))[0]
    
    stats_data = {
        'total_online': len(active_users),
        'total_rooms': len(chat_rooms),
        'total_messages': total_messages,
        'most_active_room': most_active_room,
        'server_os': platform.system(),
        'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'room_stats': room_stats,
        'active_users': list(active_users.values())
    }
    
    return render_template('stats.html', stats=stats_data)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Настройки пользователя"""
    if 'username' not in session:
        return redirect('/login')
    
    if request.method == 'POST':
        # Сохраняем настройки
        session['theme'] = request.form.get('theme', 'dark')
        session['notifications'] = 'notifications' in request.form
        session['sound_effects'] = 'sound_effects' in request.form
        session['auto_join'] = request.form.get('auto_join', 'general')
        
        return redirect('/settings?success=1')
    
    return render_template('settings.html',
                         current_theme=session.get('theme', 'dark'),
                         notifications=session.get('notifications', True),
                         sound_effects=session.get('sound_effects', True),
                         auto_join=session.get('auto_join', 'general'),
                         rooms=chat_rooms)

@app.route('/mobile')
def mobile_chat():
    """Мобильная версия"""
    if 'username' not in session:
        return redirect('/login')
    
    return render_template('mobile.html',
                         username=session['username'],
                         rooms=chat_rooms,
                         active_users_count=len(active_users))

#  SOCKET IO HANDLERS 

@socketio.on('connect')
def handle_connect():
    """Обработчик подключения"""
    if 'username' in session:
        username = session['username']
        active_users[request.sid] = username
        
        # Уведомляем всех о новом пользователе
        emit('user_list_update', {
            'users': list(active_users.values()),
            'total': len(active_users)
        }, broadcast=True)
        
        emit('system_message', {
            'text': f' {username} подключился',
            'type': 'connect'
        }, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    """Обработчик отключения"""
    username = active_users.pop(request.sid, None)
    
    if username:
        # Удаляем из всех комнат
        for room_data in chat_rooms.values():
            if username in room_data['users']:
                room_data['users'].remove(username)
        
        # Уведомляем всех
        emit('user_list_update', {
            'users': list(active_users.values()),
            'total': len(active_users)
        }, broadcast=True)
        
        emit('system_message', {
            'text': f' {username} отключился',
            'type': 'disconnect'
        }, broadcast=True)
        
        save_chat_history()

@socketio.on('join_room')
def handle_join_room(data):
    """Вход в комнату"""
    room = data['room']
    username = session['username']
    
    if room in chat_rooms:
        join_room(room)
        
        # Добавляем в комнату если еще нет
        if username not in chat_rooms[room]['users']:
            chat_rooms[room]['users'].append(username)
            user_profiles[username]['rooms_joined'] = list(set(user_profiles[username].get('rooms_joined', []) + [room]))
        
        # Отправляем историю комнаты
        emit('room_history', {
            'room': room,
            'messages': chat_rooms[room]['messages'][-50:]  # Последние 50 сообщений
        })
        
        # Уведомляем комнату
        emit('system_message', {
            'text': f'🎉 {username} присоединился к комнате',
            'type': 'room_join',
            'room': room
        }, room=room)
        
        # Обновляем список пользователей комнаты
        emit('room_users_update', {
            'room': room,
            'users': chat_rooms[room]['users']
        }, room=room)

@socketio.on('leave_room')
def handle_leave_room(data):
    """Выход из комнаты"""
    room = data['room']
    username = session['username']
    
    if room in chat_rooms and username in chat_rooms[room]['users']:
        leave_room(room)
        chat_rooms[room]['users'].remove(username)
        
        emit('system_message', {
            'text': f' {username} покинул комнату',
            'type': 'room_leave',
            'room': room
        }, room=room)
        
        emit('room_users_update', {
            'room': room,
            'users': chat_rooms[room]['users']
        }, room=room)

@socketio.on('chat_message')
def handle_chat_message(data):
    """Обработка сообщений"""
    room = data['room']
    username = session['username']
    message_text = data['text'].strip()
    
    if message_text and room in chat_rooms:
        message_data = {
            'username': username,
            'text': message_text,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'room': room,
            'id': len(chat_rooms[room]['messages']) + 1
        }
        
        # Сохраняем сообщение
        chat_rooms[room]['messages'].append(message_data)
        
        # Обновляем счетчик сообщений пользователя
        user_profiles[username]['message_count'] = user_profiles[username].get('message_count', 0) + 1
        
        # Отправляем всем в комнате
        emit('new_message', message_data, room=room)
        
        # Автосохранение каждые 5 сообщений
        if len(chat_rooms[room]['messages']) % 5 == 0:
            save_chat_history()

@socketio.on('typing')
def handle_typing(data):
    """Индикатор набора текста"""
    emit('user_typing', {
        'username': session['username'],
        'is_typing': data['is_typing'],
        'room': data['room']
    }, room=data['room'], include_self=False)

#  UTILITIES 

def get_chat_history_path():
    """Путь к файлу истории для Kali Linux"""
    base_dir = Path.home() / ".python_chat_kali"
    base_dir.mkdir(exist_ok=True)
    return base_dir / "chat_history.json"

def save_chat_history():
    """Сохранение истории чата"""
    history_file = get_chat_history_path()
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump({
                'chat_rooms': chat_rooms,
                'user_profiles': user_profiles,
                'last_save': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        print(f" История сохранена: {history_file}")
    except Exception as e:
        print(f" Ошибка сохранения: {e}")

def load_chat_history():
    """Загрузка истории чата"""
    history_file = get_chat_history_path()
    global chat_rooms, user_profiles
    
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                chat_rooms.update(data.get('chat_rooms', {}))
                user_profiles.update(data.get('user_profiles', {}))
            print(f" История загружена: {len(chat_rooms)} комнат, {len(user_profiles)} пользователей")
        except Exception as e:
            print(f" Ошибка загрузки истории: {e}")

#  MAIN 

if __name__ == '__main__':
    print(" Запуск Python Chat для Kali Linux")
    print("=" * 50)
    
    # Загружаем историю
    load_chat_history()
    
    # Запускаем сервер
    print(" Сервер запускается на http://0.0.0.0:5000")
    print(" Доступ с других устройств по IP вашей Kali Linux")
    print("  Для остановки: Ctrl+C")
    print("=" * 50)
    
    try:
        socketio.run(app,
                    host='0.0.0.0',
                    port=5000,
                    debug=True,
                    allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n Сохраняем историю...")
        save_chat_history()
        print(" Сервер остановлен")
// Socket.IO connection
const socket = io();

// Global variables
let currentChatType = null;
let currentChatId = null;
let currentChatName = null;
let typingTimer = null;
let isTyping = false;

// DOM elements
const messagesContainer = document.getElementById('messages-container');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const typingIndicator = document.getElementById('typing-indicator');
const currentChatTitle = document.getElementById('current-chat-title');

// Current user
const currentUsername = document.getElementById('current-username').value;

// Socket event handlers
socket.on('connect', function() {
    console.log('✅ Connected to server as:', currentUsername);
    updateOnlineCount();
});

socket.on('user_online', function(data) {
    console.log('🟢 User online:', data.username);
    updateUserStatus(data.username, true);
    updateOnlineCount();
    if (currentChatId && currentChatType === 'private' && data.username === currentChatName) {
        addSystemMessage(`${data.username} в сети`);
    }
});

socket.on('user_offline', function(data) {
    console.log('🔴 User offline:', data.username);
    updateUserStatus(data.username, false);
    updateOnlineCount();
    if (currentChatId && currentChatType === 'private' && data.username === currentChatName) {
        addSystemMessage(`${data.username} не в сети`);
    }
});

socket.on('online_users_update', function(data) {
    console.log('👥 Online users:', data.users.length);
    updateOnlineUsers(data.users);
    updateOnlineCount();
});

socket.on('private_chat_history', function(data) {
    console.log('💬 Private chat history received for:', data.other_user);
    console.log('Messages:', data.messages);
    
    currentChatId = data.chat_id;
    currentChatType = 'private';
    currentChatName = data.other_user;
    
    displayChatHistory(data.messages, 'private');
    updateChatTitle(data.other_user, 'private');
    enableChatInput();
});

socket.on('group_chat_history', function(data) {
    console.log('👥 Group chat history received for:', data.group_name);
    
    currentChatId = data.group_id;
    currentChatType = 'group';
    currentChatName = data.group_name;
    
    displayChatHistory(data.messages, 'group');
    updateChatTitle(data.group_name, 'group');
    enableChatInput();
});

socket.on('new_private_message', function(data) {
    console.log('📨 New private message:', data);
    if (currentChatId && data.chat_id == currentChatId) {
        displayMessage(data.message, 'private');
    }
    updatePrivateChatList(data.chat_id, data.message);
});

socket.on('new_group_message', function(data) {
    console.log('👥 New group message:', data);
    if (currentChatId && data.group_id == currentChatId) {
        displayMessage(data.message, 'group');
    }
});

socket.on('user_typing', function(data) {
    if (currentChatId && data.chat_id == currentChatId && data.username !== currentUsername) {
        showTypingIndicator(data.username);
    }
});

socket.on('user_stop_typing', function(data) {
    if (currentChatId && data.chat_id == currentChatId) {
        hideTypingIndicator();
    }
});

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Chat initialized for:', currentUsername);
    
    // Initialize event listeners
    initEventListeners();
    updateOnlineCount();
});

function initEventListeners() {
    // Start private chat with user
    document.querySelectorAll('.start-private-chat').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const otherUser = this.getAttribute('data-user');
            console.log('💬 Starting chat with:', otherUser);
            startPrivateChat(otherUser);
        });
    });

    // Open existing private chat
    document.querySelectorAll('.open-private-chat').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const chatId = this.getAttribute('data-chat-id');
            const otherUser = this.getAttribute('data-user');
            console.log('💬 Opening existing chat:', chatId, 'with', otherUser);
            openPrivateChat(chatId, otherUser);
        });
    });

    // Join group
    document.querySelectorAll('.join-group').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const groupId = this.getAttribute('data-group-id');
            console.log('👥 Joining group:', groupId);
            joinGroup(groupId);
        });
    });

    // Send message
    sendButton.addEventListener('click', sendMessage);
    
    // Enter key to send message
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Typing indicators
    messageInput.addEventListener('input', handleTyping);
    messageInput.addEventListener('blur', stopTyping);
}

// Chat functions
function startPrivateChat(otherUser) {
    if (otherUser === currentUsername) {
        alert('Нельзя начать чат с самим собой!');
        return;
    }
    
    // Clear previous chat
    clearCurrentChat();
    
    console.log('🚀 Starting private chat with:', otherUser);
    socket.emit('start_private_chat', { other_user: otherUser });
    
    // Show loading state
    showLoadingState(otherUser);
}

function openPrivateChat(chatId, otherUser) {
    // Clear previous chat
    clearCurrentChat();
    
    console.log('🚀 Opening private chat:', chatId, 'with', otherUser);
    currentChatId = chatId;
    currentChatType = 'private';
    
    // Request chat history
    socket.emit('start_private_chat', { other_user: otherUser });
    
    // Show loading state
    showLoadingState(otherUser);
}

function joinGroup(groupId) {
    // Clear previous chat
    clearCurrentChat();
    
    console.log('🚀 Joining group:', groupId);
    currentChatId = groupId;
    currentChatType = 'group';
    
    socket.emit('join_group', { group_id: groupId });
    
    // Show loading state
    showLoadingState('группу');
}

function sendMessage() {
    const text = messageInput.value.trim();
    
    if (!text) {
        console.log('❌ Empty message');
        return;
    }
    
    if (!currentChatType || !currentChatId) {
        console.log('❌ No active chat selected');
        alert('Выберите чат для отправки сообщения!');
        return;
    }

    console.log(`📤 Sending ${currentChatType} message to ${currentChatId}:`, text);

    if (currentChatType === 'private') {
        socket.emit('private_message', {
            chat_id: currentChatId,
            text: text
        });
    } else if (currentChatType === 'group') {
        socket.emit('group_message', {
            group_id: currentChatId,
            text: text
        });
    }

    messageInput.value = '';
    stopTyping();
}

function handleTyping() {
    if (!currentChatType || !currentChatId) return;
    
    if (!isTyping) {
        isTyping = true;
        socket.emit('typing_start', {
            chat_type: currentChatType,
            chat_id: currentChatId
        });
    }

    clearTimeout(typingTimer);
    typingTimer = setTimeout(stopTyping, 1000);
}

function stopTyping() {
    if (isTyping && currentChatType && currentChatId) {
        isTyping = false;
        socket.emit('typing_stop', {
            chat_type: currentChatType,
            chat_id: currentChatId
        });
    }
}

// UI functions
function clearCurrentChat() {
    currentChatType = null;
    currentChatId = null;
    currentChatName = null;
    messagesContainer.innerHTML = '';
    disableChatInput();
    hideTypingIndicator();
}

function showLoadingState(name) {
    messagesContainer.innerHTML = `
        <div class="text-center text-muted mt-5">
            <div class="spinner-border text-primary mb-3"></div>
            <p>Загрузка чата с ${name}...</p>
        </div>
    `;
}

function displayChatHistory(messages, chatType) {
    messagesContainer.innerHTML = '';
    
    if (messages.length === 0) {
        addSystemMessage('Нет сообщений. Начните общение!');
    } else {
        messages.forEach(message => {
            displayMessage(message, chatType);
        });
    }
    scrollToBottom();
}

function displayMessage(message, chatType) {
    const messageDiv = document.createElement('div');
    const isOwnMessage = message.username === currentUsername;
    
    messageDiv.className = `message ${isOwnMessage ? 'own' : 'other'}`;
    
    messageDiv.innerHTML = `
        <div class="message-header">
            <span class="message-username">${isOwnMessage ? 'Вы' : message.username}</span>
            <span class="message-time">${message.timestamp}</span>
        </div>
        <div class="message-text">${escapeHtml(message.text)}</div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

function addSystemMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system';
    messageDiv.innerHTML = `<div class="text-center text-muted"><em>${escapeHtml(text)}</em></div>`;
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

function showTypingIndicator(username) {
    const typingUserElement = document.getElementById('typing-user');
    if (typingUserElement) {
        typingUserElement.textContent = username;
    }
    typingIndicator.style.display = 'block';
    scrollToBottom();
}

function hideTypingIndicator() {
    typingIndicator.style.display = 'none';
}

function updateChatTitle(title, type) {
    const icon = type === 'private' ? 'bi-person' : 'bi-people';
    currentChatTitle.innerHTML = `<i class="bi ${icon}"></i> ${title}`;
}

function enableChatInput() {
    messageInput.disabled = false;
    sendButton.disabled = false;
    messageInput.placeholder = `Сообщение для ${currentChatName}...`;
    messageInput.focus();
    
    console.log('✅ Chat input enabled for:', currentChatName);
}

function disableChatInput() {
    messageInput.disabled = true;
    sendButton.disabled = true;
    messageInput.placeholder = 'Выберите чат для общения...';
    currentChatTitle.innerHTML = '<i class="bi bi-chat-left"></i> Выберите чат';
}

function scrollToBottom() {
    setTimeout(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 100);
}

function updateOnlineCount() {
    const onlineUsers = document.querySelectorAll('.user-online').length;
    const onlineCountElement = document.getElementById('online-count');
    if (onlineCountElement) {
        onlineCountElement.textContent = onlineUsers;
    }
}

function updateUserStatus(username, isOnline) {
    const userElements = document.querySelectorAll(`.start-private-chat[data-user="${username}"]`);
    
    userElements.forEach(element => {
        if (isOnline) {
            element.classList.remove('user-offline');
            element.classList.add('user-online');
            
            const badge = element.querySelector('.online-badge, .offline-badge');
            if (badge) {
                badge.className = 'online-badge';
            }
            
            const status = element.querySelector('.user-status');
            if (status) {
                status.className = 'text-success user-status';
                status.textContent = 'online';
            }
            
            const statusText = element.querySelector('.text-muted');
            if (statusText) {
                statusText.innerHTML = '🟢 В сети';
            }
        } else {
            element.classList.remove('user-online');
            element.classList.add('user-offline');
            
            const badge = element.querySelector('.online-badge, .offline-badge');
            if (badge) {
                badge.className = 'offline-badge';
            }
            
            const status = element.querySelector('.user-status');
            if (status) {
                status.className = 'text-muted user-status';
                status.textContent = 'offline';
            }
            
            const statusText = element.querySelector('.text-muted');
            if (statusText) {
                statusText.innerHTML = '⚫ Не в сети';
            }
        }
    });
}

function updateOnlineUsers(users) {
    console.log('🔄 Updating online users:', users);
    
    // Update all users status
    document.querySelectorAll('.start-private-chat').forEach(element => {
        const username = element.getAttribute('data-user');
        const isOnline = users.includes(username);
        updateUserStatus(username, isOnline);
    });
    
    updateOnlineCount();
}

function updatePrivateChatList(chatId, message) {
    const chatElement = document.querySelector(`.open-private-chat[data-chat-id="${chatId}"]`);
    if (chatElement && message) {
        const lastMessageElement = chatElement.querySelector('small');
        if (lastMessageElement) {
            lastMessageElement.textContent = truncateText(message.text, 25);
        }
    }
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateText(text, length) {
    if (!text) return 'Нет сообщений';
    return text.length > length ? text.substring(0, length) + '...' : text;
}

// Add CSS for loading spinner and typing dots
const style = document.createElement('style');
style.textContent = `
    .spinner-border {
        width: 2rem;
        height: 2rem;
    }
    .typing-dots span {
        animation: typing 1.4s infinite;
        display: inline-block;
    }
    .typing-dots span:nth-child(2) {
        animation-delay: 0.2s;
    }
    .typing-dots span:nth-child(3) {
        animation-delay: 0.4s;
    }
    @keyframes typing {
        0%, 60%, 100% {
            transform: translateY(0);
        }
        30% {
            transform: translateY(-5px);
        }
    }
`;
document.head.appendChild(style);
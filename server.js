// server.js
// REST API Server - Exposes WhatsApp client functionality via HTTP endpoints

const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const WhatsAppClient = require('./client');

// Initialize Express App
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Initialize WhatsApp Client
const whatsappClient = new WhatsAppClient({
    headless: true
});

// Track additional state
let lastQRCode = null;

// Setup client event listeners
whatsappClient.on('qr', (qr) => {
    lastQRCode = qr;
});

whatsappClient.on('ready', (info) => {
    console.log(`✅ API is now connected to WhatsApp`);
    lastQRCode = null;
});

whatsappClient.on('disconnected', (reason) => {
    console.log(`❌ WhatsApp disconnected: ${reason}`);
});

// Initialize the client
whatsappClient.initialize();

// ===== Middleware =====

// Check if client is ready
const requireClient = (req, res, next) => {
    if (!whatsappClient.isClientReady()) {
        return res.status(503).json({
            success: false,
            error: 'WhatsApp client is not ready. Please scan QR code first.',
            qrAvailable: lastQRCode !== null
        });
    }
    next();
};

// Error handler wrapper
const asyncHandler = (fn) => (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch(next);
};

// ===== API ENDPOINTS =====

// Root endpoint - API documentation
app.get('/', (req, res) => {
    res.json({
        name: 'WhatsApp REST API',
        version: '1.0.0',
        status: whatsappClient.isClientReady() ? 'ready' : 'not ready',
        documentation: {
            health: 'GET /health',
            qr: 'GET /qr',
            chats: 'GET /api/chats',
            unreadChats: 'GET /api/unread-chats',
            unreadMessages: 'GET /api/unread-messages',
            chatMessages: 'GET /api/chats/:chatId/messages?limit=50',
            unreadFromChat: 'GET /api/chats/:chatId/unread',
            markRead: 'POST /api/chats/:chatId/mark-read',
            markAllRead: 'POST /api/mark-all-read',
            sendMessage: 'POST /api/send-message',
            searchMessages: 'GET /api/search?query=keyword&limit=50',
            contactInfo: 'GET /api/contacts/:contactId',
            allContacts: 'GET /api/contacts'
        }
    });
});

// Health check
app.get('/health', (req, res) => {
    const info = whatsappClient.getClientInfo();

    res.json({
        success: true,
        status: whatsappClient.isClientReady() ? 'ready' : 'initializing',
        connected: whatsappClient.isClientReady(),
        qrAvailable: lastQRCode !== null,
        info: info ? {
            name: info.pushname,
            number: info.wid.user,
            platform: info.platform
        } : null
    });
});

// Get QR code
app.get('/qr', (req, res) => {
    if (whatsappClient.isClientReady()) {
        res.json({
            success: true,
            message: 'Already authenticated',
            authenticated: true
        });
    } else if (lastQRCode) {
        res.json({
            success: true,
            qr: lastQRCode,
            message: 'Scan this QR code with WhatsApp'
        });
    } else {
        res.json({
            success: false,
            message: 'QR code not yet generated. Please wait...'
        });
    }
});

// Get all chats
app.get('/api/chats', requireClient, asyncHandler(async (req, res) => {
    const chats = await whatsappClient.getChats();

    const result = chats.map(chat => ({
        id: chat.id._serialized,
        name: chat.name,
        isGroup: chat.isGroup,
        isReadOnly: chat.isReadOnly,
        unreadCount: chat.unreadCount,
        timestamp: chat.timestamp,
        archived: chat.archived,
        pinned: chat.pinned,
        lastMessage: chat.lastMessage ? {
            body: chat.lastMessage.body,
            type: chat.lastMessage.type,
            timestamp: chat.lastMessage.timestamp,
            fromMe: chat.lastMessage.fromMe
        } : null
    }));

    res.json({
        success: true,
        count: result.length,
        data: result
    });
}));

// Get all chats with unread messages
app.get('/api/unread-chats', requireClient, asyncHandler(async (req, res) => {
    const unreadChats = await whatsappClient.getUnreadChats();

    const result = unreadChats.map(chat => ({
        id: chat.id._serialized,
        name: chat.name,
        isGroup: chat.isGroup,
        unreadCount: chat.unreadCount,
        lastMessage: chat.lastMessage ? {
            body: chat.lastMessage.body,
            timestamp: chat.lastMessage.timestamp
        } : null
    }));

    res.json({
        success: true,
        count: result.length,
        totalUnread: result.reduce((sum, chat) => sum + chat.unreadCount, 0),
        data: result
    });
}));

// Get all unread messages from all chats
app.get('/api/unread-messages', requireClient, asyncHandler(async (req, res) => {
    const allUnreadMessages = await whatsappClient.getAllUnreadMessages();

    const result = allUnreadMessages.map(chat => ({
        chatId: chat.chatId,
        chatName: chat.chatName,
        isGroup: chat.isGroup,
        unreadCount: chat.unreadCount,
        messages: chat.messages.map(msg => ({
            id: msg.id._serialized,
            body: msg.body,
            type: msg.type,
            timestamp: msg.timestamp,
            from: msg.from,
            hasMedia: msg.hasMedia,
            isForwarded: msg.isForwarded
        }))
    }));

    const totalMessages = result.reduce((sum, chat) => sum + chat.messages.length, 0);

    res.json({
        success: true,
        chatCount: result.length,
        totalMessages: totalMessages,
        data: result
    });
}));

// Get messages from a specific chat
app.get('/api/chats/:chatId/messages', requireClient, asyncHandler(async (req, res) => {
    const { chatId } = req.params;
    const limit = parseInt(req.query.limit) || 50;

    const chat = await whatsappClient.getChatById(chatId);
    const messages = await whatsappClient.getMessages(chatId, limit);

    const result = messages.map(msg => ({
        id: msg.id._serialized,
        body: msg.body,
        type: msg.type,
        timestamp: msg.timestamp,
        from: msg.from,
        to: msg.to,
        fromMe: msg.fromMe,
        hasMedia: msg.hasMedia,
        isForwarded: msg.isForwarded,
        isStarred: msg.isStarred
    }));

    res.json({
        success: true,
        chatId: chatId,
        chatName: chat.name,
        count: result.length,
        data: result
    });
}));

// Get unread messages from a specific chat
app.get('/api/chats/:chatId/unread', requireClient, asyncHandler(async (req, res) => {
    const { chatId } = req.params;
    const chat = await whatsappClient.getChatById(chatId);
    const unreadMessages = await whatsappClient.getUnreadMessagesFromChat(chatId);

    const result = unreadMessages.map(msg => ({
        id: msg.id._serialized,
        body: msg.body,
        type: msg.type,
        timestamp: msg.timestamp,
        from: msg.from,
        hasMedia: msg.hasMedia
    }));

    res.json({
        success: true,
        chatId: chatId,
        chatName: chat.name,
        unreadCount: result.length,
        data: result
    });
}));

// Mark a specific chat as read
app.post('/api/chats/:chatId/mark-read', requireClient, asyncHandler(async (req, res) => {
    const { chatId } = req.params;
    const result = await whatsappClient.markChatAsRead(chatId);

    res.json({
        success: true,
        message: `Marked ${result.chatName} as read`,
        chatId: result.chatId,
        chatName: result.chatName
    });
}));

// Mark all chats as read
app.post('/api/mark-all-read', requireClient, asyncHandler(async (req, res) => {
    const results = await whatsappClient.markAllChatsAsRead();

    const markedCount = results.filter(r => r.success).length;

    res.json({
        success: true,
        message: `Marked ${markedCount} out of ${results.length} chats as read`,
        markedCount: markedCount,
        totalUnread: results.length,
        details: results
    });
}));

// Send a message
app.post('/api/send-message', requireClient, asyncHandler(async (req, res) => {
    const { chatId, message } = req.body;

    if (!chatId || !message) {
        return res.status(400).json({
            success: false,
            error: 'Both chatId and message are required'
        });
    }

    const chat = await whatsappClient.getChatById(chatId);
    const sentMessage = await whatsappClient.sendMessage(chatId, message);

    res.json({
        success: true,
        message: 'Message sent successfully',
        chatId: chatId,
        chatName: chat.name,
        messageId: sentMessage.id._serialized,
        timestamp: sentMessage.timestamp
    });
}));

// Send message to self
app.post('/api/send-message-to-self', requireClient, asyncHandler(async (req, res) => {
    const { message } = req.body;

    if (!message) {
        return res.status(400).json({
            success: false,
            error: 'message is required'
        });
    }

    const sentMessage = await whatsappClient.sendMessageToSelf(message);

    res.json({
        success: true,
        message: 'Message sent to self successfully',
        messageId: sentMessage.id._serialized,
        timestamp: sentMessage.timestamp
    });
}));

// Search messages by keyword
app.get('/api/search', requireClient, asyncHandler(async (req, res) => {
    const { query, limit = 50, chatId } = req.query;

    if (!query) {
        return res.status(400).json({
            success: false,
            error: 'query parameter is required'
        });
    }

    const results = await whatsappClient.searchMessages(query, {
        limit: parseInt(limit),
        chatId: chatId || null
    });

    const formattedResults = results.map(chat => ({
        chatId: chat.chatId,
        chatName: chat.chatName,
        isGroup: chat.isGroup,
        matchCount: chat.matches.length,
        matches: chat.matches.map(msg => ({
            id: msg.id._serialized,
            body: msg.body,
            timestamp: msg.timestamp,
            fromMe: msg.fromMe
        }))
    }));

    const totalMatches = formattedResults.reduce((sum, chat) => sum + chat.matchCount, 0);

    res.json({
        success: true,
        query: query,
        chatCount: formattedResults.length,
        totalMatches: totalMatches,
        data: formattedResults
    });
}));

// Get contact information
app.get('/api/contacts/:contactId', requireClient, asyncHandler(async (req, res) => {
    const { contactId } = req.params;
    const contact = await whatsappClient.getContactById(contactId);

    res.json({
        success: true,
        data: {
            id: contact.id._serialized,
            number: contact.number,
            name: contact.name,
            pushname: contact.pushname,
            isMyContact: contact.isMyContact,
            isBlocked: contact.isBlocked,
            isWAContact: contact.isWAContact
        }
    });
}));

// Get all contacts
app.get('/api/contacts', requireClient, asyncHandler(async (req, res) => {
    const contacts = await whatsappClient.getContacts();

    const result = contacts.map(contact => ({
        id: contact.id._serialized,
        number: contact.number,
        name: contact.name,
        pushname: contact.pushname,
        isMyContact: contact.isMyContact
    }));

    res.json({
        success: true,
        count: result.length,
        data: result
    });
}));

// Error handling middleware
app.use((err, req, res, next) => {
    console.error('Error:', err);
    res.status(500).json({
        success: false,
        error: 'Internal server error',
        message: err.message
    });
});

// 404 handler
app.use((req, res) => {
    res.status(404).json({
        success: false,
        error: 'Endpoint not found',
        path: req.path
    });
});

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('\n⚠️  Shutting down gracefully...');
    await whatsappClient.destroy();
    process.exit(0);
});

process.on('SIGTERM', async () => {
    console.log('\n⚠️  Shutting down gracefully...');
    await whatsappClient.destroy();
    process.exit(0);
});

// Start server
app.listen(PORT, () => {
    console.log('\n' + '='.repeat(50));
    console.log('🚀 WhatsApp REST API Server');
    console.log('='.repeat(50));
    console.log(`📡 Server running on http://localhost:${PORT}`);
    console.log(`📖 API documentation at http://localhost:${PORT}/`);
    console.log('='.repeat(50) + '\n');
    console.log('⏳ Waiting for WhatsApp connection...');
    console.log('   Scan the QR code when it appears\n');
    console.log('='.repeat(50) + '\n');
});

// whatsapp-client.js
// WhatsApp Client Module - Handles all WhatsApp connections and operations

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const EventEmitter = require('events');

class WhatsAppClient extends EventEmitter {
    constructor(options = {}) {
        super();

        this.client = null;
        this.isReady = false;
        this.clientInfo = null;
        this.qrCode = null;

        // Configuration
        this.config = {
            headless: options.headless !== false,
            puppeteerArgs: options.puppeteerArgs || ['--no-sandbox', '--disable-setuid-sandbox'],
            authStrategy: options.authStrategy || new LocalAuth(),
            ...options
        };
    }

    // Initialize the WhatsApp client
    initialize() {
        if (this.client) {
            console.log('Client already initialized');
            return;
        }

        this.client = new Client({
            authStrategy: this.config.authStrategy,
            puppeteer: {
                headless: this.config.headless,
                args: this.config.puppeteerArgs
            }
        });

        this._setupEventHandlers();
        this.client.initialize();

        console.log('📱 Initializing WhatsApp client...');
    }

    // Setup event handlers
    _setupEventHandlers() {
        this.client.on('qr', (qr) => {
            this.qrCode = qr;
            console.log('\n🔐 Scan this QR code with your WhatsApp:');
            qrcode.generate(qr, { small: true });
            this.emit('qr', qr);
        });

        this.client.on('ready', () => {
            this.isReady = true;
            this.clientInfo = this.client.info;
            console.log('✅ WhatsApp client is ready!');
            console.log(`📱 Connected as: ${this.clientInfo.pushname}`);
            console.log(`📞 Number: ${this.clientInfo.wid.user}`);
            this.emit('ready', this.clientInfo);
        });

        this.client.on('authenticated', () => {
            console.log('✅ Authentication successful');
            this.emit('authenticated');
        });

        this.client.on('auth_failure', (msg) => {
            console.error('❌ Authentication failure:', msg);
            this.isReady = false;
            this.emit('auth_failure', msg);
        });

        this.client.on('disconnected', (reason) => {
            console.log('❌ Client disconnected:', reason);
            this.isReady = false;
            this.emit('disconnected', reason);
        });

        this.client.on('message', async (message) => {
            try {
                const contact = await message.getContact();
                console.log(`📨 New message from ${contact.pushname || contact.number}`);
                this.emit('message', message);
            } catch (error) {
                console.error('Error handling message:', error);
            }
        });

        this.client.on('message_create', (message) => {
            this.emit('message_create', message);
        });

        this.client.on('message_ack', (message, ack) => {
            this.emit('message_ack', message, ack);
        });
    }

    // Check if client is ready
    isClientReady() {
        return this.isReady;
    }

    // Get client info
    getClientInfo() {
        return this.clientInfo;
    }

    // Get QR code
    getQRCode() {
        return this.qrCode;
    }

    // ===== CHAT OPERATIONS =====

    // Get all chats
    async getChats() {
        if (!this.isReady) throw new Error('Client is not ready');
        return await this.client.getChats();
    }

    // Get chat by ID
    async getChatById(chatId) {
        if (!this.isReady) throw new Error('Client is not ready');
        return await this.client.getChatById(chatId);
    }

    // Get all unread chats
    async getUnreadChats() {
        const chats = await this.getChats();
        return chats.filter(chat => chat.unreadCount > 0);
    }

    // Get all unread messages
    async getAllUnreadMessages() {
        const chats = await this.getChats();
        const allUnreadMessages = [];

        for (const chat of chats) {
            if (chat.unreadCount > 0) {
                const messages = await chat.fetchMessages({ limit: chat.unreadCount });
                const unreadMessages = messages.filter(msg => !msg.fromMe);

                if (unreadMessages.length > 0) {
                    allUnreadMessages.push({
                        chatId: chat.id._serialized,
                        chatName: chat.name,
                        isGroup: chat.isGroup,
                        unreadCount: unreadMessages.length,
                        messages: unreadMessages
                    });
                }
            }
        }

        return allUnreadMessages;
    }

    // Get messages from a specific chat
    async getMessages(chatId, limit = 50) {
        const chat = await this.getChatById(chatId);
        return await chat.fetchMessages({ limit });
    }

    // Get unread messages from a specific chat
    async getUnreadMessagesFromChat(chatId) {
        const chat = await this.getChatById(chatId);

        if (chat.unreadCount === 0) {
            return [];
        }

        const messages = await chat.fetchMessages({ limit: chat.unreadCount });
        return messages.filter(msg => !msg.fromMe);
    }

    // ===== MESSAGE ACTIONS =====

    // Mark chat as read
    async markChatAsRead(chatId) {
        const chat = await this.getChatById(chatId);
        await chat.sendSeen();
        return { chatId, chatName: chat.name };
    }

    // Mark all chats as read
    async markAllChatsAsRead() {
        const chats = await this.getChats();
        const unreadChats = chats.filter(chat => chat.unreadCount > 0);
        const results = [];

        for (const chat of unreadChats) {
            try {
                await chat.sendSeen();
                results.push({
                    chatId: chat.id._serialized,
                    chatName: chat.name,
                    success: true
                });
            } catch (error) {
                results.push({
                    chatId: chat.id._serialized,
                    chatName: chat.name,
                    success: false,
                    error: error.message
                });
            }
        }

        return results;
    }

    // Send a message
    async sendMessage(chatId, message) {
        const chat = await this.getChatById(chatId);
        return await chat.sendMessage(message);
    }

    // Send message to yourself (saved messages)
    async sendMessageToSelf(message) {
        if (!this.isReady) throw new Error('Client is not ready');

        const myNumber = this.clientInfo.wid._serialized;
        const sentMessage = await this.client.sendMessage(myNumber, message);

        // Mark the message as unread
        //const chat = await this.getChatById(myNumber);
        //await chat.markUnread();

        return sentMessage;
    }

    // ===== SEARCH OPERATIONS =====

    // Search messages by keyword
    async searchMessages(query, options = {}) {
        const { limit = 50, chatId = null } = options;
        const results = [];

        if (chatId) {
            // Search in specific chat
            const chat = await this.getChatById(chatId);
            const messages = await chat.fetchMessages({ limit });
            const matches = messages.filter(msg =>
                msg.body && msg.body.toLowerCase().includes(query.toLowerCase())
            );

            if (matches.length > 0) {
                results.push({
                    chatId: chat.id._serialized,
                    chatName: chat.name,
                    isGroup: chat.isGroup,
                    matches: matches
                });
            }
        } else {
            // Search in all chats
            const chats = await this.getChats();

            for (const chat of chats) {
                const messages = await chat.fetchMessages({ limit });
                const matches = messages.filter(msg =>
                    msg.body && msg.body.toLowerCase().includes(query.toLowerCase())
                );

                if (matches.length > 0) {
                    results.push({
                        chatId: chat.id._serialized,
                        chatName: chat.name,
                        isGroup: chat.isGroup,
                        matches: matches
                    });
                }
            }
        }

        return results;
    }

    // ===== CONTACT OPERATIONS =====

    // Get contact by ID
    async getContactById(contactId) {
        if (!this.isReady) throw new Error('Client is not ready');
        return await this.client.getContactById(contactId);
    }

    // Get all contacts
    async getContacts() {
        if (!this.isReady) throw new Error('Client is not ready');
        return await this.client.getContacts();
    }

    // Get current user information
    async getUserInfo() {
        if (!this.isReady) throw new Error('Client is not ready');

        return {
            pushname: this.clientInfo.pushname,
            number: this.clientInfo.wid.user,
            platform: this.clientInfo.platform,
            wid: this.clientInfo.wid._serialized,
            me: this.clientInfo.me
        };
    }

    // ===== CLIENT CONTROL =====

    // Logout and destroy client
    async logout() {
        if (this.client) {
            await this.client.logout();
            this.isReady = false;
            this.clientInfo = null;
            console.log('✅ Logged out successfully');
        }
    }

    // Destroy client
    async destroy() {
        if (this.client) {
            await this.client.destroy();
            this.client = null;
            this.isReady = false;
            this.clientInfo = null;
            console.log('✅ Client destroyed');
        }
    }
}

// Export the class
module.exports = WhatsAppClient;

// Example usage:
// const WhatsAppClient = require('./whatsapp-client');
// const client = new WhatsAppClient();
// client.initialize();
//
// client.on('ready', async () => {
//     const chats = await client.getChats();
//     console.log(chats);
// });

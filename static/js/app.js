// 主题切换逻辑
const themeToggleBtn = document.getElementById('theme-toggle');
const rootElement = document.documentElement;

themeToggleBtn.addEventListener('click', () => {
    const currentTheme = rootElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    rootElement.setAttribute('data-theme', newTheme);
    themeToggleBtn.innerHTML = newTheme === 'light' ? '🌙' : '☀️';

    // 如果想要彻底重新渲染图表颜色主题，可以强制刷新重绘，但成本较高
    // 这里保持简单的背景色彩自适应，Mermaid默认theme在亮系下显示最佳
});

// 初始化 Mermaid 工具
mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    themeVariables: {
        primaryColor: '#e0e7ff',
        primaryTextColor: '#1e293b',
        primaryBorderColor: '#818cf8',
        lineColor: '#6366f1',
        secondaryColor: '#f1f5f9',
        tertiaryColor: '#fff',
        fontFamily: 'Inter, Noto Sans SC, sans-serif'
    },
    securityLevel: 'loose'
});

const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

let chatHistory = [];

userInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

userInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendBtn.addEventListener('click', sendMessage);

async function sendMessage() {
    const rawText = userInput.value.trim();
    if (!rawText) return;

    userInput.value = '';
    userInput.style.height = 'auto';

    appendMessage('user', rawText, '👨‍💻');

    const loadingId = 'loading-' + Date.now();
    appendLoadingWait(loadingId);
    scrollToBottom();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: rawText,
                history: chatHistory
            })
        });

        if (!response.ok) {
            throw new Error(`服务器返回异常错误代号: ${response.status}`);
        }

        const data = await response.json();
        const replyText = data.answer;

        chatHistory.push({ role: 'user', content: rawText });
        chatHistory.push({ role: 'assistant', content: replyText });
        if (chatHistory.length > 6) {
            chatHistory = chatHistory.slice(-6);
        }

        removeElement(loadingId);
        appendAiMessage(replyText);

    } catch (err) {
        removeElement(loadingId);
        appendMessage('assistant', `😢 抱歉，问答服务出现错误：${err.message}`, '👨‍🏫');
    }

    scrollToBottom();
}

function appendMessage(role, content, avatarIcon) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role === 'user' ? 'user-message' : 'ai-message'}`;
    const safeContent = role === 'user' ? content.replace(/</g, "&lt;").replace(/>/g, "&gt;") : content;

    msgDiv.innerHTML = `
        <div class="avatar">${avatarIcon}</div>
        <div class="message-content">
            <p>${safeContent}</p>
        </div>
    `;
    chatContainer.appendChild(msgDiv);
}

function formatAiContent(raw) {
    const mermaidRegex = /```mermaid\s*([\s\S]*?)```/g;
    const mermaidBlocks = [];

    // 1. 拦截 Mermaid，将其抽取至安全缓存中，同时放一个防破译的标记锁位，这能 100% 防止 marked 将图表代码搞崩溃
    let rawWithoutMermaid = raw.replace(mermaidRegex, function (match, code) {
        let safeMermaidCode = code.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        mermaidBlocks.push(`\n${safeMermaidCode}\n`);
        return `UNIQUEPLACEHOLDER${mermaidBlocks.length - 1}END`;
    });

    // 2. 用 marked.js 解析清洗过干净纯粹的普通 Markdown
    let html = marked.parse(rawWithoutMermaid);

    // 3. 将抽离的带有特殊防注入转义的原版图表塞回去并在外侧包裹全屏放大器
    mermaidBlocks.forEach((code, index) => {
        let wrapper = `
            <div class="mermaid-wrapper">
                <button class="fullscreen-btn" onclick="openFullscreen(this)">🔍 放大全屏</button>
                <div class="mermaid">${code}</div>
            </div>`;
        html = html.replace(`UNIQUEPLACEHOLDER${index}END`, wrapper);
    });

    return html;
}

async function appendAiMessage(content) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message ai-message';

    const formattedHtml = formatAiContent(content);

    msgDiv.innerHTML = `
        <div class="avatar">👨‍🏫</div>
        <div class="message-content">
            ${formattedHtml}
        </div>
    `;
    chatContainer.appendChild(msgDiv);

    // 我们必须给 Mermaid 一个微小的延迟，等 DOM 彻底把元素排版后才初始化，大大降低失败率
    setTimeout(() => {
        try {
            mermaid.run({
                nodes: msgDiv.querySelectorAll('.mermaid'),
            });
        } catch (e) {
            console.error("Mermaid 渲染失败，尝试渲染时模型语法出现异常:", e);
        }
    }, 100);
}

function appendLoadingWait(id) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message ai-message';
    msgDiv.id = id;
    msgDiv.innerHTML = `
        <div class="avatar">👨‍🏫</div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    chatContainer.appendChild(msgDiv);
}

function removeElement(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}
// ============== 导图全屏放大 & 缩放拖拽逻辑 ==============

let currentScale = 1;
let panX = 0, panY = 0;
let isDragging = false;
let dragStartX = 0, dragStartY = 0;

function getSvgContainer() {
    return document.getElementById('svg-zoom-container');
}

function updateTransform() {
    const container = getSvgContainer();
    if (!container) return;
    container.style.transform = `translate(${panX}px, ${panY}px) scale(${currentScale})`;
    document.getElementById('zoom-level').textContent = Math.round(currentScale * 100) + '%';
}

function openFullscreen(btn) {
    const mermaidDiv = btn.nextElementSibling;
    const svgElement = mermaidDiv.querySelector('svg');
    if (!svgElement) return;

    const modalBody = document.getElementById('modal-body');

    // 创建一个干净的包裹层，所有 transform 作用于这个 div 而非 SVG 本身
    modalBody.innerHTML = '<div id="svg-zoom-container"></div>';
    const wrapper = document.getElementById('svg-zoom-container');

    // 深拷贝 SVG 并清除 Mermaid 注入的内联样式干扰
    const clonedSvg = svgElement.cloneNode(true);
    clonedSvg.removeAttribute('style');
    clonedSvg.style.display = 'block';
    wrapper.appendChild(clonedSvg);

    // 重置状态
    currentScale = 1;
    panX = 0;
    panY = 0;

    document.getElementById('fullscreen-modal').classList.remove('hidden');

    // 延迟一帧确保 DOM 渲染完毕后自动适应窗口
    requestAnimationFrame(() => {
        fitToScreen();
    });
}

function closeFullscreen() {
    document.getElementById('fullscreen-modal').classList.add('hidden');
    currentScale = 1;
    panX = 0;
    panY = 0;
}

function zoomIn() {
    currentScale = Math.min(currentScale * 1.25, 10);
    updateTransform();
}

function zoomOut() {
    currentScale = Math.max(currentScale / 1.25, 0.1);
    updateTransform();
}

function resetZoom() {
    currentScale = 1;
    panX = 0;
    panY = 0;
    updateTransform();
}

function fitToScreen() {
    const wrapper = getSvgContainer();
    if (!wrapper) return;
    const svg = wrapper.querySelector('svg');
    if (!svg) return;

    const modalBody = document.getElementById('modal-body');
    const cw = modalBody.clientWidth;
    const ch = modalBody.clientHeight;

    // 先重置 transform 以获取 SVG 的真实尺寸
    wrapper.style.transform = 'none';
    const sw = svg.getBoundingClientRect().width || 800;
    const sh = svg.getBoundingClientRect().height || 600;

    const scaleX = (cw - 40) / sw;
    const scaleY = (ch - 40) / sh;
    currentScale = Math.min(scaleX, scaleY, 3);
    currentScale = Math.max(currentScale, 0.1);

    panX = (cw - sw * currentScale) / 2;
    panY = (ch - sh * currentScale) / 2;
    updateTransform();
}

// 鼠标滚轮缩放（以鼠标位置为锚点）
document.getElementById('modal-body').addEventListener('wheel', function (e) {
    if (!getSvgContainer()) return;
    e.preventDefault();

    const rect = this.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const prevScale = currentScale;
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    currentScale = Math.min(Math.max(currentScale * factor, 0.1), 10);

    panX = mouseX - (mouseX - panX) * (currentScale / prevScale);
    panY = mouseY - (mouseY - panY) * (currentScale / prevScale);
    updateTransform();
}, { passive: false });

// 鼠标拖拽平移
document.getElementById('modal-body').addEventListener('mousedown', function (e) {
    if (!getSvgContainer()) return;
    isDragging = true;
    dragStartX = e.clientX - panX;
    dragStartY = e.clientY - panY;
    e.preventDefault();
});

document.addEventListener('mousemove', function (e) {
    if (!isDragging) return;
    panX = e.clientX - dragStartX;
    panY = e.clientY - dragStartY;
    updateTransform();
});

document.addEventListener('mouseup', function () {
    isDragging = false;
});


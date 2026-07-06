# EE Finance Agent - Mobile-First UI Redesign Guide

## Overview
This guide provides a complete redesign for a premium, mobile-first (99% mobile users) dark theme interface.

## Design Philosophy
- **Aesthetic**: Refined premium minimalism with sophisticated typography
- **Colors**: Dark backgrounds with electric blue/cyan accents
- **Typography**: Sora (geometric sans) + JetBrains Mono (code)
- **Mobile-First**: Bottom navigation, thumb-friendly zones, full-screen interface

## Implementation Steps

### 1. Welcome Screen (Already Created)
- Location: `app/static/welcome.html`
- Features: Animated logo, dark gradient background, auto-redirect after 2s
- Modify your main route to serve this first for new sessions

### 2. Main CSS Changes

Replace the current `:root` variables with:

```css
:root {
  /* Dark Theme Colors */
  --bg-primary: #0a0e17;
  --bg-secondary: #151a24;
  --bg-elevated: #1a1f2e;
  --text-primary: #e8eaed;
  --text-secondary: #9ca3af;
  --text-muted: #6b7280;
  
  /* Accent Colors */
  --accent-primary: #00d4ff;
  --accent-glow: rgba(0, 212, 255, 0.15);
  --accent-strong: #00b8e6;
  
  /* Semantic Colors */
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  
  /* Typography */
  --font-sans: 'Sora', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
  
  /* Shadows & Effects */
  --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.5);
  --glow: 0 0 20px var(--accent-glow);
  
  /* Spacing */
  --safe-area-bottom: env(safe-area-inset-bottom, 0px);
}
```

### 3. Mobile-First Layout Structure

```css
/* Remove desktop sidebar, use bottom nav instead */
.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
}

/* Hide desktop sidebar on mobile */
.sidebar {
  display: none;
}

/* Main content takes full height minus bottom nav */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Mobile Header - Compact */
.main-header {
  padding: 16px 20px;
  background: var(--bg-elevated);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.main-header .title {
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Messages area */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px 80px; /* Extra bottom padding for floating composer */
  -webkit-overflow-scrolling: touch;
}

/* Message bubbles - Mobile optimized */
.msg {
  max-width: 85%;
  margin-bottom: 16px;
}

.msg.user {
  align-self: flex-end;
  background: var(--accent-primary);
  color: #000;
  padding: 12px 16px;
  border-radius: 18px 18px 4px 18px;
  font-size: 15px;
  line-height: 1.5;
}

.msg.assistant {
  align-self: flex-start;
  background: var(--bg-elevated);
  color: var(--text-primary);
  padding: 12px 16px;
  border-radius: 18px 18px 18px 4px;
  font-size: 15px;
  line-height: 1.5;
  border-left: 3px solid var(--accent-primary);
}

/* Floating Composer - Bottom of screen */
.composer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--bg-elevated);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  padding: 12px 16px calc(12px + var(--safe-area-bottom));
  backdrop-filter: blur(20px);
  z-index: 100;
}

.composer-inner {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  background: var(--bg-secondary);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 24px;
  padding: 8px 12px;
}

.composer textarea {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 16px; /* Prevent iOS zoom */
  line-height: 1.5;
  resize: none;
  outline: none;
  max-height: 120px;
}

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--accent-primary);
  color: #000;
  border: none;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.send-btn:active {
  transform: scale(0.95);
}

/* Bottom Navigation */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--bg-elevated);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  padding: 8px 0 calc(8px + var(--safe-area-bottom));
  display: flex;
  justify-content: space-around;
  z-index: 101;
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.2s ease;
  min-width: 64px;
  cursor: pointer;
}

.nav-item.active {
  color: var(--accent-primary);
}

.nav-item svg {
  width: 24px;
  height: 24px;
}
```

### 4. Mobile Menu Drawer (for sessions list)

```css
/* Slide-out drawer for sessions */
.mobile-drawer {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 85vw;
  max-width: 320px;
  background: var(--bg-elevated);
  transform: translateX(-100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 200;
  overflow-y: auto;
}

.mobile-drawer.open {
  transform: translateX(0);
}

.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
  z-index: 199;
}

.drawer-overlay.open {
  opacity: 1;
  pointer-events: auto;
}

.drawer-header {
  padding: 24px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.drawer-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.session-item {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  cursor: pointer;
  transition: background 0.2s ease;
}

.session-item:active {
  background: rgba(255, 255, 255, 0.05);
}

.session-item.active {
  background: var(--accent-glow);
  border-left: 3px solid var(--accent-primary);
}
```

### 5. Modals - Full Screen on Mobile

```css
.modal-overlay {
  position: fixed;
  inset: 0;
  background: var(--bg-primary);
  z-index: 300;
  display: flex;
  flex-direction: column;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.modal-overlay.visible {
  opacity: 1;
  pointer-events: auto;
}

.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-close {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 24px;
  cursor: pointer;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
```

### 6. Touch-Friendly Buttons

```css
/* All interactive elements min 44x44px for touch */
button, .btn {
  min-height: 44px;
  padding: 0 20px;
  border-radius: 12px;
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  -webkit-tap-highlight-color: transparent;
}

.btn-primary {
  background: var(--accent-primary);
  color: #000;
  border: none;
}

.btn-primary:active {
  transform: scale(0.98);
  background: var(--accent-strong);
}

.btn-secondary {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
```

### 7. JavaScript Additions

Add to the bottom of your script section:

```javascript
// Bottom navigation
const bottomNav = document.createElement('div');
bottomNav.className = 'bottom-nav';
bottomNav.innerHTML = `
  <div class="nav-item active" data-nav="chat">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
    <span>Chat</span>
  </div>
  <div class="nav-item" data-nav="sessions">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
    </svg>
    <span>History</span>
  </div>
  <div class="nav-item" data-nav="new">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
    </svg>
    <span>New</span>
  </div>
  <div class="nav-item" data-nav="settings">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
    <span>Menu</span>
  </div>
`;

document.body.appendChild(bottomNav);

// Mobile drawer
const drawer = document.createElement('div');
drawer.className = 'mobile-drawer';
drawer.id = 'mobileDrawer';

const drawerOverlay = document.createElement('div');
drawerOverlay.className = 'drawer-overlay';
drawerOverlay.id = 'drawerOverlay';

document.body.appendChild(drawerOverlay);
document.body.appendChild(drawer);

// Navigation handlers
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    const nav = item.dataset.nav;
    
    // Update active state
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');
    
    // Handle navigation
    if (nav === 'sessions') {
      openDrawer();
    } else if (nav === 'new') {
      createSession('discussion');
    } else if (nav === 'settings') {
      openSettings();
    }
  });
});

function openDrawer() {
  document.getElementById('mobileDrawer').classList.add('open');
  document.getElementById('drawerOverlay').classList.add('open');
  
  // Render sessions in drawer
  const drawer = document.getElementById('mobileDrawer');
  drawer.innerHTML = `
    <div class="drawer-header">
      <h2>Conversations</h2>
      <button class="btn-primary" onclick="createSession('discussion')">+ New Chat</button>
    </div>
    <div id="drawerSessions"></div>
  `;
  
  // Copy session list
  const drawerSessions = document.getElementById('drawerSessions');
  state.sessions.forEach(s => {
    const item = document.createElement('div');
    item.className = 'session-item' + (s.id === state.activeSessionId ? ' active' : '');
    item.textContent = s.title || 'Untitled';
    item.addEventListener('click', () => {
      selectSession(s.id);
      closeDrawer();
    });
    drawerSessions.appendChild(item);
  });
}

function closeDrawer() {
  document.getElementById('mobileDrawer').classList.remove('open');
  document.getElementById('drawerOverlay').classList.remove('open');
}

document.getElementById('drawerOverlay').addEventListener('click', closeDrawer);

// Prevent body scroll when modals open
function preventBodyScroll(prevent) {
  document.body.style.overflow = prevent ? 'hidden' : '';
}
```

### 8. Media Queries

```css
/* Desktop view (optional, for 1% desktop users) */
@media (min-width: 768px) {
  .bottom-nav {
    display: none;
  }
  
  .sidebar {
    display: flex;
    flex-direction: column;
    width: 280px;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
  }
  
  .shell {
    flex-direction: row;
  }
  
  .composer {
    position: static;
    backdrop-filter: none;
  }
  
  .messages {
    padding-bottom: 20px;
  }
}
```

## Next Steps

1. Update the Google Fonts import in `<head>`:
```html
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
```

2. Test on actual mobile devices for:
   - Touch target sizes (min 44x44px)
   - Safe area insets (iPhone notch, etc.)
   - Landscape orientation
   - Soft keyboard behavior

3. Add haptic feedback for touch interactions (optional):
```javascript
function hapticFeedback() {
  if ('vibrate' in navigator) {
    navigator.vibrate(10);
  }
}
```

4. Consider adding pull-to-refresh for the messages view

5. Add loading skeletons for better perceived performance

## Color Scheme Alternatives

If you want different accent colors:

### Option 1: Electric Blue (Current)
- Primary: #00d4ff
- Glow: rgba(0, 212, 255, 0.15)

### Option 2: Premium Gold
- Primary: #f59e0b
- Glow: rgba(245, 158, 11, 0.15)

### Option 3: Emerald Green
- Primary: #10b981
- Glow: rgba(16, 185, 129, 0.15)

### Option 4: Purple Luxury
- Primary: #8b5cf6
- Glow: rgba(139, 92, 246, 0.15)

Choose the one that matches your brand best!
